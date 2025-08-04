import trimesh
from pathlib import Path
from typing import Dict, Optional, Union
import numpy as np

from utils.logger import logger


class STLProcessor:
    """
    Core STL file processor for loading, validating, and extracting information from STL files.
    """
    
    def __init__(self):
        self.mesh: Optional[trimesh.Trimesh] = None
        self.filepath: Optional[Path] = None
        
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
            
            # Ensure we have a Trimesh object
            if not isinstance(self.mesh, trimesh.Trimesh):
                logger.error(f"Loaded object is not a valid mesh: {type(self.mesh)}")
                return False
                
            return self.validate()
            
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            self.mesh = None
            return False
    
    def validate(self) -> bool:
        """
        Validate mesh integrity and attempt repairs.
        
        Returns:
            bool: True if mesh is valid or successfully repaired
        """
        if self.mesh is None:
            logger.error("No mesh loaded for validation")
            return False
            
        try:
            logger.info("Validating mesh integrity")
            
            # Check if mesh is empty
            if len(self.mesh.vertices) == 0 or len(self.mesh.faces) == 0:
                logger.error("Mesh is empty (no vertices or faces)")
                return False
            
            # Log mesh stats
            logger.info(f"Mesh stats: {len(self.mesh.vertices)} vertices, {len(self.mesh.faces)} faces")
            
            # Check and fix mesh issues
            if not self.mesh.is_volume:
                logger.warning("Mesh has integrity issues, attempting repairs")
                
                # Fix normals
                self.mesh.fix_normals()
                
                # Remove duplicate faces
                self.mesh.remove_duplicate_faces()
                
                # Remove degenerate faces
                self.mesh.remove_degenerate_faces()
                
                # Fill holes if possible
                if hasattr(self.mesh, 'fill_holes'):
                    self.mesh.fill_holes()
            
            # Final validity check
            is_valid = self.mesh.is_volume
            if is_valid:
                logger.info("Mesh validation successful")
            else:
                logger.warning("Mesh still has integrity issues after repair attempts")
                
            return is_valid
            
        except Exception as e:
            logger.error(f"Error during mesh validation: {e}")
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