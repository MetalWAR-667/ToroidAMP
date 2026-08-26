@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ToroidAMP] ERROR: .venv not found.
    echo Create it with: python -m venv .venv
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m toroidamp