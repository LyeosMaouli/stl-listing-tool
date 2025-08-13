# Persistence and File Management Plan

## Overview

This document details the data persistence, file organization, and state management systems required for the queue-based STL processing system. The design ensures data integrity, recovery from interruptions, and efficient file organization.

## Current State Analysis

### Existing Persistence

- ✅ **User Config**: JSON-based settings in `~/.local/stl_listing_tool/config.json`
- ✅ **Window Geometry**: Saved/restored automatically
- ✅ **Render Settings**: Material, lighting, dimensions persistence
- ✅ **Background Images**: Path persistence with validation
- ❌ **Queue State**: No persistence for batch operations
- ❌ **Job History**: No historical tracking of completed jobs

### Existing File Handling

- ✅ **Temporary Files**: Custom temp directory structure
- ✅ **Single Renders**: Individual file output with user-selected paths
- ✅ **Error Handling**: Comprehensive file access error handling
- ❌ **Batch Organization**: No systematic output organization
- ❌ **Progress Recovery**: No ability to resume interrupted operations

## Persistence Architecture

### Data Storage Hierarchy

```
~/.local/stl_listing_tool/
├── config.json                    # User preferences (existing)
├── queue_state.json               # Active queue state
├── job_history.db                 # SQLite job history database
├── templates/                     # Queue configuration templates
│   ├── default_render.json
│   ├── validation_only.json
│   └── complete_processing.json
├── cache/                         # Temporary processing cache
│   ├── job_cache/
│   └── thumbnails/
└── backups/                       # Automatic backups
    ├── queue_state_backup_1.json
    ├── queue_state_backup_2.json
    └── queue_state_backup_3.json
```

### Queue State Persistence

#### Queue State Schema

```json
{
  "version": "1.0",
  "created_at": "2024-01-15T10:30:00Z",
  "last_updated": "2024-01-15T11:45:00Z",
  "queue_settings": {
    "max_concurrent_jobs": 2,
    "auto_retry_failed": true,
    "max_retry_attempts": 3,
    "output_base_folder": "/path/to/output"
  },
  "global_render_options": {
    "generate_image": true,
    "generate_size_chart": false,
    "generate_video": false,
    "generate_color_variations": false,
    "width": 1920,
    "height": 1080,
    "material": "plastic",
    "lighting": "studio",
    "background_image": "/path/to/background.jpg"
  },
  "global_validation_options": {
    "level": "standard",
    "auto_repair": true
  },
  "jobs": [
    {
      "id": "job_001",
      "stl_path": "/path/to/model1.stl",
      "output_folder": "/output/model1",
      "state": "completed",
      "progress": 100.0,
      "created_at": "2024-01-15T10:30:15Z",
      "started_at": "2024-01-15T10:30:20Z",
      "completed_at": "2024-01-15T10:32:45Z",
      "estimated_duration": 145.0,
      "actual_duration": 145.3,
      "render_options": {
        /* job-specific overrides */
      },
      "validation_options": {
        /* job-specific overrides */
      },
      "results": {
        "validation_passed": true,
        "files_generated": [
          "/output/model1/renders/model1_render.png",
          "/output/model1/analysis/model1_analysis.json"
        ],
        "errors": [],
        "warnings": ["Minor mesh issues detected but repaired"]
      },
      "error_message": null
    }
  ]
}
```

#### Atomic Persistence Operations

```python
class QueueStateManager:
    def save_queue_state(self, queue_state: QueueState) -> bool:
        """Save queue state with atomic write and backup."""
        temp_file = self.state_path.with_suffix('.tmp')
        backup_file = self.create_backup()

        try:
            # Write to temporary file first
            with open(temp_file, 'w') as f:
                json.dump(queue_state.to_dict(), f, indent=2)

            # Atomic rename
            temp_file.replace(self.state_path)
            return True
        except Exception as e:
            # Restore from backup if needed
            if backup_file and backup_file.exists():
                backup_file.replace(self.state_path)
            raise e
        finally:
            # Cleanup
            if temp_file.exists():
                temp_file.unlink()
```

### Job History Database

#### Schema Design

