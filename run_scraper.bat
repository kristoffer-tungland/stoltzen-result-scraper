@echo off
REM Stoltzen Result Scraper - Batch Script
REM This script runs the Python scraper with default settings

echo Starting Stoltzen Result Scraper...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

REM Check if requirements.txt exists and is up to date
if not exist requirements.txt (
    echo Creating requirements.txt...
    call update_requirements.bat
)

REM Check if packages are installed
python -c "import requests, bs4" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
)

REM Default URL for Cowi results
set "DEFAULT_URL=http://stoltzen.no/resultater/2024/resklubb_16.html"

REM Run the Python script
echo Fetching results from: %DEFAULT_URL%
echo.
python stoltzen_scraper.py "%DEFAULT_URL%" > results.json 2>error.log

REM Check if the script ran successfully
if errorlevel 1 (
    echo.
    echo Error: Script failed to run successfully
    echo Check error.log for details
    type error.log
    pause
    exit /b 1
)

echo.
echo Success! Results saved to results.json
echo.

REM Show some basic statistics
for %%i in (results.json) do echo File size: %%~zi bytes
echo.

REM Ask if user wants to open the results
set /p OPEN_FILE="Do you want to open results.json? (y/n): "
if /i "%OPEN_FILE%"=="y" (
    start notepad results.json
)

echo.
echo Script completed successfully!
pause