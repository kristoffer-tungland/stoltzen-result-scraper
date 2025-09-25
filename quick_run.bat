@echo off
REM Quick run script - minimal interface
python stoltzen_scraper.py "http://stoltzen.no/resultater/2024/resklubb_16.html" > results.json
if errorlevel 1 (
    echo Error running scraper
    pause
) else (
    echo Results saved to results.json
    start results.json
)