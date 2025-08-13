import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import threading
import json
from typing import Optional, Dict, Any
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
    def __init__(self, root):
        self.root = root
        self.root.title("STL Listing Tool")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        self.current_file = None
        self.processor = None
        self.analysis_results = None
        
        # Initialize user config
        self.user_config = get_user_config()
        
        self.setup_ui()
        self.setup_drag_drop()
        self.load_user_settings()
        
        # Save window geometry on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
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
        # Save window geometry before closing
        self.save_window_geometry()
        # Close the application
        self.root.destroy()
    
    def get_temp_render_path(self):
        """Get a safe temporary path for rendering output."""
        temp_dir = Path(tempfile.gettempdir())
        # Ensure the temp directory exists
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Also ensure /tmp/images exists (for any potential screenshot functionality)
        images_dir = temp_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        return temp_dir / "stl_render.png"
        
    def setup_ui(self):
        self.create_menu()
        self.create_main_frame()
        self.create_file_selection()
        self.create_notebook()
        self.create_status_bar()
        
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open STL...", command=self.browse_file, accelerator="Ctrl+O")
        file_menu.add_separator() 
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Ctrl+Q")
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
        self.root.bind('<Control-o>', lambda e: self.browse_file())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        
    def create_main_frame(self):
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        
    def create_file_selection(self):
        file_frame = ttk.LabelFrame(self.main_frame, text="File Selection", padding="10")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        self.file_var = tk.StringVar(value="No file selected")
        
        ttk.Button(file_frame, text="Browse...", command=self.browse_file).grid(row=0, column=0, padx=(0, 10))
        file_label = ttk.Label(file_frame, textvariable=self.file_var, background="white", 
                              relief="sunken", padding="5")
        file_label.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        drop_frame = ttk.Frame(file_frame)
        drop_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        drop_frame.columnconfigure(0, weight=1)
        
        self.drop_area = tk.Label(drop_frame, text="Drop STL files here", 
                                 bg="lightgray", fg="gray", 
                                 border=2, relief="ridge", height=3)
        self.drop_area.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
    def create_notebook(self):
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.create_analysis_tab()
        self.create_validation_tab()
        self.create_rendering_tab()
        self.create_generators_tab()
        
    def create_analysis_tab(self):
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
        self.rendering_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.rendering_frame, text="Rendering")
        
        self.rendering_frame.columnconfigure(1, weight=1)
        self.rendering_frame.rowconfigure(2, weight=1)  # Make the render_display row expandable
        
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
        
        # Background preview (larger thumbnail) - no fixed size, let image determine size
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
        
    def create_status_bar(self):
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.status_frame.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.status_frame, textvariable=self.status_var,
                                relief="sunken", padding="5")
        status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
    def setup_drag_drop(self):
        def on_drop(event):
            files = self.root.tk.splitlist(event.data)
            if files:
                file_path = Path(files[0])
                if file_path.suffix.lower() == '.stl':
                    self.load_file(file_path)
                else:
                    show_error_with_logging(
                        self.root, 
                        "Invalid File Type", 
                        "Please select an STL file",
                        context={"attempted_file": str(file_path), "file_extension": file_path.suffix}
                    )
                    
        try:
            from tkinterdnd2 import DND_FILES
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind('<<Drop>>', on_drop)
            self.dnd_available = True
        except ImportError:
            self.dnd_available = False
            logger.warning("Drag-and-drop not available. Install tkinterdnd2 for full GUI functionality.")
            # Update drop area to show drag-and-drop is unavailable
            self.drop_area.config(
                text="Drag-and-drop unavailable\nUse Browse button instead",
                bg="lightyellow",
                fg="darkgray"
            )
            
    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select STL File",
            filetypes=[("STL files", "*.stl"), ("All files", "*.*")]
        )
        if file_path:
            self.load_file(Path(file_path))
            
    def load_file(self, file_path: Path):
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
        self.file_var.set(str(file_path))
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
            show_comprehensive_error(
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
                show_comprehensive_error(
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
                show_comprehensive_error(
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
                show_comprehensive_error(
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
        
    def display_validation_results(self, results):
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
        
    def render_image(self):
        if not self.current_file or not self.processor:
            messagebox.showwarning("Warning", "Please select an STL file first")
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
            
        def run_render():
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
                
                if not renderer.setup_scene(self.current_file):
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
                logger.critical(f"ABOUT TO CALL renderer.render() with window size: {renderer.render_window.GetSize()}")
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
                        "file_path": str(self.current_file),
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
                
        threading.Thread(target=run_render, daemon=True).start()
        
    def display_rendered_image(self, image_path: Path):
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
                show_comprehensive_error(
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
    
    def create_generators_tab(self):
        """Create the generators tab for video and image generation."""
        self.generators_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.generators_frame, text="Generators")
        
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
    
    def generate_rotation_video(self):
        """Generate a 360° rotation video of the current model."""
        if not self.current_file or not self.processor:
            messagebox.showwarning("Warning", "Please select an STL file first")
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
        
        def run_generation():
            try:
                # Clear log
                self.generator_log.config(state=tk.NORMAL)
                self.generator_log.delete(1.0, tk.END)
                self.generator_log.config(state=tk.DISABLED)
                
                self.log_generator_message("Starting video generation...")
                
                # Create video generator
                generator = RotationVideoGenerator()
                generator.set_progress_callback(self.update_generator_progress)
                
                # Get settings
                video_format = VideoFormat(self.video_format_var.get())
                video_quality = VideoQuality(self.video_quality_var.get())
                duration = float(self.video_duration_var.get())
                
                # Create renderer for video generation
                if not RENDERING_MODULES_AVAILABLE:
                    raise Exception("Rendering modules not available")
                
                from .rendering.vtk_renderer import VTKRenderer
                width = int(self.width_var.get())
                height = int(self.height_var.get())
                renderer = VTKRenderer(width, height)
                
                if not renderer.initialize():
                    raise Exception("Failed to initialize renderer")
                
                if not renderer.setup_scene(self.current_file):
                    raise Exception("Failed to setup scene")
                
                # Apply current material and lighting settings
                from .rendering.base_renderer import MaterialType, LightingPreset
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
                        "file_path": str(self.current_file),
                        "operation": "rotation video generation",
                        "video_format": self.video_format_var.get(),
                        "video_quality": self.video_quality_var.get()
                    }
                )
            finally:
                self.generator_progress_var.set(0)
        
        # Run in separate thread
        threading.Thread(target=run_generation, daemon=True).start()
    
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
                
                from .rendering.vtk_renderer import VTKRenderer
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
        
    def show_about(self):
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
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except ImportError:
        root = tk.Tk()
        
    app = STLProcessorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()