@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found in this folder.
    echo Please create it first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

if /i "%~1"=="--selftest" (
    ".venv\Scripts\python.exe" -c "import game.app; print('selftest OK')"
    exit /b %errorlevel%
)

".venv\Scripts\python.exe" main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Game exited with an error. Please read the message above.
    pause
)
