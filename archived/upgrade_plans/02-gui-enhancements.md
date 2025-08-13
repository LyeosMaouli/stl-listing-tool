# GUI Enhancements for Queue System

## Overview

This document details the GUI enhancements required to integrate the batch processing queue system into the existing STL Listing Tool interface. The enhancements will maintain the current single-file workflow while adding comprehensive batch processing capabilities.

## Current GUI State Analysis

### Existing Interface Components
- ✅ **File Selection**: Single file browse/drag-drop with status display
- ✅ **Analysis Tab**: STL analysis with export functionality  
- ✅ **Validation Tab**: Mesh validation with repair options
- ✅ **Rendering Tab**: Single render with material/lighting controls
- ✅ **Settings Persistence**: User preferences saved automatically
- ✅ **Progress Indicators**: Progress bar and status display
- ✅ **Error Handling**: Comprehensive error dialogs

### Current Window Layout
```
[Menu Bar: File, Help]
[File Selection: Browse + Drop Area]
[Tabs: Analysis | Validation | Rendering]
[Status Bar: Ready/Progress]
```

## Enhanced GUI Architecture

### New Window Layout
```
[Menu Bar: File, Queue, Help]
[Mode Toggle: Single File | Batch Processing]

Single File Mode (Current):
[File Selection: Browse + Drop Area]  
[Tabs: Analysis | Validation | Rendering]

Batch Mode (New):
[File/Folder Selection: Multi-select + Recursive scan]
[Tabs: Queue Setup | Queue Management | Results]

[Status Bar: Ready/Progress/Queue Status]
```

## New GUI Components

### 1. Mode Toggle Switch
**Location**: Top of main window, below menu bar
**Purpose**: Switch between single-file and batch processing modes
**Implementation**:
- Radio buttons or toggle switch
- Preserves current tab selection when switching
- Automatic mode detection based on user actions

### 2. Enhanced File Selection (Batch Mode)

#### Multi-File Selection Panel
```
┌─ File Selection ─────────────────────────────────┐
│ [Browse Files...] [Browse Folder...] [Clear All] │
│                                                   │
│ ┌─ Selected Files (0) ─────────────────────────┐ │
│ │ □ /path/to/model1.stl          [Remove]     │ │
│ │ □ /path/to/model2.stl          [Remove]     │ │
│ │ □ /path/to/subfolder/model3.stl [Remove]    │ │
│ │                            [Select All]     │ │
│ │                            [Select None]    │ │
│ └─────────────────────────────────────────────┘ │
│                                                   │
│ Options: ☑ Include subfolders  ☑ STL files only │
│          ☐ Validate before adding                │
└───────────────────────────────────────────────────┘
```

**Features**:
- Individual file selection with checkboxes
- Remove individual files from selection
- Recursive folder scanning with progress
- Real-time STL file count display
- Drag-and-drop support for files and folders
- Preview of file paths with truncation for long paths

#### Folder Browser Integration
```python
class FolderBrowser:
    def scan_folder(self, folder_path: Path, recursive: bool = True) -> List[Path]:
        """Scan folder for STL files with progress callback."""
        
    def validate_files(self, stl_files: List[Path]) -> Tuple[List[Path], List[str]]:
        """Pre-validate STL files and return valid files + error list."""
```

### 3. Queue Setup Tab

#### Processing Options Panel
```
┌─ Processing Options ─────────────────────────────┐
│ Render Options:                                   │
│ ☑ Generate Images        ☐ Generate Size Charts  │
│ ☐ Generate Videos        ☐ Generate Color Grids  │
│                                                   │
│ Validation:                                       │  
│ Level: [Standard ▼]    ☑ Auto Repair            │
│                                                   │
│ Analysis:                                         │
│ ☑ Generate Reports    Format: [JSON ▼]          │
└───────────────────────────────────────────────────┘
```

#### Render Settings Panel (Collapsible)
```
┌─ Render Settings ─────────────────────────────────┐
│ Material: [Plastic ▼]    Lighting: [Studio ▼]   │
│ Size: [1920] x [1080]    Quality: [Standard ▼]  │
│                                                   │
│ Background: [Select Image...] [Clear]            │
│ Preview: [thumbnail]                              │
│                                                   │
│ Video Settings (when enabled):                    │
│ Duration: [10.0] sec    FPS: [30]                │
│ Rotation: ☑ Full 360°   ☐ Oscillate             │
│                                                   │
│ Color Variations (when enabled):                  │
│ Palette: [Default ▼]    [Custom Colors...]       │
│ Colors: ☑Red ☑Blue ☑Green ☑Yellow ☐Custom      │
└───────────────────────────────────────────────────┘
```