```sql
CREATE TABLE job_history (
    id TEXT PRIMARY KEY,
    stl_path TEXT NOT NULL,
    stl_filename TEXT NOT NULL,
    stl_size INTEGER NOT NULL,
    stl_checksum TEXT NOT NULL,
    output_folder TEXT NOT NULL,
    queue_session_id TEXT NOT NULL,

    -- Job configuration
    render_options TEXT NOT NULL, -- JSON
    validation_options TEXT NOT NULL, -- JSON

    -- Execution details
    state TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_duration REAL,
    actual_duration REAL,

    -- Results
    validation_passed BOOLEAN,
    files_generated TEXT, -- JSON array
    error_message TEXT,
    warnings TEXT, -- JSON array

    -- Metadata
    app_version TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'gui'
);

CREATE INDEX idx_stl_path ON job_history(stl_path);
CREATE INDEX idx_stl_checksum ON job_history(stl_checksum);
CREATE INDEX idx_created_at ON job_history(created_at);
CREATE INDEX idx_state ON job_history(state);
```

#### History Management

```python
class JobHistoryManager:
    def record_job_completion(self, job: QueueJob, results: JobResults):
        """Record completed job in history database."""

    def find_similar_jobs(self, stl_path: Path) -> List[JobHistoryRecord]:
        """Find previous jobs for the same STL file."""

    def get_processing_statistics(self, days: int = 30) -> ProcessingStats:
        """Get processing statistics for recent period."""

    def cleanup_old_records(self, keep_days: int = 90):
        """Remove old job records to manage database size."""
```

## File Organization System

### Output Directory Structure

#### Per-STL Organization (Default)

```
output_folder/
├── queue_summary.json                 # Overall processing summary
├── processing_log.txt                 # Combined processing log
├── ModelA/                            # STL base filename
│   ├── source/                        # Source file information
│   │   ├── ModelA.stl -> /original/path/ModelA.stl  # Symlink to original
│   │   └── file_info.json            # File metadata and validation
│   ├── renders/
│   │   ├── ModelA_render.png         # Main render image
│   │   ├── ModelA_size_chart.png     # Size chart render
│   │   ├── ModelA_presentation.mp4   # 360° rotation video
│   │   └── color_variations/         # Color variation renders
│   │       ├── ModelA_red.png
│   │       ├── ModelA_blue.png
│   │       └── ModelA_green.png
│   ├── analysis/
│   │   ├── ModelA_analysis.json      # Detailed analysis results
│   │   ├── ModelA_dimensions.json    # Dimension data
│   │   └── ModelA_validation.json    # Validation results
│   └── logs/
│       ├── ModelA_processing.log     # Individual job log
│       └── ModelA_errors.log         # Error log (if any)
├── ModelB/
│   └── ... (same structure)
└── failed/                           # Files that couldn't be processed
    ├── broken.stl -> /original/path/broken.stl
    └── broken_error.log
```

#### Alternative Organization Modes

**Flat Structure**

```
output_folder/
├── ModelA_render.png
├── ModelA_size_chart.png
├── ModelA_analysis.json
├── ModelB_render.png
├── ModelB_size_chart.png
└── ModelB_analysis.json
```

**Grouped by Type**

```
output_folder/
├── renders/
│   ├── ModelA_render.png
│   └── ModelB_render.png
├── size_charts/
│   ├── ModelA_size_chart.png
│   └── ModelB_size_chart.png
├── videos/
│   ├── ModelA_presentation.mp4
│   └── ModelB_presentation.mp4
├── analysis/
│   ├── ModelA_analysis.json
│   └── ModelB_analysis.json
└── logs/
    ├── ModelA_processing.log
    └── ModelB_processing.log
```

### File Naming Conventions

#### Standard Naming

```python
class FileNameGenerator:
    def __init__(self, base_name: str, options: NamingOptions):
        self.base_name = base_name
        self.options = options

    def render_filename(self, suffix: str = "render") -> str:
        """Generate render filename: ModelA_render.png"""
        parts = [self.base_name, suffix]
        if self.options.include_timestamp:
            parts.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
        return f"{'_'.join(parts)}.png"

    def video_filename(self) -> str:
        """Generate video filename: ModelA_presentation.mp4"""
        return self.render_filename("presentation").replace('.png', '.mp4')

    def analysis_filename(self, format: str = "json") -> str:
        """Generate analysis filename: ModelA_analysis.json"""
        return self.render_filename("analysis").replace('.png', f'.{format}')
```

#### Naming Options

- **Timestamp Suffix**: Optional timestamp for uniqueness
- **Quality Suffix**: `_draft`, `_standard`, `_high`, `_ultra`
- **Material Suffix**: `_plastic`, `_metal`, `_resin`
- **Size Suffix**: `_1920x1080`, `_4k`
- **Custom Prefix**: User-defined prefix for all files

### Temporary File Management

#### Processing Cache

```
cache/
├── job_cache/
│   ├── job_001/                      # Per-job temporary files
│   │   ├── stl_copy.stl             # Working copy of STL
│   │   ├── render_temp.png          # Temporary render output
│   │   └── processing_state.json    # Mid-processing state
│   └── job_002/
│       └── ...
└── thumbnails/                       # STL preview thumbnails
    ├── model1_thumb.png
    └── model2_thumb.png
```

