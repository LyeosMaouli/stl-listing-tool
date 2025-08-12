"""Core STL processing modules."""

# Lazy imports to avoid loading heavy dependencies at package level

def get_stl_processor():
    """Get STLProcessor class (lazy import)."""
    from .stl_processor import STLProcessor
    return STLProcessor

def get_dimension_extractor():
    """Get DimensionExtractor class (lazy import)."""
    from .dimension_extractor import DimensionExtractor
    return DimensionExtractor

def get_mesh_validator():
    """Get MeshValidator and ValidationLevel (lazy import)."""
    from .mesh_validator import MeshValidator, ValidationLevel
    return MeshValidator, ValidationLevel

__all__ = [
    "get_stl_processor",
    "get_dimension_extractor",
    "get_mesh_validator",
]