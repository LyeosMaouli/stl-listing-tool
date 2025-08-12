# Queue System Architecture Plan

## Overview

This document outlines the architecture for implementing a comprehensive batch processing queue system for the STL Listing Tool. The system will enable users to process multiple STL files with various render options, validation settings, and output formats.

## Current State Analysis

### Existing Components
- ✅ **STL Processing**: Core STL loading, validation, and analysis (`STLProcessor`, `DimensionExtractor`, `MeshValidator`)
- ✅ **Rendering System**: VTK-based renderer with material/lighting presets (`VTKRenderer`, `BaseRenderer`)
- ✅ **GUI Framework**: Tkinter-based interface with drag-drop, settings persistence (`STLProcessorGUI`)
- ✅ **CLI Interface**: Click-based CLI with analyze, validate, render, and scale commands
- ✅ **Configuration**: Pydantic-based settings with user preferences
- ❌ **Queue System**: Empty placeholder in `src/queue/` directory

### Identified Gaps
1. No batch processing capabilities
2. No persistent job queue management
3. No progress tracking for long-running operations
4. No automatic file discovery for folders
5. No render output organization per STL file
6. No pause/resume/stop functionality

## Queue System Architecture

### Core Components

#### 1. Job Management Layer
```
src/queue/
├── job_manager.py          # Central job orchestration
├── job_types.py           # Job type definitions and validation
├── job_queue.py           # Queue operations and persistence
├── job_executor.py        # Job execution engine
├── progress_tracker.py    # Progress tracking and notifications
└── file_scanner.py        # Recursive STL file discovery
```

#### 2. Job Types

**`RenderJob`**
- **Purpose**: Render STL files with specified settings
- **Options**: 
  - Image rendering (PNG, JPG)
  - Size chart generation 
  - Video presentation (360° rotation)
  - Color variations grid
- **Output**: Organized in per-STL subfolders

**`ValidationJob`**
- **Purpose**: Validate STL mesh integrity
- **Options**: Basic, Standard, Strict validation levels
- **Output**: Validation reports and repair logs

**`AnalysisJob`**
- **Purpose**: Extract dimensions and properties
- **Output**: JSON/text analysis reports

**`CompositeJob`**
- **Purpose**: Combine multiple job types for complete processing
- **Workflow**: Validation → Analysis → Rendering options

#### 3. Queue State Management

**Job States**
```python
class JobState(Enum):
    PENDING = "pending"           # Queued, not started
    VALIDATING = "validating"     # Pre-processing validation
    PROCESSING = "processing"     # Active execution
    PAUSED = "paused"            # User paused
    COMPLETED = "completed"       # Successfully finished
    FAILED = "failed"            # Error occurred
    SKIPPED = "skipped"          # Validation failed, skipped
    CANCELLED = "cancelled"       # User cancelled
```

**Queue Operations**
- Add single files or batch from folders
- Pause/Resume individual jobs or entire queue
- Stop/Cancel with cleanup
- Reorder queue priority
- Retry failed jobs
- Save/restore queue state on application restart

### Data Models

#### Job Definition
```python
@dataclass
class QueueJob:
    id: str
    job_type: JobType
    stl_path: Path
    output_folder: Path
    render_options: RenderOptions
    validation_options: ValidationOptions
    state: JobState
    progress: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    estimated_duration: Optional[float]
```

#### Render Options
```python
@dataclass
class RenderOptions:
    generate_image: bool = False
    generate_size_chart: bool = False
    generate_video: bool = False
    generate_color_variations: bool = False
    
    # Render settings
    width: int = 1920
    height: int = 1080
    material: MaterialType = MaterialType.PLASTIC
    lighting: LightingPreset = LightingPreset.STUDIO
    background_image: Optional[Path] = None
    
    # Video settings
    video_duration: float = 10.0
    video_fps: int = 30
    
    # Color variation settings
    color_palette: List[Tuple[float, float, float]] = None
```

### Queue Persistence

**Storage Format**: JSON with atomic writes for reliability
**Location**: `~/.local/stl_listing_tools/queue_state.json`

**Persistence Features**:
- Automatic save on queue modifications
- Recovery on application restart
- Backup previous states
- Migration support for format changes

## Implementation Phases

