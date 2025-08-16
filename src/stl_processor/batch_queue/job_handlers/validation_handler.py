"""
Validation job handler for checking STL file integrity and mesh quality.
"""

import logging
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from ..job_types_v2 import Job, JobResult, JobError
from ..job_executor import JobExecutor

# Initialize availability flag
VALIDATION_AVAILABLE = False

try:
    from ...core.stl_processor import STLProcessor
    from ...core.mesh_validator import MeshValidator
    VALIDATION_AVAILABLE = True
except ImportError:
    # Fallback when validation modules are not available
    STLProcessor = None
    MeshValidator = None


logger = logging.getLogger(__name__)


class ValidationJobHandler(JobExecutor):
    """Handles validation jobs for STL files."""
    
    def __init__(self):
        self.processor = None
        
        if VALIDATION_AVAILABLE:
            try:
                self.processor = STLProcessor()
            except Exception as e:
                logger.warning(f"Could not initialize validation components: {e}")
    
    def can_handle(self, job: Job) -> bool:
        """Check if this handler can process the job."""
        return job.job_type == "validate"
    
    def execute(self, job: Job, progress_callback: Optional[Callable] = None) -> JobResult:
        """Execute a validation job."""
        start_time = time.time()
        
        if not VALIDATION_AVAILABLE:
            return JobResult(
                job_id=job.id,
                success=False,
                error=JobError(
                    code="VALIDATION_UNAVAILABLE",
                    message="Validation components are not available",
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
                progress_callback(30.0, "Creating validator...")
            
            # Create validator with loaded mesh
            validator = MeshValidator(self.processor.mesh)
            
            if progress_callback:
                progress_callback(50.0, "Validating mesh...")
            
            # Extract validation options
            options = job.options or {}
            validation_level = options.get("validation_level", "standard")
            
            try:
                from ...core.mesh_validator import ValidationLevel
                level = ValidationLevel(validation_level)
            except ValueError:
                level = ValidationLevel.STANDARD
            
            # Perform validation
            validation_results = validator.validate(level)
            
            if progress_callback:
                progress_callback(100.0, "Validation complete!")
            
            execution_time = time.time() - start_time
            
            return JobResult(
                job_id=job.id,
                success=True,
                execution_time=execution_time,
                data={
                    "validation_results": validation_results,
                    "validation_level": level.value,
                    "input_file": str(input_file)
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.exception(f"Validation job {job.id} failed with exception")
            return JobResult(
                job_id=job.id,
                success=False,
                execution_time=execution_time,
                error=JobError(
                    code="UNEXPECTED_ERROR",
                    message=f"Unexpected error during validation: {str(e)}",
                    details={"exception_type": type(e).__name__}
                )
            )
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.processor = None