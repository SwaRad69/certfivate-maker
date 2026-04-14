@echo off
REM Certificate Generator - Quick Start for Windows

cd /d "%~dp0"

echo.
echo ===================================================
echo   Certificate Generator - Development Server
echo ===================================================
echo.

REM Check if venv exists
if not exist ".venv" (
    echo ERROR: Virtual environment not found!
    echo.
    echo Create it with:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo.
    pause
    exit /b 1
)

REM Check if client_secrets.json exists
if not exist "web\client_secrets.json" (
    echo ERROR: web\client_secrets.json not found!
    echo.
    echo To fix:
    echo 1. Download client_secrets.json from Google Cloud Console
    echo 2. Save it to: web\client_secrets.json
    echo.
    pause
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Check if requirements are installed
echo Checking dependencies...
pip list | find "Flask" > nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -q -r web\requirements.txt
    if errorlevel 1 (
        echo Error installing dependencies!
        pause
        exit /b 1
    )
)

REM Start the app
echo.
echo ===================================================
echo   Starting Flask server...
echo ===================================================
echo.
echo   Open: http://localhost:5000/
echo   Stop: Press Ctrl+C
echo.

cd web
python app.py

pause
