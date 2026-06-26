@echo off
cd /d "%~dp0"
IF NOT EXIST ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
)
echo Installing requirements...
.venv\Scripts\python.exe -m pip install -r requirements.txt
IF NOT EXIST ".env" (
    copy .env.example .env
)
IF NOT EXIST "projects\cannae_001\cannae_001.hps" (
    echo Creating sample project...
    .venv\Scripts\python.exe make_sample_project.py
)
echo Starting Historical POV Studio v20...
.venv\Scripts\python.exe studio_qt.py
pause
