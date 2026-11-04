@echo off
setlocal
cd /d "%~dp0"
python -X utf8 update_surprise.py --open %*
if errorlevel 1 (
  echo Refresh failed. Previous report is preserved. See last_attempt.json.
  pause
  exit /b 1
)
endlocal
