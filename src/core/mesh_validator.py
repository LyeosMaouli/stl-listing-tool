import trimesh
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from pathlib import Path

from utils.logger import logger


class ValidationLevel(Enum):
    """Validation strictness levels."""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"


class MeshValidator:
    """
    Comprehensive mesh validation and repair system.
    """
    
    def __init__(self, mesh: trimesh.Trimesh):
        self.mesh = mesh
        self.issues: List[Dict[str, Any]] = []
        self.repairs_applied: List[str] = []
        
    def validate(self, level: ValidationLevel = ValidationLevel.STANDARD) -> Dict[str, Any]:
        """
        Perform comprehensive mesh validation.
        
        Args:
            level: Validation strictness level
            
        Returns:
            Validation results dictionary
        """
        self.issues.clear()
        self.repairs_applied.clear()
        
        try:
            logger.info(f"Starting mesh validation at {level.value} level")
            
            # Always run basic checks
            self._check_basic_structure()
            self._check_geometric_validity()
            
            if level in [ValidationLevel.STANDARD, ValidationLevel.STRICT]:
                self._check_topological_validity()
                self._check_manifold_properties()
                self._check_orientation()
                
            if level == ValidationLevel.STRICT:
                self._check_mesh_quality()
                self._check_degenerate_elements()
                self._check_self_intersections()
            
            # Compile results
            results = {
                "is_valid": len([issue for issue in self.issues if issue["severity"] == "error"]) == 0,
                "has_warnings": len([issue for issue in self.issues if issue["severity"] == "warning"]) > 0,
                "total_issues": len(self.issues),
                "issues": self.issues,
                "validation_level": level.value,
                "mesh_stats": self._get_mesh_stats()
            }
            
            logger.info(f"Validation complete. Found {results['total_issues']} issues")
            return results
            
        except Exception as e:
            logger.error(f"Error during mesh validation: {e}")
            return {"is_valid": False, "error": str(e)}
    
    def repair(self, auto_fix: bool = True) -> Dict[str, Any]:
        """
        Attempt to repair mesh issues.
        
        Args:
            auto_fix: Whether to automatically apply repairs
            
        Returns:
            Repair results dictionary
        """
        try:
            logger.info("Starting mesh repair process")
            
            if auto_fix:
                self._apply_automatic_repairs()
            
            # Re-validate after repairs
            post_repair_validation = self.validate()
            
            return {
                "repairs_applied": self.repairs_applied,
                "repair_count": len(self.repairs_applied),
                "post_repair_validation": post_repair_validation,
                "repair_successful": post_repair_validation.get("is_valid", False)
            }
            
        except Exception as e:
            logger.error(f"Error during mesh repair: {e}")
            return {"repair_successful": False, "error": str(e)}
    
    def _check_basic_structure(self):
        """Check basic mesh structure requirements."""
        # Check for empty mesh
        if len(self.mesh.vertices) == 0:
            self._add_issue("error", "mesh_empty", "Mesh has no vertices")
            
        if len(self.mesh.faces) == 0:
            self._add_issue("error", "no_faces", "Mesh has no faces")
            
        # Check for minimum viable mesh
        if len(self.mesh.vertices) < 3:
            self._add_issue("error", "insufficient_vertices", "Mesh has fewer than 3 vertices")
            
        if len(self.mesh.faces) < 1:
            self._add_issue("error", "insufficient_faces", "Mesh has no faces")
    
    def _check_geometric_validity(self):
        """Check geometric properties."""
        try:
            # Check for NaN or infinite values
            if np.any(~np.isfinite(self.mesh.vertices)):
                self._add_issue("error", "invalid_vertices", "Vertices contain NaN or infinite values")
                
            # Check vertex bounds
            bounds = self.mesh.bounds
            if np.any(~np.isfinite(bounds)):
                self._add_issue("error", "invalid_bounds", "Mesh bounds contain invalid values")
                
            # Check face indices
            max_vertex_index = len(self.mesh.vertices) - 1
            if np.any(self.mesh.faces > max_vertex_index):
                self._add_issue("error", "invalid_face_indices", "Face indices exceed vertex count")
                
            if np.any(self.mesh.faces < 0):
                self._add_issue("error", "negative_face_indices", "Face indices contain negative values")
                
        except Exception as e:
            self._add_issue("error", "geometric_check_failed", f"Geometric validation failed: {e}")
    
    def _check_topological_validity(self):
        """Check topological properties."""
        try:
            # Euler characteristic check
            V = len(self.mesh.vertices)
            E = len(self.mesh.edges)
            F = len(self.mesh.faces)
            euler_char = V - E + F
            
            # For closed surfaces, Euler characteristic should be 2
            if self.mesh.is_watertight and euler_char != 2:
                self._add_issue("warning", "euler_characteristic", 
                              f"Euler characteristic is {euler_char}, expected 2 for closed surface")
                
            # Check for isolated vertices
            vertex_faces = [[] for _ in range(V)]
            for i, face in enumerate(self.mesh.faces):
                for vertex_idx in face:
                    vertex_faces[vertex_idx].append(i)
                    
            isolated_vertices = sum(1 for vf in vertex_faces if len(vf) == 0)
            if isolated_vertices > 0:
                self._add_issue("warning", "isolated_vertices", 
                              f"Found {isolated_vertices} isolated vertices")
                
        except Exception as e:
            self._add_issue("warning", "topology_check_failed", f"Topology check failed: {e}")
    
    def _check_manifold_properties(self):
        """Check if mesh is manifold."""
        try:
            if not self.mesh.is_watertight:
                self._add_issue("warning", "not_watertight", "Mesh is not watertight")
                
            if not self.mesh.is_volume:
                self._add_issue("warning", "not_valid", "Mesh does not represent a valid volume")
                
        except Exception as e:
            self._add_issue("warning", "manifold_check_failed", f"Manifold check failed: {e}")
    
    def _check_orientation(self):
        """Check face orientation consistency."""
        try:
            # Check if mesh has consistent winding
            if hasattr(self.mesh, 'face_normals'):
                face_normals = self.mesh.face_normals
                if np.any(~np.isfinite(face_normals)):
                    self._add_issue("warning", "invalid_normals", "Some face normals are invalid")
                    
        except Exception as e:
            self._add_issue("warning", "orientation_check_failed", f"Orientation check failed: {e}")
    
    def _check_mesh_quality(self):
        """Check mesh quality metrics."""
        try:
            # Check for very small faces
            face_areas = self.mesh.area_faces
            small_face_threshold = np.mean(face_areas) * 0.001  # 0.1% of average face area
            small_faces = np.sum(face_areas < small_face_threshold)
            
            if small_faces > 0:
                self._add_issue("warning", "small_faces", 
                              f"Found {small_faces} very small faces")
                
            # Check for very large faces
            large_face_threshold = np.mean(face_areas) * 100  # 100x average face area
            large_faces = np.sum(face_areas > large_face_threshold)
            
            if large_faces > 0:
                self._add_issue("warning", "large_faces", 
                              f"Found {large_faces} very large faces")
                
        except Exception as e:
            self._add_issue("warning", "quality_check_failed", f"Quality check failed: {e}")
    
    def _check_degenerate_elements(self):
        """Check for degenerate faces and edges."""
        try:
            # Check for degenerate faces (zero area)
            face_areas = self.mesh.area_faces
            degenerate_faces = np.sum(face_areas == 0)
            
            if degenerate_faces > 0:
                self._add_issue("error", "degenerate_faces", 
                              f"Found {degenerate_faces} degenerate faces")
                
            # Check for duplicate vertices
            unique_vertices = np.unique(self.mesh.vertices, axis=0)
            if len(unique_vertices) < len(self.mesh.vertices):
                duplicate_count = len(self.mesh.vertices) - len(unique_vertices)
                self._add_issue("warning", "duplicate_vertices", 
                              f"Found {duplicate_count} duplicate vertices")
                
        except Exception as e:
            self._add_issue("warning", "degeneracy_check_failed", f"Degeneracy check failed: {e}")
    
    def _check_self_intersections(self):
        """Check for self-intersections (computationally expensive)."""
        try:
            # This is a basic check - full self-intersection detection is complex
            if not self.mesh.is_volume:
                self._add_issue("warning", "potential_self_intersection", 
                              "Mesh may have self-intersections or invalid volume")
                
        except Exception as e:
            self._add_issue("warning", "intersection_check_failed", f"Self-intersection check failed: {e}")
    
    def _apply_automatic_repairs(self):
        """Apply automatic repairs for common issues."""
        try:
            # Fix normals
            self.mesh.fix_normals()
            self.repairs_applied.append("fix_normals")
            
            # Remove duplicate faces
            if hasattr(self.mesh, 'remove_duplicate_faces'):
                self.mesh.remove_duplicate_faces()
                self.repairs_applied.append("remove_duplicate_faces")
            
            # Remove degenerate faces
            if hasattr(self.mesh, 'remove_degenerate_faces'):
                self.mesh.remove_degenerate_faces()
                self.repairs_applied.append("remove_degenerate_faces")
            
            # Fill holes (if available)
            if hasattr(self.mesh, 'fill_holes'):
                try:
                    self.mesh.fill_holes()
                    self.repairs_applied.append("fill_holes")
                except:
                    logger.warning("Could not fill holes in mesh")
                    
            logger.info(f"Applied {len(self.repairs_applied)} automatic repairs")
            
        except Exception as e:
            logger.error(f"Error applying automatic repairs: {e}")
    
    def _add_issue(self, severity: str, issue_type: str, description: str):
        """Add an issue to the issues list."""
        self.issues.append({
            "severity": severity,
            "type": issue_type,
            "description": description
        })
    
    def _get_mesh_stats(self) -> Dict[str, Any]:
        """Get basic mesh statistics."""
        try:
            return {
                "vertex_count": len(self.mesh.vertices),
                "face_count": len(self.mesh.faces),
                "edge_count": len(self.mesh.edges) if hasattr(self.mesh, 'edges') else None,
                "is_watertight": bool(self.mesh.is_watertight),
                "is_valid": bool(self.mesh.is_volume),
                "volume": float(self.mesh.volume) if self.mesh.is_volume else None,
                "surface_area": float(self.mesh.area),
                "bounding_box": self.mesh.bounds.tolist()
            }
        except Exception as e:
            logger.error(f"Error getting mesh stats: {e}")
            return {}