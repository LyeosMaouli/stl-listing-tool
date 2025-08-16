#!/usr/bin/env powershell
<#
.SYNOPSIS
    Start STL Processor GUI in virtual environment
.DESCRIPTION
    Creates virtual environment if needed, installs dependencies, and launches the GUI
#>

# Set error handling
$ErrorActionPreference = "Stop"

Write-Host "🔧 STL Processor GUI Launcher" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check if we're in the right directory
if (-not (Test-Path "setup.py")) {
    Write-Host "❌ Error: setup.py not found. Please run this script from the project root directory." -ForegroundColor Red
    exit 1
}

# Virtual environment path
$venvPath = "venv"
$activateScript = "$venvPath\Scripts\Activate.ps1"

# Create virtual environment if it doesn't exist
if (-not (Test-Path $venvPath)) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "📦 Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "🔌 Activating virtual environment..." -ForegroundColor Yellow
try {
    & $activateScript
    Write-Host "✅ Virtual environment activated" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to activate virtual environment: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Check if package is installed
Write-Host "🔍 Checking package installation..." -ForegroundColor Yellow
$packageInstalled = & python -c "import stl_processor; print('installed')" 2>$null
if ($packageInstalled -ne "installed") {
    Write-Host "📥 Installing STL Processor package..." -ForegroundColor Yellow
    & python -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install package" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Package installed" -ForegroundColor Green
} else {
    Write-Host "✅ Package already installed" -ForegroundColor Green
}

# Check moviepy specifically
Write-Host "🎬 Checking moviepy..." -ForegroundColor Yellow
$moviepyInstalled = & python -c "import moviepy; print('installed')" 2>$null
if ($moviepyInstalled -ne "installed") {
    Write-Host "📥 Installing moviepy..." -ForegroundColor Yellow
    & python -m pip install moviepy
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install moviepy" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ moviepy installed" -ForegroundColor Green
} else {
    Write-Host "✅ moviepy already installed" -ForegroundColor Green
}

# Launch GUI
Write-Host "🚀 Launching STL Processor GUI..." -ForegroundColor Cyan
Write-Host "   (Close the GUI window to return to this terminal)" -ForegroundColor Gray

try {
    & python -m stl_processor.gui
} catch {
    Write-Host "❌ Failed to launch GUI: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "🔧 You can also try: stl-gui" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "👋 GUI closed. Virtual environment is still active." -ForegroundColor Green
Write-Host "💡 To deactivate: deactivate" -ForegroundColor Gray
Write-Host "💡 To run again: python -m stl_processor.gui" -ForegroundColor Gray