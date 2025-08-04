import click
from pathlib import Path
import json
from typing import Optional

from .core.stl_processor import STLProcessor
from .core.dimension_extractor import DimensionExtractor
from .core.mesh_validator import MeshValidator, ValidationLevel
from .rendering.vtk_renderer import VTKRenderer
from .rendering.base_renderer import MaterialType, LightingPreset, RenderQuality
from .utils.logger import setup_logger

# Setup logger
logger = setup_logger("stl_processor_cli")


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(verbose):
    """STL Processing Tool - Process and render STL files for listings."""
    if verbose:
        logger.setLevel("DEBUG")
        logger.info("Verbose logging enabled")


@cli.command()
@click.argument('stl_file', type=click.Path(exists=True, path_type=Path))
@click.option('--output', '-o', type=click.Path(path_type=Path), help='Output file for analysis results')
@click.option('--format', '-f', type=click.Choice(['json', 'text']), default='text', help='Output format')
def analyze(stl_file: Path, output: Optional[Path], format: str):
    """Analyze an STL file and extract dimensions and properties."""
    try:
        logger.info(f"Analyzing STL file: {stl_file}")
        
        # Load and process STL
        processor = STLProcessor()
        if not processor.load(stl_file):
            click.echo(f"Error: Failed to load STL file: {stl_file}", err=True)
            return
        
        # Extract dimensions
        dimensions = processor.get_dimensions()
        if not dimensions:
            click.echo("Error: Failed to extract dimensions", err=True)
            return
        
        # Detailed analysis
        extractor = DimensionExtractor(processor.mesh)
        analysis = extractor.get_complete_analysis()
        
        # Format output
        if format == 'json':
            result = {
                "file": str(stl_file),
                "basic_dimensions": dimensions,
                "detailed_analysis": analysis
            }
            output_text = json.dumps(result, indent=2)
        else:
            output_text = _format_text_analysis(stl_file, dimensions, analysis)
        
        # Output results
        if output:
            output.write_text(output_text)
            click.echo(f"Analysis saved to: {output}")
        else:
            click.echo(output_text)
            
    except Exception as e:
        logger.error(f"Error analyzing file: {e}")
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument('stl_file', type=click.Path(exists=True, path_type=Path))
@click.option('--level', '-l', type=click.Choice(['basic', 'standard', 'strict']), 
              default='standard', help='Validation strictness level')
@click.option('--repair', '-r', is_flag=True, help='Attempt to repair mesh issues')
def validate(stl_file: Path, level: str, repair: bool):
    """Validate STL mesh integrity and optionally repair issues."""
    try:
        logger.info(f"Validating STL file: {stl_file}")
        
        # Load STL
        processor = STLProcessor()
        if not processor.load(stl_file):
            click.echo(f"Error: Failed to load STL file: {stl_file}", err=True)
            return
        
        # Validate mesh
        validator = MeshValidator(processor.mesh)
        validation_level = ValidationLevel(level)
        results = validator.validate(validation_level)
        
        # Display results
        click.echo(f"\n=== Validation Results for {stl_file.name} ===")
        click.echo(f"Validation Level: {level}")
        click.echo(f"Is Valid: {'✓' if results['is_valid'] else '✗'}")
        click.echo(f"Has Warnings: {'⚠' if results['has_warnings'] else '✓'}")
        click.echo(f"Total Issues: {results['total_issues']}")
        
        # Show issues
        if results['issues']:
            click.echo("\nIssues Found:")
            for issue in results['issues']:
                icon = "✗" if issue['severity'] == 'error' else "⚠"
                click.echo(f"  {icon} {issue['severity'].upper()}: {issue['description']}")
        
        # Repair if requested
        if repair and not results['is_valid']:
            click.echo("\nAttempting repairs...")
            repair_results = validator.repair(auto_fix=True)
            
            if repair_results['repair_successful']:
                click.echo("✓ Repair successful!")
                click.echo(f"Applied {repair_results['repair_count']} repairs:")
                for repair_type in repair_results['repairs_applied']:
                    click.echo(f"  - {repair_type}")
            else:
                click.echo("✗ Repair failed")
                
    except Exception as e:
        logger.error(f"Error validating file: {e}")
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument('stl_file', type=click.Path(exists=True, path_type=Path))
@click.argument('output_image', type=click.Path(path_type=Path))
@click.option('--width', '-w', default=1920, help='Render width in pixels')
@click.option('--height', '-h', default=1080, help='Render height in pixels')
@click.option('--material', '-m', type=click.Choice(['plastic', 'metal', 'resin', 'ceramic', 'wood', 'glass']),
              default='plastic', help='Material type')
@click.option('--lighting', '-l', type=click.Choice(['studio', 'natural', 'dramatic', 'soft']),
              default='studio', help='Lighting preset')
