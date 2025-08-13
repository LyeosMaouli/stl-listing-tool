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
@click.option('--background', '-bg', type=click.Path(exists=True, path_type=Path), 
              help='Background image file (PNG, JPG, etc.)')
def render(stl_file: Path, output_image: Path, width: int, height: int, 
           material: str, lighting: str, color: str, background: Optional[Path]):
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
        
        # Set background image if provided
        if background:
            if not renderer.set_background_image(background):
                click.echo(f"Error: Failed to load background image: {background}", err=True)
                return
            click.echo(f"✓ Background image loaded: {background}")
        
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
            if background:
                click.echo(f"✓ Rendered with background successfully to: {output_image}")
            else:
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


@cli.group()
def batch():
    """Batch processing commands for multiple STL files."""
    pass


@batch.command()
@click.argument('input_path', type=click.Path(exists=True, path_type=Path))
@click.argument('output_path', type=click.Path(path_type=Path))
@click.option('--job-type', '-t', type=click.Choice(['render', 'validate', 'analyze', 'composite']),
              default='composite', help='Type of processing to perform')
@click.option('--recursive', '-r', is_flag=True, help='Scan subdirectories recursively')
@click.option('--material', '-m', type=click.Choice(['plastic', 'metal', 'resin', 'ceramic', 'wood', 'glass']),
              default='plastic', help='Material type for rendering')
@click.option('--width', '-w', default=1920, help='Render width in pixels')
@click.option('--height', '-h', default=1080, help='Render height in pixels')
def process_folder(input_path: Path, output_path: Path, job_type: str, recursive: bool, 
                   material: str, width: int, height: int):
    """Process all STL files in a folder with batch processing."""
    try:
        from .batch_queue.enhanced_job_manager import EnhancedJobManager
        from .batch_queue.job_types_v2 import Job
        
        logger.info(f"Starting batch processing of {input_path}")
        
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Scan for STL files
        if recursive:
            stl_files = list(input_path.rglob("*.stl"))
        else:
            stl_files = list(input_path.glob("*.stl"))
        
        if not stl_files:
            click.echo(f"No STL files found in {input_path}")
            return
        
        click.echo(f"Found {len(stl_files)} STL files")
        
        # Initialize job manager
        job_manager = EnhancedJobManager(
            max_workers=2,
            state_dir=output_path / "batch_state",
            auto_save=True
        )
        
        # Add jobs to queue
        job_ids = job_manager.add_jobs_from_files(
            stl_files, output_path, job_type=job_type
        )
        
        click.echo(f"Added {len(job_ids)} jobs to queue")
        
        # Start processing
        if job_manager.start_processing():
            click.echo("Processing started...")
            
            # Wait for completion
            import time
            while job_manager.is_running:
                summary = job_manager.get_queue_summary()
                completed = summary.get('completed_jobs', 0)
                total = summary.get('total_jobs', 0)
                click.echo(f"\rProgress: {completed}/{total} completed", nl=False)
                time.sleep(2)
            
            click.echo(f"\nBatch processing completed!")
        else:
            click.echo("Failed to start processing")
        
        # Cleanup
        job_manager.shutdown()
        
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        click.echo(f"Error: {e}", err=True)


@batch.command()
def list_jobs():
    """List current jobs in the batch queue."""
    try:
        from .batch_queue.enhanced_job_manager import EnhancedJobManager
        
        # Try to connect to existing job manager state
        # Use user data directory for state
        import tempfile
        import os
        
        if os.name == 'nt':  # Windows
            state_dir = Path.home() / "AppData" / "Local" / "stl_listing_tool" / "batch_state"
        else:  # Unix/Linux/Mac
            state_dir = Path.home() / ".local" / "share" / "stl_listing_tool" / "batch_state"
        if not state_dir.exists():
            click.echo("No batch queue state found")
            return
            
        job_manager = EnhancedJobManager(
            max_workers=1,
            state_dir=state_dir,
            auto_save=False
        )
        
        summary = job_manager.get_queue_summary()
        
        click.echo("=== Batch Queue Status ===")
        click.echo(f"Total Jobs: {summary.get('total_jobs', 0)}")
        click.echo(f"Pending: {summary.get('pending_jobs', 0)}")
        click.echo(f"Running: {summary.get('running_jobs', 0)}")
        click.echo(f"Completed: {summary.get('completed_jobs', 0)}")
        click.echo(f"Failed: {summary.get('failed_jobs', 0)}")
        click.echo(f"Is Running: {summary.get('is_running', False)}")
        
        job_manager.shutdown()
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        click.echo(f"Error: {e}", err=True)


@batch.command()
def start_processing():
    """Start processing jobs in the batch queue."""
    try:
        from .batch_queue.enhanced_job_manager import EnhancedJobManager
        
        # Use user data directory for state
        import tempfile
        import os
        
        if os.name == 'nt':  # Windows
            state_dir = Path.home() / "AppData" / "Local" / "stl_listing_tool" / "batch_state"
        else:  # Unix/Linux/Mac
            state_dir = Path.home() / ".local" / "share" / "stl_listing_tool" / "batch_state"
        if not state_dir.exists():
            click.echo("No batch queue found")
            return
            
        job_manager = EnhancedJobManager(
            max_workers=2,
            state_dir=state_dir,
            auto_save=True
        )
        
        if job_manager.start_processing():
            click.echo("Batch processing started")
        else:
            click.echo("Failed to start processing (no jobs or already running)")
            
        job_manager.shutdown()
        
    except Exception as e:
        logger.error(f"Error starting processing: {e}")
        click.echo(f"Error: {e}", err=True)


@batch.command()
def pause_processing():
    """Pause batch processing."""
    try:
        from .batch_queue.enhanced_job_manager import EnhancedJobManager
        
        # Use user data directory for state
        import tempfile
        import os
        
        if os.name == 'nt':  # Windows
            state_dir = Path.home() / "AppData" / "Local" / "stl_listing_tool" / "batch_state"
        else:  # Unix/Linux/Mac
            state_dir = Path.home() / ".local" / "share" / "stl_listing_tool" / "batch_state"
        if not state_dir.exists():
            click.echo("No batch queue found")
            return
            
        job_manager = EnhancedJobManager(
            max_workers=2,
            state_dir=state_dir,
            auto_save=True
        )
        
        if job_manager.pause_processing():
            click.echo("Batch processing paused")
        else:
            click.echo("Failed to pause processing (not running)")
            
        job_manager.shutdown()
        
    except Exception as e:
        logger.error(f"Error pausing processing: {e}")
        click.echo(f"Error: {e}", err=True)


if __name__ == '__main__':
    cli()