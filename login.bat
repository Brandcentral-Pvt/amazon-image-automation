@echo off
REM One-time Google sign-in into the persistent Chrome profile.
REM Run this once before any generate/clean; after that all runs are headless.

setlocal
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "RUN_PY=%ROOT%run.py"

if not exist "%VENV_PY%" (
    echo ERROR: venv python not found at %VENV_PY%
    exit /b 1
)

echo ==========================================
echo  One-time Google sign-in
echo ==========================================
echo A browser will open. Sign in to Google (and Amazon if needed),
echo then come back here and press Enter.
echo.
"%VENV_PY%" "%RUN_PY%" login %*
echo.
echo Session saved. You can now run generate/clean headless.
pause
