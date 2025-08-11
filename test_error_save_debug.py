#!/usr/bin/env python3
"""
Test script to debug the error dialog save issue.
This will help us isolate where the image path is coming from.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test the error dialog functionality without GUI
def test_error_dialog_content():
    """Test creating error dialog content to see if we can reproduce the issue."""
    from error_dialog import ComprehensiveErrorDialog
    from utils.logger import setup_logger
    
    # Setup logging
    logger = setup_logger("error_debug", level="DEBUG")
    
    # Test 1: Normal error message
    print("=== Test 1: Normal error message ===")
    try:
        # Mock a parent (we won't actually show the dialog)
        class MockParent:
            pass
        
        parent = MockParent()
        
        # Create error dialog with normal content
        error_msg = "This is a normal error message"
        context = {
            "file_path": "/some/normal/path.stl",
            "operation": "test operation"
        }
        
        # Test without actually creating the GUI dialog
        dialog = ComprehensiveErrorDialog.__new__(ComprehensiveErrorDialog)
        dialog.parent = parent
        dialog.error_title = "Test Error"
        dialog.error_message = error_msg
        dialog.exception = ValueError("Test exception")
        dialog.context = context
        
        # Test get_all_dialog_text without GUI components
        text_content = dialog.generate_full_error_report()
        print(f"Generated text length: {len(text_content)}")
        print(f"First 200 chars: {text_content[:200]}")
        
        if '/tmp/images/' in text_content:
            print("ERROR: Normal content contains image path!")
        else:
            print("GOOD: Normal content does not contain image paths")
            
    except Exception as e:
        print(f"Test 1 failed: {e}")
    
    # Test 2: Error message that contains image path
    print("\n=== Test 2: Error message with image path ===")
    try:
        error_msg_with_path = "/tmp/images/image-jtVOpkGcsfPwnnwqSZU-P.png"
        
        dialog2 = ComprehensiveErrorDialog.__new__(ComprehensiveErrorDialog)
        dialog2.parent = parent
        dialog2.error_title = "Test Error"
        dialog2.error_message = error_msg_with_path
        dialog2.exception = ValueError("Test exception")
        dialog2.context = {"operation": "test"}
        
        text_content2 = dialog2.generate_full_error_report()
        print(f"Generated text length: {len(text_content2)}")
        print(f"First 200 chars: {text_content2[:200]}")
        
        if '/tmp/images/' in text_content2:
            print("EXPECTED: Content with image path contains image path")
        else:
            print("UNEXPECTED: Content should contain image path but doesn't")
            
    except Exception as e:
        print(f"Test 2 failed: {e}")

    # Test 3: Check context with image path
    print("\n=== Test 3: Context with image path ===")
    try:
        dialog3 = ComprehensiveErrorDialog.__new__(ComprehensiveErrorDialog)
        dialog3.parent = parent
        dialog3.error_title = "Test Error"
        dialog3.error_message = "Normal error message"
        dialog3.exception = ValueError("Test exception")
        dialog3.context = {
            "operation": "test",
            "temp_file_path": "/tmp/images/image-jtVOpkGcsfPwnnwqSZU-P.png",
            "render_path": "/tmp/images/another-image.png"
        }
        
        text_content3 = dialog3.generate_full_error_report()
        print(f"Generated text length: {len(text_content3)}")
        print(f"First 500 chars: {text_content3[:500]}")
        
        if '/tmp/images/' in text_content3:
            print("EXPECTED: Context with image paths shows up in report")
        else:
            print("UNEXPECTED: Context with image paths not in report")
            
    except Exception as e:
        print(f"Test 3 failed: {e}")

if __name__ == "__main__":
    test_error_dialog_content()