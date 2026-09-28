@echo off
setlocal
cd /d "%~dp0"
set "MACRO_DASH_PY=C:\Users\infomax\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%MACRO_DASH_PY%" set "MACRO_DASH_PY=python"
"%MACRO_DASH_PY%" -X utf8 "%~dp0build_dashboard.py" --output "%~dp0..\output\ecocal_dashboard"
if errorlevel 1 (
  echo Dashboard update failed. See the error above.
  pause
  exit /b 1
)
start "" "%~dp0..\output\ecocal_dashboard\index.html"
endlocal
