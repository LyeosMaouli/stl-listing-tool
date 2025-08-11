#!/usr/bin/env python3
"""
Debug script to understand the error message issue without GUI dependencies.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_error_report_generation():
    """Test the error report generation logic."""
    from datetime import datetime
    import platform
    import traceback
    
    def generate_test_error_report(error_title, error_message, exception, context):
        """Simplified version of generate_full_error_report for testing."""
        report_lines = []
        
        # Header
        report_lines.append("=" * 80)
        report_lines.append("STL PROCESSOR ERROR REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Error Title: {error_title}")
        report_lines.append("")
        
        # Error summary
        report_lines.append("ERROR SUMMARY:")
        report_lines.append("-" * 40)
        report_lines.append(error_message)
        report_lines.append("")
        
        # Exception details
        if exception:
            report_lines.append("EXCEPTION DETAILS:")
            report_lines.append("-" * 40)
            report_lines.append(f"Type: {type(exception).__name__}")
            report_lines.append(f"Message: {str(exception)}")
            report_lines.append("")
        
        # Context
        if context:
            report_lines.append("CONTEXT INFORMATION:")
            report_lines.append("-" * 40)
            for key, value in context.items():
                report_lines.append(f"{key}: {value}")
            report_lines.append("")
        
        # System info
        report_lines.append("SYSTEM INFORMATION:")
        report_lines.append("-" * 40)
        report_lines.append(f"Platform: {platform.platform()}")
        report_lines.append("")
        
        return "\n".join(report_lines)
    
    # Test scenarios
    print("=== Testing Error Report Generation ===")
    
    # Test 1: Normal error
    print("\n1. Normal error message:")
    normal_report = generate_test_error_report(
        "Test Error",
        "This is a normal error message",
        ValueError("Normal exception"),
        {"file_path": "/normal/path.stl", "operation": "test"}
    )
    print(f"Length: {len(normal_report)}")
    print(f"Contains image path: {'/tmp/images/' in normal_report}")
    print(f"Preview: {normal_report[:200]}...")
    
    # Test 2: Error message that IS an image path
    print("\n2. Error message that is an image path:")
    image_path_report = generate_test_error_report(
        "Test Error",
        "/tmp/images/image-jtVOpkGcsfPwnnwqSZU-P.png",
        ValueError("Exception"),
        {"operation": "test"}
    )
    print(f"Length: {len(image_path_report)}")
    print(f"Contains image path: {'/tmp/images/' in image_path_report}")
    print(f"Preview: {image_path_report[:200]}...")
    
    # Test 3: Context contains image path
    print("\n3. Context contains image path:")
    context_image_report = generate_test_error_report(
        "Test Error", 
        "Normal message",
        ValueError("Exception"),
        {"temp_path": "/tmp/images/image-123.png", "operation": "render"}
    )
    print(f"Length: {len(context_image_report)}")
    print(f"Contains image path: {'/tmp/images/' in context_image_report}")
    print(f"Preview: {context_image_report[:300]}...")
    
    # Test 4: Exception contains image path (this could be the issue!)
    print("\n4. Exception message contains image path:")
    exception_with_path = ValueError("Error with /tmp/images/image-456.png")
    exception_image_report = generate_test_error_report(
        "Test Error",
        "Normal message", 
        exception_with_path,
        {"operation": "test"}
    )
    print(f"Length: {len(exception_image_report)}")
    print(f"Contains image path: {'/tmp/images/' in exception_image_report}")
    print(f"Preview: {exception_image_report[:300]}...")
    
    print("\n=== Analysis ===")
    print("If you're seeing an image path when saving error logs, it's likely because:")
    print("1. The error message itself is an image path (Test 2)")
    print("2. The exception message contains an image path (Test 4)")
    print("3. The context contains image paths (Test 3 - but this would be mixed with other content)")
    print("\nThe most likely culprit is that somewhere an image path is being passed")
    print("as the error message instead of a descriptive error message.")

if __name__ == "__main__":
    test_error_report_generation()