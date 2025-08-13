"""
Video generation for 3D models including 360° rotation videos.
Supports various video formats and quality settings.
"""

import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import numpy as np
from enum import Enum
import threading
import time

from ..utils.logger import setup_logger

# Import moviepy with fallback
try:
    from moviepy.editor import ImageSequenceClip, clips_array, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

# Import PIL with fallback
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = setup_logger("video_generator")


class VideoFormat(Enum):
    """Supported video output formats."""
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    GIF = "gif"


class VideoQuality(Enum):
    """Video quality presets."""
    DRAFT = "draft"      # 480p, 12fps, fast encode
    STANDARD = "standard" # 720p, 24fps, balanced
    HIGH = "high"        # 1080p, 30fps, high quality
    ULTRA = "ultra"      # 1080p, 60fps, best quality


class RotationVideoGenerator:
    """Generates 360° rotation videos of 3D models."""
    
    def __init__(self):
        self.temp_dir = None
        self.progress_callback = None
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are available."""
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy is required for video generation. Install with: pip install moviepy")
        if not PIL_AVAILABLE:
            raise ImportError("Pillow is required for image processing. Install with: pip install Pillow")
    
    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set callback function for progress updates.
        
        Args:
            callback: Function that takes (progress_percent, status_message)
        """
        self.progress_callback = callback
    
    def _update_progress(self, progress: float, message: str):
        """Update progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(progress, message)
        logger.info(f"Progress: {progress:.1f}% - {message}")
    
    def generate_rotation_video(
        self,
        renderer,
        output_path: Path,
        video_format: VideoFormat = VideoFormat.MP4,
        quality: VideoQuality = VideoQuality.STANDARD,
        duration_seconds: float = 8.0,
        axis: str = 'y',  # 'x', 'y', or 'z'
        include_title: bool = True,
        title_text: Optional[str] = None
    ) -> bool:
        """Generate a 360° rotation video of the loaded 3D model.
        
        Args:
            renderer: Initialized renderer with loaded model
            output_path: Path to save the video file
            video_format: Output video format
            quality: Video quality preset
            duration_seconds: Duration of the rotation in seconds
            axis: Rotation axis ('x', 'y', or 'z')
            include_title: Whether to include title overlay
            title_text: Custom title text (uses filename if None)
            
        Returns:
            True if video generation succeeded, False otherwise
        """
        try:
            self._update_progress(0, "Initializing video generation...")
            
            # Setup quality parameters
            quality_settings = self._get_quality_settings(quality)
            frame_count = int(duration_seconds * quality_settings['fps'])
            
            # Create temporary directory for frames
            self.temp_dir = Path(tempfile.mkdtemp(prefix="stl_video_"))
            frame_paths = []
            
            self._update_progress(5, f"Generating {frame_count} frames...")
            
            # Generate rotation frames
            for i in range(frame_count):
                angle = (i / frame_count) * 360.0
                
                # Set camera rotation
                self._set_camera_rotation(renderer, angle, axis)
                
                # Render frame
                frame_path = self.temp_dir / f"frame_{i:04d}.png"
                if not renderer.render(frame_path):
                    raise Exception(f"Failed to render frame {i}")
                
                frame_paths.append(str(frame_path))
                
                progress = 5 + (i / frame_count) * 70  # 5-75% for frame generation
                self._update_progress(progress, f"Rendered frame {i+1}/{frame_count}")
            
            self._update_progress(75, "Processing frames...")
            
            # Add title overlay if requested
            if include_title:
                self._add_title_overlay(frame_paths, title_text, quality_settings)
            
            self._update_progress(85, "Creating video...")
            
            # Create video from frames
            success = self._create_video_from_frames(
                frame_paths, output_path, video_format, quality_settings
            )
            
            if success:
                self._update_progress(100, f"Video saved to {output_path}")
                logger.info(f"Successfully generated rotation video: {output_path}")
            else:
                logger.error("Failed to create video from frames")
                
            return success
            
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            return False
        finally:
            self._cleanup_temp_files()
    
    def _get_quality_settings(self, quality: VideoQuality) -> Dict[str, Any]:
        """Get quality settings for video generation."""
        settings = {
            VideoQuality.DRAFT: {
                'width': 854, 'height': 480, 'fps': 12, 'bitrate': '500k'
            },
            VideoQuality.STANDARD: {
                'width': 1280, 'height': 720, 'fps': 24, 'bitrate': '1500k'
            },
            VideoQuality.HIGH: {
                'width': 1920, 'height': 1080, 'fps': 30, 'bitrate': '3000k'
            },
            VideoQuality.ULTRA: {
                'width': 1920, 'height': 1080, 'fps': 60, 'bitrate': '5000k'
            }
        }
        return settings[quality]
    
    def _set_camera_rotation(self, renderer, angle: float, axis: str):
        """Set camera rotation for the given angle and axis."""
        try:
            if hasattr(renderer, 'set_camera_rotation'):
                renderer.set_camera_rotation(angle, axis)
            elif hasattr(renderer, 'render_window') and hasattr(renderer, 'renderer_obj'):
                # VTK-specific rotation
                camera = renderer.renderer_obj.GetActiveCamera()
                
                # Reset to default position
                camera.SetPosition(5, 0, 0)
                camera.SetViewUp(0, 0, 1)
                camera.SetFocalPoint(0, 0, 0)
                
                # Apply rotation based on axis
                if axis.lower() == 'y':
                    # Rotate around Y axis (most common for product shots)
                    x = 5 * np.cos(np.radians(angle))
                    z = 5 * np.sin(np.radians(angle))
                    camera.SetPosition(x, 0, z)
                elif axis.lower() == 'z':
                    # Rotate around Z axis (vertical spin)
                    x = 5 * np.cos(np.radians(angle))
                    y = 5 * np.sin(np.radians(angle))
                    camera.SetPosition(x, y, 0)
                elif axis.lower() == 'x':
                    # Rotate around X axis (flip view)
                    y = 5 * np.cos(np.radians(angle))
                    z = 5 * np.sin(np.radians(angle))
                    camera.SetPosition(0, y, z)
                
                renderer.render_window.Render()
            else:
                logger.warning("Renderer does not support camera rotation")
                
        except Exception as e:
            logger.warning(f"Failed to set camera rotation: {e}")
    
    def _add_title_overlay(self, frame_paths: List[str], title_text: Optional[str], quality_settings: Dict[str, Any]):
        """Add title overlay to frames."""
        if not title_text:
            title_text = "3D Model Rotation"
        
        try:
            width, height = quality_settings['width'], quality_settings['height']
            
            for frame_path in frame_paths:
                with Image.open(frame_path) as img:
                    # Resize image to match quality settings
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                    
                    # Create overlay
                    draw = ImageDraw.Draw(img)
                    
                    # Try to use a nice font, fall back to default
                    try:
                        font_size = max(24, height // 30)
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
                    
                    # Add semi-transparent background for text
                    text_bbox = draw.textbbox((0, 0), title_text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    
                    # Position text at bottom center
                    text_x = (width - text_width) // 2
                    text_y = height - text_height - 20
                    
                    # Draw background rectangle
                    padding = 10
                    draw.rectangle([
                        text_x - padding, text_y - padding,
                        text_x + text_width + padding, text_y + text_height + padding
                    ], fill=(0, 0, 0, 128))
                    
                    # Draw text
                    draw.text((text_x, text_y), title_text, fill=(255, 255, 255), font=font)
                    
                    # Save modified frame
                    img.save(frame_path)
                    
        except Exception as e:
            logger.warning(f"Failed to add title overlay: {e}")
    
    def _create_video_from_frames(
        self, 
        frame_paths: List[str], 
        output_path: Path, 
        video_format: VideoFormat,
        quality_settings: Dict[str, Any]
    ) -> bool:
        """Create video file from frame sequence."""
        try:
            fps = quality_settings['fps']
            
            if video_format == VideoFormat.GIF:
                # Create animated GIF
                images = []
                for frame_path in frame_paths:
                    img = Image.open(frame_path)
                    # Resize for GIF optimization
                    img = img.resize((640, 360), Image.Resampling.LANCZOS)
                    images.append(img)
                
                # Save as GIF
                images[0].save(
                    output_path,
                    save_all=True,
                    append_images=images[1:],
                    duration=int(1000 / fps),  # Duration in milliseconds
                    loop=0
                )
            else:
                # Create MP4/AVI/MOV video
                clip = ImageSequenceClip(frame_paths, fps=fps)
                
                # Set codec based on format
                codec_map = {
                    VideoFormat.MP4: 'libx264',
                    VideoFormat.AVI: 'libxvid',  
                    VideoFormat.MOV: 'libx264'
                }
                
                clip.write_videofile(
                    str(output_path),
                    codec=codec_map[video_format],
                    bitrate=quality_settings['bitrate'],
                    verbose=False,
                    logger=None  # Suppress moviepy logs
                )
                clip.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create video: {e}")
            return False
    
    def _cleanup_temp_files(self):
        """Clean up temporary files."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")


