#!/usr/bin/env python3
"""
Test script to diagnose STL loading issues
"""
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, 'src')

def test_imports():
    """Test importing all required modules"""
    print("Testing imports...")
    
    try:
        import trimesh
        print("✓ trimesh imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import trimesh: {e}")
        return False
        
    try:
        from utils.logger import logger
        print("✓ logger imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import logger: {e}")
        return False
        
    try:
        from core.stl_processor import STLProcessor
        print("✓ STLProcessor imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import STLProcessor: {e}")
        return False
        
    return True

def test_stl_loading():
    """Test STL loading functionality"""
    print("\nTesting STL loading...")
    
    # Find any STL file to test with
    stl_files = []
    for pattern in ['*.stl', '**/*.stl']:
        stl_files.extend(Path('.').glob(pattern))
        if stl_files:
            break
    
    if not stl_files:
        print("No STL files found for testing")
        return
    
    test_file = stl_files[0]
    print(f"Testing with: {test_file}")
    
    from core.stl_processor import STLProcessor
    
    processor = STLProcessor()
    try:
        result = processor.load(test_file)
        print(f"Load result: {result}")
        if processor.last_error:
            print(f"Last error: {processor.last_error}")
            print(f"Error type: {type(processor.last_error)}")
    except Exception as e:
        print(f"Exception during load: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("STL Loading Diagnostic Test")
    print("=" * 40)
    
    if test_imports():
        test_stl_loading()
    else:
        print("Import tests failed, skipping STL loading test")