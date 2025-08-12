"""
Image generation for 3D models including color variation grids and size charts.
Creates professional-looking composite images for product listings.
"""

import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union
import numpy as np
from enum import Enum
import math

from utils.logger import setup_logger

# Import PIL with fallback
try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = setup_logger("image_generator")


class GridLayout(Enum):
    """Grid layout options for color variations."""
    AUTO = "auto"        # Automatically determine best layout
    SQUARE = "square"    # Square grid (2x2, 3x3, etc.)
    HORIZONTAL = "horizontal"  # Single row
    VERTICAL = "vertical"      # Single column
    CUSTOM = "custom"    # Custom rows x columns


class ColorVariationGenerator:
    """Generates color variation grid images showing different material/color options."""
    
    def __init__(self):
        self.temp_dir = None
        self.progress_callback = None
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are available."""
        if not PIL_AVAILABLE:
            raise ImportError("Pillow is required for image processing. Install with: pip install Pillow")
    
    def set_progress_callback(self, callback):
        """Set callback function for progress updates."""
        self.progress_callback = callback
    
    def _update_progress(self, progress: float, message: str):
        """Update progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(progress, message)
        logger.info(f"Progress: {progress:.1f}% - {message}")
    
    def generate_color_grid(
        self,
        renderer,
        output_path: Path,
        color_variations: List[Dict[str, Any]],
        grid_layout: GridLayout = GridLayout.AUTO,
        grid_size: Optional[Tuple[int, int]] = None,
        image_size: Tuple[int, int] = (300, 300),
        background_color: Tuple[int, int, int] = (255, 255, 255),
        spacing: int = 10,
        include_labels: bool = True,
        title: Optional[str] = None
    ) -> bool:
        """Generate a grid image showing color variations of the 3D model.
        
        Args:
            renderer: Initialized renderer with loaded model
            output_path: Path to save the grid image
            color_variations: List of color/material configurations
            grid_layout: Layout style for the grid
            grid_size: Custom grid size (rows, cols) for CUSTOM layout
            image_size: Size of each individual render (width, height)
            background_color: Background color for the composite image
            spacing: Spacing between grid items in pixels
            include_labels: Whether to include labels under each variant
            title: Optional title for the entire grid
            
        Returns:
            True if grid generation succeeded, False otherwise
        """
        try:
            self._update_progress(0, "Initializing color grid generation...")
            
            if not color_variations:
                raise ValueError("No color variations provided")
            
            # Determine grid layout
            rows, cols = self._calculate_grid_layout(len(color_variations), grid_layout, grid_size)
            
            self._update_progress(5, f"Generating {len(color_variations)} color variants in {rows}x{cols} grid...")
            
            # Create temporary directory for individual renders
            self.temp_dir = Path(tempfile.mkdtemp(prefix="color_grid_"))
            variant_images = []
            
            # Render each color variation
            for i, variant in enumerate(color_variations):
                self._update_progress(
                    5 + (i / len(color_variations)) * 70, 
                    f"Rendering variant {i+1}: {variant.get('name', f'Variant {i+1}')}"
                )
                
                # Apply color/material to renderer
                self._apply_variant_settings(renderer, variant)
                
                # Render individual image
                variant_path = self.temp_dir / f"variant_{i:03d}.png"
                if not renderer.render(variant_path):
                    raise Exception(f"Failed to render variant {i}")
                
                # Load and resize image
                img = Image.open(variant_path).convert("RGBA")
                img = img.resize(image_size, Image.Resampling.LANCZOS)
                variant_images.append((img, variant.get('name', f'Variant {i+1}')))
            
            self._update_progress(75, "Creating composite grid image...")
            
            # Create composite grid image
            success = self._create_grid_composite(
                variant_images, output_path, rows, cols,
                image_size, background_color, spacing,
                include_labels, title
            )
            
            if success:
                self._update_progress(100, f"Color grid saved to {output_path}")
                logger.info(f"Successfully generated color grid: {output_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Color grid generation failed: {e}")
            return False
        finally:
            self._cleanup_temp_files()
    
    def _calculate_grid_layout(
        self, 
        item_count: int, 
        layout: GridLayout, 
        custom_size: Optional[Tuple[int, int]]
    ) -> Tuple[int, int]:
        """Calculate optimal grid layout."""
        if layout == GridLayout.CUSTOM and custom_size:
            return custom_size
        elif layout == GridLayout.HORIZONTAL:
            return (1, item_count)
        elif layout == GridLayout.VERTICAL:
            return (item_count, 1)
        elif layout == GridLayout.SQUARE:
            size = math.ceil(math.sqrt(item_count))
            return (size, size)
        else:  # AUTO
            # Find the most square-like arrangement
            best_ratio = float('inf')
            best_layout = (1, item_count)
            
            for rows in range(1, item_count + 1):
                cols = math.ceil(item_count / rows)
                ratio = max(rows, cols) / min(rows, cols)
                if ratio < best_ratio:
                    best_ratio = ratio
                    best_layout = (rows, cols)
            
            return best_layout
    
    def _apply_variant_settings(self, renderer, variant: Dict[str, Any]):
        """Apply color/material settings to renderer for this variant."""
        try:
            # Apply material if specified
            if 'material' in variant and hasattr(renderer, 'set_material'):
                from rendering.base_renderer import MaterialType
                material = MaterialType(variant['material'])
                color = variant.get('color', (0.8, 0.8, 0.8))
                renderer.set_material(material, color)
            
            # Apply color directly if specified
            elif 'color' in variant and hasattr(renderer, 'set_color'):
                renderer.set_color(variant['color'])
            
            # Apply custom properties if renderer supports them
            if hasattr(renderer, 'set_custom_properties'):
                custom_props = {k: v for k, v in variant.items() 
                              if k not in ['name', 'material', 'color']}
                if custom_props:
                    renderer.set_custom_properties(custom_props)
                    
        except Exception as e:
            logger.warning(f"Failed to apply variant settings: {e}")
    
    def _create_grid_composite(
        self,
        variant_images: List[Tuple[Image.Image, str]],
        output_path: Path,
        rows: int,
        cols: int,
        image_size: Tuple[int, int],
        background_color: Tuple[int, int, int],
        spacing: int,
        include_labels: bool,
        title: Optional[str]
    ) -> bool:
        """Create the final composite grid image."""
        try:
            img_width, img_height = image_size
            
            # Calculate label space
            label_height = 40 if include_labels else 0
            
            # Calculate total dimensions
            total_width = cols * img_width + (cols - 1) * spacing
            total_height = rows * (img_height + label_height) + (rows - 1) * spacing
            
            # Add space for title
            title_height = 60 if title else 0
            total_height += title_height
            
            # Create composite image
            composite = Image.new('RGB', (total_width, total_height), background_color)
            draw = ImageDraw.Draw(composite) if include_labels or title else None
            
            # Add title if specified
            if title and draw:
                try:
                    font = ImageFont.truetype("arial.ttf", 32)
                except:
                    font = ImageFont.load_default()
                
                text_bbox = draw.textbbox((0, 0), title, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_x = (total_width - text_width) // 2
                draw.text((text_x, 15), title, fill=(0, 0, 0), font=font)
            
            # Place images in grid
            for i, (img, label) in enumerate(variant_images):
                if i >= rows * cols:
                    break
                
                row = i // cols
                col = i % cols
                
                # Calculate position
                x = col * (img_width + spacing)
                y = title_height + row * (img_height + label_height + spacing)
                
                # Paste image
                composite.paste(img, (x, y))
                
                # Add label if requested
                if include_labels and draw and label:
                    try:
                        font = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font = ImageFont.load_default()
                    
                    # Center label under image
                    text_bbox = draw.textbbox((0, 0), label, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    label_x = x + (img_width - text_width) // 2
                    label_y = y + img_height + 5
                    
                    draw.text((label_x, label_y), label, fill=(0, 0, 0), font=font)
            
            # Save composite image
            composite.save(output_path, quality=95, optimize=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to create grid composite: {e}")
            return False
    
    def _cleanup_temp_files(self):
        """Clean up temporary files."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")


class SizeComparisonGenerator:
    """Generates size comparison charts and scale reference images."""
    
    def __init__(self):
        self.temp_dir = None
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set callback function for progress updates."""
        self.progress_callback = callback
    
    def _update_progress(self, progress: float, message: str):
        """Update progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(progress, message)
        logger.info(f"Progress: {progress:.1f}% - {message}")
    
    def generate_size_chart(
        self,
        renderer,
        output_path: Path,
        model_dimensions: Dict[str, float],
        scale_options: List[Dict[str, Any]] = None,
        reference_objects: List[Dict[str, Any]] = None,
        chart_style: str = "professional"
    ) -> bool:
        """Generate a professional size chart showing the model at different scales.
        
        Args:
            renderer: Initialized renderer with loaded model
            output_path: Path to save the size chart
            model_dimensions: Dictionary with 'width', 'height', 'depth' in mm
            scale_options: List of scale configurations to show
            reference_objects: List of common objects for size reference
            chart_style: Style preset ("professional", "technical", "casual")
            
        Returns:
            True if chart generation succeeded, False otherwise
        """
        try:
            self._update_progress(0, "Generating size chart...")
            
            if scale_options is None:
                scale_options = self._get_default_scale_options()
            
            if reference_objects is None:
                reference_objects = self._get_default_reference_objects()
            
            # Create temporary directory
            self.temp_dir = Path(tempfile.mkdtemp(prefix="size_chart_"))
            
            # Render model at different scales
            scale_renders = []
            for i, scale_info in enumerate(scale_options):
                self._update_progress(
                    10 + (i / len(scale_options)) * 60,
                    f"Rendering {scale_info['name']} scale..."
                )
                
                scale_path = self.temp_dir / f"scale_{i}.png"
                scaled_dimensions = self._calculate_scaled_dimensions(model_dimensions, scale_info)
                
                if self._render_with_scale(renderer, scale_path, scale_info):
                    scale_renders.append((scale_path, scale_info, scaled_dimensions))
            
            self._update_progress(70, "Creating size chart layout...")
            
            # Create the chart layout
            success = self._create_size_chart_layout(
                scale_renders, reference_objects, output_path,
                model_dimensions, chart_style
            )
            
            if success:
                self._update_progress(100, f"Size chart saved to {output_path}")
                logger.info(f"Successfully generated size chart: {output_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Size chart generation failed: {e}")
            return False
        finally:
            self._cleanup_temp_files()
    
    def _get_default_scale_options(self) -> List[Dict[str, Any]]:
        """Get default scale options for miniatures/models."""
        return [
            {"name": "28mm Heroic", "scale": "28mm", "description": "Standard tabletop gaming scale"},
            {"name": "32mm", "scale": "32mm", "description": "Larger gaming miniatures"},
            {"name": "75mm", "scale": "75mm", "description": "Display/painting scale"},
            {"name": "1:1 Scale", "scale": "full", "description": "Life-size reference"}
        ]
    
    def _get_default_reference_objects(self) -> List[Dict[str, Any]]:
        """Get default reference objects for size comparison."""
        return [
            {"name": "US Quarter", "diameter": 24.26, "type": "coin"},
            {"name": "Standard Die", "size": 16, "type": "cube"},
            {"name": "Credit Card", "width": 85.6, "height": 53.98, "type": "rectangle"},
            {"name": "USB Connector", "width": 12, "height": 4.5, "type": "rectangle"}
        ]
    
    def _calculate_scaled_dimensions(self, dimensions: Dict[str, float], scale_info: Dict[str, Any]) -> Dict[str, float]:
        """Calculate dimensions at the specified scale."""
        if scale_info['scale'] == 'full':
            return dimensions.copy()
        
        # Extract scale factor (e.g., "28mm" -> 28)
        scale_str = scale_info['scale']
        if 'mm' in scale_str:
            scale_mm = float(scale_str.replace('mm', ''))
            # Assume the model represents a ~6ft (1828mm) tall figure
            scale_factor = scale_mm / 1828
        else:
            scale_factor = 1.0
        
        return {
            key: value * scale_factor 
            for key, value in dimensions.items()
        }
    
    def _render_with_scale(self, renderer, output_path: Path, scale_info: Dict[str, Any]) -> bool:
        """Render the model with scale-appropriate settings."""
        try:
            # Could adjust camera distance, lighting, etc. based on scale
            return renderer.render(output_path)
        except Exception as e:
            logger.warning(f"Failed to render scale {scale_info['name']}: {e}")
            return False
    
    def _create_size_chart_layout(
        self,
        scale_renders: List,
        reference_objects: List[Dict[str, Any]],
        output_path: Path,
        original_dimensions: Dict[str, float],
        chart_style: str
    ) -> bool:
        """Create the final size chart layout."""
        try:
            # This would create a professional layout with:
            # - Title and model information
            # - Scale renderings arranged nicely
            # - Dimension tables
            # - Reference object comparisons
            # - Ruler/measurement guides
            
            chart_width = 1200
            chart_height = 800
            
            chart = Image.new('RGB', (chart_width, chart_height), (255, 255, 255))
            draw = ImageDraw.Draw(chart)
            
            # Add title
            title = "Size Reference Chart"
            try:
                title_font = ImageFont.truetype("arial.ttf", 36)
            except:
                title_font = ImageFont.load_default()
            
            text_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = text_bbox[2] - text_bbox[0]
            draw.text(((chart_width - title_width) // 2, 20), title, fill=(0, 0, 0), font=title_font)
            
            # Add scale renderings (simplified implementation)
            y_offset = 100
            for i, (render_path, scale_info, dimensions) in enumerate(scale_renders):
                if render_path.exists():
                    scale_img = Image.open(render_path)
                    scale_img = scale_img.resize((200, 200), Image.Resampling.LANCZOS)
                    
                    x_pos = 50 + (i % 4) * 250
                    y_pos = y_offset + (i // 4) * 300
                    
                    chart.paste(scale_img, (x_pos, y_pos))
                    
                    # Add scale label
                    label = f"{scale_info['name']}\n{dimensions['width']:.1f}x{dimensions['height']:.1f}mm"
                    try:
                        label_font = ImageFont.truetype("arial.ttf", 14)
                    except:
                        label_font = ImageFont.load_default()
                    
                    draw.text((x_pos, y_pos + 210), label, fill=(0, 0, 0), font=label_font)
            
            # Save the chart
            chart.save(output_path, quality=95, optimize=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed to create size chart layout: {e}")
            return False
    
    def _cleanup_temp_files(self):
        """Clean up temporary files."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")


# Utility functions for common image operations
def create_thumbnail_strip(images: List[Image.Image], max_width: int = 800, spacing: int = 10) -> Image.Image:
    """Create a horizontal strip of thumbnail images."""
    if not images:
        raise ValueError("No images provided")
    
    # Calculate thumbnail size
    thumb_width = (max_width - (len(images) - 1) * spacing) // len(images)
    thumb_height = int(thumb_width * 0.75)  # 4:3 aspect ratio
    
    # Create thumbnails
    thumbnails = []
    for img in images:
        thumb = img.copy()
        thumb.thumbnail((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        thumbnails.append(thumb)
    
    # Create strip
    strip_height = max(thumb.size[1] for thumb in thumbnails)
    strip = Image.new('RGB', (max_width, strip_height), (255, 255, 255))
    
    x_offset = 0
    for thumb in thumbnails:
        y_offset = (strip_height - thumb.size[1]) // 2
        strip.paste(thumb, (x_offset, y_offset))
        x_offset += thumb.size[0] + spacing
    
    return strip


def add_watermark(image: Image.Image, watermark_text: str, position: str = "bottom_right", opacity: float = 0.5) -> Image.Image:
    """Add a watermark to an image."""
    img_with_watermark = image.copy()
    
    # Create watermark overlay
    overlay = Image.new('RGBA', img_with_watermark.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Try to use a nice font
    try:
        font = ImageFont.truetype("arial.ttf", max(20, min(image.size) // 40))
    except:
        font = ImageFont.load_default()
    
    # Calculate text position
    text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    if position == "bottom_right":
        x = img_with_watermark.width - text_width - 20
        y = img_with_watermark.height - text_height - 20
    elif position == "bottom_left":
        x = 20
        y = img_with_watermark.height - text_height - 20
    elif position == "top_right":
        x = img_with_watermark.width - text_width - 20
        y = 20
    else:  # top_left
        x = 20
        y = 20
    
    # Draw watermark
    alpha = int(255 * opacity)
    draw.text((x, y), watermark_text, fill=(255, 255, 255, alpha), font=font)
    
    # Composite with original
    img_with_watermark = Image.alpha_composite(img_with_watermark.convert('RGBA'), overlay)
    return img_with_watermark.convert('RGB')