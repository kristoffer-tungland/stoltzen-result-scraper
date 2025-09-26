@echo off
REM Stoltzen Stat URL Scraper - Batch Script
REM This script runs the Python scraper with stat.php URLs from a file

echo Starting Stoltzen Stat URL Scraper...
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
if not exist src\requirements.txt (
    echo Creating requirements.txt...
    call src\update_requirements.bat
)

REM Check if packages are installed
python -c "import requests, bs4" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r src\requirements.txt
)

REM Ask user for URL file
set "DEFAULT_FILE=stat_urls.txt"
echo Default URL file: %DEFAULT_FILE%
echo.
set /p "USER_FILE=Enter URL file path (or press Enter for default): "

REM Use default if no input provided
if "%USER_FILE%"=="" (
    set "URL_FILE=%DEFAULT_FILE%"
) else (
    set "URL_FILE=%USER_FILE%"
)

REM Check if URL file exists
if not exist "%URL_FILE%" (
    echo Error: URL file "%URL_FILE%" not found
    echo.
    echo Please create a text file with stat.php URLs, one per line.
    echo Example content:
    echo   http://stoltzen.no/statistikk/stat.php?id=68772
    echo   http://stoltzen.no/statistikk/stat.php?id=12345
    echo.
    pause
    exit /b 1
)

REM Run the Python script
echo.
echo Using URL file: %URL_FILE%
echo.
echo Running stat URL scraper...
python src\stoltzen_stat_scraper.py "%URL_FILE%" --output results.csv 2>error.log

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
echo Success! Results saved to results.csv
echo.

REM Show some basic statistics
for %%i in (results.csv) do echo File size: %%~zi bytes
echo.

REM Ask if user wants to open the results
set /p OPEN_FILE="Do you want to open results.csv? (y/n): "
if /i "%OPEN_FILE%"=="y" (
    start results.csv
)

echo.
echo Script completed successfully!
pause