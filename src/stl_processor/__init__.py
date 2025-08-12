"""STL Processor package - main package for stl-processor tool."""
__version__ = "0.1.0"

# Lazy import functions to avoid loading heavy dependencies at package level
def get_cli():
    """Get CLI entry point (lazy import)."""
    from .cli import cli
    return cli

def get_gui_main():
    """Get GUI main function (lazy import)."""
    from .gui_batch import main
    return main

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

def get_job_manager():
    """Get EnhancedJobManager class (lazy import)."""
    from .batch_queue.enhanced_job_manager import EnhancedJobManager
    return EnhancedJobManager

def get_job_types():
    """Get job types (lazy import)."""
    from .batch_queue.job_types_v2 import Job, JobStatus, JobResult, JobError
    return Job, JobStatus, JobResult, JobError

# Always available utilities
from .utils.logger import setup_logger, logger

# Basic exports that are always available
__all__ = [
    # Lazy import functions
    "get_cli", "get_gui_main",
    "get_stl_processor", "get_dimension_extractor", "get_mesh_validator", 
    "get_vtk_renderer", "get_base_renderer",
    "get_job_manager", "get_job_types",
    
    # Always available
    "setup_logger", "logger", "__version__"
]