"""
Error handling system for the STL processing queue.
Provides retry mechanisms, error classification, and recovery strategies.
"""

import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from .job_types_v2 import Job, JobError, JobResult, JobStatus


logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"  
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error category types."""
    FILE_IO = "file_io"
    MEMORY = "memory"
    PROCESSING = "processing"
    SYSTEM = "system"
    VALIDATION = "validation"
    RENDERING = "rendering"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    USER_ERROR = "user_error"
    UNKNOWN = "unknown"


@dataclass
class ErrorPattern:
    """Defines a pattern for error matching and handling."""
    code_pattern: str
    message_pattern: str
    category: ErrorCategory
    severity: ErrorSeverity
    max_retries: int
    retry_delay: float
    recovery_strategy: str


class ErrorClassifier:
    """Classifies errors based on patterns and provides handling recommendations."""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
    
    def _initialize_patterns(self) -> List[ErrorPattern]:
        """Initialize default error patterns."""
        return [
            # File I/O errors
            ErrorPattern(
                code_pattern="STL_LOAD_FAILED",
                message_pattern=".*load.*file.*",
                category=ErrorCategory.FILE_IO,
                severity=ErrorSeverity.HIGH,
                max_retries=2,
                retry_delay=1.0,
                recovery_strategy="check_file_permissions"
            ),
            ErrorPattern(
                code_pattern=".*FILE.*NOT.*FOUND.*",
                message_pattern=".*not found.*|.*does not exist.*",
                category=ErrorCategory.FILE_IO,
                severity=ErrorSeverity.CRITICAL,
                max_retries=0,
                retry_delay=0.0,
                recovery_strategy="skip_job"
            ),
            
            # Memory errors
            ErrorPattern(
                code_pattern="MEMORY_ERROR",
                message_pattern=".*memory.*|.*out of memory.*",
                category=ErrorCategory.MEMORY,
                severity=ErrorSeverity.HIGH,
                max_retries=1,
                retry_delay=5.0,
                recovery_strategy="reduce_batch_size"
            ),
            
            # Processing errors
            ErrorPattern(
                code_pattern="RENDER_FAILED",
                message_pattern=".*render.*failed.*",
                category=ErrorCategory.RENDERING,
                severity=ErrorSeverity.MEDIUM,
                max_retries=3,
                retry_delay=2.0,
                recovery_strategy="fallback_renderer"
            ),
            ErrorPattern(
                code_pattern="VALIDATION_FAILED",
                message_pattern=".*validation.*failed.*",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.LOW,
                max_retries=1,
                retry_delay=1.0,
                recovery_strategy="auto_repair"
            ),
            
            # System errors
            ErrorPattern(
                code_pattern="INTERRUPTED",
                message_pattern=".*interrupt.*|.*cancel.*",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.LOW,
                max_retries=0,
                retry_delay=0.0,
                recovery_strategy="resume_later"
            ),
            
            # Default pattern
            ErrorPattern(
                code_pattern=".*",
                message_pattern=".*",
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.MEDIUM,
                max_retries=1,
                retry_delay=1.0,
                recovery_strategy="default_retry"
            )
        ]
    
    def classify_error(self, error: JobError) -> ErrorPattern:
        """Classify an error and return the matching pattern."""
        import re
        
        for pattern in self.patterns:
            # Check code pattern
            code_match = re.search(pattern.code_pattern, error.code or "", re.IGNORECASE)
            
            # Check message pattern
            message_match = re.search(pattern.message_pattern, error.message or "", re.IGNORECASE)
            
            if code_match or message_match:
                return pattern
        
        # Return default pattern if no match
        return self.patterns[-1]


class RetryManager:
    """Manages retry logic for failed jobs."""
    
    def __init__(self, classifier: Optional[ErrorClassifier] = None):
        self.classifier = classifier or ErrorClassifier()
        self.retry_counts: Dict[str, int] = {}
        self.retry_history: Dict[str, List[float]] = {}
    
    def should_retry(self, job: Job, error: JobError) -> bool:
        """Determine if a job should be retried based on error classification."""
        pattern = self.classifier.classify_error(error)
        current_retries = self.retry_counts.get(job.id, 0)
        
        return current_retries < pattern.max_retries
    
    def get_retry_delay(self, job: Job, error: JobError) -> float:
        """Get the delay before retrying a job."""
        pattern = self.classifier.classify_error(error)
        current_retries = self.retry_counts.get(job.id, 0)
        
        # Exponential backoff
        base_delay = pattern.retry_delay
        return base_delay * (2 ** current_retries)
    
    def record_retry(self, job: Job) -> None:
        """Record a retry attempt for a job."""
        self.retry_counts[job.id] = self.retry_counts.get(job.id, 0) + 1
        
        if job.id not in self.retry_history:
            self.retry_history[job.id] = []
        self.retry_history[job.id].append(time.time())
        
        logger.info(f"Recording retry {self.retry_counts[job.id]} for job {job.id}")
    
    def reset_retry_count(self, job_id: str) -> None:
        """Reset retry count for a job (after successful completion)."""
        self.retry_counts.pop(job_id, None)
        self.retry_history.pop(job_id, None)
    
    def get_retry_count(self, job_id: str) -> int:
        """Get current retry count for a job."""
        return self.retry_counts.get(job_id, 0)


class RecoveryStrategy:
    """Implements recovery strategies for different types of errors."""
    
    def __init__(self):
        self.strategies = {
            "check_file_permissions": self._check_file_permissions,
            "skip_job": self._skip_job,
            "reduce_batch_size": self._reduce_batch_size,
            "fallback_renderer": self._fallback_renderer,
            "auto_repair": self._auto_repair,
            "resume_later": self._resume_later,
            "default_retry": self._default_retry
        }
    
    def apply_strategy(self, strategy_name: str, job: Job, error: JobError) -> Dict[str, Any]:
        """Apply a recovery strategy."""
        strategy_func = self.strategies.get(strategy_name, self._default_retry)
        return strategy_func(job, error)
    
    def _check_file_permissions(self, job: Job, error: JobError) -> Dict[str, Any]:
        """Check and attempt to fix file permission issues."""
        import os
        from pathlib import Path
        
        try:
            input_path = Path(job.input_file)
            
            # Check if file exists
            if not input_path.exists():
                return {"success": False, "message": "Input file does not exist"}
            
            # Check if file is readable
            if not os.access(input_path, os.R_OK):
                return {"success": False, "message": "Input file is not readable"}
            
            # Check output directory permissions if specified
            if job.output_file:
                output_path = Path(job.output_file)
                output_dir = output_path.parent
                
                if not output_dir.exists():
                    try:
                        output_dir.mkdir(parents=True, exist_ok=True)
                        return {"success": True, "message": "Created output directory"}
                    except PermissionError:
                        return {"success": False, "message": "Cannot create output directory"}
                
                if not os.access(output_dir, os.W_OK):
                    return {"success": False, "message": "Output directory is not writable"}
            
            return {"success": True, "message": "File permissions OK"}
            
        except Exception as e:
            return {"success": False, "message": f"Permission check failed: {e}"}
    
    def _skip_job(self, job: Job, error: JobError) -> Dict[str, Any]:
        """Skip the job due to unrecoverable error."""
        job.status = JobStatus.FAILED
        return {
            "success": True,
            "message": "Job skipped due to unrecoverable error",
            "action": "skip"
        }
    
    def _reduce_batch_size(self, job: Job, error: JobError) -> Dict[str, Any]:
        """Suggest reducing batch size for memory issues."""
        return {
            "success": True,
            "message": "Consider reducing batch size or processing fewer files simultaneously",
            "action": "reduce_batch_size"
        }
    
    def _fallback_renderer(self, job: Job, error: JobError) -> Dict[str, Any]:
        """Attempt to use fallback rendering options."""
        # Modify job options to use simpler rendering
        if "render_options" in job.options:
            render_options = job.options["render_options"]
            
            # Reduce quality settings
            render_options["width"] = min(render_options.get("width", 800), 400)
            render_options["height"] = min(render_options.get("height", 600), 300)
            render_options["anti_aliasing"] = False
            render_options["high_quality"] = False
            
            return {
                "success": True,
                "message": "Using fallback rendering options",
                "action": "retry_with_fallback"
            }
        
        return {"success": False, "message": "No fallback options available"}
    
    def _auto_repair(self, job: Job, error: JobError) -> Dict[str, Any]:
        """Attempt automatic mesh repair for validation failures."""
        # Enable auto-repair in validation options
        if "validation_options" not in job.options:
            job.options["validation_options"] = {}
        
        job.options["validation_options"]["auto_repair"] = True
        job.options["validation_options"]["aggressive_repair"] = True
        
        return {
            "success": True,
            "message": "Enabled automatic mesh repair",
            "action": "retry_with_repair"
        }
    
    def _resume_later(self, job: Job, error: JobError) -> Dict[str, Any]:
        """Mark job for later resumption."""
        job.status = JobStatus.PENDING
        return {
            "success": True,
            "message": "Job marked for later resumption",
            "action": "resume_later"
        }
    
    def _default_retry(self, job: Job, error: JobError) -> Dict[str, Any]:
        """Default retry strategy."""
        return {
            "success": True,
            "message": "Will retry with same parameters",
            "action": "retry"
        }


class ErrorHandler:
    """Main error handling system."""
    
    def __init__(self):
        self.classifier = ErrorClassifier()
        self.retry_manager = RetryManager(self.classifier)
        self.recovery_strategy = RecoveryStrategy()
        
        # Error statistics
        self.error_stats: Dict[str, int] = {}
        self.recovery_stats: Dict[str, int] = {}
        
        # Callbacks
        self.on_error: Optional[Callable[[Job, JobError, ErrorPattern], None]] = None
        self.on_recovery_applied: Optional[Callable[[Job, str, Dict[str, Any]], None]] = None
    
    def handle_error(self, job: Job, error: JobError) -> Dict[str, Any]:
        """
        Handle an error for a job.
        Returns action to take and any modifications to make.
        """
        # Classify the error
        pattern = self.classifier.classify_error(error)
        
        # Update statistics
        self.error_stats[pattern.category.value] = self.error_stats.get(pattern.category.value, 0) + 1
        
        # Log the error
        logger.error(f"Job {job.id} failed with {pattern.severity.value} {pattern.category.value} error: {error.message}")
        
        # Notify callback
        if self.on_error:
            self.on_error(job, error, pattern)
        
        # Determine if we should retry
        if self.retry_manager.should_retry(job, error):
            # Apply recovery strategy
            recovery_result = self.recovery_strategy.apply_strategy(
                pattern.recovery_strategy, job, error
            )
            
            if recovery_result.get("success", False):
                # Record retry attempt
                self.retry_manager.record_retry(job)
                
                # Get retry delay
                retry_delay = self.retry_manager.get_retry_delay(job, error)
                
                # Update recovery statistics
                strategy = pattern.recovery_strategy
                self.recovery_stats[strategy] = self.recovery_stats.get(strategy, 0) + 1
                
                # Notify callback
                if self.on_recovery_applied:
                    self.on_recovery_applied(job, strategy, recovery_result)
                
                return {
                    "action": "retry",
                    "delay": retry_delay,
                    "strategy": strategy,
                    "message": recovery_result.get("message", "Applying recovery strategy"),
                    "retry_count": self.retry_manager.get_retry_count(job.id)
                }
        
        # No more retries or recovery failed
        job.status = JobStatus.FAILED
        
        return {
            "action": "fail",
            "message": f"Job failed after {self.retry_manager.get_retry_count(job.id)} retries",
            "pattern": pattern,
            "final_error": error
        }
    
    def handle_success(self, job: Job) -> None:
        """Handle successful job completion."""
        # Reset retry count
        self.retry_manager.reset_retry_count(job.id)
        
        logger.info(f"Job {job.id} completed successfully")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error handling statistics."""
        total_errors = sum(self.error_stats.values())
        total_recoveries = sum(self.recovery_stats.values())
        
        return {
            "total_errors": total_errors,
            "total_recoveries": total_recoveries,
            "recovery_rate": total_recoveries / total_errors if total_errors > 0 else 0,
            "errors_by_category": self.error_stats.copy(),
            "recoveries_by_strategy": self.recovery_stats.copy()
        }
    
    def reset_statistics(self) -> None:
        """Reset error handling statistics."""
        self.error_stats.clear()
        self.recovery_stats.clear()
        self.retry_manager.retry_counts.clear()
        self.retry_manager.retry_history.clear()