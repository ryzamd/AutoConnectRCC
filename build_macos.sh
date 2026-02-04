#!/bin/bash
# RCC Build Script for macOS
# Builds a single executable using PyInstaller

echo "=========================================="
echo "  RCC Build Script - macOS"
echo "=========================================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

# Build executable
echo ""
echo "Building executable..."
pyinstaller \
    --onefile \
    --console \
    --name RCC \
    --icon "src/rcc/assets/RCC-logo.icns" \
    --add-data "src/rcc:rcc" \
    --hidden-import=zeroconf \
    --hidden-import=requests \
    --hidden-import=rich \
    src/rcc/main.py

echo ""
echo "=========================================="
if [ -f "dist/RCC" ]; then
    echo "Build successful!"
    echo "Executable: dist/RCC"
    
    # Make executable
    chmod +x dist/RCC
    
    # Show file info
    ls -la dist/RCC
else
    echo "Build failed!"
fi
echo "=========================================="
