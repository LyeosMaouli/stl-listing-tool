"""
Render job handler for generating images and videos from STL files.
"""

import logging
import time
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


class RenderJobHandler(JobExecutor):
    """Handles rendering jobs for STL files."""
    
    def __init__(self):
        self.processor = None
        self.renderer = None
        
        if RENDERING_AVAILABLE:
            try:
                self.processor = STLProcessor()
                self.renderer = VTKRenderer()
            except Exception as e:
                logger.warning(f"Could not initialize rendering components: {e}")
    
    def can_handle(self, job: Job) -> bool:
        """Check if this handler can process the job."""
        return job.job_type == "render"
    
    def execute(self, job: Job, progress_callback: Optional[Callable] = None) -> JobResult:
        """Execute a render job."""
        start_time = time.time()
        
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
        
        if not self.processor or not self.renderer:
            return JobResult(
                job_id=job.id,
                success=False,
                error=JobError(
                    code="COMPONENTS_NOT_INITIALIZED",
                    message="Rendering components could not be initialized",
                    details={"processor": self.processor is not None, "renderer": self.renderer is not None}
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
            
            # Load STL file
            mesh_data = self.processor.load_stl(str(input_file))
            if not mesh_data:
                return JobResult(
                    job_id=job.id,
                    success=False,
                    error=JobError(
                        code="STL_LOAD_FAILED",
                        message="Failed to load STL file",
                        details={"input_file": str(input_file)}
                    )
                )
            
            if progress_callback:
                progress_callback(30.0, "Setting up renderer...")
            
            # Set up renderer
            try:
                self.renderer.set_mesh(mesh_data)
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
            
            # Extract options from job
            options = job.options or {}
            generate_image = options.get("generate_image", True)
            generate_video = options.get("generate_video", False)
            
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
                    self.renderer.render_image(str(output_path), 
                                             width=options.get("width", 1920),
                                             height=options.get("height", 1080))
                    generated_files.append(str(output_path))
                    logger.info(f"Generated image: {output_path}")
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
                
                # Generate video output filename
                video_output_dir = Path(options.get("output_dir", input_file.parent))
                video_path = video_output_dir / f"{input_file.stem}_rotation.mp4"
                video_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    # Use video generator if available
                    from ...generators.video_generator import RotationVideoGenerator
                    video_gen = RotationVideoGenerator()
                    
                    # Set up video parameters
                    duration = options.get("video_duration", 10.0)
                    fps = options.get("video_fps", 30)
                    
                    # Generate rotation video
                    video_gen.generate_rotation_video(
                        mesh_data, str(video_path), 
                        duration=duration, fps=fps
                    )
                    generated_files.append(str(video_path))
                    logger.info(f"Generated video: {video_path}")
                    
                except Exception as e:
                    logger.warning(f"Video generation failed: {e}")
                    # Video failure is not fatal, continue with success if image was generated
            
            if progress_callback:
                progress_callback(100.0, "Render complete!")
            
            execution_time = time.time() - start_time
            
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