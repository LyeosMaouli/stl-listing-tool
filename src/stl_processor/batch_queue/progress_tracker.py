"""
Progress tracking system for queue operations.

This module provides comprehensive progress tracking for batch processing jobs,
including individual job progress, overall queue progress, and time estimation.
"""

import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from collections import deque
from statistics import mean

from ..utils.logger import setup_logger
from .job_types import QueueJob, JobState

logger = setup_logger("queue.progress_tracker")


@dataclass
class JobProgress:
    """Progress information for a single job."""
    job_id: str
    job_type: str
    stl_filename: str
    state: JobState
    progress: float  # 0-100
    
    # Timing information
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    estimated_duration: Optional[float] = None
    elapsed_time: Optional[float] = None
    
    # Progress details
    current_step: Optional[str] = None
    steps_completed: int = 0
    total_steps: int = 0
    
    # Performance metrics
    processing_speed: Optional[float] = None  # Progress per second
    
    @property
    def time_remaining(self) -> Optional[float]:
        """Calculate estimated time remaining in seconds."""
        if not self.started_at or self.progress <= 0:
            return None
        
        elapsed = (datetime.now() - self.started_at).total_seconds()
        if self.progress >= 100:
            return 0.0
        
        # Estimate based on current progress rate
        progress_rate = self.progress / elapsed if elapsed > 0 else 0
        if progress_rate <= 0:
            return None
        
        remaining_progress = 100 - self.progress
        return remaining_progress / progress_rate
    
    @property
    def is_active(self) -> bool:
        """Check if job is actively processing."""
        return self.state in {JobState.PROCESSING, JobState.VALIDATING}