#### Cleanup Strategy

```python
class TempFileManager:
    def create_job_cache_dir(self, job_id: str) -> Path:
        """Create temporary directory for job processing."""

    def cleanup_job_cache(self, job_id: str):
        """Remove job-specific temporary files."""

    def cleanup_stale_cache(self, max_age_hours: int = 24):
        """Remove old temporary files from interrupted sessions."""

    def get_cache_size(self) -> int:
        """Calculate total cache directory size."""

    def cleanup_large_cache(self, max_size_mb: int = 1000):
        """Remove oldest cache files if total size exceeds limit."""
```

## Recovery and Error Handling

### Session Recovery

#### Automatic Recovery on Startup

```python
class SessionRecoveryManager:
    def check_for_recovery(self) -> Optional[QueueState]:
        """Check if there's a queue state to recover from previous session."""

    def recover_interrupted_jobs(self, queue_state: QueueState) -> RecoveryResult:
        """Attempt to recover partially completed jobs."""

    def validate_recovery_data(self, queue_state: QueueState) -> List[ValidationError]:
        """Validate recovered queue state for consistency."""
```

#### Recovery Actions

1. **Validate Queue State**: Check for corruption or inconsistencies
2. **Check File Existence**: Verify all STL files still exist
3. **Assess Job Progress**: Determine which jobs can be resumed
4. **Clean Partial Outputs**: Remove incomplete renders/analyses
5. **Reset Job States**: Set appropriate states for recovery

### Error Recovery Strategies

#### File System Errors

- **Permission Issues**: Prompt for alternative output location
- **Disk Space**: Monitor space and pause queue when low
- **Network Paths**: Handle network disconnections gracefully
- **File Locks**: Retry with backoff for locked files

#### Processing Errors

- **Corrupted STL**: Skip file and continue queue
- **Render Failures**: Retry with fallback settings
- **Memory Issues**: Process smaller batches or individual files
- **Timeout Errors**: Increase timeout or skip complex models

### Backup and Migration

#### Automatic Backups

```python
class BackupManager:
    def create_backup(self, label: str = None) -> Path:
        """Create timestamped backup of queue state."""

    def rotate_backups(self, keep_count: int = 5):
        """Maintain fixed number of backup files."""

    def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore queue state from backup file."""
```

#### Version Migration

```python
class StateMigration:
    def migrate_queue_state(self, old_state: dict, from_version: str) -> dict:
        """Migrate queue state format between versions."""

    def migrate_user_config(self, old_config: dict, from_version: str) -> dict:
        """Migrate user configuration format between versions."""
```

## Configuration Templates

### Template System

```python
@dataclass
class QueueTemplate:
    name: str
    description: str
    render_options: RenderOptions
    validation_options: ValidationOptions
    output_settings: OutputSettings
    created_at: datetime
    created_by: str

class TemplateManager:
    def save_template(self, template: QueueTemplate):
        """Save queue configuration as reusable template."""

    def load_template(self, name: str) -> QueueTemplate:
        """Load queue template by name."""

    def list_templates(self) -> List[str]:
        """List available template names."""
```

### Built-in Templates

#### Default Templates

1. **"Quick Preview"**: Basic render only, fast settings
2. **"Complete Processing"**: All render types, analysis, validation
3. **"Validation Only"**: Mesh validation and repair only
4. **"High Quality Renders"**: Premium render settings with videos
5. **"Batch Analysis"**: Analysis and validation without rendering

#### Custom Templates

- User-created templates saved in `templates/` directory
- Export/import functionality for sharing templates
- Template validation and upgrade system

## Performance Considerations

### Disk Usage Optimization

- **Compression**: Optional compression for analysis data
- **Cleanup Policies**: Automatic removal of old temporary files
- **Size Monitoring**: Track and report disk usage
- **Batch Optimization**: Efficient processing order to minimize I/O

### Concurrent Access

- **File Locking**: Prevent conflicts with concurrent access
- **Database Connections**: Connection pooling for history database
- **Cache Coordination**: Thread-safe cache management
- **Resource Limits**: Prevent excessive resource consumption

### Scalability

- **Large Queues**: Efficient handling of hundreds of STL files
- **History Management**: Pagination and archiving for large histories
- **Memory Usage**: Minimize memory footprint for queue state
- **Background Operations**: Non-blocking persistence operations

---

**Next Document**: [04-testing-strategy.md](./04-testing-strategy.md)
