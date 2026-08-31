@echo off
REM ============================================================
REM  report_pipeline daily run : Chrome -> download -> summarize -> git push
REM  * download_reports.py / summarize.py output is saved to logs\YYYY-MM-DD.log
REM    so you can check later WHY a broker (BofA/JPM etc.) failed.
REM  * console still shows step banners; full detail goes to the log file.
REM ============================================================
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM --- log file (same dating style as _자동화\run_all_0830.bat) ---
set LOGDIR=%~dp0logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set LOG=%LOGDIR%\%date:~0,10%.log
echo. >> "%LOG%"
echo ================= %date% %time% START ================= >> "%LOG%"

echo [0/3] launch selenium Chrome (debug port 9222)
echo [0/3] %date% %time% launch chrome >> "%LOG%"
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium_profile"
ping -n 8 127.0.0.1 > nul

echo [1/3] download PDFs (Selenium)  ... detail -^> "%LOG%"
echo. >> "%LOG%"
echo ----- [1/3] download_reports.py ----- >> "%LOG%"
python download_reports.py >> "%LOG%" 2>&1

echo [2/3] summarize PDFs -> reports.json  ... detail -^> "%LOG%"
echo. >> "%LOG%"
echo ----- [2/3] summarize.py ----- >> "%LOG%"
python summarize.py >> "%LOG%" 2>&1

echo [3/3] publish (git push)
echo. >> "%LOG%"
echo ----- [3/3] git push ----- >> "%LOG%"
cd /d "%~dp0\.."
git add macro_hub/public/data/reports.json macro_hub/public/report_files report_pipeline/state.json 2>nul
git commit -m "reports %date:~0,10%" >> "%LOG%" 2>&1
git push >> "%LOG%" 2>&1

echo ================= %date% %time% END ================= >> "%LOG%"
echo done.  log: %LOG%
pause
