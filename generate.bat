@echo off
REM Generate 8 images per ASIN via Gemini web.
REM Usage: generate.bat [--asins file.txt] [--force] [--headed] [--limit N]

setlocal
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "RUN_PY=%ROOT%run.py"

if not exist "%VENV_PY%" (
    echo ERROR: venv python not found at %VENV_PY%
    exit /b 1
)

echo Running: generate %*
"%VENV_PY%" "%RUN_PY%" generate %*
pause
