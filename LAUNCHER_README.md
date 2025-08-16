# STL Processor GUI Launchers

This directory contains launcher scripts to easily start the STL Processor GUI in a clean virtual environment.

## For Windows Users

### Option 1: PowerShell Script (Recommended)
```powershell
.\start_gui.ps1
```

### Option 2: Batch File
```cmd
start_gui.bat
```
or just double-click `start_gui.bat` in File Explorer.

## For Linux/Mac Users

```bash
./start_gui.sh
```

## What These Scripts Do

1. **Create virtual environment** if it doesn't exist (`venv/` directory)
2. **Activate the virtual environment** 
3. **Install the STL Processor package** in development mode (`pip install -e .`)
4. **Install moviepy and other dependencies** if needed
5. **Launch the GUI** (`python -m stl_processor.gui`)

## Troubleshooting

### If you get execution policy errors in PowerShell:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### If Python is not found:
Make sure Python 3.8+ is installed and in your PATH:
```bash
python --version  # Should show Python 3.8+
```

### Manual virtual environment setup:
If the scripts fail, you can manually create the environment:
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -e .
python -m stl_processor.gui
```

## Benefits of Using Virtual Environment

- ✅ **Isolated dependencies**: No conflicts with system packages
- ✅ **Clean installation**: All packages in one place
- ✅ **Reproducible**: Same environment every time
- ✅ **Easy cleanup**: Just delete `venv/` folder to start fresh

## After First Run

Once the virtual environment is created, you can also:

1. **Activate manually and run**:
   ```bash
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   
   python -m stl_processor.gui
   ```

2. **Use the console command** (if activated):
   ```bash
   stl-gui
   ```