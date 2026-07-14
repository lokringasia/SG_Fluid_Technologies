@echo off
REM ============================================================
REM  One-click run for Windows.
REM  Double-click this file (or run it from a terminal) to start
REM  the app. Run setup.bat first if you haven't already.
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo It looks like setup hasn't been run yet.
    echo Please double-click setup.bat first, then try run.bat again.
    echo.
    pause
    exit /b 1
)

echo Starting Installer Certification Registry...
echo Once you see "Running on http://127.0.0.1:5000", open that link in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

".venv\Scripts\python.exe" app.py

pause
