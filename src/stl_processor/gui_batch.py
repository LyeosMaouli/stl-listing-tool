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
        self.update_timer = None
        
        # Batch-specific UI components
        self.job_tree = None
        self.progress_bars = {}
        self.control_buttons = {}
        
        # Initialize parent GUI
        super().__init__(root)
        
        # Override title
        self.root.title("STL Listing Tool - Batch Processing")
        
        # Always initialize batch mode
        self.initialize_batch_mode()
    
    def setup_ui(self):
        """Override to add batch processing UI elements."""
        self.create_enhanced_menu()  # Enhanced menu with queue options
        self.create_main_frame()
        self.create_drag_drop_area()  # Drag and drop for batch processing
        self.create_notebook()
        self.create_status_bar()
    
    def create_enhanced_menu(self):
        """Create enhanced menu with batch processing options."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu with batch options
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open STL...", command=self.browse_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Add Files to Queue...", command=self.add_files_to_queue, accelerator="Ctrl+Shift+A")
        file_menu.add_command(label="Add Folder to Queue...", command=self.add_folder_to_queue, accelerator="Ctrl+Shift+F")
        file_menu.add_separator()
        file_menu.add_command(label="Clear Queue", command=self.clear_queue)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing, accelerator="Ctrl+Q")
        
        # Queue menu (new)
        self.queue_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Queue", menu=self.queue_menu)
        self.queue_menu.add_command(label="Start Processing", command=self.start_processing)
        self.queue_menu.add_command(label="Pause All Jobs", command=self.pause_processing)
        self.queue_menu.add_command(label="Resume All Jobs", command=self.resume_processing)
        self.queue_menu.add_command(label="Stop All Jobs", command=self.stop_processing)
        self.queue_menu.add_separator()
        self.queue_menu.add_command(label="Clear Completed Jobs", command=self.clear_completed)
        self.queue_menu.add_command(label="Retry Failed Jobs", command=self.retry_failed)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Batch Processing Guide", command=self.show_batch_help)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.browse_file())
        self.root.bind('<Control-q>', lambda e: self.on_closing())
        self.root.bind('<Control-Shift-A>', lambda e: self.add_files_to_queue())
        self.root.bind('<Control-Shift-F>', lambda e: self.add_folder_to_queue())
        self.root.bind('<space>', lambda e: self.toggle_pause_resume())
        self.root.bind('<F5>', lambda e: self.refresh_queue_status())
    
    def create_drag_drop_area(self):
        """Create drag and drop area for batch processing."""
        drop_frame = ttk.LabelFrame(self.main_frame, text="File Selection", padding="10")
        drop_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        drop_frame.columnconfigure(0, weight=1)
        
        # Create main drop area
        self.drop_area = tk.Label(drop_frame, text="Drop STL files or folders here", 
                                 bg="lightblue", fg="darkblue", 
                                 border=2, relief="ridge", height=4,
                                 font=('TkDefaultFont', 12, 'bold'))
        self.drop_area.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Button frame for browse options
        button_frame = ttk.Frame(drop_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Browse buttons
        ttk.Button(button_frame, text="Browse Files...", 
                  command=self.add_files_to_queue).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Browse Folder...", 
                  command=self.add_folder_to_queue).grid(row=0, column=1)
        
        # Status display
        self.file_status_var = tk.StringVar(value="Ready to process STL files")
        ttk.Label(drop_frame, textvariable=self.file_status_var, 
                 foreground="gray").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        
        # Setup drag and drop functionality
        self.setup_batch_drag_drop()
    
    def initialize_batch_mode(self):
        """Initialize batch processing mode."""
        logger.info("Initializing batch processing mode")
        
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
                return
        
        # Add batch queue tab
        self.create_batch_queue_tab()
        
        # Start update timer
        self.start_update_timer()
    
    def setup_batch_drag_drop(self):
        """Setup drag and drop functionality for batch processing."""
        def on_drop(event):
            files = self.root.tk.splitlist(event.data)
            if files:
                self.process_dropped_files(files)
                
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            
            # Try to initialize tkinterdnd2 properly
            try:
                # Make sure the root window is ready for DnD
                TkinterDnD.TkinterDnD(self.root)._init()
            except:
                # If that fails, try the direct approach
                pass
            
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind('<<Drop>>', on_drop)
            self.dnd_available = True
            logger.info("Drag-and-drop functionality enabled")

        except (ImportError, Exception) as e:
            self.dnd_available = False
            if isinstance(e, ImportError):
                logger.warning("Drag-and-drop not available. Install tkinterdnd2 for full GUI functionality.")
            else:
                logger.warning(f"Drag-and-drop initialization failed: {e}")
                logger.info("This is common on some Windows systems. Using browse buttons instead.")
            
            # Update drop area to show drag-and-drop is unavailable
            self.drop_area.config(
                text="Drag-and-drop unavailable\nUse Browse buttons instead",
                bg="lightyellow",
                fg="darkgray"
            )
    
    def process_dropped_files(self, files):
        """Process files/folders dropped onto the interface."""
        try:
            stl_files = []
            folders = []
            
            for file_path_str in files:
                file_path = Path(file_path_str)
                
                if file_path.is_file() and file_path.suffix.lower() == '.stl':
                    stl_files.append(file_path)
                elif file_path.is_dir():
                    folders.append(file_path)
                    # Recursively find STL files in folders
                    stl_files.extend(list(file_path.rglob("*.stl")))
            
            if stl_files:
                self.add_files_to_batch_queue(stl_files)
            elif folders:
                messagebox.showinfo("No STL Files", 
                                   f"No STL files found in the dropped folders")
            else:
                messagebox.showwarning("Invalid Files", 
                                      "Please drop STL files or folders containing STL files")
                                      
        except Exception as e:
            logger.error(f"Error processing dropped files: {e}")
            show_error_with_logging(
                self.root, "Drop Error",
                f"Error processing dropped files: {e}",
                exception=e
            )
    
    def add_files_to_batch_queue(self, stl_files):
        """Add STL files to the batch processing queue."""
        try:
            if not self.job_manager:
                logger.error("Job manager not initialized")
                return
            
            # Create output directory
            output_dir = Path.cwd() / "stl_processing_output"
            output_dir.mkdir(exist_ok=True)
            
            # Add jobs to queue
            job_ids = self.job_manager.add_jobs_from_files(
                stl_files, output_dir, job_type="render"
            )
            
            logger.info(f"Added {len(job_ids)} jobs to queue")
            
            # Update status
            self.file_status_var.set(f"Added {len(stl_files)} STL files to queue")
            
            messagebox.showinfo(
                "Files Added", 
                f"Added {len(stl_files)} STL files to batch queue"
            )
            
        except Exception as e:
            logger.error(f"Error adding files to queue: {e}")
            show_error_with_logging(
                self.root, "Queue Error",
                f"Error adding files to batch queue: {e}",
                exception=e
            )
    
    
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
            
            # Add files to queue
            self.add_files_to_batch_queue(stl_files)
            
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
        """Override to adjust grid position for drag-drop area."""
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
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
        if self.job_manager:
            try:
                summary = self.job_manager.get_queue_summary()
                self._update_queue_display(summary)
            except Exception as e:
                logger.error(f"Error in periodic update: {e}")
        
        # Schedule next update
        self.update_timer = self.root.after(1000, self.update_gui)
    
    # Menu command methods
    def add_files_to_queue(self):
        """Add files to queue via file dialog."""
        filetypes = [
            ("STL files", "*.stl"),
            ("All files", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            title="Select STL files to add to queue",
            filetypes=filetypes
        )
        
        if files:
            try:
                stl_files = [Path(f) for f in files]
                self.add_files_to_batch_queue(stl_files)
            except Exception as e:
                show_error_with_logging(
                    self.root, "Error Adding Files",
                    f"Error adding files to queue: {e}",
                    exception=e
                )
    
    def add_folder_to_queue(self):
        """Add folder to queue (same as existing browse_folder)."""
        self.browse_folder()
    
    def clear_queue(self):
        """Clear all jobs from queue."""
        if self.job_manager:
            try:
                count = self.job_manager.clear_all_jobs()
                if count > 0:
                    messagebox.showinfo("Queue Cleared", f"Removed {count} jobs from queue")
                else:
                    messagebox.showinfo("Queue Empty", "No jobs to clear")
            except Exception as e:
                show_error_with_logging(
                    self.root, "Error Clearing Queue",
                    f"Error clearing queue: {e}",
                    exception=e
                )
    
    def resume_processing(self):
        """Resume paused processing."""
        if self.job_manager and self.job_manager.is_paused:
            try:
                self.job_manager.resume_processing()
                logger.info("Processing resumed from menu")
            except Exception as e:
                show_error_with_logging(
                    self.root, "Error Resuming",
                    f"Error resuming processing: {e}",
                    exception=e
                )
    
    def retry_failed(self):
        """Retry failed jobs."""
        if self.job_manager:
            try:
                # This would need to be implemented in the job manager
                messagebox.showinfo("Not Implemented", "Retry failed jobs feature coming soon")
            except Exception as e:
                logger.error(f"Error retrying failed jobs: {e}")
    
    def show_batch_help(self):
        """Show batch processing help dialog."""
        help_text = """
