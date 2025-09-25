@echo off
REM Advanced Stoltzen Result Scraper - Interactive Batch Script
REM This script provides options for running the Python scraper

title Stoltzen Result Scraper
color 0A

echo ========================================
echo    Stoltzen Result Scraper v2.0
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.x and try again
    echo.
    pause
    exit /b 1
)

REM Check and update requirements if needed
echo Checking Python packages...
if not exist requirements.txt (
    echo [INFO] No requirements.txt found. Creating one...
    call update_requirements.bat
)

python -c "import requests, bs4" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Required packages not found
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install packages
        echo.
        set /p UPDATE_REQ="Update requirements.txt automatically? (y/n): "
        if /i "!UPDATE_REQ!"=="y" call update_requirements.bat
        pause
        exit /b 1
    )
)

echo [OK] Python environment ready
echo.

:MENU
echo ========================================
echo Select an option:
echo ========================================
echo 1. Run with default Cowi URL
echo 2. Enter custom URL
echo 3. View last results
echo 4. Update requirements.txt
echo 5. Show help
echo 6. Exit
echo.
set /p CHOICE="Enter your choice (1-6): "

if "%CHOICE%"=="1" goto DEFAULT_RUN
if "%CHOICE%"=="2" goto CUSTOM_URL
if "%CHOICE%"=="3" goto VIEW_RESULTS
if "%CHOICE%"=="4" goto UPDATE_REQUIREMENTS
if "%CHOICE%"=="5" goto SHOW_HELP
if "%CHOICE%"=="6" goto EXIT
echo Invalid choice. Please try again.
echo.
goto MENU

:DEFAULT_RUN
set "URL=http://stoltzen.no/resultater/2024/resklubb_16.html"
goto RUN_SCRIPT

:CUSTOM_URL
echo.
set /p URL="Enter the results URL: "
if "%URL%"=="" (
    echo Error: URL cannot be empty
    echo.
    goto MENU
)
goto RUN_SCRIPT

:RUN_SCRIPT
echo.
echo ========================================
echo Running scraper...
echo ========================================
echo URL: %URL%
echo Output: results.json
echo.

REM Create timestamp for backup
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATE=%%c%%a%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a%%b
set TIMESTAMP=%DATE%_%TIME%

REM Backup previous results if they exist
if exist results.json (
    echo Backing up previous results...
    copy results.json results_backup_%TIMESTAMP%.json >nul
)

REM Run the Python script
python stoltzen_scraper.py "%URL%" > results.json 2>scraper_error.log

if errorlevel 1 (
    echo.
    echo [ERROR] Script failed to run
    echo Error details:
    type scraper_error.log
    echo.
    pause
    goto MENU
)

REM Show success message and statistics
echo.
echo [SUCCESS] Scraper completed!
for %%i in (results.json) do (
    echo File: results.json (%%~zi bytes)
    echo Created: %%~ti
)
echo.

REM Parse basic statistics from JSON
findstr /c:"Mann" results.json >nul && echo Category: Mann found
findstr /c:"Dame" results.json >nul && echo Category: Dame found  
findstr /c:"Pluss" results.json >nul && echo Category: Pluss found
echo.

set /p OPEN_FILE="Open results.json? (y/n): "
if /i "%OPEN_FILE%"=="y" start notepad results.json

echo.
goto MENU

:VIEW_RESULTS
if not exist results.json (
    echo No results file found. Please run the scraper first.
    echo.
    pause
    goto MENU
)

echo.
echo ========================================
echo Last Results Summary
echo ========================================
for %%i in (results.json) do (
    echo File: results.json
    echo Size: %%~zi bytes
    echo Modified: %%~ti
)
echo.

set /p VIEW_FILE="Open results.json? (y/n): "
if /i "%VIEW_FILE%"=="y" start notepad results.json

echo.
goto MENU

:UPDATE_REQUIREMENTS
echo.
echo ========================================
echo Update Requirements
echo ========================================
echo This will scan the Python script and update requirements.txt
echo with any new dependencies found.
echo.
call update_requirements.bat
echo.
goto MENU

:SHOW_HELP
echo.
echo ========================================
echo Help
echo ========================================
echo This script runs the Stoltzen result scraper.
echo.
echo Options:
echo 1. Default run - Uses Cowi 2024 results URL
echo 2. Custom URL - Enter any Stoltzen results URL
echo 3. View results - Open the last generated results.json
echo 4. Update requirements.txt - Auto-detect and update dependencies
echo 5. Help - Show this help screen
echo.
echo The scraper will:
echo - Fetch participant data from the results page
echo - Get individual profile information
echo - Calculate time differences and improvements
echo - Sort participants by best time
echo - Save everything to results.json
echo.
echo Requirements:
echo - Python 3.x
echo - requests and beautifulsoup4 packages
echo.
pause
goto MENU

:EXIT
echo.
echo Thanks for using Stoltzen Result Scraper!
echo.
pause
exit /b 0