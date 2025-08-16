#!/usr/bin/env python3
"""
Test script to debug moviepy import issues.
"""

print("Testing moviepy import...")

try:
    import moviepy
    print(f"✓ moviepy module found at: {moviepy.__file__}")
    print(f"✓ moviepy version: {moviepy.__version__}")
except ImportError as e:
    print(f"✗ Failed to import moviepy: {e}")

try:
    from moviepy.editor import ImageSequenceClip, clips_array, concatenate_videoclips
    print("✓ moviepy.editor imports successful")
except ImportError as e:
    print(f"✗ Failed to import from moviepy.editor: {e}")

# Check if running in different Python environment
import sys
print(f"\nPython executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths

# Check installed packages
try:
    import pkg_resources
    installed_packages = [d.project_name for d in pkg_resources.working_set]
    if 'moviepy' in installed_packages:
        print("✓ moviepy found in installed packages")
    else:
        print("✗ moviepy not found in installed packages")
        print("Available packages containing 'movie':")
        for pkg in installed_packages:
            if 'movie' in pkg.lower():
                print(f"  - {pkg}")
except ImportError:
    print("Could not check installed packages (pkg_resources not available)")