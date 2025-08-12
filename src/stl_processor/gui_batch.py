"""
Enhanced GUI with batch processing integration.
Extends the existing GUI with queue management capabilities.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import time
from typing import Optional, Dict, Any, List
import os

# Import existing GUI base  
from .gui import STLProcessorGUI, show_error_with_logging, CORE_MODULES_AVAILABLE, RENDERING_MODULES_AVAILABLE

# Import batch processing system
from .batch_queue.enhanced_job_manager import EnhancedJobManager
from .batch_queue.job_types_v2 import Job, JobStatus, JobResult, JobError

from .utils.logger import setup_logger

logger = setup_logger("stl_processor_batch_gui")


class BatchProcessingGUI(STLProcessorGUI):
    """Enhanced GUI with batch processing capabilities."""
    
    def __init__(self, root):
        # Initialize job manager
        self.job_manager = None
        self.batch_mode = False
        self.update_timer = None
        
        # Batch-specific UI components
        self.mode_var = None
        self.batch_frame = None
        self.job_tree = None
        self.progress_bars = {}
        self.control_buttons = {}
        
        # Initialize parent GUI
        super().__init__(root)
        
        # Override title
        self.root.title("STL Listing Tool")
    
    def setup_ui(self):
        """Override to add batch processing UI elements."""
        self.create_menu()
        self.create_main_frame()
        self.create_mode_selector()  # New: Mode selector
        self.create_file_selection()
        self.create_notebook()
        self.create_status_bar()
    
    def create_mode_selector(self):
        """Create mode selector to toggle between single file and batch processing."""
        mode_frame = ttk.LabelFrame(self.main_frame, text="Processing Mode", padding="10")
        mode_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        mode_frame.columnconfigure(1, weight=1)
        
        self.mode_var = tk.StringVar(value="single")
        
        ttk.Radiobutton(
            mode_frame, text="Single File Processing", 
            variable=self.mode_var, value="single",
            command=self.on_mode_change
        ).grid(row=0, column=0, padx=(0, 20), sticky=tk.W)
        
        ttk.Radiobutton(
            mode_frame, text="Batch Processing", 
            variable=self.mode_var, value="batch",
            command=self.on_mode_change
        ).grid(row=0, column=1, sticky=tk.W)
        
        # Info label
        self.mode_info_var = tk.StringVar(value="Process one STL file at a time")
        ttk.Label(mode_frame, textvariable=self.mode_info_var, 
                 foreground="gray").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
    
    def on_mode_change(self):
        """Handle mode change between single and batch processing."""
        new_mode = self.mode_var.get()
        
        if new_mode == "batch" and not self.batch_mode:
            self.switch_to_batch_mode()
        elif new_mode == "single" and self.batch_mode:
            self.switch_to_single_mode()
    
    def switch_to_batch_mode(self):
        """Switch to batch processing mode."""
        logger.info("Switching to batch processing mode")
        self.batch_mode = True
        
        # Update mode info
        self.mode_info_var.set("Process multiple STL files in a queue with advanced options")
        
        # Initialize job manager
        if self.job_manager is None:
            try:
                state_dir = Path.cwd() / "batch_queue_state"
                self.job_manager = EnhancedJobManager(
                    max_workers=2,
                    state_dir=state_dir,
                    auto_save=True,
                    enable_recovery=True
                )
                
                # Setup job manager observers
                self.job_manager.add_observer("state", self.on_queue_state_changed)
                self.job_manager.add_observer("job", self.on_job_changed)
                
                logger.info("Job manager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize job manager: {e}")
                show_error_with_logging(
                    self.root, "Initialization Error",
                    f"Failed to initialize batch processing system: {e}",
                    exception=e
                )
                self.mode_var.set("single")
                return
        
        # Add batch queue tab
        self.create_batch_queue_tab()
        
        # Update file selection for batch mode
        self.update_file_selection_for_batch()
        
        # Start update timer
        self.start_update_timer()
    
    def switch_to_single_mode(self):
        """Switch to single file processing mode."""
        logger.info("Switching to single file processing mode")
        self.batch_mode = False
        
        # Update mode info
        self.mode_info_var.set("Process one STL file at a time")
        
        # Stop update timer
        self.stop_update_timer()
        
        # Remove batch queue tab if it exists
        if hasattr(self, 'batch_tab'):
            try:
                self.notebook.forget(self.batch_tab)
            except:
                pass
        
        # Restore original file selection
        self.update_file_selection_for_single()
        
        # Stop job manager if running
        if self.job_manager and self.job_manager.is_running:
            self.job_manager.stop_processing()
    
    def create_file_selection(self):
        """Override to support both single and batch file selection."""
        file_frame = ttk.LabelFrame(self.main_frame, text="File Selection", padding="10")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        self.file_var = tk.StringVar(value="No file selected")
        
        # Create button frame
        button_frame = ttk.Frame(file_frame)
        button_frame.grid(row=0, column=0, padx=(0, 10))
        
        # Single file browse button
        self.single_browse_btn = ttk.Button(button_frame, text="Browse File...", command=self.browse_file)
        self.single_browse_btn.grid(row=0, column=0, pady=(0, 5))
        
        # Batch folder browse button
        self.batch_browse_btn = ttk.Button(button_frame, text="Browse Folder...", command=self.browse_folder)
        self.batch_browse_btn.grid(row=1, column=0)
        
        # File/folder display
        file_label = ttk.Label(file_frame, textvariable=self.file_var, background="white", 
                              relief="sunken", padding="5")
        file_label.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # Initially show single mode
        self.update_file_selection_for_single()
    
    def update_file_selection_for_single(self):
        """Update file selection UI for single file mode."""
        self.single_browse_btn.grid()
        self.batch_browse_btn.grid_remove()
        
    def update_file_selection_for_batch(self):
        """Update file selection UI for batch mode."""
        self.single_browse_btn.grid_remove()
        self.batch_browse_btn.grid()
    
    def setup_drag_drop(self):
        """Drag and drop disabled for this GUI."""
        # Drag and drop functionality completely removed
        pass
    
    def browse_folder(self):
        """Browse for folder containing STL files."""
        folder_path = filedialog.askdirectory(
            title="Select folder containing STL files"
        )
        
        if folder_path:
            self.load_batch_folder(Path(folder_path))
    
    def load_batch_folder(self, folder_path: Path):
        """Load STL files from a folder for batch processing."""
        try:
            # Scan for STL files
            stl_files = list(folder_path.rglob("*.stl"))
            
            if not stl_files:
                messagebox.showinfo("No STL Files", f"No STL files found in {folder_path}")
                return
            
            # Update file display
            self.file_var.set(f"{folder_path} ({len(stl_files)} STL files found)")
            
            # Create output directory
            output_dir = folder_path / "stl_processing_output"
            output_dir.mkdir(exist_ok=True)
            
            # Add jobs to queue
            if self.job_manager:
                job_ids = self.job_manager.add_jobs_from_files(
                    stl_files, output_dir, job_type="render"
                )
                logger.info(f"Added {len(job_ids)} jobs to queue")
                
                messagebox.showinfo(
                    "Files Added", 
                    f"Added {len(stl_files)} STL files to batch queue"
                )
            
        except Exception as e:
            logger.error(f"Error loading batch folder: {e}")
            show_error_with_logging(
                self.root, "Folder Loading Error",
                f"Error loading STL files from folder: {e}",
                exception=e
            )
    
    def create_batch_queue_tab(self):
        """Create the batch queue management tab."""
        self.batch_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.batch_tab, text="Batch Queue")
        
        self.batch_tab.columnconfigure(0, weight=1)
        self.batch_tab.rowconfigure(1, weight=1)
        
        # Control panel
        self.create_queue_controls()
        
        # Job list
        self.create_job_list()
        
        # Progress panel
        self.create_progress_panel()
    
    def create_queue_controls(self):
        """Create queue control buttons."""
        control_frame = ttk.LabelFrame(self.batch_tab, text="Queue Controls", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Control buttons
        self.control_buttons['start'] = ttk.Button(
            control_frame, text="Start Processing", 
            command=self.start_processing
        )
        self.control_buttons['start'].grid(row=0, column=0, padx=(0, 5))
        
        self.control_buttons['pause'] = ttk.Button(
            control_frame, text="Pause", 
            command=self.pause_processing, state="disabled"
        )
        self.control_buttons['pause'].grid(row=0, column=1, padx=5)
        
        self.control_buttons['stop'] = ttk.Button(
            control_frame, text="Stop", 
            command=self.stop_processing, state="disabled"
        )
        self.control_buttons['stop'].grid(row=0, column=2, padx=5)
        
        self.control_buttons['clear'] = ttk.Button(
            control_frame, text="Clear Completed", 
            command=self.clear_completed
        )
        self.control_buttons['clear'].grid(row=0, column=3, padx=(5, 0))
        
        # Queue info
        self.queue_info_var = tk.StringVar(value="Queue empty")
        ttk.Label(control_frame, textvariable=self.queue_info_var).grid(
            row=1, column=0, columnspan=4, sticky=tk.W, pady=(10, 0)
        )
    
    def create_job_list(self):
        """Create job list with treeview."""
        list_frame = ttk.LabelFrame(self.batch_tab, text="Job Queue", padding="10")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Create treeview
        columns = ("file", "status", "progress", "type")
        self.job_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        
        # Configure columns
        self.job_tree.heading("file", text="File")
        self.job_tree.heading("status", text="Status")
        self.job_tree.heading("progress", text="Progress")
        self.job_tree.heading("type", text="Type")
        
        self.job_tree.column("file", width=300, minwidth=200)
        self.job_tree.column("status", width=100, minwidth=80)
        self.job_tree.column("progress", width=100, minwidth=80)
        self.job_tree.column("type", width=100, minwidth=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.job_tree.yview)
        self.job_tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid layout
        self.job_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    def create_progress_panel(self):
        """Create overall progress panel."""
        progress_frame = ttk.LabelFrame(self.batch_tab, text="Overall Progress", padding="10")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        # Overall progress bar
        self.overall_progress = ttk.Progressbar(
            progress_frame, mode='determinate', length=400
        )
        self.overall_progress.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Progress text
        self.progress_text_var = tk.StringVar(value="Ready to process")
        ttk.Label(progress_frame, textvariable=self.progress_text_var).grid(
            row=1, column=0, sticky=tk.W
        )
    
    def create_notebook(self):
        """Override to adjust grid position for mode selector."""
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.create_analysis_tab()
        self.create_validation_tab() 
        self.create_rendering_tab()
    
    # Queue control methods
    def start_processing(self):
        """Start batch processing."""
        if not self.job_manager:
            return
            
        try:
            success = self.job_manager.start_processing()
            if success:
                self.control_buttons['start'].config(state="disabled")
                self.control_buttons['pause'].config(state="normal")
                self.control_buttons['stop'].config(state="normal")
                logger.info("Batch processing started")
            else:
                messagebox.showwarning("Cannot Start", "No jobs in queue or processing already running")
        except Exception as e:
            logger.error(f"Error starting processing: {e}")
            show_error_with_logging(
                self.root, "Processing Error",
                f"Error starting batch processing: {e}",
                exception=e
            )
    
    def pause_processing(self):
        """Pause batch processing."""
        if not self.job_manager:
            return
            
        try:
            if self.job_manager.is_paused:
                # Resume
                self.job_manager.resume_processing()
                self.control_buttons['pause'].config(text="Pause")
                logger.info("Batch processing resumed")
            else:
                # Pause
                self.job_manager.pause_processing()
                self.control_buttons['pause'].config(text="Resume")
                logger.info("Batch processing paused")
        except Exception as e:
            logger.error(f"Error pausing/resuming processing: {e}")
    
    def stop_processing(self):
        """Stop batch processing."""
        if not self.job_manager:
            return
            
        try:
            self.job_manager.stop_processing()
            self.control_buttons['start'].config(state="normal")
            self.control_buttons['pause'].config(state="disabled", text="Pause")
            self.control_buttons['stop'].config(state="disabled")
            logger.info("Batch processing stopped")
        except Exception as e:
            logger.error(f"Error stopping processing: {e}")
    
    def clear_completed(self):
        """Clear completed jobs from queue."""
        if not self.job_manager:
            return
            
        try:
            count = self.job_manager.clear_completed_jobs()
            if count > 0:
                logger.info(f"Cleared {count} completed jobs")
            else:
                messagebox.showinfo("No Jobs", "No completed jobs to clear")
        except Exception as e:
            logger.error(f"Error clearing completed jobs: {e}")
    
    # Observer callbacks
    def on_queue_state_changed(self, summary: Dict[str, Any]):
        """Handle queue state changes."""
        # Schedule UI update on main thread
        self.root.after(0, self._update_queue_display, summary)
    
    def on_job_changed(self, event_type: str, job):
        """Handle individual job changes."""
        # Schedule UI update on main thread
        self.root.after(0, self._update_job_display, event_type, job)
    
    def _update_queue_display(self, summary: Dict[str, Any]):
        """Update queue display (runs on main thread)."""
        try:
            # Update queue info
            total = summary.get('total_jobs', 0)
            pending = summary.get('pending_jobs', 0)
            running = summary.get('running_jobs', 0)
            completed = summary.get('completed_jobs', 0)
            failed = summary.get('failed_jobs', 0)
            
            if total == 0:
                info_text = "Queue empty"
                progress_text = "Ready to process"
                progress_value = 0
            else:
                info_text = f"Total: {total}, Pending: {pending}, Running: {running}, Completed: {completed}, Failed: {failed}"
                progress_text = f"Processing: {completed}/{total} completed"
                progress_value = (completed / total) * 100 if total > 0 else 0
            
            self.queue_info_var.set(info_text)
            self.progress_text_var.set(progress_text)
            self.overall_progress['value'] = progress_value
            
            # Update control button states
            is_running = summary.get('is_running', False)
            is_paused = summary.get('is_paused', False)
            
            if is_running:
                self.control_buttons['start'].config(state="disabled")
                self.control_buttons['pause'].config(state="normal")
                self.control_buttons['stop'].config(state="normal")
                
                if is_paused:
                    self.control_buttons['pause'].config(text="Resume")
                else:
                    self.control_buttons['pause'].config(text="Pause")
            else:
                self.control_buttons['start'].config(state="normal")
                self.control_buttons['pause'].config(state="disabled", text="Pause")
                self.control_buttons['stop'].config(state="disabled")
                
        except Exception as e:
            logger.error(f"Error updating queue display: {e}")
    
    def _update_job_display(self, event_type: str, job):
        """Update individual job display (runs on main thread)."""
        try:
            # Find or create job item in tree
            job_id = job.id
            file_name = Path(job.input_file).name
            status = job.status.value
            job_type = job.job_type
            
            # Find existing item
            existing_item = None
            for item in self.job_tree.get_children():
                if self.job_tree.item(item)['values'][0] == file_name:
                    existing_item = item
                    break
            
            if existing_item:
                # Update existing item
                self.job_tree.item(existing_item, values=(file_name, status, "0%", job_type))
            else:
                # Add new item
                self.job_tree.insert("", "end", values=(file_name, status, "0%", job_type))
                
        except Exception as e:
            logger.error(f"Error updating job display: {e}")
    
    # Timer methods
    def start_update_timer(self):
        """Start periodic UI updates."""
        self.update_gui()
    
    def stop_update_timer(self):
        """Stop periodic UI updates."""
        if self.update_timer:
            self.root.after_cancel(self.update_timer)
            self.update_timer = None
    
    def update_gui(self):
        """Periodic GUI update."""
        if self.batch_mode and self.job_manager:
            try:
                summary = self.job_manager.get_queue_summary()
                self._update_queue_display(summary)
            except Exception as e:
                logger.error(f"Error in periodic update: {e}")
        
        # Schedule next update
        if self.batch_mode:
            self.update_timer = self.root.after(1000, self.update_gui)
    
    def on_closing(self):
        """Handle window closing."""
        # Stop job manager if running
        if self.job_manager:
            try:
                if self.job_manager.is_running:
                    response = messagebox.askyesno(
                        "Jobs Running",
                        "Batch processing is currently running. Stop and exit?"
                    )
                    if not response:
                        return
                
                self.job_manager.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down job manager: {e}")
        
        # Stop timer
        self.stop_update_timer()
        
        # Call parent close handler
        try:
            super().on_closing()
        except AttributeError:
            # Parent may not have on_closing method
            self.root.destroy()


def main():
    """Main function to run the batch-enabled GUI."""
    try:
        root = tk.Tk()
        app = BatchProcessingGUI(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()