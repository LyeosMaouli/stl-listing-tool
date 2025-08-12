"""
Job types and data models for the queue system.

This module defines the core data structures used throughout the batch processing
queue system, including job definitions, options, states, and results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import json

try:
    from ..rendering.base_renderer import MaterialType, LightingPreset, RenderQuality
    RENDERING_AVAILABLE = True
except ImportError:
    # Create fallback enums if rendering module is not available
    from enum import Enum
    
    class MaterialType(Enum):
        PLASTIC = "plastic"
        METAL = "metal"
        RESIN = "resin"
        CERAMIC = "ceramic"
        WOOD = "wood"
        GLASS = "glass"
    
    class LightingPreset(Enum):
        STUDIO = "studio"
        NATURAL = "natural"
        DRAMATIC = "dramatic"
        SOFT = "soft"
    
    class RenderQuality(Enum):
        DRAFT = "draft"
        STANDARD = "standard"
        HIGH = "high"
        ULTRA = "ultra"
    
    RENDERING_AVAILABLE = False


class JobType(Enum):
    """Types of jobs that can be processed in the queue."""
    RENDER = "render"
    VALIDATION = "validation"
    ANALYSIS = "analysis" 
    COMPOSITE = "composite"


class JobState(Enum):
    """Possible states for jobs in the queue."""
    PENDING = "pending"           # Queued, not started
    VALIDATING = "validating"     # Pre-processing validation
    PROCESSING = "processing"     # Active execution
    PAUSED = "paused"            # User paused
    COMPLETED = "completed"       # Successfully finished
    FAILED = "failed"            # Error occurred
    SKIPPED = "skipped"          # Validation failed, skipped
    CANCELLED = "cancelled"       # User cancelled


class ValidationLevel(Enum):
    """Mesh validation strictness levels."""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass
class RenderOptions:
    """Configuration options for rendering operations."""
    
    # What to generate
    generate_image: bool = True
    generate_size_chart: bool = False
    generate_video: bool = False
    generate_color_variations: bool = False
    
    # Basic render settings
    width: int = 1920
    height: int = 1080
    material: MaterialType = MaterialType.PLASTIC
    lighting: LightingPreset = LightingPreset.STUDIO
    quality: RenderQuality = RenderQuality.STANDARD
    background_image: Optional[Path] = None
    
    # Video settings
    video_duration: float = 10.0
    video_fps: int = 30
    video_rotation_angle: float = 360.0
    
    # Color variation settings
    color_palette: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (1.0, 0.2, 0.2),  # Red
        (0.2, 0.2, 1.0),  # Blue
        (0.2, 1.0, 0.2),  # Green
        (1.0, 1.0, 0.2),  # Yellow
        (1.0, 0.2, 1.0),  # Magenta
        (0.2, 1.0, 1.0),  # Cyan
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'generate_image': self.generate_image,
            'generate_size_chart': self.generate_size_chart,
            'generate_video': self.generate_video,
            'generate_color_variations': self.generate_color_variations,
            'width': self.width,
            'height': self.height,
            'material': self.material.value,
            'lighting': self.lighting.value,
            'quality': self.quality.value,
            'background_image': str(self.background_image) if self.background_image else None,
            'video_duration': self.video_duration,
            'video_fps': self.video_fps,
            'video_rotation_angle': self.video_rotation_angle,
            'color_palette': self.color_palette
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RenderOptions':
        """Create from dictionary (JSON deserialization)."""
        return cls(
            generate_image=data.get('generate_image', True),
            generate_size_chart=data.get('generate_size_chart', False),
            generate_video=data.get('generate_video', False),
            generate_color_variations=data.get('generate_color_variations', False),
            width=data.get('width', 1920),
            height=data.get('height', 1080),
            material=MaterialType(data.get('material', 'plastic')),
            lighting=LightingPreset(data.get('lighting', 'studio')),
            quality=RenderQuality(data.get('quality', 'standard')),
            background_image=Path(data['background_image']) if data.get('background_image') else None,
            video_duration=data.get('video_duration', 10.0),
            video_fps=data.get('video_fps', 30),
            video_rotation_angle=data.get('video_rotation_angle', 360.0),
            color_palette=data.get('color_palette', [])
        )


@dataclass 
class ValidationOptions:
    """Configuration options for validation operations."""
    
    level: ValidationLevel = ValidationLevel.STANDARD
    auto_repair: bool = True
    generate_report: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'level': self.level.value,
            'auto_repair': self.auto_repair,
            'generate_report': self.generate_report
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationOptions':
        """Create from dictionary (JSON deserialization)."""
        return cls(
            level=ValidationLevel(data.get('level', 'standard')),
            auto_repair=data.get('auto_repair', True),
            generate_report=data.get('generate_report', True)
        )


@dataclass
class AnalysisOptions:
    """Configuration options for analysis operations."""
    
    generate_report: bool = True
    report_format: str = "json"  # "json" or "text"
    include_dimensions: bool = True
    include_printability: bool = True
    include_mesh_quality: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'generate_report': self.generate_report,
            'report_format': self.report_format,
            'include_dimensions': self.include_dimensions,
            'include_printability': self.include_printability,
            'include_mesh_quality': self.include_mesh_quality
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisOptions':
        """Create from dictionary (JSON deserialization)."""
        return cls(
            generate_report=data.get('generate_report', True),
            report_format=data.get('report_format', 'json'),
            include_dimensions=data.get('include_dimensions', True),
            include_printability=data.get('include_printability', True),
            include_mesh_quality=data.get('include_mesh_quality', True)
        )


@dataclass
class JobResults:
    """Results from job execution."""
    
    validation_passed: bool = True
    files_generated: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    
    # Validation-specific results
    validation_details: Optional[Dict[str, Any]] = None
    
    # Analysis-specific results
    analysis_data: Optional[Dict[str, Any]] = None
    
    # Render-specific results
    render_details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'validation_passed': self.validation_passed,
            'files_generated': [str(f) for f in self.files_generated],
            'errors': self.errors,
            'warnings': self.warnings,
            'processing_time': self.processing_time,
            'validation_details': self.validation_details,
            'analysis_data': self.analysis_data,
            'render_details': self.render_details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobResults':
        """Create from dictionary (JSON deserialization)."""
        return cls(
            validation_passed=data.get('validation_passed', True),
            files_generated=[Path(f) for f in data.get('files_generated', [])],
            errors=data.get('errors', []),
            warnings=data.get('warnings', []),
            processing_time=data.get('processing_time', 0.0),
            validation_details=data.get('validation_details'),
            analysis_data=data.get('analysis_data'),
            render_details=data.get('render_details')
        )


@dataclass
class QueueJob:
    """A job in the processing queue."""
    
    # Identity and basic info
    id: str
    job_type: JobType
    stl_path: Path
    output_folder: Path
    
    # Configuration
    render_options: Optional[RenderOptions] = None
    validation_options: Optional[ValidationOptions] = None
    analysis_options: Optional[AnalysisOptions] = None
    
    # State management
    state: JobState = JobState.PENDING
    progress: float = 0.0
    
    # Timing information
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_duration: Optional[float] = None
    
    # Results and errors
    results: Optional[JobResults] = None
    error_message: Optional[str] = None
    
    # Priority and queue management
    priority: int = 0  # Higher numbers = higher priority
    
    def __post_init__(self):
        """Initialize default options if not provided."""
        if self.job_type == JobType.RENDER and self.render_options is None:
            self.render_options = RenderOptions()
        if self.job_type in [JobType.VALIDATION, JobType.COMPOSITE] and self.validation_options is None:
            self.validation_options = ValidationOptions()
        if self.job_type in [JobType.ANALYSIS, JobType.COMPOSITE] and self.analysis_options is None:
            self.analysis_options = AnalysisOptions()
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate actual duration if job is started."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    @property
    def stl_filename(self) -> str:
        """Get STL filename without path."""
        return self.stl_path.name
    
    @property
    def stl_basename(self) -> str:
        """Get STL filename without extension."""
        return self.stl_path.stem
    
    def start_processing(self):
        """Mark job as started."""
        self.state = JobState.PROCESSING
        self.started_at = datetime.now()
    
    def complete_processing(self, results: JobResults):
        """Mark job as completed with results."""
        self.state = JobState.COMPLETED
        self.completed_at = datetime.now()
        self.progress = 100.0
        self.results = results
    
    def fail_processing(self, error_message: str):
        """Mark job as failed with error message."""
        self.state = JobState.FAILED
        self.completed_at = datetime.now()
        self.error_message = error_message
    
    def skip_processing(self, reason: str):
        """Mark job as skipped with reason."""
        self.state = JobState.SKIPPED
        self.completed_at = datetime.now()
        self.error_message = reason
    
    def cancel_processing(self):
        """Mark job as cancelled."""
        self.state = JobState.CANCELLED
        self.completed_at = datetime.now()
    
    def pause_processing(self):
        """Pause job processing."""
        if self.state == JobState.PROCESSING:
            self.state = JobState.PAUSED
    
    def resume_processing(self):
        """Resume paused job."""
        if self.state == JobState.PAUSED:
            self.state = JobState.PROCESSING
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'job_type': self.job_type.value,
            'stl_path': str(self.stl_path),
            'output_folder': str(self.output_folder),
            'render_options': self.render_options.to_dict() if self.render_options else None,
            'validation_options': self.validation_options.to_dict() if self.validation_options else None,
            'analysis_options': self.analysis_options.to_dict() if self.analysis_options else None,
            'state': self.state.value,
            'progress': self.progress,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_duration': self.estimated_duration,
            'results': self.results.to_dict() if self.results else None,
            'error_message': self.error_message,
            'priority': self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueJob':
        """Create from dictionary (JSON deserialization)."""
        job = cls(
            id=data['id'],
            job_type=JobType(data['job_type']),
            stl_path=Path(data['stl_path']),
            output_folder=Path(data['output_folder']),
            render_options=RenderOptions.from_dict(data['render_options']) if data.get('render_options') else None,
            validation_options=ValidationOptions.from_dict(data['validation_options']) if data.get('validation_options') else None,
            analysis_options=AnalysisOptions.from_dict(data['analysis_options']) if data.get('analysis_options') else None,
            state=JobState(data.get('state', 'pending')),
            progress=data.get('progress', 0.0),
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            estimated_duration=data.get('estimated_duration'),
            results=JobResults.from_dict(data['results']) if data.get('results') else None,
            error_message=data.get('error_message'),
            priority=data.get('priority', 0)
        )
        return job


def create_render_job(
    stl_path: Path,
    output_folder: Path,
    render_options: Optional[RenderOptions] = None,
    job_id: Optional[str] = None
) -> QueueJob:
    """Create a render job with default settings."""
    import uuid
    
    if job_id is None:
        job_id = f"render_{uuid.uuid4().hex[:8]}"
    
    return QueueJob(
        id=job_id,
        job_type=JobType.RENDER,
        stl_path=stl_path,
        output_folder=output_folder,
        render_options=render_options or RenderOptions()
    )


def create_validation_job(
    stl_path: Path,
    output_folder: Path,
    validation_options: Optional[ValidationOptions] = None,
    job_id: Optional[str] = None
) -> QueueJob:
    """Create a validation job with default settings."""
    import uuid
    
    if job_id is None:
        job_id = f"validate_{uuid.uuid4().hex[:8]}"
    
    return QueueJob(
        id=job_id,
        job_type=JobType.VALIDATION,
        stl_path=stl_path,
        output_folder=output_folder,
        validation_options=validation_options or ValidationOptions()
    )


def create_analysis_job(
    stl_path: Path,
    output_folder: Path,
    analysis_options: Optional[AnalysisOptions] = None,
    job_id: Optional[str] = None
) -> QueueJob:
    """Create an analysis job with default settings."""
    import uuid
    
    if job_id is None:
        job_id = f"analyze_{uuid.uuid4().hex[:8]}"
    
    return QueueJob(
        id=job_id,
        job_type=JobType.ANALYSIS,
        stl_path=stl_path,
        output_folder=output_folder,
        analysis_options=analysis_options or AnalysisOptions()
    )


def create_composite_job(
    stl_path: Path,
    output_folder: Path,
    render_options: Optional[RenderOptions] = None,
    validation_options: Optional[ValidationOptions] = None,
    analysis_options: Optional[AnalysisOptions] = None,
    job_id: Optional[str] = None
) -> QueueJob:
    """Create a composite job that combines multiple processing steps."""
    import uuid
    
    if job_id is None:
        job_id = f"composite_{uuid.uuid4().hex[:8]}"
    
    return QueueJob(
        id=job_id,
        job_type=JobType.COMPOSITE,
        stl_path=stl_path,
        output_folder=output_folder,
        render_options=render_options,
        validation_options=validation_options or ValidationOptions(),
        analysis_options=analysis_options or AnalysisOptions()
    )