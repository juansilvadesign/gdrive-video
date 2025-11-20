@echo off
REM GDrive Video - Streamlit App Launcher
REM This script runs the Streamlit app locally

echo.
echo ====================================
echo  GDrive Video - Streamlit App
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org
    pause
    exit /b 1
)

REM Check if virtual environment exists, if not create it
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install requirements if needed
echo Installing dependencies...
pip install -q -r requirements.txt

REM Run Streamlit app
echo.
echo ====================================
echo Launching Streamlit app...
echo Opening http://localhost:8501
echo ====================================
echo.

streamlit run streamlit.py --logger.level=error

pause
