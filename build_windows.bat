@echo off
REM RCC Build Script for Windows
REM Builds a single executable using PyInstaller

echo ==========================================
echo   RCC Build Script - Windows
echo ==========================================
echo.

REM Check Python version
python --version 2>NUL
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Create virtual environment if not exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Build executable
echo.
echo Building executable...
pyinstaller ^
    --onefile ^
    --console ^
    --name RCC ^
    --icon "src\rcc\assets\RCC-logo.ico" ^
    --add-data "src/rcc;rcc" ^
    --hidden-import=zeroconf ^
    --hidden-import=paho.mqtt.client ^
    --hidden-import=requests ^
    --hidden-import=rich.console ^
    --hidden-import=rich.table ^
    --hidden-import=rich.progress ^
    --hidden-import=rich.prompt ^
    --hidden-import=rich.panel ^
    --hidden-import=rich.live ^
    --hidden-import=rich.layout ^
    --hidden-import=rich.theme ^
    --collect-all=rich ^
    run_rcc.py

echo.
echo ==========================================
if exist "dist\RCC.exe" (
    echo Build successful!
    echo Executable: dist\RCC.exe
) else (
    echo Build failed!
)
echo ==========================================

pause
