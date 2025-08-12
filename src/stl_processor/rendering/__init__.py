"""Rendering modules for STL files."""

# Lazy imports to avoid loading VTK at package level

def get_base_renderer():
    """Get base renderer classes and enums (lazy import)."""
    from .base_renderer import BaseRenderer, MaterialType, LightingPreset, RenderQuality
    return BaseRenderer, MaterialType, LightingPreset, RenderQuality

def get_vtk_renderer():
    """Get VTKRenderer class (lazy import)."""
    from .vtk_renderer import VTKRenderer
    return VTKRenderer

__all__ = [
    "get_base_renderer",
    "get_vtk_renderer",
]