"""
Job history database management.

This module provides persistent storage and retrieval of job execution history
using SQLite, with performance statistics and cleanup capabilities.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import threading

from ..utils.logger import setup_logger
from .job_types import QueueJob, JobResults, JobState

logger = setup_logger("queue.job_history")


class JobHistoryRecord:
    """Individual job history record."""
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.stl_path = kwargs.get('stl_path')
        self.stl_filename = kwargs.get('stl_filename')
        self.stl_size = kwargs.get('stl_size')
        self.stl_checksum = kwargs.get('stl_checksum')
        self.output_folder = kwargs.get('output_folder')
        self.queue_session_id = kwargs.get('queue_session_id')
        
        # Job configuration (stored as JSON strings in DB)
        self.render_options = kwargs.get('render_options')
        self.validation_options = kwargs.get('validation_options')
        
        # Execution details
        self.state = kwargs.get('state')
        self.created_at = kwargs.get('created_at')
        self.started_at = kwargs.get('started_at')
        self.completed_at = kwargs.get('completed_at')
        self.estimated_duration = kwargs.get('estimated_duration')
        self.actual_duration = kwargs.get('actual_duration')
        
        # Results (stored as JSON strings in DB)
        self.validation_passed = kwargs.get('validation_passed')
        self.files_generated = kwargs.get('files_generated')
        self.error_message = kwargs.get('error_message')
        self.warnings = kwargs.get('warnings')
        
        # Metadata
        self.app_version = kwargs.get('app_version', '1.0')
        self.created_by = kwargs.get('created_by', 'gui')


class ProcessingStats:
    """Processing statistics for a time period."""
    
    def __init__(self):
        self.total_jobs = 0
        self.successful_jobs = 0
        self.failed_jobs = 0
        self.skipped_jobs = 0
        
        self.total_processing_time = 0.0
        self.average_job_duration = 0.0
        self.median_job_duration = 0.0
        
        self.files_processed = 0
        self.total_file_size = 0
        self.files_generated = 0
        
        self.success_rate = 0.0
        self.jobs_per_hour = 0.0
        
        # By job type
        self.render_jobs = 0
        self.validation_jobs = 0
        self.analysis_jobs = 0
        self.composite_jobs = 0


class JobHistoryManager:
    """
    Manages persistent job history using SQLite database.
    
    Provides functionality to record job completion, query history,
    generate statistics, and manage database cleanup.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize job history manager.
        
        Args:
            db_path: Path to SQLite database file (default: ~/.local/stl_listing_tools/job_history.db)
        """
        if db_path is None:
            config_dir = Path.home() / ".local" / "stl_listing_tools"
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = config_dir / "job_history.db"
        
        self.db_path = db_path
        self._lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        logger.info(f"Job history manager initialized: {self.db_path}")
    
    def _init_database(self):
        """Initialize database schema."""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute('PRAGMA foreign_keys = ON')
                
                # Create main job history table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS job_history (
                        id TEXT PRIMARY KEY,
                        stl_path TEXT NOT NULL,
                        stl_filename TEXT NOT NULL,
                        stl_size INTEGER NOT NULL,
                        stl_checksum TEXT,
                        output_folder TEXT NOT NULL,
                        queue_session_id TEXT NOT NULL,
                        
                        -- Job configuration (JSON)
                        render_options TEXT,
                        validation_options TEXT,
                        
                        -- Execution details
                        state TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        estimated_duration REAL,
                        actual_duration REAL,
                        
                        -- Results (JSON)
                        validation_passed BOOLEAN,
                        files_generated TEXT,
                        error_message TEXT,
                        warnings TEXT,
                        
                        -- Metadata
                        app_version TEXT NOT NULL DEFAULT '1.0',
                        created_by TEXT NOT NULL DEFAULT 'gui'
                    )
                ''')
                
                # Create indexes for performance
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stl_path ON job_history(stl_path)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_stl_checksum ON job_history(stl_checksum)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON job_history(created_at)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_state ON job_history(state)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_queue_session ON job_history(queue_session_id)')
                
                # Create statistics view
                conn.execute('''
                    CREATE VIEW IF NOT EXISTS job_stats AS
                    SELECT 
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) as successful_jobs,
                        SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed_jobs,
                        SUM(CASE WHEN state = 'skipped' THEN 1 ELSE 0 END) as skipped_jobs,
                        AVG(actual_duration) as avg_duration,
                        SUM(actual_duration) as total_duration,
                        SUM(stl_size) as total_file_size
                    FROM job_history 
                    WHERE actual_duration IS NOT NULL
                ''')
                
                conn.commit()
                conn.close()
                
                logger.info("Database schema initialized")
                
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise
    
    def record_job_completion(self, job: QueueJob, results: JobResults, 
                            session_id: str, stl_checksum: Optional[str] = None) -> bool:
        """
        Record a completed job in the history database.
        
        Args:
            job: Completed job
            results: Job execution results
            session_id: Queue session ID
            stl_checksum: Optional STL file checksum
            
        Returns:
            bool: True if record was saved successfully
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                
                # Get STL file info
                stl_size = job.stl_path.stat().st_size if job.stl_path.exists() else 0
                
                # Calculate actual duration
                actual_duration = job.duration
                
                # Prepare JSON data
                render_options_json = json.dumps(job.render_options.to_dict()) if job.render_options else None
                validation_options_json = json.dumps(job.validation_options.to_dict()) if job.validation_options else None
                files_generated_json = json.dumps([str(f) for f in results.files_generated])
                warnings_json = json.dumps(results.warnings) if results.warnings else None
                
                # Insert record
                conn.execute('''
                    INSERT OR REPLACE INTO job_history (
                        id, stl_path, stl_filename, stl_size, stl_checksum,
                        output_folder, queue_session_id,
                        render_options, validation_options,
                        state, created_at, started_at, completed_at,
                        estimated_duration, actual_duration,
                        validation_passed, files_generated, error_message, warnings,
                        app_version, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job.id, str(job.stl_path), job.stl_filename, stl_size, stl_checksum,
                    str(job.output_folder), session_id,
                    render_options_json, validation_options_json,
                    job.state.value, job.created_at, job.started_at, job.completed_at,
                    job.estimated_duration, actual_duration,
                    results.validation_passed, files_generated_json, job.error_message, warnings_json,
                    "1.0", "gui"
                ))
                
                conn.commit()
                conn.close()
                
                logger.debug(f"Recorded job completion: {job.id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to record job completion {job.id}: {e}")
                return False
    
    def find_similar_jobs(self, stl_path: Path, limit: int = 10) -> List[JobHistoryRecord]:
        """
        Find previous jobs for the same STL file.
        
        Args:
            stl_path: Path to STL file
            limit: Maximum number of records to return
            
        Returns:
            List of similar job history records
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute('''
                    SELECT * FROM job_history 
                    WHERE stl_path = ? OR stl_filename = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (str(stl_path), stl_path.name, limit))
                
                records = []
                for row in cursor:
                    records.append(JobHistoryRecord(**dict(row)))
                
                conn.close()
                return records
                
            except Exception as e:
                logger.error(f"Failed to find similar jobs for {stl_path}: {e}")
                return []
    
    def find_jobs_by_checksum(self, checksum: str) -> List[JobHistoryRecord]:
        """Find jobs by STL file checksum (exact duplicates)."""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute('''
                    SELECT * FROM job_history 
                    WHERE stl_checksum = ?
                    ORDER BY created_at DESC
                ''', (checksum,))
                
                records = []
                for row in cursor:
                    records.append(JobHistoryRecord(**dict(row)))
                
                conn.close()
                return records
                
            except Exception as e:
                logger.error(f"Failed to find jobs by checksum {checksum}: {e}")
                return []
    
    def get_processing_statistics(self, days: int = 30) -> ProcessingStats:
        """
        Get processing statistics for recent period.
        
        Args:
            days: Number of days to include in statistics
            
        Returns:
            ProcessingStats: Statistics for the period
        """
        with self._lock:
            stats = ProcessingStats()
            
            try:
                conn = sqlite3.connect(self.db_path)
                
                # Calculate date threshold
                threshold_date = datetime.now() - timedelta(days=days)
                
                # Get basic stats
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN state = 'completed' THEN 1 ELSE 0 END) as successful_jobs,
                        SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed_jobs,
                        SUM(CASE WHEN state = 'skipped' THEN 1 ELSE 0 END) as skipped_jobs,
                        AVG(actual_duration) as avg_duration,
                        SUM(actual_duration) as total_duration,
                        SUM(stl_size) as total_file_size
                    FROM job_history 
                    WHERE created_at >= ?
                ''', (threshold_date,))
                
                row = cursor.fetchone()
                if row:
                    stats.total_jobs = row[0] or 0
                    stats.successful_jobs = row[1] or 0
                    stats.failed_jobs = row[2] or 0
                    stats.skipped_jobs = row[3] or 0
                    stats.average_job_duration = row[4] or 0.0
                    stats.total_processing_time = row[5] or 0.0
                    stats.total_file_size = row[6] or 0
                
                # Calculate success rate
                if stats.total_jobs > 0:
                    stats.success_rate = (stats.successful_jobs / stats.total_jobs) * 100
                
                # Calculate jobs per hour
                if days > 0:
                    hours = days * 24
                    stats.jobs_per_hour = stats.total_jobs / hours if hours > 0 else 0
                
                # Get median duration
                cursor = conn.execute('''
                    SELECT actual_duration
                    FROM job_history 
                    WHERE created_at >= ? AND actual_duration IS NOT NULL
                    ORDER BY actual_duration
                ''', (threshold_date,))
                
                durations = [row[0] for row in cursor]
                if durations:
                    n = len(durations)
                    stats.median_job_duration = durations[n // 2]
                
                # Count files processed and generated
                cursor = conn.execute('''
                    SELECT COUNT(*) as files_processed,
                           SUM(json_array_length(files_generated)) as files_generated
                    FROM job_history 
                    WHERE created_at >= ? AND files_generated IS NOT NULL
                ''', (threshold_date,))
                
                row = cursor.fetchone()
                if row:
                    stats.files_processed = row[0] or 0
                    stats.files_generated = row[1] or 0
                
                conn.close()
                
                logger.debug(f"Generated statistics for {days} days: {stats.total_jobs} jobs")
                return stats
                
            except Exception as e:
                logger.error(f"Failed to generate statistics: {e}")
                return stats
    
    def get_recent_jobs(self, limit: int = 50) -> List[JobHistoryRecord]:
        """Get most recent job records."""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute('''
                    SELECT * FROM job_history 
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
                
                records = []
                for row in cursor:
                    records.append(JobHistoryRecord(**dict(row)))
                
                conn.close()
                return records
                
            except Exception as e:
                logger.error(f"Failed to get recent jobs: {e}")
                return []
    
    def cleanup_old_records(self, keep_days: int = 90) -> int:
        """
        Remove old job records to manage database size.
        
        Args:
            keep_days: Number of days of history to keep
            
        Returns:
            int: Number of records removed
        """
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                
                # Calculate cutoff date
                cutoff_date = datetime.now() - timedelta(days=keep_days)
                
                # Delete old records
                cursor = conn.execute('''
                    DELETE FROM job_history 
                    WHERE created_at < ?
                ''', (cutoff_date,))
                
                removed_count = cursor.rowcount
                conn.commit()
                
                # Vacuum database to reclaim space
                conn.execute('VACUUM')
                
                conn.close()
                
                logger.info(f"Cleaned up {removed_count} old job records (older than {keep_days} days)")
                return removed_count
                
            except Exception as e:
                logger.error(f"Failed to cleanup old records: {e}")
                return 0
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the database."""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                
                # Get record count
                cursor = conn.execute('SELECT COUNT(*) FROM job_history')
                total_records = cursor.fetchone()[0]
                
                # Get database file size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                
                # Get date range
                cursor = conn.execute('SELECT MIN(created_at), MAX(created_at) FROM job_history')
                date_range = cursor.fetchone()
                
                conn.close()
                
                return {
                    'database_path': str(self.db_path),
                    'database_size': db_size,
                    'total_records': total_records,
                    'earliest_record': date_range[0],
                    'latest_record': date_range[1]
                }
                
            except Exception as e:
                logger.error(f"Failed to get database info: {e}")
                return {}
    
    def export_history(self, output_file: Path, days: Optional[int] = None) -> bool:
        """
        Export job history to JSON file.
        
        Args:
            output_file: Output file path
            days: Number of recent days to export (None = all)
            
        Returns:
            bool: True if export was successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            if days is not None:
                threshold_date = datetime.now() - timedelta(days=days)
                cursor = conn.execute('''
                    SELECT * FROM job_history 
                    WHERE created_at >= ?
                    ORDER BY created_at
                ''', (threshold_date,))
            else:
                cursor = conn.execute('''
                    SELECT * FROM job_history 
                    ORDER BY created_at
                ''')
            
            records = []
            for row in cursor:
                records.append(dict(row))
            
            conn.close()
            
            export_data = {
                'exported_at': datetime.now().isoformat(),
                'days_included': days,
                'record_count': len(records),
                'records': records
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Exported {len(records)} job records to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export history: {e}")
            return False


# Convenience functions
def get_job_history_manager(db_path: Optional[Path] = None) -> JobHistoryManager:
    """Get job history manager instance."""
    return JobHistoryManager(db_path)


def calculate_stl_checksum(stl_path: Path) -> Optional[str]:
    """Calculate MD5 checksum for STL file."""
    try:
        hash_md5 = hashlib.md5()
        with open(stl_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None