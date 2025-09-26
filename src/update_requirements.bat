@echo off
REM Simple Requirements Updater - Ensures requirements.txt is current

echo ========================================
echo   Requirements Updater
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Checking current requirements...

REM Check current requirements.txt
if exist requirements.txt (
    echo Current requirements.txt:
    type requirements.txt
    echo.
) else (
    echo No requirements.txt found.
)

echo Creating standard requirements.txt for Stoltzen Scraper...

REM Create the standard requirements file
echo # Requirements for Stoltzen Result Scraper > requirements_new.txt
echo # Generated on %date% at %time% >> requirements_new.txt
echo. >> requirements_new.txt
echo # HTTP requests >> requirements_new.txt
echo requests^>=2.28.0 >> requirements_new.txt
echo. >> requirements_new.txt
echo # HTML parsing >> requirements_new.txt
echo beautifulsoup4^>=4.11.0 >> requirements_new.txt

REM Compare with existing requirements.txt
if exist requirements.txt (
    fc requirements.txt requirements_new.txt >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [CHANGES DETECTED] Requirements will be updated!
        echo.
        echo New requirements.txt:
        type requirements_new.txt
        echo.
        set /p UPDATE="Update requirements.txt? (y/n): "
        if /i "%UPDATE%"=="y" (
            copy requirements_new.txt requirements.txt >nul
            echo [SUCCESS] requirements.txt updated!
        ) else (
            echo [SKIPPED] requirements.txt not updated
        )
    ) else (
        echo [OK] requirements.txt is up to date
    )
) else (
    copy requirements_new.txt requirements.txt >nul
    echo [CREATED] New requirements.txt created!
)

REM Clean up
del requirements_new.txt >nul 2>&1

echo.
echo Final requirements.txt:
type requirements.txt

REM Install packages if missing
echo.
echo Checking if packages are installed...
python -c "import requests, bs4" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing missing packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install some packages
    ) else (
        echo [SUCCESS] All packages installed successfully
    )
) else (
    echo [OK] All required packages are already installed
)

echo.
echo [COMPLETE] Requirements check finished!
pause