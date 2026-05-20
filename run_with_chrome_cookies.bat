@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   GDrive Video Downloader - Chrome cookies
echo ============================================
echo.
echo Use this for Drive links that only work in one Chrome profile.
echo Export cookies from that Chrome profile first, then paste the path here.
echo.

set /p "DRIVE_INPUT=Google Drive URL or file ID: "
if "!DRIVE_INPUT!"=="" (
    echo.
    echo ERROR: A Google Drive URL or file ID is required.
    pause
    exit /b 1
)

echo.
set /p "COOKIE_FILE=Path to exported cookies.txt: "
if "!COOKIE_FILE!"=="" (
    echo.
    echo ERROR: A cookies.txt file is required for private/shared videos.
    pause
    exit /b 1
)

echo.
set /p "ACCOUNT_INDEX=Google account index [0]: "
if "!ACCOUNT_INDEX!"=="" set "ACCOUNT_INDEX=0"

call "%~dp0run.bat" "!DRIVE_INPUT!" --cookies-file "!COOKIE_FILE!" --account-index !ACCOUNT_INDEX!
exit /b !errorlevel!
