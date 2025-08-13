# Batch Queue UI Enhancements Plan

## Overview
This document outlines the planned enhancements to the batch queue tab to improve user control over processing options and make batch processing the primary focus of the application.

## Current State Analysis

### Current Tab Structure (in order):
1. Analysis
2. Validation  
3. Rendering
4. Generators
5. Batch Queue (added dynamically)

### Current Queue Controls:
- Start Processing
- Pause  
- Stop
- Clear Completed

### Current Processing Pipeline:
- Fixed pipeline: Analysis → Validation → Rendering (always all three)
- No user control over which processes to run
- No restart functionality

## Planned Enhancements

### 1. Tab Reorganization
**Goal**: Make batch processing the primary focus

**Changes**:
- Move "Batch Queue" tab to be the **first tab** (index 0)
- Reorder tabs: Batch Queue → Analysis → Validation → Rendering → Generators
- Set Batch Queue as the default active tab on startup

**Implementation**:
- Modify `create_notebook()` method to call `create_batch_queue_tab()` first
- Ensure proper tab ordering in initialization

### 2. Enhanced Queue Controls
**Goal**: Add restart functionality for better queue management

**Current Layout**:
```
[Start Processing] [Pause] [Stop] [Clear Completed]
```

**New Layout**:
```
[Start Processing] [Pause] [Stop] [Restart] [Clear Completed]    [☑️ Image Rendering] [☑️ Video Rendering]
```

**Restart Button Functionality**:
- Stops current processing if running
- Resets all in-progress jobs to pending status
- Clears any partial progress
- Allows users to restart the entire queue from scratch

### 3. Processing Options Checkboxes
**Goal**: Give users control over which processes to run

**New Checkboxes** (positioned on the right side of control buttons):
- **Image Rendering**: Controls whether to generate static images
- **Video Rendering**: Controls whether to generate rotation videos

**Processing Pipeline Logic**:
- **Always Run**: Analysis + Validation (mandatory for all jobs)
- **Conditional**: Image Rendering (if checkbox checked)
- **Conditional**: Video Rendering (if checkbox checked)

**Default State**: Both checkboxes enabled (maintains current behavior)

## Implementation Plan

### Phase 1: Tab Reorganization
```python
def create_notebook(self):
    """Create notebook with batch queue as first tab."""
    self.notebook = ttk.Notebook(self.main_frame)
    self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Batch Queue first (primary focus)
    self.create_batch_queue_tab()  # Move this first
    
    # Other tabs
    self.create_analysis_tab()
    self.create_validation_tab()
    self.create_rendering_tab()
    self.create_generators_tab()
```

### Phase 2: Enhanced Queue Controls
```python
def create_queue_controls(self):
    """Create enhanced queue control buttons and options."""
    control_frame = ttk.LabelFrame(self.batch_tab, text="Queue Controls", padding="10")
    control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    control_frame.columnconfigure(2, weight=1)  # Spacer column
    
    # Left side: Control buttons
    button_frame = ttk.Frame(control_frame)
    button_frame.grid(row=0, column=0, sticky=tk.W)
    
    # Buttons: Start, Pause, Stop, Restart, Clear
    self.control_buttons['start'] = ttk.Button(button_frame, text="Start Processing", command=self.start_processing)
    self.control_buttons['pause'] = ttk.Button(button_frame, text="Pause", command=self.pause_processing)
    self.control_buttons['stop'] = ttk.Button(button_frame, text="Stop", command=self.stop_processing)
    self.control_buttons['restart'] = ttk.Button(button_frame, text="Restart", command=self.restart_processing)
    self.control_buttons['clear'] = ttk.Button(button_frame, text="Clear Completed", command=self.clear_completed)
    
    # Right side: Processing options
    options_frame = ttk.Frame(control_frame)
    options_frame.grid(row=0, column=3, sticky=tk.E)
    
    # Checkboxes for processing options
    self.image_rendering_var = tk.BooleanVar(value=True)
    self.video_rendering_var = tk.BooleanVar(value=True)
    
    ttk.Checkbutton(options_frame, text="Image Rendering", variable=self.image_rendering_var).grid(row=0, column=0, padx=(0, 10))
    ttk.Checkbutton(options_frame, text="Video Rendering", variable=self.video_rendering_var).grid(row=0, column=1)
```

