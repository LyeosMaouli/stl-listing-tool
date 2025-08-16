# Simple STL Processor GUI Launcher
Write-Host "STL Processor GUI Launcher" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan

# Check setup.py exists
if (!(Test-Path "setup.py")) {
    Write-Host "Error: setup.py not found. Run from project root." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create venv if needed
if (!(Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# Activate venv
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Install package
Write-Host "Installing package..." -ForegroundColor Yellow
python -m pip install -e .

# Install moviepy
Write-Host "Installing moviepy..." -ForegroundColor Yellow
python -m pip install moviepy

# Launch GUI
Write-Host "Launching GUI..." -ForegroundColor Cyan
python -m stl_processor.gui

Write-Host "GUI closed." -ForegroundColor Green