### Phase 1: Core Queue Infrastructure (Week 1)
1. **Job Models**: Define data structures and enums
2. **Job Queue**: Implement queue operations with persistence
3. **File Scanner**: Recursive STL discovery with filtering
4. **Progress Tracking**: Basic progress reporting system

### Phase 2: Job Execution Engine (Week 2)
1. **Job Executor**: Threading-based execution with proper cleanup
2. **Job Types**: Implement basic render, validate, and analysis jobs
3. **Error Handling**: Comprehensive error catching and reporting
4. **State Management**: Save/restore functionality

### Phase 3: Advanced Features (Week 3)
1. **Composite Jobs**: Multi-step job workflows
2. **Video Generation**: 360° rotation video creation
3. **Size Charts**: Professional dimension charts
4. **Color Variations**: Multi-color render grids

### Phase 4: GUI Integration (Week 4)
1. **Queue Management Tab**: Full queue interface
2. **File Selection**: Multi-file and folder selection
3. **Progress Visualization**: Real-time progress displays
4. **Queue Controls**: Pause/resume/stop/reorder functionality

## Technical Specifications

### Threading Model
- **Main Thread**: GUI and user interactions
- **Queue Thread**: Job management and coordination  
- **Worker Threads**: Individual job execution (configurable pool size)
- **Progress Thread**: Status updates and notifications

### Error Recovery
- **Validation Failures**: Skip non-conforming STL files with detailed logging
- **Render Failures**: Retry with fallback settings, then skip
- **System Errors**: Graceful degradation and user notification
- **Queue Corruption**: Automatic backup recovery

### Performance Considerations
- **Memory Management**: Process one STL at a time to avoid memory issues
- **Resource Cleanup**: Proper cleanup of VTK resources and temporary files
- **Progress Estimation**: Learning algorithm for better time estimates
- **Batch Optimization**: Reuse renderer instances when possible

## File Organization Strategy

### Output Structure
```
output_folder/
├── queue_summary.json                    # Overall processing results
├── ModelA/
│   ├── renders/
│   │   ├── ModelA_render.png
│   │   ├── ModelA_size_chart.png
│   │   ├── ModelA_presentation.mp4
│   │   └── color_variations/
│   │       ├── ModelA_red.png
│   │       ├── ModelA_blue.png
│   │       └── ModelA_green.png
│   ├── analysis/
│   │   ├── ModelA_analysis.json
│   │   └── ModelA_validation.json
│   └── logs/
│       └── ModelA_processing.log
└── ModelB/
    └── ... (same structure)
```

### Naming Conventions
- **Base Name**: STL filename without extension
- **Render Suffix**: `_render`, `_size_chart`, `_presentation`
- **Color Suffix**: `_colorname` (red, blue, green, etc.)
- **Quality Suffix**: `_draft`, `_standard`, `_high` (for different quality levels)

## Integration Points

### GUI Integration
- New "Batch Processing" tab in main window
- File/folder selection with STL preview
- Render options checklist with real-time preview
- Progress bars and status indicators
- Queue management controls

### CLI Integration  
- New `batch` command for CLI-based queue processing
- JSON configuration file support
- Progress reporting for headless operation
- Exit code handling for automation

### Configuration Integration
- Queue-specific settings in user config
- Default render options
- Worker thread configuration
- Output folder preferences

## Risk Mitigation

### Data Safety
- Atomic file operations for queue state
- Backup/restore mechanisms
- Input validation and sanitization
- Graceful handling of file system errors

### Performance Risks
- Memory usage monitoring and limits
- Progress estimation accuracy
- UI responsiveness during long operations
- Resource cleanup on interruption

### User Experience Risks
- Clear error messaging and recovery options
- Intuitive queue management interface
- Reasonable default settings
- Comprehensive help documentation

## Success Metrics

### Functional Requirements
- ✅ Process multiple STL files in batch
- ✅ Generate all requested render types per file
- ✅ Organize outputs in per-file subfolders
- ✅ Handle validation failures gracefully
- ✅ Persist queue state across sessions
- ✅ Provide pause/resume/stop controls

### Performance Requirements
- Process 100+ STL files without memory issues
- Maintain responsive UI during processing
- Complete render operations within reasonable time
- Provide accurate progress estimation

### Reliability Requirements
- Zero data loss on application crashes
- Graceful recovery from system errors
- Consistent output quality and organization
- Comprehensive error logging and reporting

---

**Next Document**: [02-gui-enhancements.md](./02-gui-enhancements.md)