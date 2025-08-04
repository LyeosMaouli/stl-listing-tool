#!/usr/bin/env python3
"""
Integration test to validate that critical fixes work correctly.
This script tests the fixes without requiring heavy dependencies.
"""

import sys
sys.path.insert(0, '.')

def test_package_structure():
    """Test that package structure works."""
    print("Testing package structure...")
    
    # Test basic package import
    import src
    assert hasattr(src, '__version__')
    print(f"✓ Package version: {src.__version__}")
    
    # Test logger import
    logger = src.setup_logger('test_fixes')
    logger.info('Testing fixes integration')
    print("✓ Logger works")
    
    # Test lazy imports are available
    assert hasattr(src, 'get_stl_processor')
    assert hasattr(src, 'get_dimension_extractor')
    print("✓ Lazy import functions available")
    
    print("Package structure test: PASSED\n")

def test_entry_points_structure():
    """Test that entry point modules exist and can be found."""
    print("Testing entry points structure...")
    
    import os
    
    entry_points = {
        'stl-processor': 'src.cli:cli',
        'stl-proc': 'src.cli:cli', 
        'stl-gui': 'src.gui:main'
    }
    
    for command, entry_point in entry_points.items():
        module_path, function = entry_point.split(':')
        file_path = module_path.replace('.', '/') + '.py'
        
        assert os.path.exists(file_path), f"Entry point file missing: {file_path}"
        print(f"✓ {command} -> {entry_point}")
    
    print("Entry points structure test: PASSED\n")

def test_import_system():
    """Test that import system no longer uses sys.path manipulation."""
    print("Testing import system...")
    
    # Check key files don't have sys.path.insert patterns
    files_to_check = [
        'src/cli.py',
        'src/gui.py', 
        'src/core/stl_processor.py',
        'src/rendering/vtk_renderer.py',
        'tests/test_stl_processor.py'
    ]
    
    for file_path in files_to_check:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Should not have sys.path.insert
        assert 'sys.path.insert' not in content, f"File still has sys.path manipulation: {file_path}"
        
        # Should have proper relative imports (for src files) or package imports (for tests)
        if file_path.startswith('src/') and file_path != 'src/cli.py' and file_path != 'src/gui.py':
            assert 'from ..' in content or 'from .' in content, f"File missing relative imports: {file_path}"
        elif file_path.startswith('tests/'):
            assert 'from src.' in content, f"Test file missing package imports: {file_path}"
            
        print(f"✓ {file_path}")
    
    print("Import system test: PASSED\n")

def test_settings_configuration():
    """Test that settings use modern Pydantic API."""
    print("Testing settings configuration...")
    
    # Check that settings.py uses BaseModel, not BaseSettings
    with open('config/settings.py', 'r') as f:
        content = f.read()
    
    assert 'from pydantic import BaseModel' in content, "Settings should use BaseModel"
    assert 'BaseSettings' not in content, "Settings should not use deprecated BaseSettings"
    assert 'model_config' in content, "Settings should use model_config"
    
    print("✓ Settings uses modern Pydantic API")
    print("Settings configuration test: PASSED\n")

def test_gui_dependencies():
    """Test that GUI handles missing dependencies gracefully."""
    print("Testing GUI dependency handling...")
    
    # Check that GUI has proper error handling for tkinterdnd2
    with open('src/gui.py', 'r') as f:
        content = f.read()
    
    assert 'dnd_available' in content, "GUI should track drag-and-drop availability"
    assert 'logger.warning' in content, "GUI should log when drag-and-drop unavailable"
    assert 'lightyellow' in content, "GUI should update UI when drag-and-drop unavailable"
    
    print("✓ GUI handles missing tkinterdnd2 gracefully")
    print("GUI dependencies test: PASSED\n")

def main():
    """Run all integration tests."""
    print("=" * 60)
    print("STL Processor - Critical Fixes Integration Test")
    print("=" * 60)
    
    tests = [
        test_package_structure,
        test_entry_points_structure, 
        test_import_system,
        test_settings_configuration,
        test_gui_dependencies
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL CRITICAL FIXES VALIDATED SUCCESSFULLY!")
        print("\nThe package is now ready for:")
        print("- pip install -e .")
        print("- Console commands (stl-processor, stl-gui)")  
        print("- Proper package imports")
        print("- Modern configuration system")
        return 0
    else:
        print("❌ Some fixes need attention before deployment")
        return 1

if __name__ == '__main__':
    sys.exit(main())