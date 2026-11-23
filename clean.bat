@echo off
REM Re-run watermark removal on already-generated images.
REM Usage: clean.bat [--asins file.txt]

setlocal
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "RUN_PY=%ROOT%run.py"

if not exist "%VENV_PY%" (
    echo ERROR: venv python not found at %VENV_PY%
    exit /b 1
)

echo Running: clean %*
"%VENV_PY%" "%RUN_PY%" clean %*
pause