@click.option('--color', '-c', default='0.8,0.8,0.8', help='Material color (R,G,B values 0-1)')
def render(stl_file: Path, output_image: Path, width: int, height: int, 
           material: str, lighting: str, color: str):
    """Render an STL file to an image."""
    try:
        logger.info(f"Rendering STL file: {stl_file}")
        
        # Parse color
        try:
            color_values = tuple(map(float, color.split(',')))
            if len(color_values) != 3:
                raise ValueError("Color must have 3 values")
        except ValueError:
            click.echo("Error: Color must be in format 'R,G,B' with values 0-1", err=True)
            return
        
        # Create renderer
        renderer = VTKRenderer(width, height)
        
        # Setup scene
        if not renderer.setup_scene(stl_file):
            click.echo("Error: Failed to setup rendering scene", err=True)
            return
        
        # Configure material
        material_type = MaterialType(material)
        renderer.set_material(material_type, color_values)
        
        # Configure lighting
        lighting_preset = LightingPreset(lighting)
        renderer.set_lighting(lighting_preset)
        
        # Render
        if renderer.render(output_image):
            click.echo(f"✓ Rendered successfully to: {output_image}")
        else:
            click.echo("✗ Render failed", err=True)
            
        # Cleanup
        renderer.cleanup()
        
    except Exception as e:
        logger.error(f"Error rendering file: {e}")
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument('stl_file', type=click.Path(exists=True, path_type=Path))
@click.option('--height', '-h', type=float, help='Target height in mm')
def scale(stl_file: Path, height: Optional[float]):
    """Calculate scale information for an STL file."""
    try:
        logger.info(f"Calculating scale for: {stl_file}")
        
        # Load STL
        processor = STLProcessor()
        if not processor.load(stl_file):
            click.echo(f"Error: Failed to load STL file: {stl_file}", err=True)
            return
        
        # Get scale info
        if height:
            scale_info = processor.get_scale_info(height)
            if scale_info:
                click.echo(f"\n=== Scale Information for {stl_file.name} ===")
                click.echo(f"Current Height: {scale_info['current_height_mm']:.2f} mm")
                click.echo(f"Target Height: {scale_info['target_height_mm']:.2f} mm")
                click.echo(f"Scale Factor: {scale_info['scale_factor']:.4f}")
                click.echo(f"Scale Percentage: {scale_info['scale_percentage']:.1f}%")
                click.echo(f"Scaled Dimensions: {scale_info['scaled_width']:.2f} x {scale_info['scaled_depth']:.2f} x {scale_info['target_height_mm']:.2f} mm")
        else:
            # Show common scale recommendations
            extractor = DimensionExtractor(processor.mesh)
            recommendations = extractor.get_scale_recommendations()
            
            if recommendations:
                click.echo(f"\n=== Scale Recommendations for {stl_file.name} ===")
                for size, info in recommendations.items():
                    click.echo(f"\n{size}:")
                    click.echo(f"  Scale: {info['scale_percentage']:.1f}%")
                    click.echo(f"  Dimensions: {info['scaled_width']:.1f} x {info['scaled_depth']:.1f} x {info['scaled_height']:.1f} mm")
            
    except Exception as e:
        logger.error(f"Error calculating scale: {e}")
        click.echo(f"Error: {e}", err=True)


def _format_text_analysis(stl_file: Path, dimensions: dict, analysis: dict) -> str:
    """Format analysis results as readable text."""
    output = []
    output.append(f"=== STL Analysis Report for {stl_file.name} ===\n")
    
    # Basic dimensions
    output.append("BASIC DIMENSIONS:")
    output.append(f"  Size: {dimensions.get('width', 0):.2f} x {dimensions.get('height', 0):.2f} x {dimensions.get('depth', 0):.2f} mm")
    output.append(f"  Volume: {dimensions.get('volume', 0):.2f} mm³")
    output.append(f"  Surface Area: {dimensions.get('surface_area', 0):.2f} mm²")
    output.append(f"  Center: ({dimensions.get('center', [0,0,0])[0]:.2f}, {dimensions.get('center', [0,0,0])[1]:.2f}, {dimensions.get('center', [0,0,0])[2]:.2f})")
    output.append("")
    
    # Mesh quality
    mesh_quality = analysis.get('mesh_quality', {})
    output.append("MESH QUALITY:")
    output.append(f"  Vertices: {mesh_quality.get('vertex_count', 0):,}")
    output.append(f"  Faces: {mesh_quality.get('face_count', 0):,}")
    output.append(f"  Valid: {'✓' if mesh_quality.get('is_valid', False) else '✗'}")
    output.append(f"  Watertight: {'✓' if dimensions.get('is_watertight', False) else '✗'}")
    output.append("")
    
    # Printability
    printability = analysis.get('printability', {})
    output.append("PRINTABILITY:")
    output.append(f"  Estimated Layers: {printability.get('estimated_layers', 0)}")
    output.append(f"  Stability Ratio: {printability.get('stability_ratio', 0):.2f}")
    output.append(f"  Stable for Printing: {'✓' if printability.get('is_stable_for_printing', False) else '✗'}")
    output.append(f"  Requires Supports: {'Yes' if printability.get('requires_supports', False) else 'No'}")
    output.append(f"  Complexity Score: {printability.get('complexity_score', 0):.1f}/100")
    output.append("")
    
    return "\n".join(output)


if __name__ == '__main__':
    cli()