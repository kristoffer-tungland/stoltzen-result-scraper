@echo off
setlocal

REM Recommended same-day 2026 flow: EQ Timing current results + Stoltzen history.
cd /d "%~dp0"

echo ========================================
echo    EQ Timing Stoltzen 2026
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist src\requirements.txt (
    echo [ERROR] src\requirements.txt was not found.
    pause
    exit /b 1
)

python -c "import requests, bs4" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing Python dependencies...
    python -m pip install -r src\requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)

echo [INFO] Starting live results for EQ Timing event 78640...
echo [INFO] The browser refreshes automatically every 30 seconds.
python src\live_results_server.py --event-id 78640 --club COWI --year 2026 --output results.csv --interval 30 --open-browser
if errorlevel 1 (
    echo.
    echo [ERROR] EQ Timing scraper failed.
    pause
    exit /b 1
)

endlocal
