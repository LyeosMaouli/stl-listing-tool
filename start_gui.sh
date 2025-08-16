#!/bin/bash
# STL Processor GUI Launcher - Shell Script Version
# Creates virtual environment if needed and launches the GUI

set -e  # Exit on any error

echo "🔧 STL Processor GUI Launcher"
echo "================================"

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    echo "❌ Error: setup.py not found. Please run this script from the project root directory."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "📦 Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"

# Check if package is installed
echo "🔍 Checking package installation..."
if ! python -c "import stl_processor" 2>/dev/null; then
    echo "📥 Installing STL Processor package..."
    python -m pip install -e .
    echo "✅ Package installed"
else
    echo "✅ Package already installed"
fi

# Check moviepy specifically
echo "🎬 Checking moviepy..."
if ! python -c "import moviepy" 2>/dev/null; then
    echo "📥 Installing moviepy..."
    python -m pip install moviepy
    echo "✅ moviepy installed"
else
    echo "✅ moviepy already installed"
fi

# Launch GUI
echo "🚀 Launching STL Processor GUI..."
echo "   (Close the GUI window to return to this terminal)"

python -m stl_processor.gui

echo ""
echo "👋 GUI closed. Virtual environment is still active."
echo "💡 To deactivate: deactivate"
echo "💡 To run again: python -m stl_processor.gui"