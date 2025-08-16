"""
Unified STL Listing Tool GUI with batch processing capabilities.
Dedicated to batch processing of STL files with drag-and-drop support.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import threading
import time
import json
from typing import Optional, Dict, Any, List
import os
import tempfile

# Use relative imports for package structure
try:
    from .core.stl_processor import STLProcessor
    from .core.dimension_extractor import DimensionExtractor
    from .core.mesh_validator import MeshValidator, ValidationLevel
    CORE_MODULES_AVAILABLE = True
    CORE_IMPORT_ERROR = None
except ImportError as e:
    CORE_MODULES_AVAILABLE = False
    CORE_IMPORT_ERROR = e

try:
    from .rendering.vtk_renderer import VTKRenderer
    from .rendering.base_renderer import MaterialType, LightingPreset
    RENDERING_MODULES_AVAILABLE = True
    RENDERING_IMPORT_ERROR = None
except ImportError as e:
    RENDERING_MODULES_AVAILABLE = False
    RENDERING_IMPORT_ERROR = e

from .utils.logger import setup_logger
from .error_dialog import show_comprehensive_error
from .user_config import get_user_config

# Import generators with fallback
try:
    from .generators.video_generator import RotationVideoGenerator, VideoFormat, VideoQuality
    from .generators.image_generator import ColorVariationGenerator, GridLayout
    GENERATORS_AVAILABLE = True
    GENERATORS_IMPORT_ERROR = None
except ImportError as e:
    GENERATORS_AVAILABLE = False
    GENERATORS_IMPORT_ERROR = e

# Import batch processing system
from .batch_queue.enhanced_job_manager import EnhancedJobManager
from .batch_queue.job_types_v2 import Job, JobStatus, JobResult, JobError

logger = setup_logger("stl_processor_gui")


class ColorVariationDialog:
    """Dialog for selecting color variations for grid generation."""
    
    def __init__(self, parent):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Color Variations")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog on parent
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        self.create_widgets()
        self.dialog.wait_window()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Select Color Variations:", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Predefined color variations
        self.color_vars = []
        colors = [
            {"name": "White Plastic", "material": "plastic", "color": (0.9, 0.9, 0.9)},
            {"name": "Black Plastic", "material": "plastic", "color": (0.1, 0.1, 0.1)},
            {"name": "Red Plastic", "material": "plastic", "color": (0.8, 0.2, 0.2)},
            {"name": "Blue Plastic", "material": "plastic", "color": (0.2, 0.4, 0.8)},
            {"name": "Green Plastic", "material": "plastic", "color": (0.2, 0.7, 0.3)},
            {"name": "Silver Metal", "material": "metal", "color": (0.8, 0.8, 0.9)},
            {"name": "Gold Metal", "material": "metal", "color": (0.9, 0.8, 0.4)},
            {"name": "Clear Resin", "material": "resin", "color": (0.9, 0.9, 1.0)}
        ]
        
        for color_info in colors:
            var = tk.BooleanVar()
            self.color_vars.append((var, color_info))
            ttk.Checkbutton(main_frame, text=color_info["name"], variable=var).pack(anchor=tk.W, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Generate", command=self.accept).pack(side=tk.RIGHT)
    
    def accept(self):
        selected_colors = []
        for var, color_info in self.color_vars:
            if var.get():
                selected_colors.append(color_info)
        
        if not selected_colors:
            messagebox.showwarning("Warning", "Please select at least one color variation.")
            return
        
        self.result = selected_colors
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


def show_error_with_logging(parent, title, message, exception=None, context=None):
    """Wrapper for show_comprehensive_error that adds debugging logs and fixes image path bugs."""
    logger.info(f"=== ERROR DIALOG CALLED ===")
    logger.info(f"Title: {title}")
    logger.info(f"Message: {message}")
    logger.info(f"Exception: {exception}")
    logger.info(f"Context keys: {list(context.keys()) if context else None}")
    
    # Fix: Check if message IS an image path and fix it
    original_message = message
    if str(message).strip().startswith('/tmp/images/') or (len(str(message)) < 200 and '/tmp/images/' in str(message)):
        logger.error(f"CRITICAL BUG DETECTED: Error message is an image path! Original: {message}")
        logger.error(f"This indicates a bug where an image path was passed as error message")
        
        # Generate a better error message
        fixed_message = f"An error occurred during rendering or image processing. The system attempted to save or access an image file, but the operation failed."
        
        # Add the path to context instead
        if context is None:
            context = {}
        context['detected_image_path'] = str(message)
        context['error_message_fix_applied'] = 'Image path was incorrectly passed as error message'
        
        message = fixed_message
        logger.info(f"Fixed error message: {message}")
    
    # Check if exception string contains image path
    if exception and '/tmp/images/' in str(exception):
        logger.error(f"CRITICAL: Exception contains image path! Exception: {exception}")
    
    # Check context for image paths (this is normal/expected)
    if context:
        for key, value in context.items():
            if '/tmp/images/' in str(value):
                logger.info(f"Context key '{key}' contains image path: {value} (this may be normal)")
    
    if original_message != message:
        logger.info(f"Applied error message fix: '{original_message}' -> '{message}'")
    
    logger.info(f"=== END ERROR DIALOG INFO ===")
    
    # Call the actual error dialog
    show_comprehensive_error(parent, title, message, exception, context)


class STLProcessorGUI:
    """Unified STL Listing Tool GUI with batch processing capabilities."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("STL Listing Tool - Batch Processing")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        self.current_file = None
        self.processor = None
        self.analysis_results = None
        
        # Batch processing components
        self.job_manager = None
        self.update_timer = None
        self.job_tree = None
        self.progress_bars = {}
        self.control_buttons = {}
        
        # Initialize user config
        self.user_config = get_user_config()
        
        self.setup_ui()
        self.load_user_settings()
        
        # Always initialize batch mode
        self.initialize_batch_mode()
        
        # Save window geometry on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def initialize_batch_mode(self):
        """Initialize batch processing mode."""
        logger.info("Initializing batch processing mode")
        
        # Initialize job manager
        if self.job_manager is None:
            try:
                # Use user data directory with write permissions
                import tempfile
                import os
                
                # Try user's local app data directory first
                if os.name == 'nt':  # Windows
                    state_dir = Path.home() / "AppData" / "Local" / "stl_listing_tool" / "batch_queue_state"
                else:  # Unix/Linux/Mac
                    state_dir = Path.home() / ".local" / "share" / "stl_listing_tool" / "batch_queue_state"
                
                # Fallback to temp directory if home directory fails
                try:
                    state_dir.parent.mkdir(parents=True, exist_ok=True)
                except (OSError, PermissionError):
                    state_dir = Path(tempfile.gettempdir()) / "stl_listing_tool" / "batch_queue_state"
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
        
        # Start update timer
        self.start_update_timer()
    
    def load_user_settings(self):
        """Load saved user settings from config file."""
        try:
            # Load validation settings
            if hasattr(self, 'validation_level'):
                saved_level = self.user_config.get('validation_level', 'standard')
                self.validation_level.set(saved_level)
            
            if hasattr(self, 'repair_var'):
                saved_repair = self.user_config.get('auto_repair', False)
                self.repair_var.set(saved_repair)
            
            # Load rendering settings
            if hasattr(self, 'material_var'):
                saved_material = self.user_config.get('render_material', 'plastic')
                self.material_var.set(saved_material)
            
            if hasattr(self, 'lighting_var'):
                saved_lighting = self.user_config.get('render_lighting', 'studio')
                self.lighting_var.set(saved_lighting)
            
            if hasattr(self, 'width_var'):
                saved_width = self.user_config.get('render_width', '1920')
                self.width_var.set(str(saved_width))
            
            if hasattr(self, 'height_var'):
                saved_height = self.user_config.get('render_height', '1080')
                self.height_var.set(str(saved_height))
            
            # Load background image path
            saved_background = self.user_config.get('background_image_path')
            if saved_background and Path(saved_background).exists():
                self.background_path = Path(saved_background)
                filename = self.background_path.name
                if len(filename) > 40:
                    filename = filename[:37] + "..."
                self.background_var.set(f"Selected: {filename}")
                if hasattr(self, 'update_background_preview'):
                    self.update_background_preview()
            
            # Load window geometry
            saved_geometry = self.user_config.get('window_geometry')
            if saved_geometry:
                self.root.geometry(saved_geometry)
            
            # Load generator settings
            if hasattr(self, 'video_format_var'):
                saved_video_format = self.user_config.get('video_format', 'mp4')
                self.video_format_var.set(saved_video_format)
            
            if hasattr(self, 'video_quality_var'):
                saved_video_quality = self.user_config.get('video_quality', 'standard')
                self.video_quality_var.set(saved_video_quality)
            
            if hasattr(self, 'video_duration_var'):
                saved_video_duration = self.user_config.get('video_duration', '8')
                self.video_duration_var.set(str(saved_video_duration))
            
            if hasattr(self, 'grid_layout_var'):
                saved_grid_layout = self.user_config.get('grid_layout', 'auto')
                self.grid_layout_var.set(saved_grid_layout)
            
            logger.info("User settings loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading user settings: {e}")
    
    def save_setting(self, key: str, value: Any):
        """Save a single setting to user config."""
        try:
            self.user_config.set(key, value, auto_save=True)
        except Exception as e:
            logger.error(f"Error saving setting {key}={value}: {e}")
    
    def on_validation_level_changed(self, *args):
        """Called when validation level changes."""
        self.save_setting('validation_level', self.validation_level.get())
    
    def on_repair_var_changed(self):
        """Called when auto repair checkbox changes."""
        self.save_setting('auto_repair', self.repair_var.get())
    
    def on_material_changed(self, *args):
        """Called when material selection changes."""
        self.save_setting('render_material', self.material_var.get())
    
    def on_lighting_changed(self, *args):
        """Called when lighting selection changes."""
        self.save_setting('render_lighting', self.lighting_var.get())
    
    def on_width_changed(self, *args):
        """Called when render width changes."""
        try:
            width = int(self.width_var.get())
            self.save_setting('render_width', width)
        except ValueError:
            pass  # Invalid input, don't save
    
    def on_height_changed(self, *args):
        """Called when render height changes."""
        try:
            height = int(self.height_var.get())
            self.save_setting('render_height', height)
        except ValueError:
            pass  # Invalid input, don't save
    
    def save_window_geometry(self):
        """Save current window geometry."""
        try:
            geometry = self.root.geometry()
            self.save_setting('window_geometry', geometry)
        except Exception as e:
            logger.error(f"Error saving window geometry: {e}")
    
    def on_closing(self):
        """Handle window closing event."""
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
        
        # Save window geometry before closing
        self.save_window_geometry()
        # Close the application
        self.root.destroy()
    
    def setup_ui(self):
        """Setup the user interface."""
        self.create_enhanced_menu()
        self.create_main_frame()
        self.create_drag_drop_area()
        self.create_notebook()
        self.create_status_bar()
    
    def create_enhanced_menu(self):
        """Create enhanced menu with batch processing options."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu with batch options
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Add Files to Queue...", command=self.add_files_to_queue, accelerator="Ctrl+Shift+A")
        file_menu.add_command(label="Add Folder to Queue...", command=self.add_folder_to_queue, accelerator="Ctrl+Shift+F")
        file_menu.add_separator()
        file_menu.add_command(label="Clear Queue", command=self.clear_queue)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing, accelerator="Ctrl+Q")
        
        # Queue menu
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
        self.root.bind('<Control-q>', lambda e: self.on_closing())
        self.root.bind('<Control-Shift-A>', lambda e: self.add_files_to_queue())
        self.root.bind('<Control-Shift-F>', lambda e: self.add_folder_to_queue())
        self.root.bind('<space>', lambda e: self.toggle_pause_resume())
        self.root.bind('<F5>', lambda e: self.refresh_queue_status())
    
    def create_main_frame(self):
        """Create the main application frame."""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
    
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
                text="Drag-and-drop unavailable\\nUse Browse buttons instead",
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
        """Add STL files to batch queue with user-selected processing options."""
        try:
            if not self.job_manager:
                logger.error("Job manager not initialized")
                return
            
            # Get comprehensive parameters from all tabs
            job_options = self.get_all_tab_parameters()
            
            # Use the configured output directory (with fallback if not initialized)
            if hasattr(self, 'current_output_folder') and self.current_output_folder:
                output_dir = Path(self.current_output_folder)
            else:
                # Fallback if not initialized yet
                output_dir = Path(self._get_default_output_folder())
            
            # Ensure the output directory exists
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                logger.warning(f"Could not create output directory {output_dir}: {e}")
                # Fallback to default directory
                output_dir = Path(self._get_default_output_folder())
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Using fallback output directory: {output_dir}")
            
            # Add jobs to queue with comprehensive processing options
            job_ids = self.job_manager.add_jobs_from_files(
                stl_files, output_dir, job_type="render", options=job_options
            )
            
            logger.info(f"Added {len(job_ids)} jobs to queue with options: {job_options}")
            
            # Create descriptive status message
            enabled_processes = []
            if job_options['image_rendering']:
                enabled_processes.append("Images")
            if job_options['video_rendering']:
                enabled_processes.append("Videos")
            
            process_text = " + ".join(enabled_processes) if enabled_processes else "Analysis only"
            
            # Update status
            self.file_status_var.set(f"Added {len(stl_files)} STL files to queue ({process_text})")
            
            messagebox.showinfo(
                "Files Added", 
                f"Added {len(stl_files)} STL files to batch queue\nProcessing: Analysis + Validation + {process_text}"
            )
            
        except Exception as e:
            logger.error(f"Error adding files to queue: {e}")
            show_error_with_logging(
                self.root, "Queue Error",
                f"Error adding files to batch queue: {e}",
                exception=e
            )
    
    def get_all_tab_parameters(self):
        """Collect parameters from all tabs for batch processing."""
        return {
            # Analysis tab parameters (always enabled for now)
            'analysis': True,
            
            # Validation tab parameters  
            'validation': True,
            'repair_meshes': getattr(self, 'repair_var', None) and self.repair_var.get(),
            
            # Image Rendering tab parameters
            'image_rendering': getattr(self, 'image_rendering_var', None) and self.image_rendering_var.get(),
            'material': getattr(self, 'material_var', None) and self.material_var.get() or 'plastic',
            'lighting': getattr(self, 'lighting_var', None) and self.lighting_var.get() or 'studio', 
            'image_width': int(getattr(self, 'width_var', None) and self.width_var.get() or '1920'),
            'image_height': int(getattr(self, 'height_var', None) and self.height_var.get() or '1080'),
            'background_image': getattr(self, 'background_image_path', None),
            
            # Video Generator tab parameters
            'video_rendering': getattr(self, 'video_rendering_var', None) and self.video_rendering_var.get(),
            'video_format': getattr(self, 'video_format_var', None) and self.video_format_var.get() or 'mp4',
            'video_quality': getattr(self, 'video_quality_var', None) and self.video_quality_var.get() or 'standard',
            'video_duration': float(getattr(self, 'video_duration_var', None) and self.video_duration_var.get() or '8'),
            
            # Output configuration
            'output_dir': getattr(self, 'current_output_folder', None) or self._get_default_output_folder()
        }
    
    def get_first_queue_item(self):
        """Get the first item in the queue for single-item processing."""
        if not self.job_manager:
            return None
        
        try:
            # Import JobStatus for comparison
            from .batch_queue.job_types_v2 import JobStatus
            
            # Get pending jobs
            pending_jobs = [job for job in self.job_manager._jobs.values() if job.status == JobStatus.PENDING]
            if pending_jobs:
                return pending_jobs[0]
            return None
        except Exception as e:
            logger.error(f"Error getting first queue item: {e}")
            return None
    
    def get_temp_render_path(self):
        """Get a safe temporary path for rendering output."""
        temp_dir = Path(tempfile.gettempdir())
        # Ensure the temp directory exists
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Also ensure /tmp/images exists (for any potential screenshot functionality)
        images_dir = temp_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        return temp_dir / "stl_render.png"
    
    def create_notebook(self):
        """Create notebook with batch queue as first tab (primary focus)."""
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Batch Queue first (primary focus for batch processing)
        self.create_batch_queue_tab()
        
        # Individual processing tabs
        self.create_analysis_tab()
        self.create_validation_tab()
        self.create_rendering_tab()
        self.create_generators_tab()
    
    def create_analysis_tab(self):
        """Create the analysis tab."""
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text="Analysis")
        
        self.analysis_frame.columnconfigure(0, weight=1)
        self.analysis_frame.rowconfigure(1, weight=1)
        
        button_frame = ttk.Frame(self.analysis_frame)
        button_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(button_frame, text="Analyze File", 
                  command=self.analyze_file).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Export Results", 
                  command=self.export_analysis).pack(side=tk.LEFT)
        
        self.analysis_text = scrolledtext.ScrolledText(self.analysis_frame, 
                                                      state=tk.DISABLED, 
                                                      wrap=tk.WORD)
        self.analysis_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def create_validation_tab(self):
        """Create the validation tab."""
        self.validation_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.validation_frame, text="Validation")
        
        self.validation_frame.columnconfigure(0, weight=1)
        self.validation_frame.rowconfigure(2, weight=1)
        
        controls_frame = ttk.Frame(self.validation_frame)
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(controls_frame, text="Validation Level:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.validation_level = tk.StringVar(value="standard")
        level_combo = ttk.Combobox(controls_frame, textvariable=self.validation_level,
                                  values=["basic", "standard", "strict"], state="readonly")
        level_combo.pack(side=tk.LEFT, padx=(0, 10))
        # Connect change handler
        self.validation_level.trace('w', self.on_validation_level_changed)
        
        self.repair_var = tk.BooleanVar()
        repair_checkbox = ttk.Checkbutton(controls_frame, text="Auto Repair", 
                                         variable=self.repair_var, command=self.on_repair_var_changed)
        repair_checkbox.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Validate", 
                  command=self.validate_file).pack(side=tk.LEFT)
        
        self.validation_results = ttk.Frame(self.validation_frame)
        self.validation_results.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.validation_text = scrolledtext.ScrolledText(self.validation_frame, 
                                                        state=tk.DISABLED, 
                                                        wrap=tk.WORD)
        self.validation_text.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def create_rendering_tab(self):
        """Create the rendering tab."""
        self.rendering_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.rendering_frame, text="Image Rendering")
        
        self.rendering_frame.columnconfigure(1, weight=1)
        self.rendering_frame.rowconfigure(2, weight=1)
        
        settings_frame = ttk.LabelFrame(self.rendering_frame, text="Render Settings", padding="10")
        settings_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(settings_frame, text="Material:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.material_var = tk.StringVar(value="plastic")
        material_combo = ttk.Combobox(settings_frame, textvariable=self.material_var,
                                     values=["plastic", "metal", "resin", "ceramic", "wood", "glass"],
                                     state="readonly")
        material_combo.grid(row=0, column=1, padx=(0, 20))
        # Connect change handler
        self.material_var.trace('w', self.on_material_changed)
        
        ttk.Label(settings_frame, text="Lighting:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.lighting_var = tk.StringVar(value="studio")
        lighting_combo = ttk.Combobox(settings_frame, textvariable=self.lighting_var,
                                     values=["studio", "natural", "dramatic", "soft"],
                                     state="readonly")
        lighting_combo.grid(row=0, column=3, padx=(0, 20))
        # Connect change handler
        self.lighting_var.trace('w', self.on_lighting_changed)
        
        ttk.Label(settings_frame, text="Size:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        size_frame = ttk.Frame(settings_frame)
        size_frame.grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.width_var = tk.StringVar(value="1920")
        self.height_var = tk.StringVar(value="1080")
        
        width_entry = ttk.Entry(size_frame, textvariable=self.width_var, width=8)
        width_entry.pack(side=tk.LEFT)
        ttk.Label(size_frame, text=" x ").pack(side=tk.LEFT)
        height_entry = ttk.Entry(size_frame, textvariable=self.height_var, width=8)
        height_entry.pack(side=tk.LEFT)
        
        # Connect change handlers
        self.width_var.trace('w', self.on_width_changed)
        self.height_var.trace('w', self.on_height_changed)
        ttk.Label(size_frame, text=" pixels").pack(side=tk.LEFT)
        
        # Background image selection
        ttk.Label(settings_frame, text="Background:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        bg_frame = ttk.Frame(settings_frame)
        bg_frame.grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.background_var = tk.StringVar(value="No background selected")
        self.background_path = None
        
        ttk.Button(bg_frame, text="Select Background...", 
                  command=self.browse_background_image).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(bg_frame, text="Clear", 
                  command=self.clear_background_image).pack(side=tk.LEFT, padx=(0, 10))
        
        bg_status_label = ttk.Label(bg_frame, textvariable=self.background_var, 
                                   foreground="gray")
        bg_status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Background preview
        self.bg_preview = tk.Label(bg_frame, text="No preview", bg="lightgray", 
                                  relief="sunken", bd=2, compound="center")
        self.bg_preview.pack(side=tk.LEFT, padx=(10, 0))
        
        render_button_frame = ttk.Frame(self.rendering_frame)
        render_button_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        ttk.Button(render_button_frame, text="Render Image", 
                  command=self.render_image).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(render_button_frame, text="Save As...", 
                  command=self.save_render).pack(side=tk.LEFT)
        
        self.render_display = tk.Label(self.rendering_frame, text="Rendered image will appear here",
                                      bg="white", relief="sunken", width=80, height=40)
        self.render_display.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        progress_frame = ttk.Frame(self.rendering_frame)
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           maximum=100, mode='determinate')
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.progress_label = ttk.Label(progress_frame, text="Ready")
        self.progress_label.grid(row=0, column=1)
    
    def create_generators_tab(self):
        """Create the generators tab for video and image generation."""
        self.generators_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.generators_frame, text="Video Generator")
        
        self.generators_frame.columnconfigure(0, weight=1)
        self.generators_frame.rowconfigure(2, weight=1)
        
        # Video Generation Section
        video_frame = ttk.LabelFrame(self.generators_frame, text="Video Generation", padding="10")
        video_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        video_frame.columnconfigure(1, weight=1)
        
        # Video settings
        ttk.Label(video_frame, text="Format:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.video_format_var = tk.StringVar(value="mp4")
        video_format_combo = ttk.Combobox(video_frame, textvariable=self.video_format_var,
                                         values=["mp4", "avi", "mov", "gif"], state="readonly")
        video_format_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(video_frame, text="Quality:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.video_quality_var = tk.StringVar(value="standard")
        quality_combo = ttk.Combobox(video_frame, textvariable=self.video_quality_var,
                                    values=["draft", "standard", "high", "ultra"], state="readonly")
        quality_combo.grid(row=0, column=3, sticky=tk.W)
        
        ttk.Label(video_frame, text="Duration (sec):").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.video_duration_var = tk.StringVar(value="8")
        duration_entry = ttk.Entry(video_frame, textvariable=self.video_duration_var, width=8)
        duration_entry.grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        
        # Video generation buttons
        video_buttons_frame = ttk.Frame(video_frame)
        video_buttons_frame.grid(row=2, column=0, columnspan=4, pady=(15, 0))
        
        ttk.Button(video_buttons_frame, text="Generate 360° Video",
                  command=self.generate_rotation_video).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(video_buttons_frame, text="Multi-Angle Video",
                  command=self.generate_multi_angle_video).pack(side=tk.LEFT)
        
        # Image Generation Section
        image_frame = ttk.LabelFrame(self.generators_frame, text="Image Generation", padding="10")
        image_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        image_frame.columnconfigure(1, weight=1)
        
        # Color variation settings
        ttk.Label(image_frame, text="Grid Layout:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.grid_layout_var = tk.StringVar(value="auto")
        layout_combo = ttk.Combobox(image_frame, textvariable=self.grid_layout_var,
                                   values=["auto", "square", "horizontal", "vertical"], state="readonly")
        layout_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Image generation buttons
        image_buttons_frame = ttk.Frame(image_frame)
        image_buttons_frame.grid(row=1, column=0, columnspan=4, pady=(15, 0))
        
        ttk.Button(image_buttons_frame, text="Color Variations Grid",
                  command=self.generate_color_grid).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(image_buttons_frame, text="Size Chart",
                  command=self.generate_size_chart).pack(side=tk.LEFT)
        
        # Progress section for generators
        progress_frame = ttk.LabelFrame(self.generators_frame, text="Generation Progress", padding="10")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(1, weight=1)
        
        self.generator_progress_var = tk.DoubleVar()
        self.generator_progress_bar = ttk.Progressbar(progress_frame, variable=self.generator_progress_var,
                                                     maximum=100, mode='determinate')
        self.generator_progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.generator_log = scrolledtext.ScrolledText(progress_frame, height=8, state=tk.DISABLED)
        self.generator_log.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Connect settings change handlers
        self.video_format_var.trace('w', lambda *args: self.save_setting('video_format', self.video_format_var.get()))
        self.video_quality_var.trace('w', lambda *args: self.save_setting('video_quality', self.video_quality_var.get()))
        self.video_duration_var.trace('w', lambda *args: self.save_setting('video_duration', self.video_duration_var.get()))
        self.grid_layout_var.trace('w', lambda *args: self.save_setting('grid_layout', self.grid_layout_var.get()))
    
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
        """Create enhanced queue control buttons and processing options."""
        control_frame = ttk.LabelFrame(self.batch_tab, text="Queue Controls", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(3, weight=1)  # Spacer column to separate buttons and options
        
        # Left side: Control buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=0, column=0, sticky=tk.W)
        
        # Buttons: Start, Pause, Stop, Restart, Clear
        self.control_buttons['start'] = ttk.Button(
            button_frame, text="Start Processing", 
            command=self.start_processing
        )
        self.control_buttons['start'].grid(row=0, column=0, padx=(0, 5))
        
        self.control_buttons['pause'] = ttk.Button(
            button_frame, text="Pause", 
            command=self.pause_processing, state="disabled"
        )
        self.control_buttons['pause'].grid(row=0, column=1, padx=5)
        
        self.control_buttons['stop'] = ttk.Button(
            button_frame, text="Stop", 
            command=self.stop_processing, state="disabled"
        )
        self.control_buttons['stop'].grid(row=0, column=2, padx=5)
        
        # NEW: Restart button
        self.control_buttons['restart'] = ttk.Button(
            button_frame, text="Restart", 
            command=self.restart_processing
        )
        self.control_buttons['restart'].grid(row=0, column=3, padx=5)
        
        self.control_buttons['clear'] = ttk.Button(
            button_frame, text="Clear Completed", 
            command=self.clear_completed
        )
        self.control_buttons['clear'].grid(row=0, column=4, padx=(5, 0))
        
        # Middle: Output folder selection (NEW)
        output_frame = ttk.Frame(control_frame)
        output_frame.grid(row=0, column=1, padx=(20, 20))
        
        ttk.Button(
            output_frame, text="Output Folder...", 
            command=self.select_output_folder
        ).grid(row=0, column=0)
        
        # Initialize and display current output folder
        self.current_output_folder = self.user_config.get('output_folder', self._get_default_output_folder())
        self.output_folder_var = tk.StringVar(value=self._format_folder_display(self.current_output_folder))
        ttk.Label(
            output_frame, textvariable=self.output_folder_var,
            foreground="gray", font=('TkDefaultFont', 8)
        ).grid(row=1, column=0, sticky=tk.W, pady=(2, 0))
        
        # Right side: Processing options
        options_frame = ttk.LabelFrame(control_frame, text="Processing Options", padding="5")
        options_frame.grid(row=0, column=4, sticky=tk.E, padx=(20, 0))
        
        # Initialize processing option variables with user settings
        self.image_rendering_var = tk.BooleanVar(value=self.user_config.get('enable_image_rendering', True))
        self.video_rendering_var = tk.BooleanVar(value=self.user_config.get('enable_video_rendering', True))
        
        # Create checkboxes
        ttk.Checkbutton(
            options_frame, text="Image Rendering", 
            variable=self.image_rendering_var,
            command=self.on_processing_option_changed
        ).grid(row=0, column=0, padx=(0, 10), sticky=tk.W)
        
        ttk.Checkbutton(
            options_frame, text="Video Rendering", 
            variable=self.video_rendering_var,
            command=self.on_processing_option_changed
        ).grid(row=0, column=1, sticky=tk.W)
        
        # Queue info (spans full width)
        self.queue_info_var = tk.StringVar(value="Queue empty")
        ttk.Label(control_frame, textvariable=self.queue_info_var).grid(
            row=1, column=0, columnspan=5, sticky=tk.W, pady=(10, 0)
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
    
    def create_status_bar(self):
        """Create status bar."""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.status_frame.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.status_frame, textvariable=self.status_var,
                                relief="sunken", padding="5")
        status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
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
    
    def restart_processing(self):
        """Reset job statuses to restart processing (keeps jobs in queue)."""
        if not self.job_manager:
            return
        
        try:
            # Stop current processing if running
            if self.job_manager.is_running:
                response = messagebox.askyesno(
                    "Restart Processing",
                    "This will stop current processing and reset all job statuses to pending. The jobs will remain in the queue. Continue?"
                )
                if not response:
                    return
                    
                self.job_manager.stop_processing()
            
            # Reset job statuses only (don't clear the queue)
            if hasattr(self.job_manager, 'reset_job_statuses'):
                count = self.job_manager.reset_job_statuses()
            else:
                # Fallback: reset progress tracking only
                count = 0
                if hasattr(self.job_manager, 'progress_tracker'):
                    self.job_manager.progress_tracker.reset_tracking()
            
            # Reset control button states
            self.control_buttons['start'].config(state="normal")
            self.control_buttons['pause'].config(state="disabled", text="Pause")
            self.control_buttons['stop'].config(state="disabled")
            
            # Update job tree display to show reset statuses (don't clear jobs)
            if hasattr(self, 'job_tree'):
                for item in self.job_tree.get_children():
                    # Update existing items to show "pending" status instead of deleting them
                    values = list(self.job_tree.item(item)['values'])
                    if len(values) >= 2:
                        values[1] = "pending"  # Status column
                        values[2] = "0%"       # Progress column
                        self.job_tree.item(item, values=values)
            
            # Reset progress display
            if hasattr(self, 'overall_progress'):
                self.overall_progress['value'] = 0
            if hasattr(self, 'progress_text_var'):
                self.progress_text_var.set("Ready to process")
            
            # Update queue info to reflect reset
            if hasattr(self, 'queue_info_var') and self.job_manager:
                try:
                    summary = self.job_manager.get_queue_summary()
                    total = summary.get('total_jobs', 0)
                    self.queue_info_var.set(f"All {total} jobs reset to pending - ready to start")
                except:
                    self.queue_info_var.set("Job statuses reset - ready to start")
            
            logger.info("Batch queue job statuses reset by user")
            messagebox.showinfo("Processing Reset", "All job statuses have been reset to pending. Jobs remain in queue and are ready to process again.")
            
        except Exception as e:
            logger.error(f"Error resetting job statuses: {e}")
            show_error_with_logging(
                self.root, "Restart Error",
                f"Error resetting job statuses: {e}",
                exception=e
            )
    
    def on_processing_option_changed(self):
        """Handle changes to processing options (checkboxes)."""
        try:
            # Save user preferences
            self.user_config.set('enable_image_rendering', self.image_rendering_var.get())
            self.user_config.set('enable_video_rendering', self.video_rendering_var.get())
            
            # Update status to show current settings
            image_status = "✓" if self.image_rendering_var.get() else "✗"
            video_status = "✓" if self.video_rendering_var.get() else "✗"
            
            logger.info(f"Processing options updated: Image {image_status}, Video {video_status}")
            
        except Exception as e:
            logger.error(f"Error updating processing options: {e}")
    
    def select_output_folder(self):
        """Open folder selection dialog for output directory."""
        try:
            # Get current folder or default
            initial_folder = self.current_output_folder
            
            # Open folder selection dialog
            selected_folder = filedialog.askdirectory(
                title="Select Output Folder for Processed STL Files",
                initialdir=initial_folder
            )
            
            if selected_folder:
                # Update current folder
                self.current_output_folder = selected_folder
                
                # Save to user configuration
                self.user_config.set('output_folder', selected_folder)
                
                # Update display
                self.output_folder_var.set(self._format_folder_display(selected_folder))
                
                logger.info(f"Output folder updated to: {selected_folder}")
                
                # Show confirmation
                messagebox.showinfo(
                    "Output Folder Updated", 
                    f"Output folder set to:\n{selected_folder}"
                )
                
        except Exception as e:
            logger.error(f"Error selecting output folder: {e}")
            show_error_with_logging(
                self.root, "Folder Selection Error",
                f"Error selecting output folder: {e}",
                exception=e
            )
    
    def _get_default_output_folder(self):
        """Get the default output folder based on platform."""
        import tempfile
        import os
        
        if os.name == 'nt':  # Windows
            default_folder = Path.home() / "AppData" / "Local" / "stl_listing_tool" / "stl_processing_output"
        else:  # Unix/Linux/Mac
            default_folder = Path.home() / ".local" / "share" / "stl_listing_tool" / "stl_processing_output"
        
        # Ensure the folder exists
        try:
            default_folder.mkdir(parents=True, exist_ok=True)
            return str(default_folder)
        except (OSError, PermissionError):
            # Fallback to temp directory
            fallback_folder = Path(tempfile.gettempdir()) / "stl_listing_tool" / "stl_processing_output"
            fallback_folder.mkdir(parents=True, exist_ok=True)
            return str(fallback_folder)
    
    def _format_folder_display(self, folder_path):
        """Format folder path for display (truncate if too long)."""
        if not folder_path:
            return "No folder selected"
            
        path_str = str(folder_path)
        max_length = 50
        
        if len(path_str) <= max_length:
            return path_str
        else:
            # Truncate in the middle, showing start and end
            return f"{path_str[:20]}...{path_str[-25:]}"
    
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
        """Add folder to queue."""
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
    
    # Single file processing methods (for individual tab functionality)
    def browse_file(self):
        """Browse for a single STL file (for individual processing)."""
        file_path = filedialog.askopenfilename(
            title="Select STL File",
            filetypes=[("STL files", "*.stl"), ("All files", "*.*")]
        )
        if file_path:
            self.load_file(Path(file_path))
            
    def load_file(self, file_path: Path):
        """Load a single STL file for individual processing."""
        if not file_path.exists():
            show_error_with_logging(
                self.root,
                "File Not Found",
                f"The selected file does not exist: {file_path}",
                context={
                    "file_path": str(file_path),
                    "parent_directory": str(file_path.parent),
                    "parent_exists": file_path.parent.exists(),
                    "current_working_directory": str(Path.cwd())
                }
            )
            return
            
        self.current_file = file_path
        self.status_var.set(f"Loaded: {file_path.name}")
        
        # Check if core modules are available before proceeding
        if not CORE_MODULES_AVAILABLE:
            show_error_with_logging(
                self.root,
                "Missing Dependencies", 
                "STL processing dependencies are not installed. Please run 'pip install -r requirements.txt' to install required packages.",
                exception=CORE_IMPORT_ERROR,
                context={
                    "file_path": str(file_path),
                    "missing_modules": "core STL processing modules",
                    "import_error": str(CORE_IMPORT_ERROR)
                }
            )
            return

        self.processor = STLProcessor()
        try:
            if not self.processor.load(file_path):
                # Get the actual exception if available
                exception = self.processor.last_error
                show_error_with_logging(
                    self.root,
                    "STL Loading Failed", 
                    f"Failed to load STL file: {file_path}",
                    exception=exception,
                    context={
                        "file_path": str(file_path),
                        "file_size": file_path.stat().st_size if file_path.exists() else "Unknown",
                        "file_extension": file_path.suffix,
                        "processor_state": "Failed during load operation"
                    }
                )
                return
        except Exception as e:
            show_error_with_logging(
                self.root,
                "STL Loading Error",
                f"An exception occurred while loading STL file: {file_path}",
                exception=e,
                context={
                    "file_path": str(file_path),
                    "file_size": file_path.stat().st_size if file_path.exists() else "Unknown",
                    "file_extension": file_path.suffix,
                    "operation": "STL file loading"
                }
            )
            return
            
        logger.info(f"Loaded STL file: {file_path}")
    
    def analyze_file(self):
        """Analyze the current STL file."""
        if not self.current_file or not self.processor:
            messagebox.showwarning("Warning", "Please select an STL file first")
            return
            
        def run_analysis():
            try:
                self.status_var.set("Analyzing file...")
                self.progress_var.set(20)
                
                dimensions = self.processor.get_dimensions()
                self.progress_var.set(50)
                
                extractor = DimensionExtractor(self.processor.mesh)
                analysis = extractor.get_complete_analysis()
                self.analysis_results = {
                    "dimensions": dimensions,
                    "analysis": analysis
                }
                self.progress_var.set(80)
                
                self.display_analysis_results()
                self.progress_var.set(100)
                self.status_var.set("Analysis complete")
                
            except Exception as e:
                logger.error(f"Analysis error: {e}")
                show_error_with_logging(
                    self.root,
                    "Analysis Failed",
                    f"Analysis failed during processing: {str(e)}",
                    exception=e,
                    context={
                        "file_path": str(self.current_file),
                        "operation": "STL analysis",
                        "processor_loaded": self.processor is not None,
                        "analysis_stage": "dimension_extraction_or_analysis"
                    }
                )
                self.status_var.set("Analysis failed")
            finally:
                self.progress_var.set(0)
                
        threading.Thread(target=run_analysis, daemon=True).start()
    
    def display_analysis_results(self):
        """Display analysis results in the text widget."""
        if not self.analysis_results:
            return
            
        dimensions = self.analysis_results["dimensions"]
        analysis = self.analysis_results["analysis"]
        
        output = []
        output.append(f"=== STL Analysis Report for {self.current_file.name} ===\n")
        
        output.append("BASIC DIMENSIONS:")
        output.append(f"  Size: {dimensions.get('width', 0):.2f} x {dimensions.get('height', 0):.2f} x {dimensions.get('depth', 0):.2f} mm")
        output.append(f"  Volume: {dimensions.get('volume', 0):.2f} mm³")
        output.append(f"  Surface Area: {dimensions.get('surface_area', 0):.2f} mm²")
        center = dimensions.get('center', [0, 0, 0])
        output.append(f"  Center: ({center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f})")
        output.append("")
        
        mesh_quality = analysis.get('mesh_quality', {})
        output.append("MESH QUALITY:")
        output.append(f"  Vertices: {mesh_quality.get('vertex_count', 0):,}")
        output.append(f"  Faces: {mesh_quality.get('face_count', 0):,}")
        output.append(f"  Valid: {'✓' if mesh_quality.get('is_valid', False) else '✗'}")
        output.append(f"  Watertight: {'✓' if dimensions.get('is_watertight', False) else '✗'}")
        output.append("")
        
        printability = analysis.get('printability', {})
        output.append("PRINTABILITY:")
        output.append(f"  Estimated Layers: {printability.get('estimated_layers', 0)}")
        output.append(f"  Stability Ratio: {printability.get('stability_ratio', 0):.2f}")
        output.append(f"  Stable for Printing: {'✓' if printability.get('is_stable_for_printing', False) else '✗'}")
        output.append(f"  Requires Supports: {'Yes' if printability.get('requires_supports', False) else 'No'}")
        output.append(f"  Complexity Score: {printability.get('complexity_score', 0):.1f}/100")
        
        self.analysis_text.config(state=tk.NORMAL)
        self.analysis_text.delete(1.0, tk.END)
        self.analysis_text.insert(1.0, "\n".join(output))
        self.analysis_text.config(state=tk.DISABLED)
    
    def export_analysis(self):
        """Export analysis results."""
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No analysis results to export")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Export Analysis Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")]
        )
        
        if file_path:
            try:
                path = Path(file_path)
                if path.suffix.lower() == '.json':
                    with open(path, 'w') as f:
                        json.dump(self.analysis_results, f, indent=2)
                else:
                    with open(path, 'w') as f:
                        f.write(self.analysis_text.get(1.0, tk.END))
                        
                messagebox.showinfo("Success", f"Analysis exported to {file_path}")
            except Exception as e:
                show_error_with_logging(
                    self.root,
                    "Export Failed",
                    f"Failed to export analysis results: {str(e)}",
                    exception=e,
                    context={
                        "export_file_path": str(file_path),
                        "export_format": path.suffix.lower(),
                        "has_analysis_results": self.analysis_results is not None,
                        "operation": "analysis export"
                    }
                )
    
    def validate_file(self):
        """Validate the current STL file."""
        if not self.current_file or not self.processor:
            messagebox.showwarning("Warning", "Please select an STL file first")
            return
            
        def run_validation():
            try:
                self.status_var.set("Validating mesh...")
                self.progress_var.set(30)
                
                validator = MeshValidator(self.processor.mesh)
                level = ValidationLevel(self.validation_level.get())
                results = validator.validate(level)
                
                self.progress_var.set(70)
                
                if self.repair_var.get() and not results['is_valid']:
                    self.status_var.set("Repairing mesh...")
                    repair_results = validator.repair(auto_fix=True)
                    results['repair_results'] = repair_results
                    
                self.display_validation_results(results)
                self.progress_var.set(100)
                self.status_var.set("Validation complete")
                
            except Exception as e:
                logger.error(f"Validation error: {e}")
                show_error_with_logging(
                    self.root,
                    "Validation Failed",
                    f"Mesh validation failed: {str(e)}",
                    exception=e,
                    context={
                        "file_path": str(self.current_file),
                        "operation": "mesh validation",
                        "validation_level": self.validation_level.get(),
                        "auto_repair_enabled": self.repair_var.get(),
                        "processor_loaded": self.processor is not None
                    }
                )
                self.status_var.set("Validation failed")
            finally:
                self.progress_var.set(0)
                
        threading.Thread(target=run_validation, daemon=True).start()
    
    def display_validation_results(self, results):
        """Display validation results."""
        output = []
        output.append(f"=== Validation Results for {self.current_file.name} ===\n")
        output.append(f"Validation Level: {self.validation_level.get()}")
        output.append(f"Is Valid: {'✓' if results['is_valid'] else '✗'}")
        output.append(f"Has Warnings: {'⚠' if results['has_warnings'] else '✓'}")
        output.append(f"Total Issues: {results['total_issues']}")
        output.append("")
        
        if results['issues']:
            output.append("Issues Found:")
            for issue in results['issues']:
                icon = "✗" if issue['severity'] == 'error' else "⚠"
                output.append(f"  {icon} {issue['severity'].upper()}: {issue['description']}")
            output.append("")
            
        if 'repair_results' in results:
            repair = results['repair_results']
            output.append("Repair Results:")
            if repair['repair_successful']:
                output.append("✓ Repair successful!")
                output.append(f"Applied {repair['repair_count']} repairs:")
                for repair_type in repair['repairs_applied']:
                    output.append(f"  - {repair_type}")
            else:
                output.append("✗ Repair failed")
                
        self.validation_text.config(state=tk.NORMAL)
        self.validation_text.delete(1.0, tk.END)
        self.validation_text.insert(1.0, "\n".join(output))
        self.validation_text.config(state=tk.DISABLED)
    
    def browse_background_image(self):
        """Open file dialog to select background image."""
        file_path = filedialog.askopenfilename(
            title="Select Background Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.background_path = Path(file_path)
            # Show filename in the status label
            filename = self.background_path.name
            if len(filename) > 40:
                filename = filename[:37] + "..."
            self.background_var.set(f"Selected: {filename}")
            self.status_var.set(f"Background image selected: {self.background_path.name}")
            logger.info(f"Background image selected: {self.background_path}")
            
            # Save background image path to config
            self.save_setting('background_image_path', str(self.background_path))
            
            # Show preview thumbnail
            self.update_background_preview()
    
    def clear_background_image(self):
        """Clear the selected background image."""
        self.background_path = None
        self.background_var.set("No background selected")
        self.status_var.set("Background image cleared")
        logger.info("Background image cleared")
        
        # Remove background image path from config
        self.user_config.remove('background_image_path', auto_save=True)
        
        # Clear preview and restore default size
        self.bg_preview.config(image="", text="No preview", width=0, height=0)
        if hasattr(self.bg_preview, 'image'):
            delattr(self.bg_preview, 'image')
    
    def update_background_preview(self):
        """Update the background image preview thumbnail."""
        if not self.background_path or not self.background_path.exists():
            return
        
        try:
            from PIL import Image, ImageTk
            
            # Load and create larger thumbnail
            with Image.open(self.background_path) as img:
                # Create thumbnail (160x120 pixels for better visibility)
                img.thumbnail((160, 120), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                
                # Update preview widget - clear width/height to let image determine size
                self.bg_preview.config(image=photo, text="", width=0, height=0)
                self.bg_preview.image = photo  # Keep reference to prevent garbage collection
                
        except ImportError:
            # PIL not available, show text instead
            self.bg_preview.config(text="IMG", image="", width=10, height=3)
        except Exception as e:
            logger.warning(f"Failed to create background preview: {e}")
            self.bg_preview.config(text="ERR", image="", width=10, height=3)
    
    def render_image(self):
        """Render an image using the first item in the queue with current tab parameters."""
        # Check if we have items in queue
        first_job = self.get_first_queue_item()
        if not first_job:
            messagebox.showwarning("Warning", "Please add STL files to the queue first")
            return
            
        # Check if rendering modules are available
        if not RENDERING_MODULES_AVAILABLE:
            show_error_with_logging(
                self.root,
                "Missing Rendering Dependencies", 
                "Rendering dependencies are not installed. Please run 'pip install vtk' to enable rendering.",
                exception=RENDERING_IMPORT_ERROR,
                context={
                    "missing_modules": "VTK rendering modules",
                    "import_error": str(RENDERING_IMPORT_ERROR)
                }
            )
            return
            
        def run_render(queue_item):
            renderer = None
            try:
                self.status_var.set("Setting up renderer...")
                self.progress_var.set(20)
                
                width = int(self.width_var.get())
                height = int(self.height_var.get())
                
                logger.info(f"Creating VTK renderer with dimensions: {width}x{height}")
                renderer = VTKRenderer(width, height)
                
                # Set background image if selected
                if self.background_path and self.background_path.exists():
                    self.status_var.set("Loading background image...")
                    logger.info(f"Setting background image: {self.background_path}")
                    if not renderer.set_background_image(self.background_path):
                        logger.warning(f"Failed to load background image: {self.background_path}")
                        # Continue with rendering but without background
                    else:
                        logger.info("Background image loaded successfully")
                
                # Explicitly initialize the renderer first
                logger.info("Initializing VTK renderer...")
                if not renderer.initialize():
                    raise Exception("Failed to initialize VTK renderer")
                
                # Verify the renderer window size after initialization
                if hasattr(renderer, 'render_window') and renderer.render_window:
                    actual_size = renderer.render_window.GetSize()
                    logger.info(f"Renderer initialized with actual window size: {actual_size[0]}x{actual_size[1]}")
                    
                    # If size doesn't match, force set it again
                    if actual_size[0] != width or actual_size[1] != height:
                        logger.warning(f"Window size mismatch! Expected {width}x{height}, got {actual_size[0]}x{actual_size[1]}")
                        renderer.render_window.SetSize(width, height)
                        renderer.render_window.Modified()
                        final_size = renderer.render_window.GetSize()
                        logger.info(f"Forced window size to: {final_size[0]}x{final_size[1]}")
                
                self.progress_var.set(40)
                self.status_var.set("Loading mesh...")
                
                # Use the file from the queue item
                queue_file = Path(queue_item.input_file)
                if not renderer.setup_scene(queue_file):
                    raise Exception("Failed to setup rendering scene")
                    
                self.progress_var.set(60)
                self.status_var.set("Configuring materials...")
                
                material_type = MaterialType(self.material_var.get())
                renderer.set_material(material_type, (0.8, 0.8, 0.8))
                
                lighting_preset = LightingPreset(self.lighting_var.get())
                renderer.set_lighting(lighting_preset)
                
                self.progress_var.set(80)
                self.status_var.set("Rendering...")
                
                temp_path = self.get_temp_render_path()
                logger.info(f"Starting render to temp path: {temp_path}")
                
                # Final window size check before rendering
                logger.info(f"ABOUT TO CALL renderer.render() with window size: {renderer.render_window.GetSize()}")
                if hasattr(renderer, 'render_window') and renderer.render_window:
                    pre_render_size = renderer.render_window.GetSize()
                    logger.info(f"Window size before render: {pre_render_size[0]}x{pre_render_size[1]}")
                
                if renderer.render(temp_path):
                    logger.info(f"Render successful, displaying image from: {temp_path}")
                    self.display_rendered_image(temp_path)
                    self.progress_var.set(100)
                    self.status_var.set("Render complete")
                else:
                    logger.error(f"Renderer returned False for path: {temp_path}")
                    raise Exception("Render failed")
                
            except Exception as e:
                logger.error(f"Render error: {e}")
                show_error_with_logging(
                    self.root,
                    "Rendering Failed",
                    f"Image rendering failed: {str(e)}",
                    exception=e,
                    context={
                        "file_path": str(queue_item.input_file),
                        "operation": "image rendering",
                        "render_width": self.width_var.get(),
                        "render_height": self.height_var.get(),
                        "material_type": self.material_var.get(),
                        "lighting_preset": self.lighting_var.get(),
                        "background_image": str(self.background_path) if self.background_path else "None",
                        "has_background": self.background_path is not None,
                        "processor_loaded": self.processor is not None
                    }
                )
                self.status_var.set("Render failed")
            finally:
                # Ensure proper cleanup of renderer resources
                if renderer:
                    try:
                        logger.info("Cleaning up renderer resources...")
                        renderer.cleanup()
                    except Exception as cleanup_error:
                        logger.warning(f"Error during renderer cleanup: {cleanup_error}")
                self.progress_var.set(0)
                
        threading.Thread(target=lambda: run_render(first_job), daemon=True).start()
    
    def display_rendered_image(self, image_path: Path):
        """Display rendered image in the GUI."""
        try:
            from PIL import Image, ImageTk
            
            logger.info(f"Loading rendered image from: {image_path}")
            image = Image.open(image_path)
            original_size = image.size
            logger.info(f"Original image size: {original_size[0]}x{original_size[1]}")
            
            # Get the actual display widget size instead of using hardcoded values
            self.render_display.update_idletasks()  # Ensure geometry is calculated
            
            # Get widget dimensions (convert from characters to pixels approximately)
            widget_width = self.render_display.winfo_width()
            widget_height = self.render_display.winfo_height()
            
            # If widget hasn't been drawn yet, use reasonable defaults based on window size
            if widget_width <= 1 or widget_height <= 1:
                # Fallback: use a reasonable size based on the GUI layout
                widget_width = 800  # Reasonable default width
                widget_height = 600  # Reasonable default height
                logger.info(f"Using fallback display size: {widget_width}x{widget_height}")
            else:
                logger.info(f"Display widget actual size: {widget_width}x{widget_height}")
            
            # Use the actual available space for thumbnailing, with some padding
            max_width = widget_width - 20  # Leave 20px padding
            max_height = widget_height - 20  # Leave 20px padding
            
            # Ensure minimum reasonable size
            max_width = max(400, max_width)
            max_height = max(300, max_height)
            
            logger.info(f"Thumbnailing to max size: {max_width}x{max_height}")
            
            # Create thumbnail that maintains aspect ratio
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            final_size = image.size
            logger.info(f"Final display image size: {final_size[0]}x{final_size[1]}")
            
            photo = ImageTk.PhotoImage(image)
            self.render_display.config(image=photo, text="")
            self.render_display.image = photo
            logger.info(f"Successfully displayed rendered image: {image_path}")
            
        except ImportError:
            fallback_text = f"Rendered image saved to:\n{image_path}"
            self.render_display.config(text=fallback_text)
            logger.info(f"PIL not available, showing fallback text: {fallback_text}")
        except Exception as e:
            error_text = f"Error displaying image: {e}"
            self.render_display.config(text=error_text)
            logger.error(f"Error displaying image {image_path}: {e}")
    
    def save_render(self):
        """Save the rendered image."""
        if not hasattr(self.render_display, 'image'):
            messagebox.showwarning("Warning", "No rendered image to save")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Save Rendered Image",
            defaultextension=".png", 
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
        )
        
        if file_path and hasattr(self.render_display, 'image'):
            try:
                temp_path = self.get_temp_render_path()
                if temp_path.exists():
                    import shutil
                    shutil.copy(temp_path, file_path)
                    messagebox.showinfo("Success", f"Image saved to {file_path}")
            except Exception as e:
                show_error_with_logging(
                    self.root,
                    "Save Failed",
                    f"Failed to save rendered image: {str(e)}",
                    exception=e,
                    context={
                        "save_file_path": str(file_path),
                        "temp_file_exists": self.get_temp_render_path().exists(),
                        "operation": "image save"
                    }
                )
    
    # Generator methods
    def generate_rotation_video(self):
        """Generate a 360° rotation video using the first item in the queue with current tab parameters."""
        # Check if we have items in queue
        first_job = self.get_first_queue_item()
        if not first_job:
            messagebox.showwarning("Warning", "Please add STL files to the queue first")
            return
        
        if not GENERATORS_AVAILABLE:
            show_error_with_logging(
                self.root,
                "Missing Dependencies",
                "Video generation dependencies are not installed. Please run 'pip install moviepy' to enable video generation.",
                exception=GENERATORS_IMPORT_ERROR,
                context={"missing_modules": "video generation modules"}
            )
            return
        
        # Get save location
        file_path = filedialog.asksaveasfilename(
            title="Save Rotation Video",
            defaultextension=f".{self.video_format_var.get()}",
            filetypes=[
                ("MP4 files", "*.mp4"),
                ("AVI files", "*.avi"), 
                ("MOV files", "*.mov"),
                ("GIF files", "*.gif"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        def run_generation(queue_item):
            try:
                # Clear log
                self.generator_log.config(state=tk.NORMAL)
                self.generator_log.delete(1.0, tk.END)
                self.generator_log.config(state=tk.DISABLED)
                
                self.log_generator_message("Starting video generation...")
                
                # Create video generator
                generator = RotationVideoGenerator()
                
                # Check if video generation is available
                if not generator.dependencies_available:
                    self.log_generator_message("❌ Video generation not available - moviepy not installed properly")
                    self.log_generator_message("💡 You can still use image rendering and other features")
                    self.log_generator_message("🔧 To fix: pip uninstall moviepy && pip install moviepy")
                    self.update_generator_progress(0, "Video generation unavailable")
                    return
                
                generator.set_progress_callback(self.update_generator_progress)
                
                # Get settings
                video_format = VideoFormat(self.video_format_var.get())
                video_quality = VideoQuality(self.video_quality_var.get())
                duration = float(self.video_duration_var.get())
                
                # Create renderer for video generation
                if not RENDERING_MODULES_AVAILABLE:
                    raise Exception("Rendering modules not available")
                
                width = int(self.width_var.get())
                height = int(self.height_var.get())
                renderer = VTKRenderer(width, height)
                
                if not renderer.initialize():
                    raise Exception("Failed to initialize renderer")
                
                # Use the file from the queue item
                queue_file = Path(queue_item.input_file)
                if not renderer.setup_scene(queue_file):
                    raise Exception("Failed to setup scene")
                
                # Apply current material and lighting settings
                material_type = MaterialType(self.material_var.get())
                renderer.set_material(material_type, (0.8, 0.8, 0.8))
                
                lighting_preset = LightingPreset(self.lighting_var.get())
                renderer.set_lighting(lighting_preset)
                
                # Generate video
                success = generator.generate_rotation_video(
                    renderer, Path(file_path), video_format, video_quality, duration
                )
                
                if success:
                    self.log_generator_message(f"✓ Video saved successfully: {file_path}")
                    messagebox.showinfo("Success", f"Video generated successfully!\nSaved to: {file_path}")
                else:
                    self.log_generator_message("✗ Video generation failed")
                    
            except Exception as e:
                logger.error(f"Video generation error: {e}")
                self.log_generator_message(f"✗ Error: {str(e)}")
                show_error_with_logging(
                    self.root,
                    "Video Generation Failed",
                    f"Failed to generate rotation video: {str(e)}",
                    exception=e,
                    context={
                        "file_path": str(queue_item.input_file),
                        "operation": "rotation video generation",
                        "video_format": self.video_format_var.get(),
                        "video_quality": self.video_quality_var.get()
                    }
                )
            finally:
                self.generator_progress_var.set(0)
        
        # Run in separate thread
        threading.Thread(target=lambda: run_generation(first_job), daemon=True).start()
    
    def generate_multi_angle_video(self):
        """Generate a multi-angle video showing different views."""
        messagebox.showinfo("Coming Soon", "Multi-angle video generation will be available in a future update.")
    
    def generate_color_grid(self):
        """Generate a color variation grid image."""
        if not self.current_file or not self.processor:
            messagebox.showwarning("Warning", "Please select an STL file first")
            return
        
        # Show color selection dialog
        colors_dialog = ColorVariationDialog(self.root)
        if colors_dialog.result:
            color_variations = colors_dialog.result
            
            # Get save location
            file_path = filedialog.asksaveasfilename(
                title="Save Color Grid",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
            )
            
            if file_path:
                self._generate_color_grid_async(color_variations, file_path)
    
    def generate_size_chart(self):
        """Generate a size comparison chart."""
        messagebox.showinfo("Coming Soon", "Size chart generation will be available in a future update.")
    
    def _generate_color_grid_async(self, color_variations, output_path):
        """Generate color grid in background thread."""
        def run_generation():
            try:
                self.log_generator_message("Starting color grid generation...")
                
                generator = ColorVariationGenerator()
                generator.set_progress_callback(self.update_generator_progress)
                
                # Create renderer
                if not RENDERING_MODULES_AVAILABLE:
                    raise Exception("Rendering modules not available")
                
                renderer = VTKRenderer(300, 300)
                
                if not renderer.initialize():
                    raise Exception("Failed to initialize renderer")
                
                if not renderer.setup_scene(self.current_file):
                    raise Exception("Failed to setup scene")
                
                # Generate grid
                grid_layout = GridLayout(self.grid_layout_var.get())
                success = generator.generate_color_grid(
                    renderer, Path(output_path), color_variations, grid_layout
                )
                
                if success:
                    self.log_generator_message(f"✓ Color grid saved: {output_path}")
                    messagebox.showinfo("Success", f"Color grid generated!\nSaved to: {output_path}")
                else:
                    self.log_generator_message("✗ Color grid generation failed")
                    
            except Exception as e:
                logger.error(f"Color grid generation error: {e}")
                self.log_generator_message(f"✗ Error: {str(e)}")
            finally:
                self.generator_progress_var.set(0)
        
        threading.Thread(target=run_generation, daemon=True).start()
    
    def update_generator_progress(self, progress: float, message: str):
        """Update generator progress bar and log."""
        self.generator_progress_var.set(progress)
        self.log_generator_message(f"{progress:.1f}% - {message}")
    
    def log_generator_message(self, message: str):
        """Add a message to the generator log."""
        self.generator_log.config(state=tk.NORMAL)
        self.generator_log.insert(tk.END, f"{message}\n")
        self.generator_log.see(tk.END)
        self.generator_log.config(state=tk.DISABLED)
    
    # Help and About methods
    def show_batch_help(self):
        """Show batch processing help dialog."""
        help_text = """
STL Listing Tool - Batch Processing Guide

GETTING STARTED:
1. Add files: File → Add Files to Queue or Add Folder to Queue  
2. Configure processing options in the individual tabs (Analysis, Validation, Rendering, Generators)
3. Start processing: Queue → Start Processing or use the Batch Queue tab

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
    
    def show_about(self):
        """Show about dialog."""
        about_text = """STL Listing Tool v1.0

A professional STL file processing tool with:
• Advanced mesh analysis and validation
• High-quality rendering with material presets  
• Batch processing capabilities
• Professional listing generation

Built with Python, VTK, and Tkinter
© 2024 Terragon Labs"""
        
        messagebox.showinfo("About", about_text)


def main():
    """Main function to run the unified GUI."""
    try:
        try:
            from tkinterdnd2 import TkinterDnD
            root = TkinterDnD.Tk()
        except ImportError:
            root = tk.Tk()
            
        app = STLProcessorGUI(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()