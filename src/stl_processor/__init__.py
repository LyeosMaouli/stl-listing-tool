"""STL Processing and Listing Tool Package."""

__version__ = "1.0.0"

# Core processing modules
from .core.stl_processor import STLProcessor
from .core.dimension_extractor import DimensionExtractor  
from .core.mesh_validator import MeshValidator, ValidationLevel

# Rendering modules
from .rendering.base_renderer import (
    MaterialType, 
    LightingPreset, 
    RenderQuality,
    BaseRenderer
)

# Video and image generation
from .generators.video_generator import (
    RotationVideoGenerator,
    MultiAngleVideoGenerator, 
    VideoFormat,
    VideoQuality
)
from .generators.image_generator import (
    ColorVariationGenerator,
    SizeComparisonGenerator,
    GridLayout
)

# Utilities
from .utils.logger import setup_logger

__all__ = [
    'STLProcessor',
    'DimensionExtractor',
    'MeshValidator',
    'ValidationLevel',
    'MaterialType',
    'LightingPreset', 
    'RenderQuality',
    'BaseRenderer',
    'RotationVideoGenerator',
    'MultiAngleVideoGenerator',
    'VideoFormat',
    'VideoQuality', 
    'ColorVariationGenerator',
    'SizeComparisonGenerator',
    'GridLayout',
    'setup_logger'
]