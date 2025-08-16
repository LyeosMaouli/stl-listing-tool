"""Analysis job handler for extracting detailed information from STL files."""

import logging
import time
from typing import Optional, Callable, Dict, Any

from ..job_types_v2 import Job, JobResult, JobError
from ..job_executor import JobExecutor

ANALYSIS_AVAILABLE = False

try:
    from ...core.stl_processor import STLProcessor
    ANALYSIS_AVAILABLE = True
except ImportError:
    STLProcessor = None

logger = logging.getLogger(__name__)

class AnalysisJobHandler(JobExecutor):
    """Handles analysis jobs for STL files."""
    
    def __init__(self):
        self.processor = None
        
        if ANALYSIS_AVAILABLE:
            try:
                self.processor = STLProcessor()
            except Exception as e:
                logger.warning(f"Could not initialize analysis components: {e}")
    
    def can_handle(self, job: Job) -> bool:
        """Check if this handler can process the job."""
        return job.job_type == "analyze"
    
    def execute(self, job: Job, progress_callback: Optional[Callable] = None) -> JobResult:
        """Execute an analysis job."""
        start_time = time.time()
        
        if not ANALYSIS_AVAILABLE:
            return JobResult(
                job_id=job.id,
                success=False,
                error=JobError(
                    code="ANALYSIS_UNAVAILABLE",
                    message="Analysis components are not available",
                    details={"job_type": job.job_type}
                )
            )
        
        if not self.processor:
            return JobResult(
                job_id=job.id,
                success=False,
                error=JobError(
                    code="PROCESSOR_NOT_INITIALIZED",
                    message="STL processor could not be initialized",
                    details={"processor": self.processor is not None}
                )
            )
        
        try:
            from pathlib import Path
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
            
            if progress_callback:
                progress_callback(50.0, "Calculating dimensions...")
            
            # Extract dimensions
            dimensions = self.processor.get_dimensions()
            
            if progress_callback:
                progress_callback(80.0, "Calculating scale info...")
            
            # Extract scale information
            scale_info = self.processor.get_scale_info()
            
            if progress_callback:
                progress_callback(100.0, "Analysis complete!")
            
            execution_time = time.time() - start_time
            
            return JobResult(
                job_id=job.id,
                success=True,
                execution_time=execution_time,
                data={
                    "dimensions": dimensions,
                    "scale_info": scale_info,
                    "input_file": str(input_file)
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.exception(f"Analysis job {job.id} failed with exception")
            return JobResult(
                job_id=job.id,
                success=False,
                execution_time=execution_time,
                error=JobError(
                    code="UNEXPECTED_ERROR",
                    message=f"Unexpected error during analysis: {str(e)}",
                    details={"exception_type": type(e).__name__}
                )
            )
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.processor = None