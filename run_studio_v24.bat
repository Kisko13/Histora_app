@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo Historical POV Studio - V24
echo ================================================
echo.

REM Create local virtual environment if it does not exist.
REM This is free. It only installs Python packages needed to run the app.
if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ERROR: Could not create .venv.
    echo Make sure Python 3.11+ is installed and added to PATH.
    pause
    exit /b 1
)

echo Checking required packages...
".venv\Scripts\python.exe" -c "import PySide6, dotenv, requests" >nul 2>nul
if errorlevel 1 (
    echo Installing required packages. First run can take a few minutes...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Package installation failed.
        echo Check your internet connection, then run this file again.
        pause
        exit /b 1
    )
)

echo Starting studio...
".venv\Scripts\python.exe" studio_qt.py

echo.
echo Studio closed.
pause
