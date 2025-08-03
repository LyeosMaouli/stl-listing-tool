import trimesh
import numpy as np
from typing import Dict, List, Union, Tuple, Optional
from ..utils.logger import logger


class DimensionExtractor:
    """
    Advanced dimension extraction and analysis for STL meshes.
    """
    
    def __init__(self, mesh: trimesh.Trimesh):
        self.mesh = mesh
        
    def get_basic_dimensions(self) -> Dict[str, Union[float, List[float]]]:
        """
        Extract basic dimensional information.
        
        Returns:
            Dictionary with basic dimensions
        """
        try:
            extents = self.mesh.extents
            bounds = self.mesh.bounds
            
            return {
                "width": float(extents[0]),
                "height": float(extents[1]),
                "depth": float(extents[2]),
                "diagonal": float(np.linalg.norm(extents)),
                "bounding_box_volume": float(np.prod(extents)),
                "center": self.mesh.centroid.tolist(),
                "bounds_min": bounds[0].tolist(),
                "bounds_max": bounds[1].tolist()
            }
        except Exception as e:
            logger.error(f"Error extracting basic dimensions: {e}")
            return {}
    
    def get_volume_analysis(self) -> Dict[str, float]:
        """
        Perform detailed volume analysis.
        
        Returns:
            Dictionary with volume metrics
        """
        try:
            volume = self.mesh.volume if self.mesh.is_volume else 0.0
            surface_area = self.mesh.area
            extents = self.mesh.extents
            bounding_volume = np.prod(extents)
            
            # Calculate volume efficiency (how much of bounding box is filled)
            volume_efficiency = volume / bounding_volume if bounding_volume > 0 else 0.0
            
            # Surface area to volume ratio
            sa_to_vol_ratio = surface_area / volume if volume > 0 else float('inf')
            
            return {
                "volume": float(volume),
                "surface_area": float(surface_area),
                "bounding_volume": float(bounding_volume),
                "volume_efficiency": float(volume_efficiency),
                "surface_to_volume_ratio": float(sa_to_vol_ratio),
                "is_volume": bool(self.mesh.is_volume),
                "is_watertight": bool(self.mesh.is_watertight)
            }
        except Exception as e:
            logger.error(f"Error in volume analysis: {e}")
            return {}
    
    def get_mesh_quality_metrics(self) -> Dict[str, Union[int, float, bool]]:
        """
        Analyze mesh quality and complexity.
        
        Returns:
            Dictionary with mesh quality metrics
        """
        try:
            vertices = self.mesh.vertices
            faces = self.mesh.faces
            
            # Basic counts
            vertex_count = len(vertices)
            face_count = len(faces)
            edge_count = len(self.mesh.edges)
            
            # Euler characteristic (should be 2 for closed surfaces)
            euler_char = vertex_count - edge_count + face_count
            
            # Mesh density (faces per unit volume)
            volume = self.mesh.volume if self.mesh.is_volume else 1.0
            mesh_density = face_count / volume if volume > 0 else face_count
            
            # Face areas for analysis
            face_areas = self.mesh.area_faces
            
            return {
                "vertex_count": int(vertex_count),
                "face_count": int(face_count),
                "edge_count": int(edge_count),
                "euler_characteristic": int(euler_char),
                "is_topologically_valid": euler_char == 2,
                "mesh_density": float(mesh_density),
                "min_face_area": float(np.min(face_areas)) if len(face_areas) > 0 else 0.0,
                "max_face_area": float(np.max(face_areas)) if len(face_areas) > 0 else 0.0,
                "avg_face_area": float(np.mean(face_areas)) if len(face_areas) > 0 else 0.0,
                "is_valid": bool(self.mesh.is_valid),
                "is_convex": bool(self.mesh.is_convex)
            }
        except Exception as e:
            logger.error(f"Error analyzing mesh quality: {e}")
            return {}
    
    def get_printability_analysis(self, layer_height: float = 0.2) -> Dict[str, Union[float, bool, int]]:
        """
        Analyze printability characteristics for 3D printing.
        
        Args:
            layer_height: Layer height in mm for printing analysis
            
        Returns:
            Dictionary with printability metrics
        """
        try:
            dimensions = self.get_basic_dimensions()
            volume_info = self.get_volume_analysis()
            
            # Estimate print time based on height and layer height
            height = dimensions.get('height', 0)
            estimated_layers = int(np.ceil(height / layer_height)) if layer_height > 0 else 0
            
            # Print volume efficiency
            volume = volume_info.get('volume', 0)
            bounding_volume = volume_info.get('bounding_volume', 1)
            
            # Aspect ratios for stability analysis
            width = dimensions.get('width', 0)
            depth = dimensions.get('depth', 0)
            
            stability_ratio = min(width, depth) / height if height > 0 else 1.0
            
            return {
                "estimated_layers": estimated_layers,
                "estimated_print_height_mm": float(height),
                "volume_mm3": float(volume),
                "material_efficiency": float(volume / bounding_volume),
                "stability_ratio": float(stability_ratio),
                "is_stable_for_printing": stability_ratio > 0.3,
                "requires_supports": stability_ratio < 0.5,
                "is_watertight": volume_info.get('is_watertight', False),
                "complexity_score": float(self.calculate_complexity_score())
            }
        except Exception as e:
            logger.error(f"Error in printability analysis: {e}")
            return {}
    
    def calculate_complexity_score(self) -> float:
        """
        Calculate a complexity score based on mesh characteristics.
        
        Returns:
            Complexity score (0-100, higher = more complex)
        """
        try:
            quality_metrics = self.get_mesh_quality_metrics()
            volume_info = self.get_volume_analysis()
            
            # Factors contributing to complexity
            face_count = quality_metrics.get('face_count', 0)
            volume_efficiency = volume_info.get('volume_efficiency', 1.0)
            surface_to_vol_ratio = volume_info.get('surface_to_volume_ratio', 1.0)
            
            # Normalize and combine factors
            face_complexity = min(face_count / 10000, 1.0) * 40  # Up to 40 points
            efficiency_complexity = (1.0 - volume_efficiency) * 30  # Up to 30 points  
            surface_complexity = min(surface_to_vol_ratio / 100, 1.0) * 30  # Up to 30 points
            
            total_complexity = face_complexity + efficiency_complexity + surface_complexity
            
            return min(total_complexity, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating complexity score: {e}")
            return 50.0  # Default medium complexity
    
    def get_scale_recommendations(self, target_sizes_mm: List[float] = None) -> Dict[str, Dict[str, float]]:
        """
        Generate scale recommendations for different target sizes.
        
        Args:
            target_sizes_mm: List of target heights in millimeters
            
        Returns:
            Dictionary with scale recommendations
        """
        if target_sizes_mm is None:
            target_sizes_mm = [15, 28, 32, 54, 75]  # Common miniature scales
            
        try:
            dimensions = self.get_basic_dimensions()
            current_height = dimensions.get('height', 0)
            
            if current_height <= 0:
                return {}
                
            recommendations = {}
            
            for target_height in target_sizes_mm:
                scale_factor = target_height / current_height
                
                recommendations[f"{target_height}mm"] = {
                    "scale_factor": float(scale_factor),
                    "scale_percentage": float(scale_factor * 100),
                    "scaled_width": float(dimensions.get('width', 0) * scale_factor),
                    "scaled_height": float(target_height),
                    "scaled_depth": float(dimensions.get('depth', 0) * scale_factor),
                    "scaled_volume": float(dimensions.get('volume', 0) * (scale_factor ** 3))
                }
                
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating scale recommendations: {e}")
            return {}
    
    def get_complete_analysis(self) -> Dict[str, Dict]:
        """
        Get complete dimensional analysis combining all metrics.
        
        Returns:
            Comprehensive analysis dictionary
        """
        return {
            "basic_dimensions": self.get_basic_dimensions(),
            "volume_analysis": self.get_volume_analysis(),
            "mesh_quality": self.get_mesh_quality_metrics(),
            "printability": self.get_printability_analysis(),
            "scale_recommendations": self.get_scale_recommendations()
        }