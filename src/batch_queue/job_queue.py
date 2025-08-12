"""
Job queue implementation for managing batch processing jobs.

This module provides the core queue functionality for storing, managing,
and processing STL jobs in a thread-safe manner.
"""

import threading
from collections import deque
from typing import Dict, List, Optional, Callable, Iterator
import uuid
from pathlib import Path

from utils.logger import setup_logger
from .job_types import QueueJob, JobState, JobType

logger = setup_logger("queue.job_queue")


class JobQueue:
    """
    Thread-safe job queue for managing batch processing operations.
    
    Provides functionality to add, remove, reorder, and manage jobs
    with proper thread synchronization and state management.
    """
    
    def __init__(self):
        self._jobs: deque[QueueJob] = deque()
        self._job_index: Dict[str, QueueJob] = {}
        self._lock = threading.RLock()  # Reentrant lock for nested operations
        self._observers: List[Callable[[str, QueueJob], None]] = []
        
        logger.info("JobQueue initialized")
    
    def add_observer(self, observer: Callable[[str, QueueJob], None]):
        """
        Add observer for job state changes.
        
        Args:
            observer: Callback function(event_type, job) for notifications
        """
        with self._lock:
            self._observers.append(observer)
    
    def remove_observer(self, observer: Callable[[str, QueueJob], None]):
        """Remove observer from notifications."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    def _notify_observers(self, event_type: str, job: QueueJob):
        """Notify all observers of job state changes."""
        # Create a copy of observers list to avoid modification during iteration
        observers_copy = self._observers.copy()
        for observer in observers_copy:
            try:
                observer(event_type, job)
            except Exception as e:
                logger.error(f"Error in observer notification: {e}")
    
    def add_job(self, job: QueueJob, position: Optional[int] = None) -> bool:
        """
        Add a job to the queue.
        
        Args:
            job: The job to add
            position: Optional position to insert at (None = end of queue)
            
        Returns:
            bool: True if job was added successfully
        """
        with self._lock:
            # Check for duplicate job ID
            if job.id in self._job_index:
                logger.warning(f"Job with ID {job.id} already exists in queue")
                return False
            
            # Validate job
            if not self._validate_job(job):
                logger.error(f"Job validation failed for {job.id}")
                return False
            
            try:
                # Add to queue at specified position
                if position is None:
                    self._jobs.append(job)
                else:
                    # Convert deque to list for insertion, then back to deque
                    jobs_list = list(self._jobs)
                    jobs_list.insert(position, job)
                    self._jobs = deque(jobs_list)
                
                # Update index
                self._job_index[job.id] = job
                
                logger.info(f"Added job {job.id} ({job.job_type.value}) for {job.stl_filename}")
                self._notify_observers("job_added", job)
                return True
                
            except Exception as e:
                logger.error(f"Error adding job {job.id}: {e}")
                return False
    
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a job from the queue.
        
        Args:
            job_id: ID of job to remove
            
        Returns:
            bool: True if job was removed successfully
        """
        with self._lock:
            if job_id not in self._job_index:
                logger.warning(f"Job {job_id} not found in queue")
                return False
            
            try:
                job = self._job_index[job_id]
                
                # Remove from deque
                self._jobs.remove(job)
                
                # Remove from index
                del self._job_index[job_id]
                
                logger.info(f"Removed job {job_id}")
                self._notify_observers("job_removed", job)
                return True
                
            except Exception as e:
                logger.error(f"Error removing job {job_id}: {e}")
                return False
    
    def get_job(self, job_id: str) -> Optional[QueueJob]:
        """Get a job by ID."""
        with self._lock:
            return self._job_index.get(job_id)
    
    def get_next_job(self) -> Optional[QueueJob]:
        """
        Get the next job ready for processing.
        
        Returns the first job with state PENDING, ordered by priority
        then by queue position.
        """
        with self._lock:
            # Filter pending jobs and sort by priority (descending) then queue order
            pending_jobs = [job for job in self._jobs if job.state == JobState.PENDING]
            
            if not pending_jobs:
                return None
            
            # Sort by priority (higher first), then by creation time (earlier first)
            pending_jobs.sort(key=lambda j: (-j.priority, j.created_at))
            return pending_jobs[0]
    
    def get_jobs_by_state(self, state: JobState) -> List[QueueJob]:
        """Get all jobs with a specific state."""
        with self._lock:
            return [job for job in self._jobs if job.state == state]
    
    def get_all_jobs(self) -> List[QueueJob]:
        """Get all jobs in queue order."""
        with self._lock:
            return list(self._jobs)
    
    def reorder_job(self, job_id: str, new_position: int) -> bool:
        """
        Move a job to a new position in the queue.
        
        Args:
            job_id: ID of job to move
            new_position: New position (0-based index)
            
        Returns:
            bool: True if job was moved successfully
        """
        with self._lock:
            if job_id not in self._job_index:
                logger.warning(f"Job {job_id} not found in queue")
                return False
            
            try:
                job = self._job_index[job_id]
                
                # Convert to list for easier manipulation
                jobs_list = list(self._jobs)
                
                # Remove from current position
                jobs_list.remove(job)
                
                # Insert at new position (clamp to valid range)
                new_position = max(0, min(new_position, len(jobs_list)))
                jobs_list.insert(new_position, job)
                
                # Convert back to deque
                self._jobs = deque(jobs_list)
                
                logger.info(f"Moved job {job_id} to position {new_position}")
                self._notify_observers("job_reordered", job)
                return True
                
            except Exception as e:
                logger.error(f"Error reordering job {job_id}: {e}")
                return False
    
    def update_job_state(self, job_id: str, new_state: JobState, 
                        progress: Optional[float] = None,
                        error_message: Optional[str] = None) -> bool:
        """
        Update job state and optionally progress/error message.
        
        Args:
            job_id: ID of job to update
            new_state: New state for the job
            progress: Optional progress percentage (0-100)
            error_message: Optional error message for failed jobs
            
        Returns:
            bool: True if job was updated successfully
        """
        with self._lock:
            if job_id not in self._job_index:
                logger.warning(f"Job {job_id} not found in queue")
                return False
            
            try:
                job = self._job_index[job_id]
                old_state = job.state
                
                job.state = new_state
                
                if progress is not None:
                    job.progress = max(0, min(100, progress))
                
                if error_message is not None:
                    job.error_message = error_message
                
                logger.debug(f"Updated job {job_id}: {old_state.value} -> {new_state.value}")
                self._notify_observers("job_updated", job)
                return True
                
            except Exception as e:
                logger.error(f"Error updating job {job_id}: {e}")
                return False
    
    def clear_completed(self) -> int:
        """
        Remove all completed and failed jobs from the queue.
        
        Returns:
            int: Number of jobs removed
        """
        with self._lock:
            completed_states = {JobState.COMPLETED, JobState.FAILED, JobState.SKIPPED, JobState.CANCELLED}
            jobs_to_remove = [job for job in self._jobs if job.state in completed_states]
            
            removed_count = 0
            for job in jobs_to_remove:
                if self.remove_job(job.id):
                    removed_count += 1
            
            logger.info(f"Cleared {removed_count} completed jobs")
            return removed_count
    
    def clear_all(self) -> int:
        """
        Remove all jobs from the queue.
        
        Returns:
            int: Number of jobs removed
        """
        with self._lock:
            job_count = len(self._jobs)
            self._jobs.clear()
            self._job_index.clear()
            
            logger.info(f"Cleared all {job_count} jobs from queue")
            return job_count
    
    def pause_all_jobs(self) -> int:
        """
        Pause all processing jobs.
        
        Returns:
            int: Number of jobs paused
        """
        with self._lock:
            paused_count = 0
            for job in self._jobs:
                if job.state == JobState.PROCESSING:
                    job.pause_processing()
                    paused_count += 1
                    self._notify_observers("job_updated", job)
            
            logger.info(f"Paused {paused_count} jobs")
            return paused_count
    
    def resume_all_jobs(self) -> int:
        """
        Resume all paused jobs.
        
        Returns:
            int: Number of jobs resumed
        """
        with self._lock:
            resumed_count = 0
            for job in self._jobs:
                if job.state == JobState.PAUSED:
                    job.resume_processing()
                    resumed_count += 1
                    self._notify_observers("job_updated", job)
            
            logger.info(f"Resumed {resumed_count} jobs")
            return resumed_count
    
    def cancel_all_pending(self) -> int:
        """
        Cancel all pending jobs.
        
        Returns:
            int: Number of jobs cancelled
        """
        with self._lock:
            cancelled_count = 0
            for job in self._jobs:
                if job.state == JobState.PENDING:
                    job.cancel_processing()
                    cancelled_count += 1
                    self._notify_observers("job_updated", job)
            
            logger.info(f"Cancelled {cancelled_count} pending jobs")
            return cancelled_count
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get statistics about the queue."""
        with self._lock:
            stats = {state.value: 0 for state in JobState}
            stats['total'] = len(self._jobs)
            
            for job in self._jobs:
                stats[job.state.value] += 1
            
            return stats
    
    def get_progress_summary(self) -> Dict[str, float]:
        """Get overall queue progress information."""
        with self._lock:
            if not self._jobs:
                return {'overall_progress': 0.0, 'completed_jobs': 0, 'total_jobs': 0}
            
            total_jobs = len(self._jobs)
            completed_jobs = len([j for j in self._jobs if j.state in {
                JobState.COMPLETED, JobState.FAILED, JobState.SKIPPED, JobState.CANCELLED
            }])
            
            # Calculate weighted progress including partial completion
            total_progress = sum(job.progress for job in self._jobs)
            overall_progress = total_progress / total_jobs if total_jobs > 0 else 0.0
            
            return {
                'overall_progress': overall_progress,
                'completed_jobs': completed_jobs,
                'total_jobs': total_jobs
            }
    
    def _validate_job(self, job: QueueJob) -> bool:
        """Validate job before adding to queue."""
        try:
            # Check required fields
            if not job.id:
                logger.error("Job ID is required")
                return False
            
            if not job.stl_path or not job.stl_path.exists():
                logger.error(f"STL file does not exist: {job.stl_path}")
                return False
            
            if not job.stl_path.suffix.lower() == '.stl':
                logger.error(f"File is not an STL file: {job.stl_path}")
                return False
            
            if not job.output_folder:
                logger.error("Output folder is required")
                return False
            
            # Validate job type specific options
            if job.job_type == JobType.RENDER and not job.render_options:
                logger.error("Render job requires render options")
                return False
            
            if job.job_type == JobType.VALIDATION and not job.validation_options:
                logger.error("Validation job requires validation options")
                return False
            
            if job.job_type == JobType.ANALYSIS and not job.analysis_options:
                logger.error("Analysis job requires analysis options")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating job: {e}")
            return False
    
    def __len__(self) -> int:
        """Return number of jobs in queue."""
        with self._lock:
            return len(self._jobs)
    
    def __contains__(self, job_id: str) -> bool:
        """Check if job ID exists in queue."""
        with self._lock:
            return job_id in self._job_index
    
    def __iter__(self) -> Iterator[QueueJob]:
        """Iterate over jobs in queue order."""
        with self._lock:
            # Return a copy to avoid modification during iteration
            return iter(list(self._jobs))


def create_job_from_stl(
    stl_path: Path,
    output_base: Path,
    job_type: JobType = JobType.COMPOSITE,
    render_options: Optional['RenderOptions'] = None,
    validation_options: Optional['ValidationOptions'] = None,
    analysis_options: Optional['AnalysisOptions'] = None
) -> QueueJob:
    """
    Create a job for an STL file with automatic output folder setup.
    
    Args:
        stl_path: Path to the STL file
        output_base: Base output directory
        job_type: Type of job to create
        render_options: Optional render configuration
        validation_options: Optional validation configuration
        analysis_options: Optional analysis configuration
        
    Returns:
        QueueJob: Configured job ready for queue
    """
    from .job_types import (
        create_render_job, create_validation_job, create_analysis_job, 
        create_composite_job, RenderOptions, ValidationOptions, AnalysisOptions
    )
    
    # Create output folder based on STL filename
    stl_basename = stl_path.stem
    output_folder = output_base / stl_basename
    
    # Generate unique job ID
    job_id = f"{job_type.value}_{uuid.uuid4().hex[:8]}_{stl_basename}"
    
    if job_type == JobType.RENDER:
        return create_render_job(stl_path, output_folder, render_options, job_id)
    elif job_type == JobType.VALIDATION:
        return create_validation_job(stl_path, output_folder, validation_options, job_id)
    elif job_type == JobType.ANALYSIS:
        return create_analysis_job(stl_path, output_folder, analysis_options, job_id)
    else:  # COMPOSITE
        return create_composite_job(
            stl_path, output_folder, render_options, 
            validation_options, analysis_options, job_id
        )