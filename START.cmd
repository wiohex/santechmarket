@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python environment is missing. Follow README.md: first installation.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m scripts.run_site
if errorlevel 1 pause
