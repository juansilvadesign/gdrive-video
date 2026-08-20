@echo off
setlocal enabledelayedexpansion

REM Legacy local Streamlit launcher. It does not use Milestone D's safe core.
set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"

if not exist "!VENV_PYTHON!" (
    echo ERROR: Virtual environment Python not found at .venv\Scripts\python.exe
    echo.
    echo Set it up once with:
    echo   py -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements-streamlit.txt
    pause
    exit /b 1
)

echo WARNING: This is a legacy local preview/install surface.
echo Use run.bat for private, large, resumable, or integrity-sensitive transfers.
"!VENV_PYTHON!" -m streamlit run "%SCRIPT_DIR%streamlit.py" --logger.level=error
set "RUN_EXIT_CODE=!errorlevel!"
pause
exit /b !RUN_EXIT_CODE!
