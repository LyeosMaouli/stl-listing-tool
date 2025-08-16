"""
Enhanced job manager with integrated execution engine.
Combines the queue management with job execution capabilities.
"""

import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set
from concurrent.futures import Future

from ..utils.logger import setup_logger
from .job_types_v2 import Job, JobStatus, JobResult, JobError
from .job_executor import JobExecutionEngine
from .job_handlers import RenderJobHandler, ValidationJobHandler, AnalysisJobHandler
from .error_handler import ErrorHandler
from .recovery_manager import SessionRecoveryManager
from .progress_tracker import ProgressTracker
from .file_scanner import FileScanner

logger = setup_logger("queue.enhanced_job_manager")


class EnhancedJobManager:
    """
    Enhanced job manager with integrated execution engine.
    
    Combines queue management, job execution, error handling, and recovery
    into a single coordinated system.
    """
    
    def __init__(self, 
                 max_workers: int = 2,
                 state_dir: Optional[Path] = None,
                 auto_save: bool = True,
                 enable_recovery: bool = True):
        """
        Initialize enhanced job manager.
        
        Args:
            max_workers: Maximum number of concurrent workers
            state_dir: Directory for state files (None = default location)
            auto_save: Whether to automatically save state on changes
            enable_recovery: Whether to enable session recovery
        """
        self._lock = threading.RLock()
        
        # Core components
        self.progress_tracker = ProgressTracker()
        self.execution_engine = JobExecutionEngine(max_workers, self.progress_tracker)
        self.error_handler = ErrorHandler()
        self.file_scanner = FileScanner()
        
        # Job storage
        self._jobs: Dict[str, Job] = {}
        self._pending_jobs: List[str] = []  # Job IDs in execution order
        self._running_jobs: Set[str] = set()
        self._completed_jobs: Dict[str, Job] = {}
        self._failed_jobs: Dict[str, Job] = {}
        
        # Job futures for tracking execution
        self._job_futures: Dict[str, Future] = {}
        
        # State management - use user data directory for state if no state_dir provided
        if state_dir:
            self.state_dir = Path(state_dir)
        else:
            import tempfile
            import os
            
            if os.name == 'nt':  # Windows
                self.state_dir = Path.home() / "AppData" / "Local" / "stl_listing_tool" / "queue_state"
            else:  # Unix/Linux/Mac
                self.state_dir = Path.home() / ".local" / "share" / "stl_listing_tool" / "queue_state"
            
            # Fallback to temp directory if home directory fails
            try:
                self.state_dir.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError):
                self.state_dir = Path(tempfile.gettempdir()) / "stl_listing_tool" / "queue_state"
        
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.auto_save = auto_save
        
        # Recovery management
        self.recovery_manager = None
        if enable_recovery:
            recovery_dir = self.state_dir / "recovery"
            self.recovery_manager = SessionRecoveryManager(
                recovery_dir, progress_tracker=self.progress_tracker
            )
        
        # Session management
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"
        self.is_running = False
        self.is_paused = False
        
        # Observer patterns
        self._state_observers: List[Callable[[Dict[str, Any]], None]] = []
        self._job_observers: List[Callable[[str, Job], None]] = []
        
        # Setup job executors
        self._setup_executors()
        
        # Setup error handler callbacks
        self._setup_error_callbacks()
        
        # Setup execution engine callbacks
        self._setup_execution_callbacks()
        
        # Start recovery session if enabled
        if self.recovery_manager:
            self.recovery_manager.start_session(self.session_id)
        
        logger.info(f"EnhancedJobManager initialized (session: {self.session_id})")
    
    def _setup_executors(self):
        """Setup job executors for different job types."""
        self.execution_engine.register_executor("render", RenderJobHandler())
        self.execution_engine.register_executor("validate", ValidationJobHandler())
        self.execution_engine.register_executor("analyze", AnalysisJobHandler())
    
    def _setup_error_callbacks(self):
        """Setup error handler callbacks."""
        def on_error(job: Job, error: JobError, pattern):
            logger.error(f"Job {job.id} error ({pattern.severity.value}): {error.message}")
            self._notify_job_observers("job_error", job)
        
        def on_recovery_applied(job: Job, strategy: str, result: Dict[str, Any]):
            logger.info(f"Applied recovery strategy '{strategy}' to job {job.id}: {result.get('message', 'No message')}")
            self._notify_job_observers("job_recovery", job)
        
        self.error_handler.on_error = on_error
        self.error_handler.on_recovery_applied = on_recovery_applied
    
    def _setup_execution_callbacks(self):
        """Setup execution engine callbacks."""
        def on_job_started(job: Job):
            with self._lock:
                job.status = JobStatus.RUNNING
                self._running_jobs.add(job.id)
                # Job already removed from _pending_jobs in _process_next_jobs
            
            # Register job with progress tracker
            self.progress_tracker.start_job_tracking_v2(job)
            
            logger.info(f"Job started: {job.id}")
            self._notify_job_observers("job_started", job)
            self._checkpoint_if_needed()
        
        def on_job_completed(job: Job, result: JobResult):
            with self._lock:
                job.status = JobStatus.COMPLETED
                self._running_jobs.discard(job.id)
                self._completed_jobs[job.id] = job
            
            # Notify progress tracker of completion
            if result and result.execution_time:
                self.progress_tracker.complete_job(job.id, result.execution_time)
            else:
                self.progress_tracker.complete_job(job.id, 0.0)
            
            self.error_handler.handle_success(job)
            logger.info(f"Job completed: {job.id}")
            self._notify_job_observers("job_completed", job)
            self._checkpoint_if_needed()
            
            # Continue processing next jobs
            self._process_next_jobs()
        
        def on_job_failed(job: Job, error: JobError):
            # Handle error and determine action
            error_result = self.error_handler.handle_error(job, error)
            
            with self._lock:
                if error_result["action"] == "retry":
                    # Schedule retry
                    delay = error_result.get("delay", 0)
                    if delay > 0:
                        # Schedule retry with delay
                        timer = threading.Timer(delay, self._retry_job, args=(job.id,))
                        timer.start()
                    else:
                        # Retry immediately
                        self._retry_job(job.id)
                else:
                    # Job failed permanently
                    job.status = JobStatus.FAILED
                    self._running_jobs.discard(job.id)
                    self._failed_jobs[job.id] = job
                    
                    # Notify progress tracker of failure
                    self.progress_tracker.fail_job(job.id, error.message)
                    
                    logger.error(f"Job failed permanently: {job.id}")
                    self._notify_job_observers("job_failed", job)
                    self._checkpoint_if_needed()
                    
                    # Continue processing next jobs
                    self._process_next_jobs()
        
        def on_job_progress(job: Job, progress: float, message: str):
            # Forward progress to progress tracker
            self.progress_tracker.update_job_progress(job.id, progress, message)
            self._notify_job_observers("job_progress", job)
        
        self.execution_engine.on_job_started = on_job_started
        self.execution_engine.on_job_completed = on_job_completed
        self.execution_engine.on_job_failed = on_job_failed
        self.execution_engine.on_job_progress = on_job_progress
    
    def add_observer(self, observer_type: str, observer: Callable):
        """Add observer for state or job changes."""
        with self._lock:
            if observer_type == "state":
                self._state_observers.append(observer)
            elif observer_type == "job":
                self._job_observers.append(observer)
    
    def remove_observer(self, observer_type: str, observer: Callable):
        """Remove observer."""
        with self._lock:
            if observer_type == "state":
                if observer in self._state_observers:
                    self._state_observers.remove(observer)
            elif observer_type == "job":
                if observer in self._job_observers:
                    self._job_observers.remove(observer)
    
    def add_job(self, job: Job) -> bool:
        """Add a job to the queue."""
        with self._lock:
            if job.id in self._jobs:
                logger.warning(f"Job {job.id} already exists")
                return False
            
            self._jobs[job.id] = job
            self._pending_jobs.append(job.id)
            job.status = JobStatus.PENDING
            
            logger.info(f"Added job {job.id} to queue")
            self._notify_job_observers("job_added", job)
            self._checkpoint_if_needed()
            
            return True
    
    def add_jobs_from_files(self, 
                           stl_files: List[Path],
                           output_dir: Path,
                           job_type: str = "render",
                           options: Optional[Dict[str, Any]] = None) -> List[str]:
        """Add jobs from list of STL files."""
        options = options or {}
        added_job_ids = []
        
        for stl_file in stl_files:
            try:
                # Generate output file path
                output_file = output_dir / f"{stl_file.stem}_render.png"
                
                # Create job
                job = Job(
                    job_type=job_type,
                    input_file=str(stl_file),
                    output_file=str(output_file),
                    options=options.copy()
                )
                
                if self.add_job(job):
                    added_job_ids.append(job.id)
                    
            except Exception as e:
                logger.error(f"Error creating job for {stl_file}: {e}")
        
        logger.info(f"Added {len(added_job_ids)} jobs from {len(stl_files)} files")
        return added_job_ids
    
    def scan_and_add_jobs(self,
                         paths: List[Path],
                         output_dir: Path,
                         recursive: bool = True,
                         job_type: str = "render",
                         options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Scan paths for STL files and add jobs."""
        logger.info(f"Scanning {len(paths)} paths for STL files")
        
        # Scan for files
        all_files = []
        for path in paths:
            if path.is_file() and path.suffix.lower() == '.stl':
                all_files.append(path)
            elif path.is_dir():
                pattern = "**/*.stl" if recursive else "*.stl"
                all_files.extend(path.glob(pattern))
        
        # Add jobs
        job_ids = self.add_jobs_from_files(all_files, output_dir, job_type, options)
        
        return {
            'files_found': len(all_files),
            'jobs_added': len(job_ids),
            'job_ids': job_ids
        }
    
    def start_processing(self) -> bool:
        """Start processing jobs in the queue."""
        with self._lock:
            if self.is_running:
                logger.warning("Processing is already running")
                return False
            
            if not self._pending_jobs:
                logger.info("No jobs in queue to process")
                return False
            
            self.is_running = True
            self.is_paused = False
            
            # Start execution engine
            self.execution_engine.start()
            
            # Start processing
            self._process_next_jobs()
            
            logger.info(f"Started processing {len(self._pending_jobs)} jobs")
            self._notify_state_observers()
            
            return True
    
    def pause_processing(self) -> bool:
        """Pause job processing."""
        with self._lock:
            if not self.is_running:
                logger.warning("Processing is not running")
                return False
            
            self.is_paused = True
            self.execution_engine.pause()
            
            logger.info("Processing paused")
            self._notify_state_observers()
            
            return True
    
    def resume_processing(self) -> bool:
        """Resume job processing."""
        with self._lock:
            if not self.is_running or not self.is_paused:
                logger.warning("Processing is not paused")
                return False
            
            self.is_paused = False
            self.execution_engine.resume()
            
            # Resume processing
            self._process_next_jobs()
            
            logger.info("Processing resumed")
            self._notify_state_observers()
            
            return True
    
    def stop_processing(self) -> bool:
        """Stop job processing."""
        with self._lock:
            if not self.is_running:
                logger.warning("Processing is not running")
                return False
            
            self.is_running = False
            self.is_paused = False
            
            # Cancel running jobs
            for job_id in list(self._running_jobs):
                self.execution_engine.cancel_job(job_id)
                job = self._jobs.get(job_id)
                if job:
                    job.status = JobStatus.CANCELLED
                    self._running_jobs.discard(job_id)
                    self._pending_jobs.append(job_id)  # Move back to pending
            
            logger.info("Processing stopped")
            self._notify_state_observers()
            self._checkpoint_if_needed()
            
            return True
    
    def shutdown(self, wait: bool = True):
        """Shutdown the job manager."""
        logger.info("Shutting down enhanced job manager...")
        
        # Stop processing if running
        if self.is_running:
            self.stop_processing()
        
        # Shutdown execution engine
        self.execution_engine.shutdown(wait)
        
        # End recovery session
        if self.recovery_manager:
            self.recovery_manager.end_session()
        
        logger.info("Enhanced job manager shutdown complete")
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def remove_job(self, job_id: str) -> bool:
        """Remove job from queue."""
        with self._lock:
            if job_id not in self._jobs:
                return False
            
            # Cancel if running
            if job_id in self._running_jobs:
                self.execution_engine.cancel_job(job_id)
                self._running_jobs.discard(job_id)
            
            # Remove from all collections
            self._jobs.pop(job_id, None)
            if job_id in self._pending_jobs:
                self._pending_jobs.remove(job_id)
            self._completed_jobs.pop(job_id, None)
            self._failed_jobs.pop(job_id, None)
            self._job_futures.pop(job_id, None)
            
            logger.info(f"Removed job {job_id}")
            self._checkpoint_if_needed()
            
            return True
    
    def clear_completed_jobs(self) -> int:
        """Remove completed jobs."""
        with self._lock:
            count = len(self._completed_jobs)
            for job_id in list(self._completed_jobs.keys()):
                self._jobs.pop(job_id, None)
            self._completed_jobs.clear()
            
            if count > 0:
                self._checkpoint_if_needed()
            
            return count
    
    def clear_failed_jobs(self) -> int:
        """Remove failed jobs."""
        with self._lock:
            count = len(self._failed_jobs)
            for job_id in list(self._failed_jobs.keys()):
                self._jobs.pop(job_id, None)
            self._failed_jobs.clear()
            
            if count > 0:
                self._checkpoint_if_needed()
            
            return count
    
    def get_queue_summary(self) -> Dict[str, Any]:
        """Get comprehensive queue summary."""
        with self._lock:
            return {
                'session_id': self.session_id,
                'is_running': self.is_running,
                'is_paused': self.is_paused,
                'total_jobs': len(self._jobs),
                'pending_jobs': len(self._pending_jobs),
                'running_jobs': len(self._running_jobs),
                'completed_jobs': len(self._completed_jobs),
                'failed_jobs': len(self._failed_jobs),
                'overall_progress': self.progress_tracker.get_queue_progress(),
                'error_stats': self.error_handler.get_error_statistics(),
                'timestamp': datetime.now().isoformat()
            }
    
    def can_recover(self) -> bool:
        """Check if recovery data is available."""
        return self.recovery_manager and self.recovery_manager.can_recover()
    
    def get_recovery_info(self) -> Optional[Dict[str, Any]]:
        """Get recovery information."""
        if self.recovery_manager:
            return self.recovery_manager.get_recovery_info()
        return None
    
    def recover_session(self) -> bool:
        """Recover from previous session."""
        if not self.recovery_manager:
            return False
        
        # Set queue reference for recovery
        self.recovery_manager.job_queue = self
        
        success = self.recovery_manager.recover_session()
        if success:
            self._notify_state_observers()
        
        return success
    
    def _process_next_jobs(self):
        """Process next pending jobs if slots available."""
        if self.is_paused or not self.is_running:
            return
        
        with self._lock:
            # Calculate available slots
            max_concurrent = self.execution_engine.max_workers
            available_slots = max_concurrent - len(self._running_jobs)
            
            if available_slots <= 0:
                return
            
            # Submit jobs up to available slots
            jobs_to_submit = min(available_slots, len(self._pending_jobs))
            
            for _ in range(jobs_to_submit):
                if not self._pending_jobs:
                    break
                
                job_id = self._pending_jobs.pop(0)  # Remove immediately to prevent duplicates
                job = self._jobs.get(job_id)
                
                if job:
                    # Check if job is already running to avoid race conditions
                    if job_id in self._running_jobs:
                        logger.warning(f"Job {job_id} already running, skipping duplicate submission")
                        continue
                    
                    future = self.execution_engine.submit_job(job)
                    self._job_futures[job_id] = future
                    logger.debug(f"Submitted job {job_id} for execution")
    
    def _retry_job(self, job_id: str):
        """Retry a failed job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            
            # Move job back to pending
            job.status = JobStatus.PENDING
            if job_id not in self._pending_jobs:
                self._pending_jobs.insert(0, job_id)  # Retry with priority
            
            # Remove from failed jobs
            self._failed_jobs.pop(job_id, None)
            
            logger.info(f"Retrying job {job_id}")
            
            # Try to process if not paused
            if self.is_running and not self.is_paused:
                self._process_next_jobs()
    
    def _checkpoint_if_needed(self):
        """Create recovery checkpoint if enabled."""
        if self.recovery_manager and self.auto_save:
            self.recovery_manager.checkpoint()
    
    def _notify_state_observers(self):
        """Notify state observers."""
        summary = self.get_queue_summary()
        for observer in self._state_observers.copy():
            try:
                observer(summary)
            except Exception as e:
                logger.error(f"Error in state observer: {e}")
    
    def _notify_job_observers(self, event_type: str, job: Job):
        """Notify job observers."""
        for observer in self._job_observers.copy():
            try:
                observer(event_type, job)
            except Exception as e:
                logger.error(f"Error in job observer: {e}")
    
    # Queue interface methods for recovery manager
    def get_all_jobs(self) -> List[Job]:
        """Get all jobs (for recovery interface)."""
        return list(self._jobs.values())
    
    def clear(self):
        """Clear all jobs (for recovery interface)."""
        with self._lock:
            self._jobs.clear()
            self._pending_jobs.clear()
            self._running_jobs.clear()
            self._completed_jobs.clear()
            self._failed_jobs.clear()
            self._job_futures.clear()