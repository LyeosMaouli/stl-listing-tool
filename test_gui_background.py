#!/usr/bin/env python3
"""
Test script to verify GUI background image functionality.
This tests the GUI modifications without requiring full GUI display.
"""

import sys
from pathlib import Path
from PIL import Image
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))


def test_gui_background_methods():
    """Test that GUI has background image methods."""
    try:
        # Import the GUI class
        from gui import STLProcessorGUI
        
        # Check if the required methods exist
        required_methods = [
            'browse_background_image',
            'clear_background_image',
            'update_background_preview'
        ]
        
        for method_name in required_methods:
            if hasattr(STLProcessorGUI, method_name):
                print(f"✓ STLProcessorGUI.{method_name} exists")
            else:
                print(f"✗ STLProcessorGUI.{method_name} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ GUI methods test failed: {e}")
        return False


def test_gui_structure():
    """Test that GUI file contains background-related code."""
    try:
        gui_file_path = Path("src/gui.py")
        
        if not gui_file_path.exists():
            print("✗ GUI file not found")
            return False
        
        content = gui_file_path.read_text()
        
        # Check for key background-related GUI code
        required_patterns = [
            'Select Background...',
            'background_path',
            'background_var',
            'bg_preview',
            'set_background_image',
            'update_background_preview',
            'Background image selected'
        ]
        
        for pattern in required_patterns:
            if pattern in content:
                print(f"✓ GUI contains: {pattern}")
            else:
                print(f"✗ GUI missing: {pattern}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ GUI structure test failed: {e}")
        return False


def test_background_preview_logic():
    """Test the background preview thumbnail logic."""
    try:
        # Create a test image
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)
        
        # Create sample image 
        test_img = np.zeros((200, 300, 3), dtype=np.uint8)
        test_img[:, :, 0] = 150  # Red background
        test_img[:, :, 1] = 100  # Green component
        test_img[:, :, 2] = 200  # Blue component
        
        test_pil = Image.fromarray(test_img, 'RGB')
        test_path = output_dir / "test_bg_gui.png"
        test_pil.save(test_path)
        
        # Test thumbnail creation (simulating the GUI method)
        with Image.open(test_path) as img:
            original_size = img.size
            img.thumbnail((64, 48), Image.Resampling.LANCZOS)
            thumbnail_size = img.size
            
            print(f"✓ Original image size: {original_size}")
            print(f"✓ Thumbnail size: {thumbnail_size}")
            
            # Verify thumbnail is smaller
            if thumbnail_size[0] <= 64 and thumbnail_size[1] <= 48:
                print("✓ Thumbnail created with correct max dimensions")
            else:
                print(f"✗ Thumbnail too large: {thumbnail_size}")
                return False
        
        # Save thumbnail for visual inspection
        thumbnail_path = output_dir / "test_thumbnail.png"
        with Image.open(test_path) as img:
            img.thumbnail((64, 48), Image.Resampling.LANCZOS)
            img.save(thumbnail_path)
        print(f"✓ Test thumbnail saved: {thumbnail_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Background preview test failed: {e}")
        return False


def test_gui_background_integration():
    """Test that rendering integration has background support."""
    try:
        gui_file_path = Path("src/gui.py")
        content = gui_file_path.read_text()
        
        # Check for background integration in render method
        integration_patterns = [
            'self.background_path and self.background_path.exists()',
            'renderer.set_background_image',
            'background_image',
            'Loading background image'
        ]
        
        for pattern in integration_patterns:
            if pattern in content:
                print(f"✓ Render integration has: {pattern}")
            else:
                print(f"✗ Render integration missing: {pattern}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ GUI integration test failed: {e}")
        return False


def main():
    """Run all GUI background tests."""
    print("=== GUI Background Image Tests ===\n")
    
    tests = [
        ("GUI Background Methods", test_gui_background_methods),
        ("GUI Structure", test_gui_structure),
        ("Background Preview Logic", test_background_preview_logic),
        ("GUI Background Integration", test_gui_background_integration),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        if test_func():
            print(f"✓ {test_name} PASSED\n")
            passed += 1
        else:
            print(f"✗ {test_name} FAILED\n")
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("\n🎉 All GUI tests passed! Background image functionality is integrated.")
        print("\nGUI Features:")
        print("• 'Select Background...' button in Rendering tab")
        print("• 'Clear' button to remove background")
        print("• Live preview thumbnail of selected background")
        print("• Status text showing selected filename")
        print("• Integration with VTK renderer for background compositing")
        print("\nUsage:")
        print("1. Open the GUI: python src/gui.py")
        print("2. Load an STL file")
        print("3. Go to Rendering tab")
        print("4. Click 'Select Background...' to choose an image")
        print("5. Configure other render settings")
        print("6. Click 'Render Image' to create image with background")
        return True
    else:
        print(f"\n❌ {total - passed} tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)