"""Queue modules for batch processing."""

from .job_types import (
    JobType, JobState, ValidationLevel,
    RenderOptions, ValidationOptions, AnalysisOptions,
    JobResults, QueueJob,
    create_render_job, create_validation_job, create_analysis_job, create_composite_job
)

from .job_queue import JobQueue, create_job_from_stl

from .file_scanner import (
    FileInfo, ScanResult, FileScanner,
    scan_for_stl_files, find_duplicate_files
)

from .progress_tracker import (
    JobProgress, QueueProgress, ProgressTracker,
    create_simple_progress_callback, create_step_progress_callback
)

from .queue_persistence import (
    QueueStateManager, QueueConfiguration,
    save_queue_to_file, load_queue_from_file, get_queue_state_manager
)

from .job_history import (
    JobHistoryRecord, ProcessingStats, JobHistoryManager,
    get_job_history_manager, calculate_stl_checksum
)

from .job_manager import (
    JobManager, QueueManagerError,
    create_job_manager, get_default_job_manager
)

# Phase 2: Job Execution Engine
from .job_types_v2 import Job as ExecutionJob, JobStatus, JobResult, JobError
from .job_executor import JobExecutor, JobExecutionEngine
from .job_handlers import RenderJobHandler, ValidationJobHandler, AnalysisJobHandler
from .error_handler import (
    ErrorHandler, ErrorSeverity, ErrorCategory, 
    RetryManager, RecoveryStrategy, ErrorClassifier
)
from .recovery_manager import SessionRecoveryManager
from .enhanced_job_manager import EnhancedJobManager

__all__ = [
    # Job types and models
    'JobType', 'JobState', 'ValidationLevel',
    'RenderOptions', 'ValidationOptions', 'AnalysisOptions',
    'JobResults', 'QueueJob',
    'create_render_job', 'create_validation_job', 'create_analysis_job', 'create_composite_job',
    
    # Job queue
    'JobQueue', 'create_job_from_stl',
    
    # File scanning  
    'FileInfo', 'ScanResult', 'FileScanner',
    'scan_for_stl_files', 'find_duplicate_files',
    
    # Progress tracking
    'JobProgress', 'QueueProgress', 'ProgressTracker',
    'create_simple_progress_callback', 'create_step_progress_callback',
    
    # Persistence and configuration
    'QueueStateManager', 'QueueConfiguration',
    'save_queue_to_file', 'load_queue_from_file', 'get_queue_state_manager',
    
    # Job history
    'JobHistoryRecord', 'ProcessingStats', 'JobHistoryManager',
    'get_job_history_manager', 'calculate_stl_checksum',
    
    # Job management
    'JobManager', 'QueueManagerError',
    'create_job_manager', 'get_default_job_manager',
    
    # Phase 2: Job Execution Engine
    'ExecutionJob', 'JobStatus', 'JobResult', 'JobError',
    'JobExecutor', 'JobExecutionEngine',
    'RenderJobHandler', 'ValidationJobHandler', 'AnalysisJobHandler',
    'ErrorHandler', 'ErrorSeverity', 'ErrorCategory',
    'RetryManager', 'RecoveryStrategy', 'ErrorClassifier',
    'SessionRecoveryManager', 'EnhancedJobManager'
]