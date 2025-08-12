"""STL Processor package."""
__version__ = "0.1.0"

# Import only utilities that don't have heavy dependencies
from .utils.logger import setup_logger, logger

# Lazy import functions to avoid loading heavy dependencies at package level
def get_stl_processor():
    """Get STLProcessor class (lazy import)."""
    from .core.stl_processor import STLProcessor
    return STLProcessor

def get_dimension_extractor():
    """Get DimensionExtractor class (lazy import)."""
    from .core.dimension_extractor import DimensionExtractor
    return DimensionExtractor

def get_mesh_validator():
    """Get MeshValidator and ValidationLevel (lazy import)."""
    from .core.mesh_validator import MeshValidator, ValidationLevel
    return MeshValidator, ValidationLevel

def get_vtk_renderer():
    """Get VTKRenderer class (lazy import)."""
    from .rendering.vtk_renderer import VTKRenderer
    return VTKRenderer

def get_base_renderer():
    """Get base renderer classes and enums (lazy import)."""
    from .rendering.base_renderer import BaseRenderer, MaterialType, LightingPreset, RenderQuality
    return BaseRenderer, MaterialType, LightingPreset, RenderQuality

# Basic exports that are always available
__all__ = [
    "setup_logger",
    "logger",
    "get_stl_processor",
    "get_dimension_extractor", 
    "get_mesh_validator",
    "get_vtk_renderer",
    "get_base_renderer",
]