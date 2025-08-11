import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import traceback
import sys
import platform
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
# Optional clipboard support
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

from utils.logger import logger


class ComprehensiveErrorDialog:
    """
    A comprehensive error dialog that provides detailed error information,
    context, suggested solutions, and debugging capabilities.
    """
    
    def __init__(self, parent: tk.Tk, error_title: str, error_message: str, 
                 exception: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        self.parent = parent
        self.error_title = error_title
        self.error_message = error_message
        self.exception = exception
        self.context = context or {}
        
        # Debug logging for error dialog creation
        logger.info(f"Creating error dialog: title='{error_title}', message='{error_message[:100]}{'...' if len(error_message) > 100 else ''}'")
        if '/tmp/images/' in str(error_message):
            logger.error(f"ERROR: Image path detected in error message during dialog creation: {error_message}")
            logger.error(f"Context: {self.context}")
            logger.error(f"Exception: {exception}")
        
        self.dialog = None
        self.create_dialog()
        
    def create_dialog(self):
        """Create the comprehensive error dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"Error - {self.error_title}")
        self.dialog.geometry("800x700")
        self.dialog.minsize(600, 500)
        
        # Make dialog modal
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center dialog on parent
        self.center_dialog()
        
        # Create UI elements
        self.create_header()
        self.create_notebook()
        self.create_buttons()
        
        # Focus on dialog
        self.dialog.focus_set()
        
    def center_dialog(self):
        """Center the dialog on the screen (not just parent window)."""
        self.dialog.update_idletasks()
        
        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        
        # Get dialog dimensions
        dialog_width = self.dialog.winfo_width()
        dialog_height = self.dialog.winfo_height()
        
        # Calculate center position
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        
        # Ensure dialog doesn't go off-screen
        x = max(0, min(x, screen_width - dialog_width))
        y = max(0, min(y, screen_height - dialog_height))
        
        self.dialog.geometry(f"+{x}+{y}")
        
    def create_header(self):
        """Create the error header with icon and summary."""
        header_frame = ttk.Frame(self.dialog, padding="20")
        header_frame.pack(fill=tk.X)
        
        # Error icon and title
        icon_frame = ttk.Frame(header_frame)
        icon_frame.pack(fill=tk.X)
        
        # Error icon (using Unicode symbol)
        error_icon = ttk.Label(icon_frame, text="⚠", font=("Arial", 24), foreground="red")
        error_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        # Title and timestamp
        title_frame = ttk.Frame(icon_frame)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        title_label = ttk.Label(title_frame, text=self.error_title, 
                               font=("Arial", 14, "bold"))
        title_label.pack(anchor=tk.W)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_label = ttk.Label(title_frame, text=f"Occurred at: {timestamp}", 
                              font=("Arial", 9), foreground="gray")
        time_label.pack(anchor=tk.W)
        
        # Quick summary
        summary_frame = ttk.LabelFrame(header_frame, text="Error Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(10, 0))
        
        summary_text = tk.Text(summary_frame, height=3, wrap=tk.WORD, 
                              font=("Arial", 10), state=tk.DISABLED,
                              background=self.dialog.cget('bg'))
        summary_text.pack(fill=tk.X)
        
        summary_text.config(state=tk.NORMAL)
        summary_text.insert(1.0, self.error_message)
        summary_text.config(state=tk.DISABLED)
        
    def create_notebook(self):
        """Create tabbed interface for detailed error information."""
        self.notebook = ttk.Notebook(self.dialog)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        self.create_details_tab()
        self.create_context_tab()
        self.create_system_tab()
        self.create_suggestions_tab()
        
    def create_details_tab(self):
        """Create the detailed error information tab."""
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text="Error Details")
        
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(1, weight=1)
        
        # Exception type and message
        if self.exception:
            exception_frame = ttk.LabelFrame(details_frame, text="Exception Information", padding="10")
            exception_frame.pack(fill=tk.X, pady=(0, 10))
            exception_frame.columnconfigure(1, weight=1)
            
            ttk.Label(exception_frame, text="Type:", font=("Arial", 10, "bold")).grid(
                row=0, column=0, sticky=tk.W, padx=(0, 10))
            ttk.Label(exception_frame, text=type(self.exception).__name__,
                     font=("Arial", 10)).grid(row=0, column=1, sticky=tk.W)
            
            ttk.Label(exception_frame, text="Message:", font=("Arial", 10, "bold")).grid(
                row=1, column=0, sticky=tk.NW, padx=(0, 10), pady=(5, 0))
            
            msg_text = tk.Text(exception_frame, height=3, wrap=tk.WORD, font=("Arial", 10))
            msg_text.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(5, 0))
            msg_text.insert(1.0, str(self.exception))
            msg_text.config(state=tk.DISABLED)
        
        # Full traceback
        traceback_frame = ttk.LabelFrame(details_frame, text="Full Traceback", padding="10")
        traceback_frame.pack(fill=tk.BOTH, expand=True)
        traceback_frame.columnconfigure(0, weight=1)
        traceback_frame.rowconfigure(0, weight=1)
        
        self.traceback_text = scrolledtext.ScrolledText(
            traceback_frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED)
        self.traceback_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Get and display traceback
        if self.exception:
            tb_lines = traceback.format_exception(type(self.exception), self.exception, 
                                                 self.exception.__traceback__)
            traceback_str = "".join(tb_lines)
        else:
            # Get current traceback if no exception provided
            traceback_str = "".join(traceback.format_stack())
        
        self.traceback_text.config(state=tk.NORMAL)
        self.traceback_text.insert(1.0, traceback_str)
        self.traceback_text.config(state=tk.DISABLED)
        
    def create_context_tab(self):
        """Create the context information tab."""
        context_frame = ttk.Frame(self.notebook)
        self.notebook.add(context_frame, text="Context")
        
        context_frame.columnconfigure(0, weight=1)
        context_frame.rowconfigure(0, weight=1)
        
        context_text = scrolledtext.ScrolledText(
            context_frame, wrap=tk.WORD, font=("Arial", 10), state=tk.DISABLED)
        context_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Build context information
        context_info = []
        
        # Add provided context
        if self.context:
            context_info.append("=== Application Context ===")
            for key, value in self.context.items():
                context_info.append(f"{key}: {value}")
            context_info.append("")
        
        # Add file context if available
        if 'file_path' in self.context:
            file_path = Path(self.context['file_path'])
            context_info.append("=== File Information ===")
            context_info.append(f"File Path: {file_path}")
            context_info.append(f"File Exists: {file_path.exists() if file_path else 'N/A'}")
            if file_path and file_path.exists():
                try:
                    stat = file_path.stat()
                    context_info.append(f"File Size: {stat.st_size:,} bytes")
                    context_info.append(f"Last Modified: {datetime.fromtimestamp(stat.st_mtime)}")
                    context_info.append(f"File Extension: {file_path.suffix}")
                except Exception as e:
                    context_info.append(f"Could not get file stats: {e}")
            context_info.append("")
        
        # Add recent log entries
        context_info.append("=== Recent Log Entries ===")
        try:
            # Try to get recent log entries from logger
            log_entries = self.get_recent_log_entries()
            if log_entries:
                context_info.extend(log_entries)
            else:
                context_info.append("No recent log entries available")
        except Exception as e:
            context_info.append(f"Could not retrieve log entries: {e}")
        
        context_text.config(state=tk.NORMAL)
        context_text.insert(1.0, "\n".join(context_info))
        context_text.config(state=tk.DISABLED)
        
    def create_system_tab(self):
        """Create the system information tab."""
        system_frame = ttk.Frame(self.notebook)
        self.notebook.add(system_frame, text="System Info")
        
        system_frame.columnconfigure(0, weight=1)
        system_frame.rowconfigure(0, weight=1)
        
        system_text = scrolledtext.ScrolledText(
            system_frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED)
        system_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Collect system information
        system_info = []
        system_info.append("=== System Information ===")
        system_info.append(f"Platform: {platform.platform()}")
        system_info.append(f"Python Version: {sys.version}")
        system_info.append(f"Python Executable: {sys.executable}")
        system_info.append("")
        
        system_info.append("=== Environment ===")
        system_info.append(f"Working Directory: {Path.cwd()}")
        system_info.append(f"PATH: {sys.path[0]}")
        system_info.append("")
        
        # Module versions
        system_info.append("=== Installed Packages ===")
        key_modules = ['tkinter', 'trimesh', 'numpy', 'vtk', 'PIL', 'open3d']
        for module_name in key_modules:
            try:
                module = __import__(module_name)
                version = getattr(module, '__version__', 'Unknown')
                system_info.append(f"{module_name}: {version}")
            except ImportError:
                system_info.append(f"{module_name}: Not installed")
            except Exception as e:
                system_info.append(f"{module_name}: Error - {e}")
        
        system_text.config(state=tk.NORMAL)
        system_text.insert(1.0, "\n".join(system_info))
        system_text.config(state=tk.DISABLED)
        
    def create_suggestions_tab(self):
        """Create the suggestions and solutions tab."""
        suggestions_frame = ttk.Frame(self.notebook)
        self.notebook.add(suggestions_frame, text="Suggestions")
        
        suggestions_frame.columnconfigure(0, weight=1)
        suggestions_frame.rowconfigure(0, weight=1)
        
        suggestions_text = scrolledtext.ScrolledText(
            suggestions_frame, wrap=tk.WORD, font=("Arial", 10), state=tk.DISABLED)
        suggestions_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Generate context-aware suggestions
        suggestions = self.generate_suggestions()
        
        suggestions_text.config(state=tk.NORMAL)
        suggestions_text.insert(1.0, "\n".join(suggestions))
        suggestions_text.config(state=tk.DISABLED)
        
    def generate_suggestions(self) -> List[str]:
        """Generate context-aware suggestions for fixing the error."""
        suggestions = []
        suggestions.append("=== Suggested Solutions ===")
        suggestions.append("")
        
        error_msg_lower = self.error_message.lower()
        exception_name = type(self.exception).__name__ if self.exception else ""
        
        # File loading errors
        if "failed to load" in error_msg_lower or "file not found" in error_msg_lower:
            suggestions.append("File Loading Issues:")
            suggestions.append("• Ensure the file path is correct and the file exists")
            suggestions.append("• Check file permissions - ensure the file is readable")
            suggestions.append("• Verify the file is a valid STL file and not corrupted")
            suggestions.append("• Try opening the file in another STL viewer to verify it's valid")
            suggestions.append("• Check available disk space and memory")
            suggestions.append("")
        
        # Memory errors
        if "memory" in error_msg_lower or exception_name == "MemoryError":
            suggestions.append("Memory Issues:")
            suggestions.append("• The STL file may be too large for available memory")
            suggestions.append("• Try closing other applications to free up memory")
            suggestions.append("• Consider using a smaller/simplified version of the STL file")
            suggestions.append("• Restart the application to free up memory")
            suggestions.append("")
        
        # Import/dependency errors
        if "import" in error_msg_lower or exception_name in ["ImportError", "ModuleNotFoundError"]:
            suggestions.append("Dependency Issues:")
            suggestions.append("• A required Python package may be missing or incompatible")
            suggestions.append("• Try reinstalling the application: pip install -e .")
            suggestions.append("• Check the System Info tab for missing packages")
            suggestions.append("• Update packages: pip install --upgrade -r requirements.txt")
            suggestions.append("")
        
        # VTK/rendering errors
        if "vtk" in error_msg_lower or "render" in error_msg_lower:
            suggestions.append("Rendering Issues:")
            suggestions.append("• VTK may not be properly installed or configured")
            suggestions.append("• Try a different rendering backend if available")
            suggestions.append("• Check graphics drivers are up to date")
            suggestions.append("• Try running with software rendering")
            suggestions.append("")
        
        # Mesh validation errors
        if "mesh" in error_msg_lower or "validation" in error_msg_lower:
            suggestions.append("Mesh Issues:")
            suggestions.append("• The STL file may have mesh integrity problems")
            suggestions.append("• Try using mesh repair software like Meshmixer or Blender")
            suggestions.append("• Check the Validation tab for specific mesh issues")
            suggestions.append("• Enable auto-repair option if available")
            suggestions.append("")
        
        # Generic suggestions
        suggestions.append("General Troubleshooting:")
        suggestions.append("• Check the Error Details tab for specific error information")
        suggestions.append("• Review the Context tab for additional information")
        suggestions.append("• Try with a different STL file to isolate the issue")
        suggestions.append("• Restart the application")
        suggestions.append("• Check application logs for more details")
        suggestions.append("")
        
        suggestions.append("Getting Help:")
        suggestions.append("• Copy error details using the 'Copy to Clipboard' button")
        suggestions.append("• Include system information when reporting issues")
        suggestions.append("• Check project documentation and issue tracker")
        suggestions.append("• Provide the full error details when seeking support")
        
        return suggestions
        
    def get_recent_log_entries(self, max_entries: int = 10) -> List[str]:
        """Get recent log entries from the logger."""
        # This is a simplified version - in a real implementation,
        # you might want to maintain a log buffer or read from log files
        try:
            # Try to get recent entries from logger if it supports it
            if hasattr(logger, 'get_recent_entries'):
                return logger.get_recent_entries(max_entries)
            else:
                return ["Recent log entries not available (logger doesn't support buffering)"]
        except Exception:
            return ["Could not retrieve recent log entries"]
    
    def get_all_dialog_text(self) -> str:
        """Get all text content from all tabs in the dialog."""
        all_text = []
        
        # Header information
        all_text.append("=" * 80)
        all_text.append(f"ERROR DIALOG CONTENT - {self.error_title}")
        all_text.append("=" * 80)
        all_text.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        all_text.append("")
        
        # Summary from header
        all_text.append("ERROR SUMMARY:")
        all_text.append("-" * 40)
        # Debug: Check if error_message contains image path
        if '/tmp/images/' in str(self.error_message):
            logger.warning(f"Error message appears to contain image path: {self.error_message}")
            all_text.append("WARNING: Error message contains image path - this may indicate a bug")
            all_text.append(f"Original message: {self.error_message}")
        else:
            all_text.append(self.error_message)
        all_text.append("")
        
        # Error Details tab content
        if hasattr(self, 'traceback_text'):
            all_text.append("ERROR DETAILS:")
            all_text.append("-" * 40)
            
            if self.exception:
                all_text.append(f"Exception Type: {type(self.exception).__name__}")
                all_text.append(f"Exception Message: {str(self.exception)}")
                all_text.append("")
            
            all_text.append("Full Traceback:")
            try:
                traceback_content = self.traceback_text.get(1.0, tk.END).strip()
                all_text.append(traceback_content)
            except:
                all_text.append("Could not retrieve traceback content")
            all_text.append("")
        
        # Context tab content
        all_text.append("CONTEXT INFORMATION:")
        all_text.append("-" * 40)
        
        # Add provided context
        if self.context:
            all_text.append("Application Context:")
            for key, value in self.context.items():
                all_text.append(f"  {key}: {value}")
            all_text.append("")
        
        # File context if available
        if 'file_path' in self.context:
            file_path = Path(self.context['file_path'])
            all_text.append("File Information:")
            all_text.append(f"  File Path: {file_path}")
            all_text.append(f"  File Exists: {file_path.exists() if file_path else 'N/A'}")
            if file_path and file_path.exists():
                try:
                    stat = file_path.stat()
                    all_text.append(f"  File Size: {stat.st_size:,} bytes")
                    all_text.append(f"  Last Modified: {datetime.fromtimestamp(stat.st_mtime)}")
                    all_text.append(f"  File Extension: {file_path.suffix}")
                except Exception as e:
                    all_text.append(f"  Could not get file stats: {e}")
            all_text.append("")
        
        # Recent log entries
        all_text.append("Recent Log Entries:")
        try:
            log_entries = self.get_recent_log_entries()
            all_text.extend(log_entries)
        except Exception as e:
            all_text.append(f"Could not retrieve log entries: {e}")
        all_text.append("")
        
        # System Information
        all_text.append("SYSTEM INFORMATION:")
        all_text.append("-" * 40)
        all_text.append(f"Platform: {platform.platform()}")
        all_text.append(f"Python Version: {sys.version}")
        all_text.append(f"Python Executable: {sys.executable}")
        all_text.append(f"Working Directory: {Path.cwd()}")
        all_text.append("")
        
        # Module versions
        all_text.append("Installed Packages:")
        key_modules = ['tkinter', 'trimesh', 'numpy', 'vtk', 'PIL', 'open3d']
        for module_name in key_modules:
            try:
                module = __import__(module_name)
                version = getattr(module, '__version__', 'Unknown')
                all_text.append(f"  {module_name}: {version}")
            except ImportError:
                all_text.append(f"  {module_name}: Not installed")
            except Exception as e:
                all_text.append(f"  {module_name}: Error - {e}")
        all_text.append("")
        
        # Suggestions
        suggestions = self.generate_suggestions()
        all_text.extend(suggestions)
        
        return "\n".join(all_text)
        
    def create_buttons(self):
        """Create the dialog buttons.""" 
        button_frame = ttk.Frame(self.dialog, padding="20")
        button_frame.pack(fill=tk.X)
        
        # Left side buttons (actions)
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        # Copy all text button (primary copy function)
        copy_all_button = ttk.Button(left_buttons, text="Copy All Text", 
                                    command=self.copy_all_text)
        copy_all_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Copy structured report button (original functionality)
        copy_report_button = ttk.Button(left_buttons, text="Copy Error Report", 
                                       command=self.copy_to_clipboard)
        copy_report_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Save as .log file button
        save_log_button = ttk.Button(left_buttons, text="Save as .log", 
                                    command=self.save_as_log_file)
        save_log_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Save full report button (original functionality)
        save_report_button = ttk.Button(left_buttons, text="Save Full Report", 
                                       command=self.save_error_report)
        save_report_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Right side buttons (navigation)
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        # Close button
        close_button = ttk.Button(right_buttons, text="Close", command=self.close_dialog)
        close_button.pack(side=tk.RIGHT)
        
        # Make close button default
        self.dialog.bind('<Return>', lambda e: self.close_dialog())
        self.dialog.bind('<Escape>', lambda e: self.close_dialog())
    
    def copy_all_text(self):
        """Copy all text content from the dialog to clipboard."""
        try:
            all_text = self.get_all_dialog_text()
            
            if CLIPBOARD_AVAILABLE:
                pyperclip.copy(all_text)
                messagebox.showinfo("Copied", "All dialog text copied to clipboard!", parent=self.dialog)
            else:
                # Fallback: use tkinter clipboard
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(all_text)
                self.dialog.update()  # Now it stays on the clipboard after the window is closed
                messagebox.showinfo("Copied", "All dialog text copied to clipboard!\n(Using fallback method)", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy all text to clipboard: {e}", parent=self.dialog)
    
    def save_as_log_file(self):
        """Save all dialog content as a .log file."""
        try:
            from tkinter import filedialog
            
            # Debug logging at start of save operation
            logger.info("Starting save_as_log_file operation")
            logger.info(f"Error title: {self.error_title}")
            logger.info(f"Error message: {self.error_message}")
            logger.info(f"Context keys: {list(self.context.keys()) if self.context else 'None'}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"error_log_{timestamp}.log"
            
            file_path = filedialog.asksaveasfilename(
                parent=self.dialog,
                title="Save Error Log",
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                initialname=default_filename
            )
            
            if file_path:
                logger.info(f"User selected save path: {file_path}")
                
                # Get the error log content (not image paths)
                all_text = self.get_all_dialog_text()
                logger.info(f"Generated dialog text length: {len(all_text) if all_text else 0}")
                logger.info(f"Dialog text preview (first 200 chars): {all_text[:200] if all_text else 'None'}")
                
                # Debug: Ensure we're not accidentally saving image paths
                contains_image_path = '/tmp/images/' in all_text[:500] if all_text else False
                starts_with_image_path = all_text.strip().startswith('/tmp/images/') if all_text else False
                
                logger.info(f"Content analysis: starts_with_image_path={starts_with_image_path}, contains_image_path={contains_image_path}")
                
                if all_text and not (starts_with_image_path or contains_image_path):
                    logger.info("Saving normal dialog text")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(all_text)
                    messagebox.showinfo("Saved", f"Error log saved to {file_path}", parent=self.dialog)
                    logger.info("Successfully saved normal dialog text")
                else:
                    # Fallback: Generate fresh error report if content appears corrupted
                    logger.warning(f"Dialog text appears corrupted (contains image paths), generating fresh error report")
                    logger.warning(f"Corrupted content preview: {all_text[:500] if all_text else 'None'}")
                    
                    fresh_report = self.generate_full_error_report()
                    logger.info(f"Generated fresh report length: {len(fresh_report)}")
                    logger.info(f"Fresh report preview: {fresh_report[:200]}")
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fresh_report)
                    messagebox.showinfo("Saved", f"Error log saved to {file_path} (used fallback report due to corrupted content)", parent=self.dialog)
                    logger.info("Successfully saved fallback report")
        except Exception as e:
            logger.error(f"Failed to save log file: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to save log file: {e}", parent=self.dialog)
        
    def copy_to_clipboard(self):
        """Copy all error information to clipboard."""
        try:
            error_report = self.generate_full_error_report()
            
            if CLIPBOARD_AVAILABLE:
                pyperclip.copy(error_report)
                messagebox.showinfo("Copied", "Error details copied to clipboard!", parent=self.dialog)
            else:
                # Fallback: use tkinter clipboard
                self.dialog.clipboard_clear()
                self.dialog.clipboard_append(error_report)
                self.dialog.update()  # Now it stays on the clipboard after the window is closed
                messagebox.showinfo("Copied", "Error details copied to clipboard!\n(Using fallback method)", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard: {e}", parent=self.dialog)
            
    def save_error_report(self):
        """Save error report to a file."""
        try:
            from tkinter import filedialog
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"error_report_{timestamp}.txt"
            
            file_path = filedialog.asksaveasfilename(
                parent=self.dialog,
                title="Save Error Report",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialname=default_filename
            )
            
            if file_path:
                error_report = self.generate_full_error_report()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(error_report)
                messagebox.showinfo("Saved", f"Error report saved to {file_path}", parent=self.dialog)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save error report: {e}", parent=self.dialog)
            
    def generate_full_error_report(self) -> str:
        """Generate a complete error report."""
        report_lines = []
        
        # Header
        report_lines.append("=" * 80)
        report_lines.append("STL PROCESSOR ERROR REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Error Title: {self.error_title}")
        report_lines.append("")
        
        # Error summary
        report_lines.append("ERROR SUMMARY:")
        report_lines.append("-" * 40)
        report_lines.append(self.error_message)
        report_lines.append("")
        
        # Exception details
        if self.exception:
            report_lines.append("EXCEPTION DETAILS:")
            report_lines.append("-" * 40)
            report_lines.append(f"Type: {type(self.exception).__name__}")
            report_lines.append(f"Message: {str(self.exception)}")
            report_lines.append("")
            
            report_lines.append("FULL TRACEBACK:")
            report_lines.append("-" * 40)
            tb_lines = traceback.format_exception(type(self.exception), self.exception, 
                                                 self.exception.__traceback__)
            report_lines.extend("".join(tb_lines).split('\n'))
            report_lines.append("")
        
        # Context
        if self.context:
            report_lines.append("CONTEXT INFORMATION:")
            report_lines.append("-" * 40)
            for key, value in self.context.items():
                report_lines.append(f"{key}: {value}")
            report_lines.append("")
        
        # System info
        report_lines.append("SYSTEM INFORMATION:")
        report_lines.append("-" * 40)
        report_lines.append(f"Platform: {platform.platform()}")
        report_lines.append(f"Python Version: {sys.version}")
        report_lines.append(f"Working Directory: {Path.cwd()}")
        report_lines.append("")
        
        # Suggestions
        suggestions = self.generate_suggestions()
        report_lines.extend(suggestions)
        
        return "\n".join(report_lines)
        
    def close_dialog(self):
        """Close the error dialog."""
        self.dialog.grab_release()
        self.dialog.destroy()
        
    def show(self):
        """Show the dialog and wait for it to be dismissed."""
        self.dialog.wait_window()


def show_comprehensive_error(parent: tk.Tk, title: str, message: str, 
                           exception: Optional[Exception] = None, 
                           context: Optional[Dict[str, Any]] = None):
    """
    Show a comprehensive error dialog.
    
    Args:
        parent: Parent tkinter window
        title: Error title/category
        message: Main error message
        exception: Exception object if available
        context: Additional context information
    """
    dialog = ComprehensiveErrorDialog(parent, title, message, exception, context)
    dialog.show()