@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
python -X utf8 "%~dp0update_daily_tables.py" --open %*
if errorlevel 1 (
  echo Update failed. Please check the error and update.log.
  pause
  exit /b 1
)
endlocal