#### Output Configuration Panel
```
┌─ Output Settings ─────────────────────────────────┐
│ Output Folder: [/path/to/output] [Browse...]      │
│                                                   │
│ Organization:                                     │
│ ● Create subfolder per STL file                  │
│ ○ Flat structure with prefixed names             │
│ ○ Group by render type                           │
│                                                   │
│ Naming Convention:                                │
│ ● Use STL filename as base                       │
│ ○ Custom prefix: [____]                         │
│ ☑ Add timestamp suffix                          │
│                                                   │
│ [Preview Structure...] [Start Queue]             │
└───────────────────────────────────────────────────┘
```

### 4. Queue Management Tab

#### Queue Overview Panel
```
┌─ Queue Status ────────────────────────────────────┐
│ Total Jobs: 45    Completed: 23    Failed: 2     │
│ Estimated Time Remaining: 2h 15m                 │
│ Current: Processing model_dragon.stl (67%)       │
│                                                   │
│ [Pause All] [Resume All] [Stop All] [Clear Done] │
└───────────────────────────────────────────────────┘
```

#### Job List with Controls
```
┌─ Job Queue ───────────────────────────────────────┐
│ Status │ STL File        │ Progress │ Actions      │
├────────┼─────────────────┼──────────┼──────────────┤
│ ⏸      │ model1.stl      │ [████████] 100% │ [View] │
│ ▶      │ model2.stl      │ [███░░░░░] 45%  │ [Pause]│
│ ⏸      │ model3.stl      │ [░░░░░░░░]  0%  │ [Skip] │
│ ❌      │ broken.stl      │ Failed          │ [Retry]│
│ ⏸      │ model5.stl      │ Pending         │ [Up]   │
└───────────────────────────────────────────────────┘
```

#### Detailed Job View (Expandable rows or side panel)
```
Selected Job: model2.stl
├─ Render Options: Image ✓, Video ✗, Size Chart ✓
├─ Progress Details:
│  ├─ Validation: Complete ✓
│  ├─ Image Render: In Progress (45%)
│  └─ Size Chart: Pending
├─ Output Location: /output/model2/
├─ Started: 14:23:15
├─ Estimated Completion: 14:35:42
└─ Logs: [View Full Log]
```

### 5. Results Tab

#### Results Summary Panel  
```
┌─ Processing Results ──────────────────────────────┐
│ Completed: 23/25 STL files                       │
│ Total Duration: 1h 34m                           │
│ Success Rate: 92%                                │
│                                                   │
│ Generated Files:                                  │
│ ├─ Images: 23 files                              │
│ ├─ Size Charts: 23 files                        │
│ ├─ Videos: 0 files                              │
│ ├─ Analysis Reports: 23 files                   │
│ └─ Validation Reports: 25 files                 │
│                                                   │
│ [Open Output Folder] [Generate Summary Report]   │
└───────────────────────────────────────────────────┘
```

#### Results File Browser
```
┌─ Output Files ────────────────────────────────────┐
│ model1/                                           │
│ ├─ renders/                                      │
│ │  ├─ model1_render.png            [Preview]     │
│ │  └─ model1_size_chart.png        [Preview]     │
│ ├─ analysis/                                     │
│ │  └─ model1_analysis.json         [View]        │
│ └─ logs/                                         │
│    └─ model1_processing.log        [View]        │
│                                                   │
│ model2/                                          │
│ └─ ... (similar structure)                       │
└───────────────────────────────────────────────────┘
```

## Enhanced Menu System

### New Menu Items
```
File Menu:
├─ Open STL...                     [Existing]
├─ ──────────────
├─ Add Files to Queue...           [New]
├─ Add Folder to Queue...          [New] 
├─ Clear Queue                     [New]
├─ ──────────────
├─ Export Queue Configuration...   [New]
├─ Import Queue Configuration...   [New]
├─ ──────────────
├─ Exit                           [Existing]

Queue Menu:                        [New Menu]
├─ Start Processing
├─ Pause All Jobs
├─ Resume All Jobs  
├─ Stop All Jobs
├─ ──────────────
├─ Clear Completed Jobs
├─ Clear Failed Jobs
├─ Retry Failed Jobs
├─ ──────────────
├─ Queue Settings...

Help Menu:
├─ About                          [Existing]
├─ Batch Processing Guide         [New]
└─ Keyboard Shortcuts             [New]
```

