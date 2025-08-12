import trimesh
from pathlib import Path
from typing import Dict, Optional, Union
import numpy as np

from ..utils.logger import logger


class STLProcessor:
    """
    Core STL file processor for loading, validating, and extracting information from STL files.
    """
    
    def __init__(self):
        self.mesh: Optional[trimesh.Trimesh] = None
        self.filepath: Optional[Path] = None
        self.last_error: Optional[Exception] = None
        
    def load(self, filepath: Union[str, Path]) -> bool:
        """
        Load STL file with validation.
        
        Args:
            filepath: Path to the STL file
            
        Returns:
            bool: True if successfully loaded, False otherwise
        """
        try:
            self.filepath = Path(filepath)
            
            if not self.filepath.exists():
                logger.error(f"File does not exist: {filepath}")
                return False
                
            if not self.filepath.suffix.lower() == '.stl':
                logger.warning(f"File does not have .stl extension: {filepath}")
            
            logger.info(f"Loading STL file: {filepath}")
            self.mesh = trimesh.load(str(self.filepath))
            logger.debug(f"Loaded object type: {type(self.mesh)}")
            logger.debug(f"Loaded object: {self.mesh}")
            
            # Ensure we have a Trimesh object
            if not isinstance(self.mesh, trimesh.Trimesh):
                error_msg = f"Loaded object is not a valid mesh: {type(self.mesh)}"
                logger.error(error_msg)
                self.last_error = Exception(error_msg)
                return False
                
            validation_result = self.validate()
            if not validation_result:
                # If validation failed but no specific error was set, create one
                if self.last_error is None:
                    error_msg = "Mesh validation failed - see logs for details"
                    logger.error(error_msg)
                    self.last_error = Exception(error_msg)
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            self.mesh = None
            self.last_error = e
            return False
    
    def validate(self) -> bool:
        """
        Perform basic validation on mesh structure only.
        
        Returns:
            bool: True if mesh has basic structure (vertices and faces)
        """
        if self.mesh is None:
            error_msg = "No mesh loaded for validation"
            logger.error(error_msg)
            self.last_error = Exception(error_msg)
            return False
            
        try:
            logger.info("Performing basic mesh validation")
            
            # Check if mesh is empty
            if len(self.mesh.vertices) == 0 or len(self.mesh.faces) == 0:
                error_msg = "Mesh is empty (no vertices or faces)"
                logger.error(error_msg)
                self.last_error = Exception(error_msg)
                return False
            
            # Check for minimum viable mesh
            if len(self.mesh.vertices) < 3:
                error_msg = "Mesh has fewer than 3 vertices"
                logger.error(error_msg)
                self.last_error = Exception(error_msg)
                return False
            
            # Log mesh stats
            logger.info(f"Basic validation passed: {len(self.mesh.vertices)} vertices, {len(self.mesh.faces)} faces")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during basic mesh validation: {e}")
            self.last_error = e
            return False
    
    def get_dimensions(self) -> Dict[str, Union[float, list]]:
        """
        Extract accurate dimensions and properties from the mesh.
        
        Returns:
            Dict containing mesh dimensions and properties
        """
        if self.mesh is None:
            logger.error("No mesh loaded for dimension extraction")
            return {}
            
        try:
            # Get bounding box extents
            extents = self.mesh.extents
            
            # Calculate additional properties
            dimensions = {
                "width": float(extents[0]),
                "height": float(extents[1]), 
                "depth": float(extents[2]),
                "volume": float(self.mesh.volume) if self.mesh.is_volume else 0.0,
                "surface_area": float(self.mesh.area),
                "center": self.mesh.centroid.tolist(),
                "bounding_box_min": self.mesh.bounds[0].tolist(),
                "bounding_box_max": self.mesh.bounds[1].tolist(),
                "is_watertight": bool(self.mesh.is_watertight),
                "is_valid": bool(self.mesh.is_volume),
                "vertex_count": int(len(self.mesh.vertices)),
                "face_count": int(len(self.mesh.faces))
            }
            
            logger.info(f"Extracted dimensions: {dimensions['width']:.2f} x {dimensions['height']:.2f} x {dimensions['depth']:.2f}")
            
            return dimensions
            
        except Exception as e:
            logger.error(f"Error extracting dimensions: {e}")
            return {}
    
    def get_scale_info(self, target_height_mm: float = 28.0) -> Dict[str, float]:
        """
        Calculate scale information for miniature printing.
        
        Args:
            target_height_mm: Target height in millimeters for scaling
            
        Returns:
            Dict containing scale information
        """
        if self.mesh is None:
            return {}
            
        try:
            dimensions = self.get_dimensions()
            if not dimensions:
                return {}
                
            current_height = dimensions['height']
            scale_factor = target_height_mm / current_height if current_height > 0 else 1.0
            
            scale_info = {
                "current_height_mm": current_height,
                "target_height_mm": target_height_mm,
                "scale_factor": scale_factor,
                "scale_percentage": scale_factor * 100,
                "scaled_width": dimensions['width'] * scale_factor,
                "scaled_depth": dimensions['depth'] * scale_factor,
                "scaled_volume": dimensions['volume'] * (scale_factor ** 3)
            }
            
            return scale_info
            
        except Exception as e:
            logger.error(f"Error calculating scale info: {e}")
            return {}
    
    def export_mesh(self, output_path: Union[str, Path], file_format: str = None) -> bool:
        """
        Export the mesh to a different format.
        
        Args:
            output_path: Path for the output file
            file_format: Target file format (if None, inferred from extension)
            
        Returns:
            bool: True if export successful
        """
        if self.mesh is None:
            logger.error("No mesh loaded for export")
            return False
            
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Exporting mesh to: {output_path}")
            self.mesh.export(str(output_path), file_type=file_format)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting mesh: {e}")
            return False