@echo off
rem KrAIna Chat Standalone Build Script for Windows
rem This script builds a standalone executable from the kraina_app application

setlocal enabledelayedexpansion

echo ==========================================
echo Building KrAIna Chat Standalone Application
echo ==========================================

rem Ensure we're in the correct directory
if not exist "app\kraina_app.py" (
    echo Error: app\kraina_app.py not found. Please run this script from the project root.
    exit /b 1
)

rem Check if virtual environment exists
if not exist ".venv" (
    echo Error: Virtual environment not found. Please create one first.
    exit /b 1
)

rem Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Error: Failed to activate virtual environment.
    exit /b 1
)

rem Check if PyInstaller is installed
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

rem Clean previous builds
echo Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"

rem Build the GUI application
echo Building standalone kraina_app...
pyinstaller ^
    --onefile ^
    --windowed ^
    app\kraina_app.py ^
    --paths src ^
    --add-data src\kraina_chat\img:kraina_chat\img ^
    --add-data src\kraina\libs\notification\logo.png:kraina\libs\notification\ ^
    --add-data src\kraina\assistants:kraina\assistants ^
    --add-data src\kraina\snippets:kraina\snippets ^
    --add-data src\kraina\tools:kraina\tools ^
    --add-data src\kraina\macros:kraina\macros ^
    --add-data src\kraina\templates:kraina\templates ^
    --collect-all tkinterweb ^
    --collect-all tkinterweb_tkhtml ^
    --collect-all sv_ttk ^
    --collect-all pywinstyles ^
    --hidden-import=tiktoken_ext.openai_public ^
    --hidden-import=tiktoken_ext ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=aenum ^
    --hidden-import=pywinstyles ^
    --hidden-import=ctypes.wintypes ^
    --exclude-module pkg_resources ^
    --exclude-module gi ^
    --exclude-module gi.repository.Rsvg ^
    --exclude-module gi.repository.GdkPixbuf ^
    --exclude-module gi.repository.cairo ^
    --exclude-module gi.repository.Gio ^
    --exclude-module gi.repository.GLib ^
    --exclude-module gi.repository.GObject ^
    --exclude-module pygobject ^
    --exclude-module pgi ^
    --exclude-module python-xlib ^
    --icon=img\logo.ico ^
    --splash=img\kraina_banner_loading.png

if %errorlevel% neq 0 (
    echo Error: Failed to build kraina_app.
    exit /b 1
)

rem Build the CLI application
echo Building standalone kraina_cli...
pyinstaller ^
    --onefile ^
    app\kraina_cli.py ^
    --paths src ^
    --add-data src\kraina\templates:kraina\templates ^
    --add-data src\kraina\libs\notification\logo.png:kraina\libs\notification\ ^
    --hidden-import=windows_toasts ^
    --exclude-module pkg_resources ^
    --exclude-module gi.repository.Rsvg ^
    --exclude-module gi.repository.GdkPixbuf ^
    --exclude-module gi.repository.cairo ^
    --exclude-module gi.repository.Gio ^
    --exclude-module gi.repository.GLib ^
    --exclude-module gi.repository.GObject ^
    --exclude-module pygobject ^
    --exclude-module pgi ^
    --exclude-module python-xlib ^
    --icon=img\logo.ico

if %errorlevel% neq 0 (
    echo Error: Failed to build kraina_cli.
    exit /b 1
)

rem Check if build was successful
if exist "dist\kraina_app.exe" if exist "dist\kraina_cli.exe" (
    echo ==========================================
    echo Build completed successfully!
    echo Executable location: dist\kraina_app.exe
    for %%A in ("dist\kraina_app.exe") do echo File size: %%~zA bytes
    echo Executable location: dist\kraina_cli.exe
    for %%A in ("dist\kraina_cli.exe") do echo File size: %%~zA bytes
    echo ==========================================
) else (
    echo Build failed! Check the output above for errors.
    exit /b 1
)

echo.
echo Build process completed. You can now run the applications from the dist folder.
pause 