STL Listing Tool - Batch Processing Guide

GETTING STARTED:
1. Switch to Batch Processing mode using the radio button
2. Add files: File → Add Files to Queue or Add Folder to Queue  
3. Configure processing options in the Queue Setup tab
4. Start processing: Queue → Start Processing

QUEUE OPERATIONS:
• Start/Pause/Stop: Control processing from Queue menu or buttons
• Clear Completed: Remove finished jobs to keep queue clean
• Job Status: View progress in the Batch Queue tab

KEYBOARD SHORTCUTS:
• Ctrl+Shift+A: Add files to queue
• Ctrl+Shift+F: Add folder to queue
• Space: Pause/Resume processing
• F5: Refresh queue status

OUTPUT ORGANIZATION:
Each STL file gets its own subfolder with:
• renders/ - Generated images and videos
• analysis/ - Dimension and validation reports
• logs/ - Processing logs and errors

For more help, see the documentation or contact support.
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Batch Processing Guide")
        help_window.geometry("600x500")
        help_window.transient(self.root)
        help_window.grab_set()
        
        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=20, pady=20)
        scrollbar = ttk.Scrollbar(help_window, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.insert("1.0", help_text)
        text_widget.config(state="disabled")
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def toggle_pause_resume(self):
        """Toggle between pause and resume (Space key)."""
        if self.job_manager:
            if self.job_manager.is_running:
                if self.job_manager.is_paused:
                    self.resume_processing()
                else:
                    self.pause_processing()
    
    def refresh_queue_status(self):
        """Refresh queue display (F5 key)."""
        if self.job_manager:
            try:
                summary = self.job_manager.get_queue_summary()
                self._update_queue_display(summary)
            except Exception as e:
                logger.error(f"Error refreshing queue status: {e}")
    
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