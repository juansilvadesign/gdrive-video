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

REM Always run from the project virtual environment.
if not exist "!VENV_PYTHON!" (
    echo.
    echo ERROR: Virtual environment Python not found.
    echo.
    echo This launcher only uses the local virtual environment.
    echo Expected Python at: !VENV_PYTHON!
    echo.
    echo Create or repair it with:
    echo   py -m venv .env
    echo   .env\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Using virtual environment Python
"!VENV_PYTHON!" "%SCRIPT_DIR%main.py" %*
set "RUN_EXIT_CODE=!errorlevel!"

if not "!RUN_EXIT_CODE!"=="0" (
    echo.
    echo ERROR: The virtual environment Python failed.
    echo.
    echo If this virtual environment is broken, recreate it with:
    echo   rmdir /s /q .env
    echo   py -m venv .env
    echo   .env\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b !RUN_EXIT_CODE!
)

pause
