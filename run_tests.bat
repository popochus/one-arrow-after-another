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

".venv\Scripts\python.exe" tools\run_tests.py
set RESULT=%errorlevel%

echo.
if "%RESULT%"=="0" (
    echo [OK] All tests passed.
    echo Report written to: docs\test_report.md
) else (
    echo [FAIL] Some tests failed. Please read the output above.
)

pause
exit /b %RESULT%
