from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any
import numpy as np
from enum import Enum
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..utils.logger import logger

class MaterialType(Enum):
    """Material preset types."""
    PLASTIC = "plastic"
    METAL = "metal"
    RESIN = "resin"
    CERAMIC = "ceramic"
    WOOD = "wood"
    GLASS = "glass"
    CUSTOM = "custom"


class RenderQuality(Enum):
    """Render quality presets."""
    DRAFT = "draft"
    STANDARD = "standard"
    HIGH = "high"
    ULTRA = "ultra"


class LightingPreset(Enum):
    """Lighting preset types."""
    STUDIO = "studio"
    NATURAL = "natural"
    DRAMATIC = "dramatic"
    SOFT = "soft"
    CUSTOM = "custom"


class BaseRenderer(ABC):
    """
    Abstract base class for 3D mesh renderers.
    """
    
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.mesh_path: Optional[Path] = None
        self.is_initialized = False
        
        # Default settings
        self.background_color = (1.0, 1.0, 1.0, 1.0)  # White
        self.background_image_path: Optional[Path] = None
        self.background_image: Optional[np.ndarray] = None
        self.material_type = MaterialType.PLASTIC
        self.lighting_preset = LightingPreset.STUDIO
        self.render_quality = RenderQuality.STANDARD
        
        logger.info(f"Initialized {self.__class__.__name__} renderer ({width}x{height})")
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the rendering system.
        
        Returns:
            bool: True if initialization successful
        """
        pass
    
    @abstractmethod
    def setup_scene(self, mesh_path: Path) -> bool:
        """
        Load mesh and setup scene.
        
        Args:
            mesh_path: Path to the mesh file
            
        Returns:
            bool: True if scene setup successful
        """
        pass
    
    @abstractmethod
    def set_camera(self, 
                   position: Tuple[float, float, float],
                   target: Tuple[float, float, float] = (0, 0, 0),
                   up: Tuple[float, float, float] = (0, 1, 0)) -> bool:
        """
        Configure camera position and orientation.
        
        Args:
            position: Camera position (x, y, z)
            target: Camera target point (x, y, z)
            up: Camera up vector (x, y, z)
            
        Returns:
            bool: True if camera setup successful
        """
        pass
    
    @abstractmethod
    def set_lighting(self, preset: LightingPreset = LightingPreset.STUDIO) -> bool:
        """
        Setup lighting configuration.
        
        Args:
            preset: Lighting preset to use
            
        Returns:
            bool: True if lighting setup successful
        """
        pass
    
    @abstractmethod
    def set_material(self, 
                     material_type: MaterialType = MaterialType.PLASTIC,
                     color: Tuple[float, float, float] = (0.8, 0.8, 0.8),
                     **kwargs) -> bool:
        """
        Configure material properties.
        
        Args:
            material_type: Type of material preset
            color: Base color (r, g, b)
            **kwargs: Additional material properties
            
        Returns:
            bool: True if material setup successful
        """
        pass
    
    @abstractmethod
    def render(self, output_path: Path) -> bool:
        """
        Render scene to image file.
        
        Args:
            output_path: Path for output image
            
        Returns:
            bool: True if render successful
        """
        pass
    
    @abstractmethod
    def render_to_array(self) -> Optional[np.ndarray]:
        """
        Render scene to numpy array.
        
        Returns:
            numpy array containing rendered image, or None if failed
        """
        pass
    
    def set_background(self, color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)):
        """
        Set background color.
        
        Args:
            color: Background color (r, g, b, a)
        """
        self.background_color = color
        # Clear background image when setting color
        self.background_image_path = None
        self.background_image = None
        logger.debug(f"Set background color to {color}")
    
    def set_background_image(self, image_path: Path) -> bool:
        """
        Set background image from file.
        
        Args:
            image_path: Path to background image file
            
        Returns:
            bool: True if image loaded successfully
        """
        if not PIL_AVAILABLE:
            logger.error("PIL/Pillow is required for background image support. Install with: pip install Pillow")
            return False
        
        if not image_path.exists():
            logger.error(f"Background image not found: {image_path}")
            return False
        
        try:
            logger.info(f"Loading background image: {image_path}")
            
            # Load and resize image to match render size
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize to match render dimensions
                img_resized = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
                
                # Convert to numpy array
                self.background_image = np.array(img_resized, dtype=np.uint8)
                self.background_image_path = image_path
                
                logger.info(f"Background image loaded successfully: {self.background_image.shape}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load background image: {e}")
            return False
    
    def has_background_image(self) -> bool:
        """Check if a background image is set."""
        return self.background_image is not None
    
    def composite_with_background(self, rendered_image: np.ndarray) -> np.ndarray:
        """
        Composite rendered image with background image.
        
        Args:
            rendered_image: Rendered image array (with or without alpha channel)
            
        Returns:
            Composited image array
        """
        if not self.has_background_image():
            return rendered_image
        
        try:
            # Ensure both images have the same dimensions
            if rendered_image.shape[:2] != self.background_image.shape[:2]:
                logger.warning(f"Image size mismatch: rendered {rendered_image.shape[:2]} vs background {self.background_image.shape[:2]}")
                # Resize background to match rendered image
                bg_resized = Image.fromarray(self.background_image).resize(
                    (rendered_image.shape[1], rendered_image.shape[0]), 
                    Image.Resampling.LANCZOS
                )
                background = np.array(bg_resized, dtype=np.uint8)
            else:
                background = self.background_image.copy()
            
            # Handle different channel configurations
            if rendered_image.shape[2] == 4:  # RGBA
                # Extract alpha channel
                alpha = rendered_image[:, :, 3:4] / 255.0
                rgb = rendered_image[:, :, :3]
                
                # Alpha composite: result = foreground * alpha + background * (1 - alpha)
                composited = (rgb * alpha + background * (1 - alpha)).astype(np.uint8)
                
            elif rendered_image.shape[2] == 3:  # RGB - assume no transparency
                composited = rendered_image
            
            else:
                logger.error(f"Unsupported image format: {rendered_image.shape}")
                return rendered_image
            
            logger.debug("Successfully composited image with background")
            return composited
            
        except Exception as e:
            logger.error(f"Failed to composite with background: {e}")
            return rendered_image
    
    def set_render_quality(self, quality: RenderQuality):
        """
        Set render quality preset.
        
        Args:
            quality: Quality preset to use
        """
        self.render_quality = quality
        logger.debug(f"Set render quality to {quality.value}")
    
    def get_quality_settings(self) -> Dict[str, Any]:
        """
        Get render settings based on quality preset.
        
        Returns:
            Dictionary with quality-specific settings
        """
        quality_map = {
            RenderQuality.DRAFT: {
                "samples": 32,
                "max_bounces": 4,
                "tile_size": 256,
                "denoising": False
            },
            RenderQuality.STANDARD: {
                "samples": 128,
                "max_bounces": 8,
                "tile_size": 128,
                "denoising": True
            },
            RenderQuality.HIGH: {
                "samples": 256,
                "max_bounces": 12,
                "tile_size": 64,
                "denoising": True
            },
            RenderQuality.ULTRA: {
                "samples": 512,
                "max_bounces": 16,
                "tile_size": 32,
                "denoising": True
            }
        }
        
        return quality_map.get(self.render_quality, quality_map[RenderQuality.STANDARD])
    
    def get_material_properties(self, material_type: MaterialType) -> Dict[str, Any]:
        """
        Get material properties for a given material type.
        
        Args:
            material_type: Type of material
            
        Returns:
            Dictionary with material properties
        """
        material_map = {
            MaterialType.PLASTIC: {
                "roughness": 0.3,
                "metallic": 0.0,
                "specular": 0.5,
                "ior": 1.45,
                "subsurface": 0.0
            },
            MaterialType.METAL: {
                "roughness": 0.1,
                "metallic": 1.0,
                "specular": 1.0,
                "ior": 1.0,
                "subsurface": 0.0
            },
            MaterialType.RESIN: {
                "roughness": 0.05,
                "metallic": 0.0,
                "specular": 0.8,
                "ior": 1.5,
                "subsurface": 0.1
            },
            MaterialType.CERAMIC: {
                "roughness": 0.02,
                "metallic": 0.0,
                "specular": 0.9,
                "ior": 1.6,
                "subsurface": 0.0
            },
            MaterialType.WOOD: {
                "roughness": 0.8,
                "metallic": 0.0,
                "specular": 0.2,
                "ior": 1.4,
                "subsurface": 0.3
            },
            MaterialType.GLASS: {
                "roughness": 0.0,
                "metallic": 0.0,
                "specular": 1.0,
                "ior": 1.52,
                "transmission": 1.0,
                "subsurface": 0.0
            }
        }
        
        return material_map.get(material_type, material_map[MaterialType.PLASTIC])
    
    def get_lighting_setup(self, preset: LightingPreset) -> Dict[str, Any]:
        """
        Get lighting configuration for a preset.
        
        Args:
            preset: Lighting preset
            
        Returns:
            Dictionary with lighting configuration
        """
        lighting_map = {
            LightingPreset.STUDIO: {
                "key_light": {"position": (2, 2, 2), "intensity": 1.0, "color": (1, 1, 1)},
                "fill_light": {"position": (-1, 1, 1), "intensity": 0.5, "color": (1, 1, 1)},
                "rim_light": {"position": (0, 0, -2), "intensity": 0.3, "color": (1, 1, 1)},
                "ambient": 0.1
            },
            LightingPreset.NATURAL: {
                "sun_light": {"position": (1, 3, 1), "intensity": 2.0, "color": (1, 0.95, 0.8)},
                "sky_light": {"intensity": 0.3, "color": (0.5, 0.7, 1.0)},
                "ambient": 0.05
            },
            LightingPreset.DRAMATIC: {
                "key_light": {"position": (3, 1, 0), "intensity": 2.0, "color": (1, 0.9, 0.7)},
                "rim_light": {"position": (-2, 0, -1), "intensity": 0.8, "color": (0.7, 0.8, 1.0)},
                "ambient": 0.02
            },
            LightingPreset.SOFT: {
                "area_light": {"position": (0, 2, 2), "intensity": 0.8, "size": 2.0, "color": (1, 1, 1)},
                "fill_light": {"position": (-1, 0, 1), "intensity": 0.3, "color": (1, 1, 1)},
                "ambient": 0.2
            }
        }
        
        return lighting_map.get(preset, lighting_map[LightingPreset.STUDIO])
    
    def calculate_camera_distance(self, mesh_bounds: np.ndarray, fov: float = 45.0) -> float:
        """
        Calculate optimal camera distance based on mesh bounds.
        
        Args:
            mesh_bounds: Mesh bounding box [[min_x, min_y, min_z], [max_x, max_y, max_z]]
            fov: Camera field of view in degrees
            
        Returns:
            Optimal camera distance
        """
        # Calculate mesh diagonal
        extents = mesh_bounds[1] - mesh_bounds[0]
        diagonal = np.linalg.norm(extents)
        
        # Calculate distance based on FOV
        fov_rad = np.radians(fov)
        distance = (diagonal / 2) / np.tan(fov_rad / 2)
        
        # Add some padding
        return distance * 1.2
    
    def get_orbit_positions(self, 
                           center: Tuple[float, float, float],
                           radius: float,
                           num_positions: int = 8,
                           elevation: float = 15.0) -> List[Tuple[float, float, float]]:
        """
        Generate camera positions for orbit animation.
        
        Args:
            center: Center point to orbit around
            radius: Orbit radius
            num_positions: Number of positions to generate
            elevation: Elevation angle in degrees
            
        Returns:
            List of camera positions
        """
        positions = []
        elevation_rad = np.radians(elevation)
        
        for i in range(num_positions):
            angle = (2 * np.pi * i) / num_positions
            
            x = center[0] + radius * np.cos(angle) * np.cos(elevation_rad)
            y = center[1] + radius * np.sin(elevation_rad)
            z = center[2] + radius * np.sin(angle) * np.cos(elevation_rad)
            
            positions.append((x, y, z))
            
        return positions
    
    def cleanup(self):
        """Cleanup renderer resources."""
        logger.debug(f"Cleaning up {self.__class__.__name__} renderer")
        self.is_initialized = False