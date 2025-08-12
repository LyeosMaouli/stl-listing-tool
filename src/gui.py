import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import threading
import json
from typing import Optional, Dict, Any
import os
import tempfile

# Use absolute imports for entry point compatibility
try:
    from core.stl_processor import STLProcessor
    from core.dimension_extractor import DimensionExtractor
    from core.mesh_validator import MeshValidator, ValidationLevel
    CORE_MODULES_AVAILABLE = True
    CORE_IMPORT_ERROR = None
except ImportError as e:
    CORE_MODULES_AVAILABLE = False
    CORE_IMPORT_ERROR = e

try:
    from rendering.vtk_renderer import VTKRenderer
    from rendering.base_renderer import MaterialType, LightingPreset
    RENDERING_MODULES_AVAILABLE = True
    RENDERING_IMPORT_ERROR = None
except ImportError as e:
    RENDERING_MODULES_AVAILABLE = False
    RENDERING_IMPORT_ERROR = e

from utils.logger import setup_logger
from error_dialog import show_comprehensive_error

logger = setup_logger("stl_processor_gui")

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
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        self.current_file = None
        self.processor = None
        self.analysis_results = None
        
        self.setup_ui()
        self.setup_drag_drop()
    
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
        
        self.repair_var = tk.BooleanVar()
        ttk.Checkbutton(controls_frame, text="Auto Repair", 
                       variable=self.repair_var).pack(side=tk.LEFT, padx=(0, 10))
        
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
        self.rendering_frame.rowconfigure(3, weight=1)
        
        settings_frame = ttk.LabelFrame(self.rendering_frame, text="Render Settings", padding="10")
        settings_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(settings_frame, text="Material:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.material_var = tk.StringVar(value="plastic")
        material_combo = ttk.Combobox(settings_frame, textvariable=self.material_var,
                                     values=["plastic", "metal", "resin", "ceramic", "wood", "glass"],
                                     state="readonly")
        material_combo.grid(row=0, column=1, padx=(0, 20))
        
        ttk.Label(settings_frame, text="Lighting:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.lighting_var = tk.StringVar(value="studio")
        lighting_combo = ttk.Combobox(settings_frame, textvariable=self.lighting_var,
                                     values=["studio", "natural", "dramatic", "soft"],
                                     state="readonly")
        lighting_combo.grid(row=0, column=3, padx=(0, 20))
        
        ttk.Label(settings_frame, text="Size:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        size_frame = ttk.Frame(settings_frame)
        size_frame.grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.width_var = tk.StringVar(value="1920")
        self.height_var = tk.StringVar(value="1080")
        
        ttk.Entry(size_frame, textvariable=self.width_var, width=8).pack(side=tk.LEFT)
        ttk.Label(size_frame, text=" x ").pack(side=tk.LEFT)
        ttk.Entry(size_frame, textvariable=self.height_var, width=8).pack(side=tk.LEFT)
        ttk.Label(size_frame, text=" pixels").pack(side=tk.LEFT)
        
        render_button_frame = ttk.Frame(self.rendering_frame)
        render_button_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        ttk.Button(render_button_frame, text="Render Image", 
                  command=self.render_image).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(render_button_frame, text="Save As...", 
                  command=self.save_render).pack(side=tk.LEFT)
        
        self.render_display = tk.Label(self.rendering_frame, text="Rendered image will appear here",
                                      bg="white", relief="sunken", width=60, height=20)
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