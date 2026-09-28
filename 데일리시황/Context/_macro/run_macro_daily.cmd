@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "MACRO_PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%MACRO_PYTHON%" set "MACRO_PYTHON=python"
"%MACRO_PYTHON%" -u "%~dp0run_macro_daily.py" %*
exit /b %ERRORLEVEL%
