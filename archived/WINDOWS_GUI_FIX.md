# Windows GUI Compatibility Fix

## Issue
On Windows systems, the batch GUI was failing to launch with the error:
```
_tkinter.TclError: invalid command name "tkdnd::drop_target"
```

This occurred because the `tkinterdnd2` library's drag-and-drop functionality requires specific Windows components that may not be properly installed or configured on all systems.

## Root Cause
- The `tkinterdnd2` package depends on the Tkinter DND (tkdnd) extension
- On Windows, this requires proper installation and registration of DLL files
- When tkdnd is not properly set up, it throws a `TclError` when trying to register drop targets

## Solution Applied

### 1. Enhanced Error Handling in `gui.py`
```python
try:
    from tkinterdnd2 import DND_FILES
    self.drop_area.drop_target_register(DND_FILES)
    self.drop_area.dnd_bind('<<Drop>>', on_drop)
    self.dnd_available = True
except ImportError:
    # Handle missing tkinterdnd2 package
    self.dnd_available = False
except Exception as e:
    # Handle tkdnd initialization errors (common on Windows)
    self.dnd_available = False
    logger.warning(f"Drag-and-drop initialization failed: {e}")
```

### 2. Graceful Fallback UI
- When drag-and-drop fails, the drop area displays: "Drag-and-drop unavailable\nUse Browse button instead"
- Background color changes to light yellow to indicate the limitation
- All browse button functionality remains fully operational

### 3. Batch GUI Override
The `BatchProcessingGUI` class includes an override of `setup_drag_drop()` to provide batch-specific messaging when drag-and-drop is unavailable.

### 4. Initialization Order Fix
Moved `setup_drag_drop()` to be called after `drop_area` is created in `create_file_selection()` to prevent attribute errors.

## User Impact

### Before Fix
- ❌ Application crashes on startup with TclError
- ❌ No GUI available for batch processing on affected Windows systems

### After Fix  
- ✅ Application launches normally on all Windows systems
- ✅ Clear indication when drag-and-drop is unavailable
- ✅ Browse File and Browse Folder buttons work perfectly
- ✅ All batch processing functionality remains available

## Alternative Solutions for Full Drag-and-Drop

If users want full drag-and-drop functionality on Windows, they can:

1. **Install tkdnd manually**: Download and install the tkdnd extension for their Tcl/Tk installation
2. **Use conda**: Install tkinterdnd2 via conda which handles dependencies better
3. **Use alternative distributions**: Some Python distributions include better tkinter/tkdnd support

## Testing
The fix includes automated tests in `test_windows_fix.py` that verify:
- TclError exceptions are caught and handled gracefully
- UI falls back to showing appropriate messages
- Browse button functionality remains intact
- Batch GUI specific handling works correctly

## Status: ✅ RESOLVED
Windows users can now use the STL Listing Tool batch GUI without drag-and-drop errors. The application gracefully degrades to browse-button-only file selection while maintaining full functionality.