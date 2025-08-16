"""
Render job handler for generating images and videos from STL files.
"""

import logging
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from ..job_types_v2 import Job, JobResult, JobError
from ..job_executor import JobExecutor

# Initialize availability flag
RENDERING_AVAILABLE = False

try:
    from ...core.stl_processor import STLProcessor
    from ...rendering.vtk_renderer import VTKRenderer
    RENDERING_AVAILABLE = True
except ImportError:
    # Fallback when rendering modules are not available
    STLProcessor = None
    VTKRenderer = None


logger = logging.getLogger(__name__)

# Global lock to prevent VTK threading issues
_vtk_render_lock = threading.Lock()


class RenderJobHandler(JobExecutor):
    """Handles rendering jobs for STL files."""
    
    def __init__(self):
        self.processor = None
        self.renderer = None
        
        if RENDERING_AVAILABLE:
            try:
                self.processor = STLProcessor()
                # Renderer will be created per-job with job-specific dimensions
                self.renderer = None
            except Exception as e:
                logger.warning(f"Could not initialize rendering components: {e}")
    
    def can_handle(self, job: Job) -> bool:
        """Check if this handler can process the job."""
        return job.job_type == "render"
    
    def execute(self, job: Job, progress_callback: Optional[Callable] = None) -> JobResult:
        """Execute a render job."""
        start_time = time.time()
        
        # Use lock to prevent VTK threading issues
        with _vtk_render_lock:
            return self._execute_with_lock(job, progress_callback, start_time)
    
    def _execute_with_lock(self, job: Job, progress_callback: Optional[Callable], start_time: float) -> JobResult:
        """Execute render job with VTK lock held."""
        if not RENDERING_AVAILABLE:
            return JobResult(
                job_id=job.id,
                success=False,
                error=JobError(
                    code="RENDERING_UNAVAILABLE",
                    message="Rendering components are not available",
                    details={"job_type": job.job_type}
                )
            )
        
        if not self.processor:
            return JobResult(
                job_id=job.id,
                success=False,
                error=JobError(
                    code="COMPONENTS_NOT_INITIALIZED",
                    message="STL processor could not be initialized",
                    details={"processor": self.processor is not None}
                )
            )
        
        try:
            input_file = Path(job.input_file)
            
            if not input_file.exists():
                return JobResult(
                    job_id=job.id,
                    success=False,
                    error=JobError(
                        code="FILE_NOT_FOUND",
                        message=f"Input file not found: {input_file}",
                        details={"input_file": str(input_file)}
                    )
                )
            
            if progress_callback:
                progress_callback(10.0, "Loading STL file...")
            
            # Load STL file using processor for validation
            success = self.processor.load(str(input_file))
            if not success:
                error_msg = "Failed to load STL file"
                if self.processor.last_error:
                    error_msg = f"Failed to load STL file: {self.processor.last_error}"
                
                return JobResult(
                    job_id=job.id,
                    success=False,
                    error=JobError(
                        code="STL_LOAD_FAILED",
                        message=error_msg,
                        details={"input_file": str(input_file)}
                    )
                )
            
            # Get the loaded mesh for reference (renderer will load directly)
            mesh_data = self.processor.mesh
            
            # Extract options from job first
            options = job.options or {}
            generate_image = options.get("image_rendering", options.get("generate_image", True))
            generate_video = options.get("video_rendering", options.get("generate_video", False))
            
            # Apply rendering parameters
            material = options.get("material", "plastic")
            lighting = options.get("lighting", "studio")
            image_width = options.get("image_width", 1920)
            image_height = options.get("image_height", 1080)
            video_format = options.get("video_format", "mp4")
            video_quality = options.get("video_quality", "standard") 
            video_duration = options.get("video_duration", 8.0)
            
            if progress_callback:
                progress_callback(30.0, "Setting up renderer...")
            
            # Create renderer with job-specific dimensions
            self.renderer = VTKRenderer(image_width, image_height)
            
            # Set up renderer by loading the STL file directly
            try:
                success = self.renderer.setup_scene(input_file)
                if not success:
                    return JobResult(
                        job_id=job.id,
                        success=False,
                        error=JobError(
                            code="RENDERER_SETUP_FAILED",
                            message="Failed to set up renderer scene",
                            details={"input_file": str(input_file)}
                        )
                    )
                
                # Apply material and lighting settings from options
                if hasattr(self.renderer, 'set_material'):
                    try:
                        from ...rendering.base_renderer import MaterialType
                        material_type = MaterialType(material)
                        self.renderer.set_material(material_type, (0.8, 0.8, 0.8))
                    except Exception as mat_error:
                        logger.warning(f"Failed to set material '{material}': {mat_error}")
                
                if hasattr(self.renderer, 'set_lighting'):
                    try:
                        from ...rendering.base_renderer import LightingPreset
                        lighting_preset = LightingPreset(lighting)
                        self.renderer.set_lighting(lighting_preset)
                    except Exception as light_error:
                        logger.warning(f"Failed to set lighting '{lighting}': {light_error}")
                
            except Exception as e:
                return JobResult(
                    job_id=job.id,
                    success=False,
                    error=JobError(
                        code="RENDERER_SETUP_FAILED",
                        message=f"Failed to set up renderer: {str(e)}",
                        details={"input_file": str(input_file)}
                    )
                )
            
            generated_files = []
            
            if generate_image:
                if progress_callback:
                    progress_callback(60.0, "Rendering image...")
                
                # Generate output filename
                if job.output_file:
                    output_path = Path(job.output_file)
                else:
                    output_dir = Path(options.get("output_dir", input_file.parent))
                    output_path = output_dir / f"{input_file.stem}_render.png"
                
                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Render image
                try:
                    success = self.renderer.render(output_path)
                    if success:
                        generated_files.append(str(output_path))
                        logger.info(f"Generated image: {output_path}")
                    else:
                        return JobResult(
                            job_id=job.id,
                            success=False,
                            error=JobError(
                                code="IMAGE_RENDER_FAILED",
                                message="Failed to render image",
                                details={"output_path": str(output_path)}
                            )
                        )
                except Exception as e:
                    return JobResult(
                        job_id=job.id,
                        success=False,
                        error=JobError(
                            code="IMAGE_RENDER_FAILED",
                            message=f"Failed to render image: {str(e)}",
                            details={"output_path": str(output_path)}
                        )
                    )
            
            if generate_video:
                if progress_callback:
                    progress_callback(80.0, "Rendering video...")
                
                # Generate video output filename with correct extension
                video_output_dir = Path(options.get("output_dir", input_file.parent))
                video_path = video_output_dir / f"{input_file.stem}_rotation.{video_format}"
                video_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    # Use video generator if available
                    from ...generators.video_generator import RotationVideoGenerator, VideoFormat, VideoQuality
                    video_gen = RotationVideoGenerator()
                    
                    # Convert string parameters to enums
                    video_format_enum = VideoFormat(video_format)
                    video_quality_enum = VideoQuality(video_quality)
                    
                    # Generate rotation video using the renderer with job parameters
                    success = video_gen.generate_rotation_video(
                        self.renderer, video_path, 
                        video_format=video_format_enum,
                        quality=video_quality_enum,
                        duration_seconds=video_duration
                    )
                    
                    if success:
                        generated_files.append(str(video_path))
                        logger.info(f"Generated video: {video_path}")
                    else:
                        logger.warning(f"Video generation failed for {video_path}")
                    
                except Exception as e:
                    logger.warning(f"Video generation failed: {e}")
                    # Video failure is not fatal, continue with success if image was generated
            
            if progress_callback:
                progress_callback(100.0, "Render complete!")
            
            execution_time = time.time() - start_time
            
            # Clean up renderer resources
            if self.renderer:
                try:
                    self.renderer.cleanup()
                except Exception as cleanup_error:
                    logger.warning(f"Error during renderer cleanup: {cleanup_error}")
            
            return JobResult(
                job_id=job.id,
                success=True,
                execution_time=execution_time,
                data={
                    "generated_files": generated_files,
                    "output_count": len(generated_files),
                    "input_file": str(input_file)
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.exception(f"Render job {job.id} failed with exception")
            
            # Clean up renderer resources even on failure
            if self.renderer:
                try:
                    self.renderer.cleanup()
                except Exception as cleanup_error:
                    logger.warning(f"Error during renderer cleanup after failure: {cleanup_error}")
            
            return JobResult(
                job_id=job.id,
                success=False,
                execution_time=execution_time,
                error=JobError(
                    code="UNEXPECTED_ERROR",
                    message=f"Unexpected error during rendering: {str(e)}",
                    details={"exception_type": type(e).__name__}
                )
            )
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if self.renderer:
            try:
                self.renderer.cleanup()
            except Exception as e:
                logger.warning(f"Error during renderer cleanup: {e}")
        
        self.processor = None
        self.renderer = None