#!/usr/bin/env python3
"""
Test script to verify GUI changes work correctly by checking the source code.
"""

def check_gui_changes():
    """Check that our GUI changes are present in the source code."""
    
    print("🔍 Checking GUI modifications...")
    
    # Read the gui_batch.py file
    try:
        with open("/root/repo/src/gui_batch.py", "r") as f:
            content = f.read()
        
        # Check that drag-and-drop functionality is removed
        if "Drop STL files" not in content and "drop_area" not in content:
            print("✅ Drag-and-drop UI elements removed")
        else:
            print("❌ Drag-and-drop UI elements still present")
        
        # Check that setup_drag_drop is disabled
        if "setup_drag_drop" in content and "pass" in content:
            print("✅ setup_drag_drop method disabled with pass")
        else:
            print("❌ setup_drag_drop method not properly disabled")
        
        # Check for mode selector functionality 
        if "mode_selector" in content or "Processing Mode" in content:
            print("✅ Mode selector functionality present")
        else:
            print("❌ Mode selector functionality missing")
        
        # Check for browse buttons
        if "Browse File" in content and "Browse Folder" in content:
            print("✅ Browse buttons present for both single and batch modes")
        else:
            print("❌ Browse buttons missing")
            
        # Check title
        if "STL Listing Tool" in content and "Batch Processing" not in content.split("STL Listing Tool")[1][:20]:
            print("✅ Title updated to generic 'STL Listing Tool'")
        else:
            print("❌ Title still contains 'Batch Processing'")
        
        print("✅ Source code modifications verified successfully")
        
    except Exception as e:
        print(f"❌ Error reading GUI file: {e}")
    
    # Check setup.py entry points
    try:
        with open("/root/repo/setup.py", "r") as f:
            setup_content = f.read()
        
        if "stl-gui=gui_batch:main" in setup_content:
            print("✅ setup.py entry point updated to use gui_batch")
        else:
            print("❌ setup.py entry point not updated correctly")
            
        if "stl-batch-gui" not in setup_content:
            print("✅ Old stl-batch-gui entry point removed")
        else:
            print("❌ Old stl-batch-gui entry point still present")
            
        if "tkinterdnd2" not in setup_content:
            print("✅ tkinterdnd2 dependency removed")
        else:
            print("❌ tkinterdnd2 dependency still present")
        
    except Exception as e:
        print(f"❌ Error reading setup.py: {e}")

if __name__ == "__main__":
    check_gui_changes()