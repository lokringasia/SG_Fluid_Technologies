@echo off
REM ============================================================
REM  One-click setup for Windows.
REM  Double-click this file (or run it from a terminal) once.
REM  It creates the virtual environment and installs Flask for you
REM  -- no manual venv/activate/pip commands needed.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create the virtual environment.
        echo Make sure Python is installed and added to PATH, then try again.
        pause
        exit /b 1
    )
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo ============================================================
echo  Setup complete! Double-click run.bat any time to start the app.
echo ============================================================
pause