### Phase 3: Restart Functionality
```python
def restart_processing(self):
    """Restart the entire batch queue processing."""
    if not self.job_manager:
        return
    
    try:
        # Stop current processing
        if self.job_manager.is_running:
            self.job_manager.stop_processing()
        
        # Reset all jobs to pending status
        self.job_manager.reset_all_jobs()
        
        # Clear progress tracking
        if hasattr(self.job_manager, 'progress_tracker'):
            self.job_manager.progress_tracker.reset_tracking()
        
        # Update UI
        self._reset_control_buttons()
        
        messagebox.showinfo("Queue Restarted", "All jobs have been reset and are ready to process again.")
        logger.info("Batch queue restarted by user")
        
    except Exception as e:
        logger.error(f"Error restarting queue: {e}")
        show_error_with_logging(
            self.root, "Restart Error",
            f"Error restarting batch queue: {e}",
            exception=e
        )
```

### Phase 4: Processing Pipeline Logic
```python
def add_files_to_batch_queue(self, stl_files):
    """Add STL files to batch queue with user-selected processing options."""
    try:
        if not self.job_manager:
            logger.error("Job manager not initialized")
            return
        
        # Get user preferences
        enable_image_rendering = self.image_rendering_var.get()
        enable_video_rendering = self.video_rendering_var.get()
        
        # Create job options based on checkboxes
        job_options = {
            'analysis': True,      # Always enabled
            'validation': True,    # Always enabled  
            'image_rendering': enable_image_rendering,
            'video_rendering': enable_video_rendering
        }
        
        # Create output directory
        output_dir = self._get_user_output_directory()
        
        # Add jobs with custom options
        job_ids = self.job_manager.add_jobs_from_files(
            stl_files, output_dir, 
            job_type="composite",  # Use composite for multiple operations
            job_options=job_options
        )
        
        logger.info(f"Added {len(job_ids)} jobs with options: {job_options}")
        self.file_status_var.set(f"Added {len(stl_files)} STL files with selected processing options")
        
    except Exception as e:
        logger.error(f"Error adding files to queue: {e}")
        show_error_with_logging(self.root, "Queue Error", f"Error adding files: {e}", exception=e)
```

## User Experience Flow

### 1. User Opens Application
- **Batch Queue tab is immediately visible and active**
- User sees drag-and-drop area prominently
- Processing options (checkboxes) are visible and set to defaults

### 2. User Adds Files
- Drags files or uses browse buttons
- Files appear in the job queue list
- Processing options affect what will be done to each file

### 3. User Configures Processing
- Can toggle Image Rendering on/off
- Can toggle Video Rendering on/off
- Analysis and Validation always run (core requirements)

### 4. User Manages Queue
- Start/Pause/Stop as before
- **New**: Restart to reset entire queue and start over
- Clear completed jobs when done

## Technical Implementation Notes

### Job Manager Integration
- Need to extend job types to support conditional processing
- Update job execution logic to respect processing options
- Ensure proper state management for restart functionality

### UI State Management
- Save user checkbox preferences to user config
- Maintain checkbox state across sessions
- Update job display to show which processes will run

### Error Handling
- Graceful handling of restart during active processing
- Proper cleanup of partial job states
- User feedback for all operations

## Files to Modify

1. **`src/stl_processor/gui.py`**:
   - `create_notebook()` - reorder tabs
   - `create_batch_queue_tab()` - ensure proper initialization order
   - `create_queue_controls()` - add restart button and checkboxes
   - `restart_processing()` - new method
   - `add_files_to_batch_queue()` - update with processing options

2. **`src/stl_processor/batch_queue/enhanced_job_manager.py`**:
   - `reset_all_jobs()` - new method for restart functionality
   - `add_jobs_from_files()` - support processing options parameter

3. **`src/stl_processor/user_config.py`**:
   - Add keys for saving checkbox preferences

4. **`src/stl_processor/batch_queue/job_types_v2.py`**:
   - Extend job options to support conditional processing

## Success Criteria

1. ✅ Batch Queue tab appears first and is active by default
2. ✅ Restart button successfully resets all jobs to pending
3. ✅ Image Rendering checkbox controls image generation
4. ✅ Video Rendering checkbox controls video generation  
5. ✅ Analysis and Validation always run regardless of checkboxes
6. ✅ User preferences persist across application sessions
7. ✅ UI provides clear feedback for all operations

## Future Enhancements

- **Template Saving**: Save processing option combinations as templates
- **Batch Configuration**: Per-job custom settings
- **Progress Indicators**: Show which processes are running per job
- **Results Preview**: Quick preview of generated files in the queue tab