## Progress Visualization Enhancements

### Multi-Level Progress Indicators

#### Overall Queue Progress
```
Queue Progress: [████████████████░░░░] 78% (18/23 jobs)
Current Job: [██████████░░░░░░░░░░] 52% - Rendering model5.stl
```

#### Individual Job Progress (in queue list)
```
Job: model3.stl [██████░░░░░░░░░░] 35%
├─ Validation: Complete ✓
├─ Analysis: Complete ✓  
├─ Image Render: In Progress 67%
├─ Size Chart: Pending
└─ Video: Disabled
```

### Status Icons and Colors
- ⏸ **Paused**: Gray/Yellow
- ▶ **Running**: Green/Blue
- ✓ **Complete**: Green
- ❌ **Failed**: Red
- ⏯ **Waiting**: Gray
- ⚠ **Warning**: Orange

## Responsive Design Considerations

### Window Size Management
- **Minimum Size**: 1200x800 (increased from current 1000x700)
- **Expandable Sections**: Collapsible render settings, job details
- **Scrollable Lists**: File selection, job queue with virtual scrolling
- **Resizable Panels**: Adjustable split between tabs and content

### Performance Optimizations
- **Virtual Scrolling**: For large file/job lists
- **Lazy Loading**: Job details loaded on demand
- **Background Updates**: Progress updates without blocking UI
- **Memory Management**: Proper cleanup of preview images and job data

## User Experience Improvements

### Keyboard Shortcuts
- **Ctrl+Shift+A**: Add files to queue
- **Ctrl+Shift+F**: Add folder to queue
- **Space**: Pause/Resume current job
- **Ctrl+Shift+P**: Pause all jobs
- **Ctrl+Shift+R**: Resume all jobs
- **Delete**: Remove selected jobs
- **F5**: Refresh queue status

### Drag and Drop Enhancements
- **Files to Queue**: Direct drag from file manager to job queue
- **Folder Processing**: Drag folders for automatic STL scanning
- **Job Reordering**: Drag jobs within queue to change priority
- **Visual Feedback**: Clear drop zones and drag indicators

### Context Menus
- **Job Right-Click**: Pause, Skip, Retry, View Details, Remove
- **File List Right-Click**: Remove, Preview, Properties
- **Results Right-Click**: Open Folder, Preview, Copy Path

## Implementation Strategy

### Phase 1: Core GUI Structure
1. Add mode toggle and basic batch UI skeleton
2. Implement enhanced file selection with multi-file support
3. Create queue setup tab with basic options
4. Add queue management tab with job list

### Phase 2: Queue Integration
1. Connect GUI to queue system backend
2. Implement progress visualization and status updates
3. Add queue control buttons (start, pause, stop)
4. Create results display and file browser

### Phase 3: Advanced Features
1. Job reordering and priority management
2. Detailed job progress and log viewing
3. Configuration export/import
4. Enhanced error handling and recovery options

### Phase 4: Polish and Optimization
1. Performance optimization for large queues
2. Accessibility improvements
3. Help system and tooltips
4. User testing and feedback integration

## Technical Implementation Details

### GUI Architecture Changes
```python
class STLProcessorGUI:
    def __init__(self):
        # Existing initialization
        self.mode = "single"  # "single" or "batch"
        self.queue_manager = QueueManager()
        self.setup_enhanced_ui()
    
    def setup_enhanced_ui(self):
        self.create_mode_toggle()
        self.create_batch_interface()
        self.setup_queue_integration()
```

### State Management
- **Single File State**: Preserve existing functionality completely
- **Batch State**: New state management for queue operations
- **Mode Switching**: Clean transitions without losing user data
- **Session Persistence**: Save/restore queue state and UI preferences

### Thread Safety
- **GUI Updates**: All queue updates via thread-safe mechanisms
- **Progress Callbacks**: Proper event-driven progress reporting  
- **Resource Management**: Careful handling of shared resources
- **Error Propagation**: Safe error handling across threads

---

**Next Document**: [03-persistence-and-file-management.md](./03-persistence-and-file-management.md)