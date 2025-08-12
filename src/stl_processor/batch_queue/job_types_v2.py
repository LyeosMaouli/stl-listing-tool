"""
Job types for Phase 2 execution engine.
Simplified job models focused on execution.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobError:
    """Job error information."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class JobResult:
    """Job execution result."""
    job_id: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[JobError] = None
    execution_time: Optional[float] = None


@dataclass
class Job:
    """Simple job for execution engine."""
    job_type: str
    input_file: str
    output_file: Optional[str] = None
    priority: int = 1
    options: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Execution tracking
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    created_at: Optional[float] = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())