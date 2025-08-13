"""
Recovery manager for session recovery and state restoration.
Handles recovery from unexpected shutdowns and system crashes.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .job_types_v2 import Job, JobStatus, JobResult
from .job_queue import JobQueue
from .progress_tracker import ProgressTracker


logger = logging.getLogger(__name__)


class SessionRecoveryManager:
    """
    Manages session recovery and state restoration.
    """
    
    def __init__(self, 
                 recovery_dir: Path,
                 job_queue: Optional[JobQueue] = None,
                 progress_tracker: Optional[ProgressTracker] = None):
        self.recovery_dir = Path(recovery_dir)
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        
        self.job_queue = job_queue
        self.progress_tracker = progress_tracker
        
        # Recovery files
        self.session_file = self.recovery_dir / "session.json"
        self.jobs_file = self.recovery_dir / "jobs.json"
        self.progress_file = self.recovery_dir / "progress.json"
        self.metadata_file = self.recovery_dir / "metadata.json"
        
        # Session metadata
        self.session_id: Optional[str] = None
        self.session_start_time: Optional[float] = None
        self.last_checkpoint: Optional[float] = None
        
    def start_session(self, session_id: str) -> None:
        """Start a new recovery session."""
        self.session_id = session_id
        self.session_start_time = time.time()
        self.last_checkpoint = self.session_start_time
        
        # Create session metadata
        metadata = {
            "session_id": session_id,
            "start_time": self.session_start_time,
            "last_checkpoint": self.last_checkpoint,
            "version": "1.0"
        }
        
        self._save_json(self.metadata_file, metadata)
        logger.info(f"Started recovery session: {session_id}")
    
    def checkpoint(self) -> None:
        """Create a recovery checkpoint."""
        if not self.session_id:
            logger.warning("Cannot checkpoint: no active session")
            return
        
        try:
            current_time = time.time()
            
            # Save session state
            self._save_session_state()
            
            # Save job queue state
            if self.job_queue:
                self._save_job_queue_state()
            
            # Save progress tracker state
            if self.progress_tracker:
                self._save_progress_state()
            
            # Update metadata
            metadata = {
                "session_id": self.session_id,
                "start_time": self.session_start_time,
                "last_checkpoint": current_time,
                "version": "1.0"
            }
            self._save_json(self.metadata_file, metadata)
            
            self.last_checkpoint = current_time
            logger.debug(f"Created checkpoint for session: {self.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
    
    def can_recover(self) -> bool:
        """Check if recovery data is available."""
        return (self.metadata_file.exists() and 
                self.session_file.exists() and
                self.jobs_file.exists())
    
    def get_recovery_info(self) -> Optional[Dict[str, Any]]:
        """Get information about available recovery data."""
        if not self.can_recover():
            return None
        
        try:
            metadata = self._load_json(self.metadata_file)
            session_data = self._load_json(self.session_file)
            jobs_data = self._load_json(self.jobs_file)
            
            # Calculate recovery statistics
            total_jobs = len(jobs_data.get("jobs", []))
            completed_jobs = sum(1 for job in jobs_data.get("jobs", []) 
                               if job.get("status") == JobStatus.COMPLETED.value)
            running_jobs = sum(1 for job in jobs_data.get("jobs", [])
                             if job.get("status") == JobStatus.RUNNING.value)
            
            return {
                "session_id": metadata.get("session_id"),
                "start_time": metadata.get("start_time"),
                "last_checkpoint": metadata.get("last_checkpoint"),
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "running_jobs": running_jobs,
                "interrupted_jobs": running_jobs,  # Jobs that were running when interrupted
                "recovery_age": time.time() - metadata.get("last_checkpoint", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get recovery info: {e}")
            return None
    
    def recover_session(self) -> bool:
        """
        Recover a previous session.
        Returns True if recovery was successful.
        """
        if not self.can_recover():
            logger.warning("No recovery data available")
            return False
        
        try:
            logger.info("Starting session recovery...")
            
            # Load metadata
            metadata = self._load_json(self.metadata_file)
            self.session_id = metadata.get("session_id")
            self.session_start_time = metadata.get("start_time")
            self.last_checkpoint = metadata.get("last_checkpoint")
            
            # Recover job queue state
            if self.job_queue and not self._recover_job_queue_state():
                logger.error("Failed to recover job queue state")
                return False
            
            # Recover progress tracker state
            if self.progress_tracker and not self._recover_progress_state():
                logger.warning("Failed to recover progress state (continuing anyway)")
            
            # Mark interrupted jobs as pending
            self._handle_interrupted_jobs()
            
            logger.info(f"Session recovery completed for: {self.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Session recovery failed: {e}")
            return False
    
    def cleanup_recovery_data(self) -> None:
        """Clean up recovery data files."""
        try:
            for file_path in [self.session_file, self.jobs_file, 
                            self.progress_file, self.metadata_file]:
                if file_path.exists():
                    file_path.unlink()
            
            logger.info("Recovery data cleaned up")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup recovery data: {e}")
    
    def end_session(self) -> None:
        """End the current session and cleanup."""
        if self.session_id:
            logger.info(f"Ending recovery session: {self.session_id}")
            self.cleanup_recovery_data()
            
            self.session_id = None
            self.session_start_time = None
            self.last_checkpoint = None
    
    def _save_session_state(self) -> None:
        """Save general session state."""
        session_data = {
            "session_id": self.session_id,
            "start_time": self.session_start_time,
            "checkpoint_time": time.time(),
            "status": "active"
        }
        
        self._save_json(self.session_file, session_data)
    
    def _save_job_queue_state(self) -> None:
        """Save job queue state."""
        if not self.job_queue:
            return
        
        try:
            # Get all jobs from queue
            jobs_data = []
            
            # Get jobs from different queues
            for job in self.job_queue.get_all_jobs():
                jobs_data.append({
                    "id": job.id,
                    "job_type": job.job_type,
                    "input_file": job.input_file,
                    "output_file": job.output_file,
                    "status": job.status.value,
                    "priority": job.priority,
                    "options": job.options,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "metadata": job.metadata
                })
            
            queue_data = {
                "jobs": jobs_data,
                "queue_size": len(jobs_data),
                "checkpoint_time": time.time()
            }
            
            self._save_json(self.jobs_file, queue_data)
            
        except Exception as e:
            logger.error(f"Failed to save job queue state: {e}")
            raise
    
    def _save_progress_state(self) -> None:
        """Save progress tracker state."""
        if not self.progress_tracker:
            return
        
        try:
            progress_data = {
                "job_progress": dict(self.progress_tracker.job_progress),
                "job_messages": dict(self.progress_tracker.job_messages),
                "overall_progress": self.progress_tracker.get_overall_progress(),
                "checkpoint_time": time.time()
            }
            
            self._save_json(self.progress_file, progress_data)
            
        except Exception as e:
            logger.error(f"Failed to save progress state: {e}")
    
    def _recover_job_queue_state(self) -> bool:
        """Recover job queue state."""
        try:
            jobs_data = self._load_json(self.jobs_file)
            
            # Clear current queue
            self.job_queue.clear()
            
            # Restore jobs
            for job_data in jobs_data.get("jobs", []):
                job = Job(
                    id=job_data["id"],
                    job_type=job_data["job_type"],
                    input_file=job_data["input_file"],
                    output_file=job_data.get("output_file"),
                    priority=job_data.get("priority", 1),
                    options=job_data.get("options", {}),
                    metadata=job_data.get("metadata", {})
                )
                
                # Restore job state
                job.status = JobStatus(job_data["status"])
                job.created_at = job_data.get("created_at")
                job.started_at = job_data.get("started_at")
                job.completed_at = job_data.get("completed_at")
                
                # Add job back to queue
                if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                    self.job_queue.add_job(job)
                elif job.status == JobStatus.COMPLETED:
                    # Add to completed jobs if queue supports it
                    if hasattr(self.job_queue, '_completed_jobs'):
                        self.job_queue._completed_jobs[job.id] = job
                elif job.status == JobStatus.FAILED:
                    # Add to failed jobs if queue supports it
                    if hasattr(self.job_queue, '_failed_jobs'):
                        self.job_queue._failed_jobs[job.id] = job
            
            logger.info(f"Recovered {len(jobs_data.get('jobs', []))} jobs")
            return True
            
        except Exception as e:
            logger.error(f"Failed to recover job queue state: {e}")
            return False
    
    def _recover_progress_state(self) -> bool:
        """Recover progress tracker state."""
        try:
            if not self.progress_file.exists():
                return True  # No progress data to recover
            
            progress_data = self._load_json(self.progress_file)
            
            # Restore progress data using the new method
            success = self.progress_tracker.restore_progress_state(progress_data)
            if success:
                logger.info("Recovered progress tracker state")
            else:
                logger.warning("Partial recovery of progress tracker state")
            return True
            
        except Exception as e:
            logger.error(f"Failed to recover progress state: {e}")
            return False
    
    def _handle_interrupted_jobs(self) -> None:
        """Handle jobs that were interrupted during processing."""
        if not self.job_queue:
            return
        
        try:
            interrupted_count = 0
            
            # Find jobs that were running when session was interrupted
            for job in self.job_queue.get_all_jobs():
                if job.status == JobStatus.RUNNING:
                    # Reset to pending status
                    job.status = JobStatus.PENDING
                    job.started_at = None
                    
                    # Clear partial progress
                    if self.progress_tracker:
                        self.progress_tracker.reset_job_progress(job.id)
                    
                    interrupted_count += 1
                    logger.info(f"Reset interrupted job to pending: {job.id}")
            
            if interrupted_count > 0:
                logger.info(f"Reset {interrupted_count} interrupted jobs to pending status")
                
        except Exception as e:
            logger.error(f"Failed to handle interrupted jobs: {e}")
    
    def _save_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save data to JSON file with atomic write."""
        try:
            # Write to temporary file first
            temp_file = file_path.with_suffix('.tmp')
            
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            # Atomic rename
            temp_file.replace(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save JSON to {file_path}: {e}")
            raise
    
    def _load_json(self, file_path: Path) -> Dict[str, Any]:
        """Load data from JSON file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Failed to load JSON from {file_path}: {e}")
            raise