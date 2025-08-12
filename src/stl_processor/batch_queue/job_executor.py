"""
Job execution engine for the STL processing queue system.
Provides threaded job execution with resource management and error handling.
"""

import logging
import threading  
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import traceback

# Import Python's built-in queue to avoid naming conflicts
import queue as python_queue

from .job_types_v2 import Job, JobStatus, JobResult, JobError
from .progress_tracker import ProgressTracker


logger = logging.getLogger(__name__)


class JobExecutor(ABC):
    """Abstract base class for job executors."""
    
    @abstractmethod
    def execute(self, job: Job, progress_callback: Optional[Callable] = None) -> JobResult:
        """Execute a single job."""
        pass
    
    @abstractmethod
    def can_handle(self, job: Job) -> bool:
        """Check if this executor can handle the given job type."""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources used by the executor."""
        pass


class JobExecutionEngine:
    """
    Main job execution engine that manages worker threads and job processing.
    """
    
    def __init__(self, max_workers: int = 2, progress_tracker: Optional[ProgressTracker] = None):
        self.max_workers = max_workers
        self.progress_tracker = progress_tracker or ProgressTracker()
        self.executor_pool: Optional[ThreadPoolExecutor] = None
        self.active_futures: Dict[str, Future] = {}
        self.paused = threading.Event()
        self.paused.set()  # Start unpaused
        self.shutdown_requested = threading.Event()
        
        # Registry of job executors
        self.executors: Dict[str, JobExecutor] = {}
        
        # Job execution callbacks
        self.on_job_started: Optional[Callable[[Job], None]] = None
        self.on_job_completed: Optional[Callable[[Job, JobResult], None]] = None
        self.on_job_failed: Optional[Callable[[Job, JobError], None]] = None
        self.on_job_progress: Optional[Callable[[Job, float, str], None]] = None
        
        self._lock = threading.RLock()
        
    def register_executor(self, job_type: str, executor: JobExecutor) -> None:
        """Register a job executor for a specific job type."""
        with self._lock:
            self.executors[job_type] = executor
            logger.info(f"Registered executor for job type: {job_type}")
    
    def unregister_executor(self, job_type: str) -> None:
        """Unregister a job executor."""
        with self._lock:
            if job_type in self.executors:
                executor = self.executors.pop(job_type)
                executor.cleanup()
                logger.info(f"Unregistered executor for job type: {job_type}")
    
    def start(self) -> None:
        """Start the execution engine."""
        with self._lock:
            if self.executor_pool is None:
                self.executor_pool = ThreadPoolExecutor(
                    max_workers=self.max_workers,
                    thread_name_prefix="job-executor"
                )
                self.shutdown_requested.clear()
                logger.info(f"Started job execution engine with {self.max_workers} workers")
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the execution engine."""
        with self._lock:
            self.shutdown_requested.set()
            
            if self.executor_pool is not None:
                logger.info("Shutting down job execution engine...")
                
                # Cancel active futures
                for job_id, future in list(self.active_futures.items()):
                    if not future.done():
                        logger.info(f"Cancelling job: {job_id}")
                        future.cancel()
                
                # Shutdown thread pool
                self.executor_pool.shutdown(wait=wait)
                self.executor_pool = None
                
                # Cleanup executors
                for executor in self.executors.values():
                    executor.cleanup()
                
                logger.info("Job execution engine shutdown complete")
    
    def pause(self) -> None:
        """Pause job execution."""
        self.paused.clear()
        logger.info("Job execution paused")
    
    def resume(self) -> None:
        """Resume job execution."""
        self.paused.set()
        logger.info("Job execution resumed")
    
    def is_paused(self) -> bool:
        """Check if execution is paused."""
        return not self.paused.is_set()
    
    def submit_job(self, job: Job) -> Future:
        """Submit a job for execution."""
        if self.executor_pool is None:
            self.start()
        
        # Find appropriate executor
        executor = self._get_executor_for_job(job)
        if executor is None:
            error = JobError(
                code="EXECUTOR_NOT_FOUND",
                message=f"No executor found for job type: {job.job_type}",
                details={"job_type": job.job_type}
            )
            # Create a future that's already failed
            failed_future = Future()
            failed_future.set_exception(RuntimeError(error.message))
            return failed_future
        
        # Submit job for execution
        future = self.executor_pool.submit(self._execute_job_with_wrapper, job, executor)
        
        with self._lock:
            self.active_futures[job.id] = future
        
        return future
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        with self._lock:
            future = self.active_futures.get(job_id)
            if future and not future.done():
                success = future.cancel()
                if success:
                    logger.info(f"Cancelled job: {job_id}")
                return success
            return False
    
    def get_active_jobs(self) -> List[str]:
        """Get list of currently active job IDs."""
        with self._lock:
            return [job_id for job_id, future in self.active_futures.items() 
                   if not future.done()]
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Wait for all active jobs to complete."""
        with self._lock:
            futures = list(self.active_futures.values())
        
        if futures:
            logger.info(f"Waiting for {len(futures)} jobs to complete...")
            for future in as_completed(futures, timeout=timeout):
                try:
                    future.result()  # This will raise any exceptions
                except Exception as e:
                    logger.error(f"Job failed: {e}")
    
    def _get_executor_for_job(self, job: Job) -> Optional[JobExecutor]:
        """Find the appropriate executor for a job."""
        executor = self.executors.get(job.job_type)
        if executor and executor.can_handle(job):
            return executor
        
        # Try to find any executor that can handle this job
        for executor in self.executors.values():
            if executor.can_handle(job):
                return executor
        
        return None
    
    def _execute_job_with_wrapper(self, job: Job, executor: JobExecutor) -> JobResult:
        """
        Execute a job with proper error handling and progress tracking.
        This runs in a worker thread.
        """
        try:
            # Wait if paused
            while not self.paused.wait(timeout=0.1):
                if self.shutdown_requested.is_set():
                    raise InterruptedError("Execution engine shutdown requested")
            
            logger.info(f"Starting job execution: {job.id} ({job.job_type})")
            
            # Update job status
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            
            # Notify callbacks
            if self.on_job_started:
                self.on_job_started(job)
            
            # Create progress callback
            def progress_callback(progress: float, message: str = ""):
                if self.on_job_progress:
                    self.on_job_progress(job, progress, message)
                
                # Update progress tracker
                self.progress_tracker.update_job_progress(job.id, progress, message)
                
                # Check for pause/shutdown
                if not self.paused.wait(timeout=0.1) or self.shutdown_requested.is_set():
                    raise InterruptedError("Job execution interrupted")
            
            # Execute the job
            result = executor.execute(job, progress_callback)
            
            # Update job status
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()
            result.execution_time = job.completed_at - (job.started_at or 0)
            
            logger.info(f"Job completed successfully: {job.id}")
            
            # Notify callback
            if self.on_job_completed:
                self.on_job_completed(job, result)
            
            return result
            
        except InterruptedError:
            # Job was cancelled or interrupted
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            
            error = JobError(
                code="INTERRUPTED",
                message="Job execution was interrupted",
                details={"job_id": job.id}
            )
            
            logger.info(f"Job interrupted: {job.id}")
            return JobResult(
                job_id=job.id,
                success=False,
                error=error
            )
            
        except Exception as e:
            # Job failed with error
            job.status = JobStatus.FAILED
            job.completed_at = time.time()
            
            error_details = {
                "job_id": job.id,
                "exception_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
            
            error = JobError(
                code="EXECUTION_FAILED",
                message=str(e),
                details=error_details
            )
            
            logger.error(f"Job failed: {job.id} - {e}")
            logger.debug(f"Job failure traceback:\n{traceback.format_exc()}")
            
            # Notify callback
            if self.on_job_failed:
                self.on_job_failed(job, error)
            
            return JobResult(
                job_id=job.id,
                success=False,
                error=error
            )
        
        finally:
            # Clean up active futures
            with self._lock:
                self.active_futures.pop(job.id, None)