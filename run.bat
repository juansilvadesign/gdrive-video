@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   GDrive Video Downloader
echo ============================================
echo.

REM Get the script directory
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%.env\Scripts\python.exe"

REM Check if virtual environment Python exists
if exist "!VENV_PYTHON!" (
    echo ✓ Using virtual environment Python
    "!VENV_PYTHON!" main.py
    goto :end
)

REM Fallback to system Python
echo ! Virtual environment not found, attempting to use system Python...
python --version >nul 2>&1
if !errorlevel! equ 0 (
    echo ✓ Using system Python
    python main.py
    goto :end
)

REM If no Python found, show error
echo.
echo ✗ ERROR: Python not found!
echo.
echo Please ensure one of the following:
echo   1. A virtual environment exists at: !VENV_PYTHON!
echo   2. Python is installed and added to PATH
echo.
echo For setup instructions, visit: https://github.com/juansilvadesign/gdrive-video
echo.
pause
exit /b 1

:end
pause