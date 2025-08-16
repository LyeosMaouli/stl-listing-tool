"""
OpenCV-based video generation as an alternative to moviepy.
More reliable and has fewer dependencies.
"""

import tempfile
import shutil
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

class OpenCVVideoGenerator:
    """Simple video generator using OpenCV instead of moviepy."""
    
    def __init__(self):
        self.temp_dir = None
        self.progress_callback = None
        
    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set callback function for progress updates."""
        self.progress_callback = callback
        
    def _update_progress(self, percentage: float, message: str):
        """Update progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(percentage, message)
            
    def generate_rotation_video(
        self,
        renderer,
        output_path: Path,
        video_format: str = "mp4",
        fps: int = 30,
        duration_seconds: float = 8.0,
        axis: str = 'y'
    ) -> bool:
        """Generate 360° rotation video using OpenCV."""
        
        if not OPENCV_AVAILABLE:
            raise ImportError("OpenCV is required for video generation. Install with: pip install opencv-python")
            
        try:
            self._update_progress(0, "Starting OpenCV video generation...")
            
            # Calculate frame count
            frame_count = int(duration_seconds * fps)
            
            # Create temporary directory for frames
            self.temp_dir = Path(tempfile.mkdtemp(prefix="stl_opencv_video_"))
            frame_paths = []
            
            self._update_progress(5, f"Generating {frame_count} frames...")
            
            # Calculate proper camera distance from model bounds
            radius = 5.0  # Default distance
            try:
                if hasattr(renderer, 'mesh_bounds') and renderer.mesh_bounds is not None:
                    # Calculate appropriate camera distance from mesh bounds
                    bounds = renderer.mesh_bounds
                    max_dimension = max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
                    radius = max_dimension * 2.5  # Distance should be 2.5x the largest dimension
                    logger.info(f"Calculated camera radius: {radius} from mesh bounds")
                elif hasattr(renderer, 'current_mesh') and renderer.current_mesh is not None:
                    # Try to get bounds from the mesh object
                    try:
                        bounds = renderer.current_mesh.GetBounds()
                        max_dimension = max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
                        radius = max_dimension * 2.5
                        logger.info(f"Calculated camera radius: {radius} from mesh object")
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Could not calculate camera distance from bounds: {e}")
                
            # Ensure minimum distance
            radius = max(radius, 2.0)
            logger.info(f"Using camera radius: {radius}")
            
            # Setup initial camera to fit the mesh properly
            if hasattr(renderer, 'renderer') and hasattr(renderer, 'camera'):
                # Let VTK automatically fit the camera to the mesh
                renderer.renderer.ResetCamera()
                renderer.camera.Zoom(0.8)  # Add some padding
                
                # Get the automatically calculated camera position as starting point
                initial_pos = renderer.camera.GetPosition()
                focal_point = renderer.camera.GetFocalPoint()
                radius = np.linalg.norm(np.array(initial_pos) - np.array(focal_point))
                logger.info(f"Using VTK-calculated camera distance: {radius}")
            
            # Generate rotation frames
            for i in range(frame_count):
                angle = (i / frame_count) * 360
                progress = 5 + (i / frame_count) * 80  # 5% to 85%
                self._update_progress(progress, f"Rendering frame {i+1}/{frame_count} (angle: {angle:.1f}°)")
                
                # Calculate camera position for rotation
                angle_rad = np.radians(angle)
                if axis.lower() == 'y':
                    position = (radius * np.sin(angle_rad), 0, radius * np.cos(angle_rad))
                elif axis.lower() == 'x':
                    position = (0, radius * np.sin(angle_rad), radius * np.cos(angle_rad))
                else:  # z axis
                    position = (radius * np.cos(angle_rad), radius * np.sin(angle_rad), 0)
                
                # Use the mesh center as focal point instead of origin
                if hasattr(renderer, 'camera'):
                    focal_point = renderer.camera.GetFocalPoint()
                else:
                    focal_point = (0, 0, 0)
                
                # Set camera position
                success = renderer.set_camera(position, target=focal_point, up=(0, 1, 0))
                if not success:
                    raise RuntimeError(f"Failed to set camera for frame {i}")
                
                # Render frame
                frame_path = self.temp_dir / f"frame_{i:06d}.png"
                success = renderer.render(frame_path)
                if not success:
                    raise RuntimeError(f"Failed to render frame {i}")
                    
                frame_paths.append(str(frame_path))
            
            self._update_progress(85, "Combining frames into video...")
            
            # Read first frame to get dimensions
            first_frame = cv2.imread(frame_paths[0])
            height, width, _ = first_frame.shape
            
            # Define codec and create VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            
            # Write frames to video
            for i, frame_path in enumerate(frame_paths):
                frame = cv2.imread(frame_path)
                out.write(frame)
                
                progress = 85 + (i / len(frame_paths)) * 10  # 85% to 95%
                self._update_progress(progress, f"Writing frame {i+1}/{len(frame_paths)}")
            
            # Release video writer
            out.release()
            
            self._update_progress(100, "Video generation complete!")
            return True
            
        except Exception as e:
            logger.error(f"OpenCV video generation failed: {e}")
            return False
            
        finally:
            # Cleanup temporary files
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None