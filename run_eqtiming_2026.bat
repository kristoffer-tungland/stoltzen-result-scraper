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

echo [INFO] Fetching COWI results for EQ Timing event 78640...
python src\eqtiming_scraper.py --event-id 78640 --club COWI --year 2026 --output results.csv
if errorlevel 1 (
    echo.
    echo [ERROR] EQ Timing scraper failed.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Results saved to results.csv
set /p OPEN_VIEWER="Open results_viewer.html now? (y/n): "
if /i "%OPEN_VIEWER%"=="y" start "" "results_viewer.html"

endlocal
