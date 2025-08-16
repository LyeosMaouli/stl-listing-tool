@echo off
REM STL Processor GUI Launcher - Batch Version
REM Creates virtual environment if needed and launches the GUI

echo 🔧 STL Processor GUI Launcher
echo ================================

REM Check if we're in the right directory
if not exist "setup.py" (
    echo ❌ Error: setup.py not found. Please run this script from the project root directory.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created
) else (
    echo 📦 Virtual environment already exists
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Failed to activate virtual environment
    pause
    exit /b 1
)
echo ✅ Virtual environment activated

REM Check if package is installed
echo 🔍 Checking package installation...
python -c "import stl_processor" 2>nul
if errorlevel 1 (
    echo 📥 Installing STL Processor package...
    python -m pip install -e .
    if errorlevel 1 (
        echo ❌ Failed to install package
        pause
        exit /b 1
    )
    echo ✅ Package installed
) else (
    echo ✅ Package already installed
)

REM Check moviepy specifically
echo 🎬 Checking moviepy...
python -c "from moviepy.editor import ImageSequenceClip" 2>nul
if errorlevel 1 (
    echo 📥 Installing moviepy...
    python -m pip install moviepy
    if errorlevel 1 (
        echo ❌ Failed to install moviepy
        pause
        exit /b 1
    )
    echo ✅ moviepy installed
) else (
    echo ✅ moviepy already installed
)

REM Launch GUI
echo 🚀 Launching STL Processor GUI...
echo    (Close the GUI window to return to this terminal)
python -m stl_processor.gui

echo.
echo 👋 GUI closed. 
echo 💡 To run again, just double-click this file or run: python -m stl_processor.gui
pause