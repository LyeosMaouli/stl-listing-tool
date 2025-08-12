#!/usr/bin/env python3
"""
Test script for the comprehensive error dialog.
"""

import tkinter as tk
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from error_dialog import show_comprehensive_error


def test_file_not_found_error():
    """Test file not found error scenario."""
    try:
        # Simulate file not found error
        file_path = Path("nonexistent_file.stl")
        raise FileNotFoundError(f"No such file or directory: '{file_path}'")
    except Exception as e:
        show_comprehensive_error(
            root,
            "File Not Found",
            f"The selected file does not exist: {file_path}",
            exception=e,
            context={
                "file_path": str(file_path),
                "parent_directory": str(file_path.parent),
                "parent_exists": file_path.parent.exists(),
                "current_working_directory": str(Path.cwd()),
                "operation": "file loading"
            }
        )


def test_stl_loading_error():
    """Test STL loading error scenario."""
    try:
        # Simulate STL loading error
        file_path = Path("D:/dev/stl-listing-tool/stl/kneeling_Darth_Vader_Pen_Holder.stl")
        raise ValueError("Mesh validation failed: invalid geometry detected")
    except Exception as e:
        show_comprehensive_error(
            root,
            "STL Loading Error",
            f"An exception occurred while loading STL file: {file_path}",
            exception=e,
            context={
                "file_path": str(file_path),
                "file_size": "1.2 MB",
                "file_extension": file_path.suffix,
                "operation": "STL file loading",
                "processor_state": "mesh validation failed"
            }
        )


def test_memory_error():
    """Test memory error scenario."""
    try:
        # Simulate memory error
        raise MemoryError("Not enough memory to load large STL file")
    except Exception as e:
        show_comprehensive_error(
            root,
            "Memory Error",
            "Insufficient memory to process the STL file",
            exception=e,
            context={
                "file_path": "large_model.stl",
                "file_size": "500 MB",
                "operation": "STL loading",
                "memory_usage": "High"
            }
        )


def test_rendering_error():
    """Test rendering error scenario."""
    try:
        # Simulate VTK rendering error
        raise RuntimeError("VTK rendering failed: OpenGL context not available")
    except Exception as e:
        show_comprehensive_error(
            root,
            "Rendering Failed",
            "Image rendering failed due to graphics system error",
            exception=e,
            context={
                "file_path": "model.stl",
                "operation": "image rendering",
                "render_width": "1920",
                "render_height": "1080",
                "material_type": "plastic",
                "lighting_preset": "studio",
                "graphics_backend": "VTK"
            }
        )


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Error Dialog Test")
    root.geometry("400x300")
    
    # Create test buttons
    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    tk.Label(frame, text="Enhanced Error Dialog Test", font=("Arial", 16, "bold")).pack(pady=10)
    tk.Label(frame, text="Click a button to test different error scenarios:").pack(pady=5)
    tk.Label(frame, text="New features: Always centers on screen, 'Copy All Text' button, 'Save as .log' option", 
             font=("Arial", 9), fg="blue", wraplength=350).pack(pady=5)
    
    tk.Button(frame, text="File Not Found Error", 
             command=test_file_not_found_error, width=25).pack(pady=5)
    
    tk.Button(frame, text="STL Loading Error", 
             command=test_stl_loading_error, width=25).pack(pady=5)
    
    tk.Button(frame, text="Memory Error", 
             command=test_memory_error, width=25).pack(pady=5)
    
    tk.Button(frame, text="Rendering Error", 
             command=test_rendering_error, width=25).pack(pady=5)
    
    tk.Button(frame, text="Exit", command=root.quit, width=25).pack(pady=10)
    
    root.mainloop()