@echo off
REM Selenium companion: launch Chrome with a DEDICATED profile + debug port 9222.
REM Chrome 136+ blocks remote-debugging on the real/default profile, so we use a
REM separate profile (C:\selenium_profile). Log in to the 4 sites ONCE here; it persists.

set "PROFILE=C:\selenium_profile"
set "CHROME="
for %%P in (
  "C:\Program Files\Google\Chrome\Application\chrome.exe"
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
  "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do if exist "%%~P" set "CHROME=%%~P"
if not defined CHROME set "CHROME=chrome"

echo Launching: %CHROME%
echo Profile  : %PROFILE%
start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE%"

echo.
echo Done. Open http://localhost:9222/json/version to confirm (should show JSON).
echo If refused, close all Chrome first:  taskkill /F /IM chrome.exe
echo Log in to Marquee / BofA / HSBC / JPMM once, keep Chrome open, then run:
echo    python download_reports.py
echo.
pause