@dataclass
class QueueProgress:
    """Overall progress information for the entire queue."""
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    active_jobs: int
    pending_jobs: int
    
    overall_progress: float  # 0-100 weighted progress
    
    # Timing estimates
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    estimated_total_duration: Optional[float] = None
    elapsed_time: Optional[float] = None
    
    # Performance metrics
    jobs_per_hour: Optional[float] = None
    average_job_duration: Optional[float] = None
    
    # Current activity
    current_jobs: List[JobProgress] = field(default_factory=list)
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage based on finished jobs."""
        if self.total_jobs == 0:
            return 100.0
        return (self.completed_jobs / self.total_jobs) * 100
    
    @property
    def time_remaining(self) -> Optional[float]:
        """Calculate estimated time remaining for entire queue."""
        if not self.started_at or self.overall_progress >= 100:
            return 0.0
        
        elapsed = (datetime.now() - self.started_at).total_seconds()
        if elapsed <= 0 or self.overall_progress <= 0:
            return None
        
        # Estimate based on overall progress rate
        progress_rate = self.overall_progress / elapsed
        if progress_rate <= 0:
            return None
        
        remaining_progress = 100 - self.overall_progress
        return remaining_progress / progress_rate


class ProgressTracker:
    """
    Tracks progress for queue operations with time estimation and reporting.
    
    Provides real-time progress updates, time estimates, and performance metrics
    for individual jobs and the overall queue.
    """
    
    def __init__(self, max_history: int = 100):
        self._job_progress: Dict[str, JobProgress] = {}
        self._queue_progress: Optional[QueueProgress] = None
        self._lock = threading.RLock()
        
        # Performance tracking
        self._job_durations: deque = deque(maxlen=max_history)
        self._completion_times: deque = deque(maxlen=max_history)
        
        # Observers for progress updates
        self._observers: List[Callable[[QueueProgress], None]] = []
        self._job_observers: List[Callable[[JobProgress], None]] = []
        
        # Queue timing
        self._queue_start_time: Optional[datetime] = None
        self._last_update_time: Optional[datetime] = None
        
        logger.info("ProgressTracker initialized")
    
    def add_progress_observer(self, observer: Callable[[QueueProgress], None]):
        """Add observer for queue progress updates."""
        with self._lock:
            self._observers.append(observer)
    
    def remove_progress_observer(self, observer: Callable[[QueueProgress], None]):
        """Remove queue progress observer."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    def add_job_observer(self, observer: Callable[[JobProgress], None]):
        """Add observer for individual job progress updates."""
        with self._lock:
            self._job_observers.append(observer)
    
    def remove_job_observer(self, observer: Callable[[JobProgress], None]):
        """Remove job progress observer."""
        with self._lock:
            if observer in self._job_observers:
                self._job_observers.remove(observer)
    
    def start_queue_tracking(self, total_jobs: int):
        """Start tracking progress for a queue of jobs."""
        with self._lock:
            self._queue_start_time = datetime.now()
            self._last_update_time = self._queue_start_time
            
            self._queue_progress = QueueProgress(
                total_jobs=total_jobs,
                completed_jobs=0,
                failed_jobs=0,
                active_jobs=0,
                pending_jobs=total_jobs,
                overall_progress=0.0,
                started_at=self._queue_start_time
            )
            
            logger.info(f"Started tracking queue with {total_jobs} jobs")
            self._notify_queue_observers()
    
    def start_job_tracking(self, job: QueueJob):
        """Start tracking progress for a specific job."""
        with self._lock:
            job_progress = JobProgress(
                job_id=job.id,
                job_type=job.job_type.value,
                stl_filename=job.stl_filename,
                state=job.state,
                progress=0.0,
                started_at=datetime.now(),
                total_steps=self._estimate_job_steps(job)
            )
            
            self._job_progress[job.id] = job_progress
            
            logger.debug(f"Started tracking job {job.id}")
            self._notify_job_observers(job_progress)
            self._update_queue_progress()
    
    def update_job_progress(
        self,
        job_id: str,
        progress: float,
        current_step: Optional[str] = None,
        steps_completed: Optional[int] = None
    ):
        """
        Update progress for a specific job.
        
        Args:
            job_id: ID of the job to update
            progress: Progress percentage (0-100)
            current_step: Optional description of current step
            steps_completed: Optional number of steps completed
        """
        with self._lock:
            if job_id not in self._job_progress:
                logger.warning(f"Job {job_id} not found in progress tracker")
                return
            
            job_progress = self._job_progress[job_id]
            old_progress = job_progress.progress
            
            # Update progress values
            job_progress.progress = max(0, min(100, progress))
            if current_step:
                job_progress.current_step = current_step
            if steps_completed is not None:
                job_progress.steps_completed = steps_completed
            
            # Update timing estimates
            if job_progress.started_at:
                elapsed = (datetime.now() - job_progress.started_at).total_seconds()
                job_progress.elapsed_time = elapsed
                
                # Calculate processing speed (progress per second)
                if elapsed > 0:
                    job_progress.processing_speed = job_progress.progress / elapsed
            
            # Update estimated duration and completion time
            time_remaining = job_progress.time_remaining
            if time_remaining is not None:
                job_progress.estimated_completion = datetime.now() + timedelta(seconds=time_remaining)
                if job_progress.started_at:
                    job_progress.estimated_duration = job_progress.elapsed_time + time_remaining
            
            # Log significant progress updates
            if progress >= 100 or progress - old_progress >= 10:
                logger.debug(f"Job {job_id} progress: {progress:.1f}% ({current_step or 'processing'})")
            
            self._notify_job_observers(job_progress)
            self._update_queue_progress()
    
    def complete_job(self, job_id: str, duration: float):
        """Mark a job as completed and record its duration."""
        with self._lock:
            if job_id in self._job_progress:
                job_progress = self._job_progress[job_id]
                job_progress.progress = 100.0
                job_progress.state = JobState.COMPLETED
                job_progress.current_step = "Completed"
                
                # Record completion metrics
                self._job_durations.append(duration)
                self._completion_times.append(datetime.now())
                
                logger.info(f"Job {job_id} completed in {duration:.1f}s")
                
                self._notify_job_observers(job_progress)
                self._update_queue_progress()
    
    def fail_job(self, job_id: str, error_message: str):
        """Mark a job as failed."""
        with self._lock:
            if job_id in self._job_progress:
                job_progress = self._job_progress[job_id]
                job_progress.state = JobState.FAILED
                job_progress.current_step = f"Failed: {error_message}"
                
                logger.warning(f"Job {job_id} failed: {error_message}")
                
                self._notify_job_observers(job_progress)
                self._update_queue_progress()
    
    def skip_job(self, job_id: str, reason: str):
        """Mark a job as skipped."""
        with self._lock:
            if job_id in self._job_progress:
                job_progress = self._job_progress[job_id]
                job_progress.state = JobState.SKIPPED
                job_progress.current_step = f"Skipped: {reason}"
                job_progress.progress = 100.0  # Consider skipped as "completed"
                
                logger.info(f"Job {job_id} skipped: {reason}")
                
                self._notify_job_observers(job_progress)
                self._update_queue_progress()
    
    def cancel_job(self, job_id: str):
        """Mark a job as cancelled."""
        with self._lock:
            if job_id in self._job_progress:
                job_progress = self._job_progress[job_id]
                job_progress.state = JobState.CANCELLED
                job_progress.current_step = "Cancelled"
                
                logger.info(f"Job {job_id} cancelled")
                
                self._notify_job_observers(job_progress)
                self._update_queue_progress()
    
    def get_job_progress(self, job_id: str) -> Optional[JobProgress]:
        """Get progress information for a specific job."""
        with self._lock:
            return self._job_progress.get(job_id)
    
    def get_queue_progress(self) -> Optional[QueueProgress]:
        """Get overall queue progress information."""
        with self._lock:
            return self._queue_progress
    
    def get_active_jobs(self) -> List[JobProgress]:
        """Get list of currently active jobs."""
        with self._lock:
            return [jp for jp in self._job_progress.values() if jp.is_active]
    
    @property
    def job_progress(self) -> Dict[str, Any]:
        """Get job progress dictionary for recovery/serialization."""
        with self._lock:
            # Convert JobProgress objects to serializable dictionaries
            serializable_progress = {}
            for job_id, progress in self._job_progress.items():
                try:
                    serializable_progress[job_id] = {
                        'job_id': progress.job_id,
                        'job_type': progress.job_type,
                        'stl_filename': progress.stl_filename,
                        'state': progress.state.value if progress.state else 'pending',
                        'progress': progress.progress,
                        'current_step': progress.current_step,
                        'steps_completed': progress.steps_completed,
                        'total_steps': progress.total_steps,
                        'started_at': progress.started_at.isoformat() if progress.started_at else None,
                        'elapsed_time': progress.elapsed_time,
                        'processing_speed': progress.processing_speed,
                    }
                except Exception as e:
                    logger.warning(f"Could not serialize progress for job {job_id}: {e}")
                    # Provide minimal fallback data
                    serializable_progress[job_id] = {
                        'job_id': job_id,
                        'progress': 0.0,
                        'state': 'pending'
                    }
            return serializable_progress
    
    @property 
    def job_messages(self) -> Dict[str, str]:
        """Get job messages dictionary for recovery/serialization."""
        with self._lock:
            # Extract current step messages from job progress
            return {job_id: progress.current_step or "" 
                    for job_id, progress in self._job_progress.items()}
    
    def get_overall_progress(self) -> float:
        """Get overall progress percentage for recovery/serialization."""
        with self._lock:
            if self._queue_progress:
                return self._queue_progress.overall_progress
            return 0.0
    
    def reset_job_progress(self, job_id: str):
        """Reset progress for a specific job (used by recovery manager)."""
        with self._lock:
            if job_id in self._job_progress:
                job_progress = self._job_progress[job_id]
                job_progress.progress = 0.0
                job_progress.state = JobState.PENDING
                job_progress.current_step = None
                job_progress.started_at = None
                job_progress.elapsed_time = None
                logger.info(f"Reset progress for job {job_id}")
                self._notify_job_observers(job_progress)
                self._update_queue_progress()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        with self._lock:
            stats = {
                'total_jobs_tracked': len(self._job_progress),
                'jobs_in_history': len(self._job_durations),
                'average_job_duration': None,
                'median_job_duration': None,
                'jobs_per_hour': None,
                'queue_started_at': self._queue_start_time,
                'queue_elapsed_time': None
            }
            
            if self._job_durations:
                stats['average_job_duration'] = mean(self._job_durations)
                sorted_durations = sorted(self._job_durations)
                n = len(sorted_durations)
                stats['median_job_duration'] = sorted_durations[n // 2]
            
            if self._queue_start_time:
                elapsed_hours = (datetime.now() - self._queue_start_time).total_seconds() / 3600
                stats['queue_elapsed_time'] = elapsed_hours
                
                if elapsed_hours > 0:
                    completed_jobs = len([jp for jp in self._job_progress.values() 
                                        if jp.state in {JobState.COMPLETED, JobState.SKIPPED}])
                    stats['jobs_per_hour'] = completed_jobs / elapsed_hours
            
            return stats
    
    def clear_completed_jobs(self):
        """Remove completed jobs from tracking to save memory."""
        with self._lock:
            completed_states = {JobState.COMPLETED, JobState.FAILED, JobState.SKIPPED, JobState.CANCELLED}
            jobs_to_remove = [job_id for job_id, progress in self._job_progress.items() 
                            if progress.state in completed_states]
            
            for job_id in jobs_to_remove:
                del self._job_progress[job_id]
            
            logger.info(f"Cleared {len(jobs_to_remove)} completed jobs from progress tracking")
    
    def reset_tracking(self):
        """Reset all tracking data."""
        with self._lock:
            self._job_progress.clear()
            self._queue_progress = None
            self._queue_start_time = None
            self._last_update_time = None
            
            logger.info("Progress tracking reset")
    
    def _update_queue_progress(self):
        """Update overall queue progress based on individual jobs."""
        if not self._queue_progress:
            return
        
        # Count jobs by state
        completed = 0
        failed = 0
        active = 0
        pending = 0
        total_progress = 0.0
        
        current_jobs = []
        
        for job_progress in self._job_progress.values():
            if job_progress.state == JobState.COMPLETED:
                completed += 1
            elif job_progress.state in {JobState.FAILED, JobState.CANCELLED}:
                failed += 1
            elif job_progress.state in {JobState.PROCESSING, JobState.VALIDATING}:
                active += 1
                current_jobs.append(job_progress)
            elif job_progress.state == JobState.PENDING:
                pending += 1
            elif job_progress.state == JobState.SKIPPED:
                completed += 1  # Count skipped as completed for progress calculation
            
            total_progress += job_progress.progress
        
        # Update queue progress
        self._queue_progress.completed_jobs = completed
        self._queue_progress.failed_jobs = failed
        self._queue_progress.active_jobs = active
        self._queue_progress.pending_jobs = pending
        self._queue_progress.current_jobs = current_jobs
        
        # Calculate overall progress
        if self._queue_progress.total_jobs > 0:
            self._queue_progress.overall_progress = total_progress / self._queue_progress.total_jobs
        else:
            self._queue_progress.overall_progress = 100.0
        
        # Update timing estimates
        if self._queue_start_time:
            elapsed = (datetime.now() - self._queue_start_time).total_seconds()
            self._queue_progress.elapsed_time = elapsed
            
            # Calculate performance metrics
            if len(self._job_durations) > 0:
                self._queue_progress.average_job_duration = mean(self._job_durations)
                
            if elapsed > 0:
                completed_jobs = completed + len([jp for jp in self._job_progress.values() 
                                               if jp.state == JobState.SKIPPED])
                self._queue_progress.jobs_per_hour = (completed_jobs / elapsed) * 3600
        
        self._notify_queue_observers()
    
    def _estimate_job_steps(self, job: QueueJob) -> int:
        """Estimate number of processing steps for a job."""
        steps = 1  # Base processing
        
        if job.validation_options:
            steps += 1
        
        if job.render_options:
            if job.render_options.generate_image:
                steps += 1
            if job.render_options.generate_size_chart:
                steps += 1
            if job.render_options.generate_video:
                steps += 2  # Video takes longer
            if job.render_options.generate_color_variations:
                steps += len(job.render_options.color_palette)
        
        if job.analysis_options:
            steps += 1
        
        return max(1, steps)
    
    def _notify_queue_observers(self):
        """Notify all queue progress observers."""
        if not self._queue_progress:
            return
        
        observers_copy = self._observers.copy()
        for observer in observers_copy:
            try:
                observer(self._queue_progress)
            except Exception as e:
                logger.error(f"Error in queue progress observer: {e}")
    
    def _notify_job_observers(self, job_progress: JobProgress):
        """Notify all job progress observers."""
        observers_copy = self._job_observers.copy()
        for observer in observers_copy:
            try:
                observer(job_progress)
            except Exception as e:
                logger.error(f"Error in job progress observer: {e}")


# Convenience functions for common progress tracking scenarios
def create_simple_progress_callback(tracker: ProgressTracker, job_id: str) -> Callable[[float, str], None]:
    """Create a simple progress callback for a job."""
    def callback(progress: float, step: str = ""):
        tracker.update_job_progress(job_id, progress, step)
    return callback


def create_step_progress_callback(tracker: ProgressTracker, job_id: str, total_steps: int) -> Callable[[int, str], None]:
    """Create a step-based progress callback."""
    def callback(completed_steps: int, current_step: str = ""):
        progress = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        tracker.update_job_progress(job_id, progress, current_step, completed_steps)
    return callback