#!/bin/bash

# KrAIna Chat Standalone Build Script
# This script builds a standalone executable from the chat.py application

set -e  # Exit on any error

echo "=========================================="
echo "Building KrAIna Chat Standalone Application"
echo "=========================================="

# Ensure we're in the correct directory
if [ ! -f "app/chat.py" ]; then
    echo "Error: app/chat.py not found. Please run this script from the project root."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found. Please create one first."
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ *.spec

# Build the application
echo "Building standalone kraina_app..."
pyinstaller \
    --onefile \
    --windowed \
    app/kraina_app.py \
    --paths src \
    --add-data "src/kraina_chat/img:kraina_chat/img" \
    --add-data "src/kraina/libs/notification/logo.png:kraina/libs/notification/" \
    --add-data "src/kraina/assistants:kraina/assistants" \
    --add-data "src/kraina/snippets:kraina/snippets" \
    --add-data "src/kraina/tools:kraina/tools" \
    --add-data "src/kraina/macros:kraina/macros" \
    --add-data "src/kraina/templates:kraina/templates" \
    --collect-all tkinterweb \
    --collect-all tkinterweb_tkhtml \
    --collect-all sv_ttk \
    --hidden-import=tiktoken_ext.openai_public \
    --hidden-import=tiktoken_ext \
    --hidden-import=PIL._tkinter_finder \
    --hidden-import=aenum \
    --icon=img/logo.ico

pyinstaller \
    --onefile \
    app/kraina_cli.py \
    --add-data "src/kraina/templates:kraina/templates" \
    --icon=img/logo.ico

# Check if build was successful
if [ -f "dist/kraina_app" ] && [ -f "dist/kraina_cli" ]; then
    echo "=========================================="
    echo "Build completed successfully!"
    echo "Executable location: dist/kraina_app"
    echo "File size: $(du -h dist/kraina_app | cut -f1)"
    echo "Executable location: dist/kraina_cli"
    echo "File size: $(du -h dist/kraina_cli | cut -f1)"
    echo "=========================================="
else
    echo "Build failed! Check the output above for errors."
    exit 1
fi 