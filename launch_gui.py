#!/usr/bin/env python3
"""
GUI Launcher for STL Processor
Alternative launcher if entry points have issues
"""
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

if __name__ == "__main__":
    try:
        from gui import main
        main()
    except ImportError as e:
        print(f"Error: Failed to import GUI module: {e}")
        print("Please make sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        print("  pip install tkinterdnd2  # Optional, for drag & drop")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)