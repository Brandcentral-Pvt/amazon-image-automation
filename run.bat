@echo off
REM Amazon ASIN -> 8-Image Bundle — one-click entry point
REM Activates the project venv and runs the requested pipeline stage.

setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "RUN_PY=%ROOT%run.py"

if not exist "%VENV_PY%" (
    echo ERROR: venv python not found at %VENV_PY%
    echo Run: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if "%~1"=="" (
    echo.
    echo ==========================================
    echo  Amazon ASIN -> 8-Image Bundle (Bot)
    echo ==========================================
    echo.
    echo  1) login     - one-time Google sign-in (persistent profile)
    echo  2) scrape    - crawl Amazon + download base images
    echo  3) generate  - build prompts + generate 8 images via Gemini
    echo  4) clean     - re-run watermark removal on generated images
    echo  5) all       - full pipeline (scrape + generate)
    echo  6) status    - show status for one ASIN
    echo  0) exit
    echo.
    set /p choice="Choose an option: "
    if "!choice!"=="1" goto login
    if "!choice!"=="2" goto scrape
    if "!choice!"=="3" goto generate
    if "!choice!"=="4" goto clean
    if "!choice!"=="5" goto all
    if "!choice!"=="6" goto status
    if "!choice!"=="0" goto exit
    echo Invalid choice.
    goto start

:login
    shift
    echo Running: login %*
    "%VENV_PY%" "%RUN_PY%" login %*
    goto end

:scrape
    shift
    echo Running: scrape %*
    "%VENV_PY%" "%RUN_PY%" scrape %*
    goto end

:generate
    shift
    echo Running: generate %*
    "%VENV_PY%" "%RUN_PY%" generate %*
    goto end

:clean
    shift
    echo Running: clean %*
    "%VENV_PY%" "%RUN_PY%" clean %*
    goto end

:all
    shift
    echo Running: all (scrape + generate) %*
    "%VENV_PY%" "%RUN_PY%" all %*
    goto end

:status
    shift
    echo Running: bot status %*
    "%VENV_PY%" "%ROOT%bot.py" status %*
    goto end

:exit
    exit /b 0

:end
    echo.
    echo Done.
    pause
