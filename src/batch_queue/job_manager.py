"""
Central job manager for orchestrating queue operations.

This module provides the main interface for managing batch processing jobs,
coordinating between the job queue, progress tracking, persistence, and history.
"""

import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Set
import time

from utils.logger import setup_logger
from .job_types import QueueJob, JobState, JobType, JobResults
from .job_queue import JobQueue, create_job_from_stl
from .progress_tracker import ProgressTracker
from .queue_persistence import QueueStateManager, QueueConfiguration
from .job_history import JobHistoryManager, calculate_stl_checksum
from .file_scanner import FileScanner, FileInfo

logger = setup_logger("queue.job_manager")


class QueueManagerError(Exception):
    """Custom exception for queue manager errors."""
    pass


class JobManager:
    """
    Central manager for coordinating all queue operations.
    
    Provides high-level interface for job management, coordinating between
    job queue, progress tracking, persistence, and history systems.
    """
    
    def __init__(self, 
                 state_file: Optional[Path] = None,
                 history_db: Optional[Path] = None,
                 auto_save: bool = True):
        """
        Initialize job manager.
        
        Args:
            state_file: Path to queue state file (None = default location)
            history_db: Path to history database (None = default location) 
            auto_save: Whether to automatically save state on changes
        """
        self._lock = threading.RLock()
        
        # Core components
        self.job_queue = JobQueue()
        self.progress_tracker = ProgressTracker()
        self.state_manager = QueueStateManager(state_file)
        self.history_manager = JobHistoryManager(history_db)
        self.file_scanner = FileScanner()
        self.config_manager = QueueConfiguration()
        
        # Settings
        self.auto_save = auto_save
        
        # Queue session management
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"
        self.is_running = False
        self.is_paused = False
        
        # Observers
        self._state_observers: List[Callable[[Dict[str, Any]], None]] = []
        self._job_observers: List[Callable[[str, QueueJob], None]] = []
        
        # Set up internal observers
        self.job_queue.add_observer(self._on_job_queue_change)
        self.progress_tracker.add_progress_observer(self._on_progress_update)
        
        # Create default templates
        self.config_manager.create_default_templates()
        
        logger.info(f"JobManager initialized (session: {self.session_id})")
    
    def add_state_observer(self, observer: Callable[[Dict[str, Any]], None]):
        """Add observer for queue state changes."""
        with self._lock:
            self._state_observers.append(observer)
    
    def remove_state_observer(self, observer: Callable[[Dict[str, Any]], None]):
        """Remove state observer."""
        with self._lock:
            if observer in self._state_observers:
                self._state_observers.remove(observer)
    
    def add_job_observer(self, observer: Callable[[str, QueueJob], None]):
        """Add observer for job changes."""
        with self._lock:
            self._job_observers.append(observer)
    
    def remove_job_observer(self, observer: Callable[[str, QueueJob], None]):
        """Remove job observer."""
        with self._lock:
            if observer in self._job_observers:
                self._job_observers.remove(observer)
    
    def add_jobs_from_files(self, 
                           stl_files: List[Path],
                           output_base: Path,
                           job_type: JobType = JobType.COMPOSITE,
                           render_options: Optional['RenderOptions'] = None,
                           validation_options: Optional['ValidationOptions'] = None,
                           analysis_options: Optional['AnalysisOptions'] = None) -> List[str]:
        """
        Add jobs from list of STL files.
        
        Args:
            stl_files: List of STL file paths
            output_base: Base output directory
            job_type: Type of jobs to create
            render_options: Render configuration
            validation_options: Validation configuration  
            analysis_options: Analysis configuration
            
        Returns:
            List of job IDs that were added
        """
        with self._lock:
            added_job_ids = []
            
            for stl_file in stl_files:
                try:
                    # Create job
                    job = create_job_from_stl(
                        stl_file, output_base, job_type,
                        render_options, validation_options, analysis_options
                    )
                    
                    # Add to queue
                    if self.job_queue.add_job(job):
                        added_job_ids.append(job.id)
                        logger.info(f"Added job {job.id} for {job.stl_filename}")
                    else:
                        logger.warning(f"Failed to add job for {stl_file}")
                        
                except Exception as e:
                    logger.error(f"Error creating job for {stl_file}: {e}")
                    continue
            
            if added_job_ids and self.auto_save:
                self._save_queue_state()
            
            logger.info(f"Added {len(added_job_ids)} jobs from {len(stl_files)} files")
            return added_job_ids
    
    def scan_and_add_jobs(self, 
                         paths: List[Path],
                         output_base: Path,
                         recursive: bool = True,
                         validate_files: bool = True,
                         job_type: JobType = JobType.COMPOSITE,
                         render_options: Optional['RenderOptions'] = None,
                         validation_options: Optional['ValidationOptions'] = None,
                         analysis_options: Optional['AnalysisOptions'] = None,
                         progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Dict[str, Any]:
        """
        Scan paths for STL files and add jobs for them.
        
        Args:
            paths: List of files and directories to scan
            output_base: Base output directory
            recursive: Whether to scan directories recursively
            validate_files: Whether to validate STL files during scan
            job_type: Type of jobs to create
            render_options: Render configuration
            validation_options: Validation configuration
            analysis_options: Analysis configuration
            progress_callback: Optional scan progress callback
            
        Returns:
            Dict with scan results and job IDs
        """
        with self._lock:
            logger.info(f"Scanning {len(paths)} paths for STL files")
            
            # Scan for STL files
            scan_result = self.file_scanner.scan_multiple_paths(
                paths, recursive, validate_files, progress_callback
            )
            
            # Filter to valid files only
            valid_files = [f.path for f in scan_result.valid_files]
            
            # Add jobs for valid files
            job_ids = []
            if valid_files:
                job_ids = self.add_jobs_from_files(
                    valid_files, output_base, job_type,
                    render_options, validation_options, analysis_options
                )
            
            return {
                'scan_result': scan_result,
                'valid_files': len(valid_files),
                'jobs_added': len(job_ids),
                'job_ids': job_ids,
                'errors': scan_result.errors
            }
    
    def start_processing(self) -> bool:
        """
        Start processing jobs in the queue.
        
        Returns:
            bool: True if processing started successfully
        """
        with self._lock:
            if self.is_running:
                logger.warning("Processing is already running")
                return False
            
            jobs = self.job_queue.get_all_jobs()
            if not jobs:
                logger.info("No jobs in queue to process")
                return False
            
            self.is_running = True
            self.is_paused = False
            
            # Start progress tracking
            pending_jobs = self.job_queue.get_jobs_by_state(JobState.PENDING)
            self.progress_tracker.start_queue_tracking(len(pending_jobs))
            
            logger.info(f"Started processing {len(pending_jobs)} jobs")
            self._notify_state_observers()
            
            return True
    
    def pause_processing(self) -> bool:
        """
        Pause processing of jobs.
        
        Returns:
            bool: True if processing was paused
        """
        with self._lock:
            if not self.is_running:
                logger.warning("Processing is not running")
                return False
            
            self.is_paused = True
            paused_count = self.job_queue.pause_all_jobs()
            
            logger.info(f"Paused processing ({paused_count} jobs paused)")
            self._notify_state_observers()
            
            return True
    
    def resume_processing(self) -> bool:
        """
        Resume paused processing.
        
        Returns:
            bool: True if processing was resumed
        """
        with self._lock:
            if not self.is_running or not self.is_paused:
                logger.warning("Processing is not paused")
                return False
            
            self.is_paused = False
            resumed_count = self.job_queue.resume_all_jobs()
            
            logger.info(f"Resumed processing ({resumed_count} jobs resumed)")
            self._notify_state_observers()
            
            return True
    
    def stop_processing(self) -> bool:
        """
        Stop processing jobs.
        
        Returns:
            bool: True if processing was stopped
        """
        with self._lock:
            if not self.is_running:
                logger.warning("Processing is not running")
                return False
            
            self.is_running = False
            self.is_paused = False
            
            # Cancel pending jobs
            cancelled_count = self.job_queue.cancel_all_pending()
            
            logger.info(f"Stopped processing ({cancelled_count} jobs cancelled)")
            self._notify_state_observers()
            
            if self.auto_save:
                self._save_queue_state()
            
            return True
    
    def get_next_job(self) -> Optional[QueueJob]:
        """
        Get next job for processing.
        
        Returns:
            Next job to process or None if no jobs available
        """
        if not self.is_running or self.is_paused:
            return None
        
        return self.job_queue.get_next_job()
    
    def complete_job(self, job_id: str, results: JobResults) -> bool:
        """
        Mark job as completed with results.
        
        Args:
            job_id: ID of completed job
            results: Job execution results
            
        Returns:
            bool: True if job was marked as completed
        """
        with self._lock:
            job = self.job_queue.get_job(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found")
                return False
            
            # Update job
            job.complete_processing(results)
            
            # Update progress tracking
            duration = job.duration or 0.0
            self.progress_tracker.complete_job(job_id, duration)
            
            # Record in history
            try:
                stl_checksum = calculate_stl_checksum(job.stl_path)
                self.history_manager.record_job_completion(
                    job, results, self.session_id, stl_checksum
                )
            except Exception as e:
                logger.warning(f"Failed to record job history for {job_id}: {e}")
            
            logger.info(f"Job {job_id} completed successfully")
            
            if self.auto_save:
                self._save_queue_state()
            
            return True
    
    def fail_job(self, job_id: str, error_message: str) -> bool:
        """
        Mark job as failed.
        
        Args:
            job_id: ID of failed job
            error_message: Error description
            
        Returns:
            bool: True if job was marked as failed
        """
        with self._lock:
            job = self.job_queue.get_job(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found")
                return False
            
            # Update job
            job.fail_processing(error_message)
            
            # Update progress tracking
            self.progress_tracker.fail_job(job_id, error_message)
            
            # Record in history with empty results
            try:
                empty_results = JobResults(
                    validation_passed=False,
                    errors=[error_message]
                )
                stl_checksum = calculate_stl_checksum(job.stl_path)
                self.history_manager.record_job_completion(
                    job, empty_results, self.session_id, stl_checksum
                )
            except Exception as e:
                logger.warning(f"Failed to record job failure for {job_id}: {e}")
            
            logger.error(f"Job {job_id} failed: {error_message}")
            
            if self.auto_save:
                self._save_queue_state()
            
            return True
    
    def skip_job(self, job_id: str, reason: str) -> bool:
        """
        Mark job as skipped.
        
        Args:
            job_id: ID of job to skip
            reason: Reason for skipping
            
        Returns:
            bool: True if job was marked as skipped
        """
        with self._lock:
            job = self.job_queue.get_job(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found")
                return False
            
            # Update job
            job.skip_processing(reason)
            
            # Update progress tracking
            self.progress_tracker.skip_job(job_id, reason)
            
            logger.info(f"Job {job_id} skipped: {reason}")
            
            if self.auto_save:
                self._save_queue_state()
            
            return True
    
    def remove_job(self, job_id: str) -> bool:
        """Remove job from queue."""
        with self._lock:
            success = self.job_queue.remove_job(job_id)
            
            if success and self.auto_save:
                self._save_queue_state()
            
            return success
    
    def reorder_job(self, job_id: str, new_position: int) -> bool:
        """Reorder job in queue."""
        with self._lock:
            success = self.job_queue.reorder_job(job_id, new_position)
            
            if success and self.auto_save:
                self._save_queue_state()
            
            return success
    
    def clear_completed_jobs(self) -> int:
        """Remove completed jobs from queue."""
        with self._lock:
            removed_count = self.job_queue.clear_completed()
            self.progress_tracker.clear_completed_jobs()
            
            if removed_count > 0 and self.auto_save:
                self._save_queue_state()
            
            return removed_count
    
    def clear_all_jobs(self) -> int:
        """Remove all jobs from queue."""
        with self._lock:
            removed_count = self.job_queue.clear_all()
            self.progress_tracker.reset_tracking()
            
            if removed_count > 0 and self.auto_save:
                self._save_queue_state()
            
            return removed_count
    
    def get_queue_summary(self) -> Dict[str, Any]:
        """Get comprehensive queue summary."""
        with self._lock:
            queue_stats = self.job_queue.get_queue_stats()
            progress_summary = self.job_queue.get_progress_summary()
            queue_progress = self.progress_tracker.get_queue_progress()
            
            return {
                'session_id': self.session_id,
                'is_running': self.is_running,
                'is_paused': self.is_paused,
                'queue_stats': queue_stats,
                'progress_summary': progress_summary,
                'queue_progress': queue_progress,
                'total_jobs': len(self.job_queue),
                'timestamp': datetime.now().isoformat()
            }
    
    def save_queue_state(self) -> bool:
        """Manually save queue state."""
        with self._lock:
            return self._save_queue_state()
    
    def load_queue_state(self) -> bool:
        """Load queue state from file."""
        with self._lock:
            try:
                state_data = self.state_manager.load_queue_state()
                if not state_data:
                    logger.info("No saved queue state found")
                    return False
                
                # Load jobs
                jobs = self.state_manager.load_jobs_from_state(state_data)
                
                # Clear current queue and add loaded jobs
                self.job_queue.clear_all()
                
                for job in jobs:
                    self.job_queue.add_job(job)
                
                # Restore session info from metadata
                metadata = state_data.get('metadata', {})
                if 'session_id' in metadata:
                    self.session_id = metadata['session_id']
                
                logger.info(f"Loaded {len(jobs)} jobs from saved state")
                return True
                
            except Exception as e:
                logger.error(f"Failed to load queue state: {e}")
                return False
    
    def export_queue_config(self, config_name: str) -> bool:
        """Export current queue configuration as template."""
        with self._lock:
            try:
                jobs = self.job_queue.get_all_jobs()
                if not jobs:
                    logger.warning("No jobs in queue to export config from")
                    return False
                
                # Use first job as template
                template_job = jobs[0]
                
                template_data = {
                    'name': config_name,
                    'description': f'Configuration exported on {datetime.now().isoformat()}',
                    'job_type': template_job.job_type.value,
                    'render_options': template_job.render_options.to_dict() if template_job.render_options else None,
                    'validation_options': template_job.validation_options.to_dict() if template_job.validation_options else None,
                    'analysis_options': template_job.analysis_options.to_dict() if template_job.analysis_options else None
                }
                
                return self.config_manager.save_template(config_name, template_data)
                
            except Exception as e:
                logger.error(f"Failed to export queue config: {e}")
                return False
    
    def _save_queue_state(self) -> bool:
        """Internal method to save queue state."""
        try:
            jobs = self.job_queue.get_all_jobs()
            metadata = {
                'session_id': self.session_id,
                'is_running': self.is_running,
                'is_paused': self.is_paused,
                'saved_at': datetime.now().isoformat()
            }
            
            return self.state_manager.save_queue_state(jobs, metadata)
            
        except Exception as e:
            logger.error(f"Failed to save queue state: {e}")
            return False
    
    def _on_job_queue_change(self, event_type: str, job: QueueJob):
        """Handle job queue change events."""
        # Notify job observers
        observers_copy = self._job_observers.copy()
        for observer in observers_copy:
            try:
                observer(event_type, job)
            except Exception as e:
                logger.error(f"Error in job observer: {e}")
        
        # Auto-save if enabled
        if self.auto_save and event_type in ['job_added', 'job_removed', 'job_updated']:
            self._save_queue_state()
        
        # Notify state observers
        self._notify_state_observers()
    
    def _on_progress_update(self, queue_progress):
        """Handle progress update events."""
        self._notify_state_observers()
    
    def _notify_state_observers(self):
        """Notify state observers of changes."""
        summary = self.get_queue_summary()
        observers_copy = self._state_observers.copy()
        
        for observer in observers_copy:
            try:
                observer(summary)
            except Exception as e:
                logger.error(f"Error in state observer: {e}")


# Convenience functions
def create_job_manager(state_file: Optional[Path] = None, 
                      history_db: Optional[Path] = None,
                      auto_save: bool = True) -> JobManager:
    """Create job manager instance."""
    return JobManager(state_file, history_db, auto_save)


def get_default_job_manager() -> JobManager:
    """Get default job manager with standard configuration."""
    return JobManager(auto_save=True)