class MultiAngleVideoGenerator:
    """Generates videos showing multiple angles of a 3D model."""
    
    def __init__(self):
        self.video_generator = RotationVideoGenerator()
    
    def generate_multi_angle_video(
        self,
        renderer,
        output_path: Path,
        angles: List[Dict[str, float]] = None,
        video_format: VideoFormat = VideoFormat.MP4,
        quality: VideoQuality = VideoQuality.STANDARD
    ) -> bool:
        """Generate video showing multiple preset angles.
        
        Args:
            renderer: Initialized renderer with loaded model
            output_path: Path to save the video file
            angles: List of angle dictionaries with 'rotation', 'elevation', 'duration'
            video_format: Output video format  
            quality: Video quality preset
            
        Returns:
            True if video generation succeeded, False otherwise
        """
        if angles is None:
            # Default angles: front, back, left, right, top, bottom
            angles = [
                {'rotation': 0, 'elevation': 0, 'duration': 2.0, 'label': 'Front'},
                {'rotation': 180, 'elevation': 0, 'duration': 2.0, 'label': 'Back'},  
                {'rotation': 90, 'elevation': 0, 'duration': 2.0, 'label': 'Left'},
                {'rotation': 270, 'elevation': 0, 'duration': 2.0, 'label': 'Right'},
                {'rotation': 0, 'elevation': 90, 'duration': 2.0, 'label': 'Top'},
                {'rotation': 0, 'elevation': -90, 'duration': 2.0, 'label': 'Bottom'}
            ]
        
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="multi_angle_"))
            video_clips = []
            
            for i, angle_info in enumerate(angles):
                # Generate short clip for this angle
                angle_video = temp_dir / f"angle_{i}.mp4"
                
                # Set camera to angle
                self._set_camera_angle(renderer, angle_info)
                
                # Generate short rotation or static video
                if self.video_generator.generate_rotation_video(
                    renderer, angle_video, video_format, quality,
                    duration_seconds=angle_info.get('duration', 2.0),
                    include_title=True,
                    title_text=angle_info.get('label', f'Angle {i+1}')
                ):
                    video_clips.append(angle_video)
            
            # Concatenate all clips
            if video_clips:
                return self._concatenate_videos(video_clips, output_path)
            
            return False
            
        except Exception as e:
            logger.error(f"Multi-angle video generation failed: {e}")
            return False
        finally:
            # Cleanup temp files
            if 'temp_dir' in locals():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
    
    def _set_camera_angle(self, renderer, angle_info: Dict[str, float]):
        """Set camera to specific angle."""
        # Implementation would depend on renderer capabilities
        pass
    
    def _concatenate_videos(self, video_paths: List[Path], output_path: Path) -> bool:
        """Concatenate multiple video files."""
        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips
            
            clips = [VideoFileClip(str(path)) for path in video_paths]
            final_clip = concatenate_videoclips(clips)
            final_clip.write_videofile(str(output_path), verbose=False, logger=None)
            
            # Close clips to free memory
            for clip in clips:
                clip.close()
            final_clip.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to concatenate videos: {e}")
            return False