@echo off
REM Scrape Amazon product data + base images for the given ASINs.
REM Usage: scrape.bat [--asins file.txt] [--limit N]

setlocal
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "RUN_PY=%ROOT%run.py"

if not exist "%VENV_PY%" (
    echo ERROR: venv python not found at %VENV_PY%
    exit /b 1
)

echo Running: scrape %*
"%VENV_PY%" "%RUN_PY%" scrape %*
pause
