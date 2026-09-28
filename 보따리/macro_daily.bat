@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 5
if not exist "%~dp0macro_daily.cmd" (
  echo ERROR: macro_daily.cmd was not found beside this file.
  exit /b 5
)
call "%~dp0macro_daily.cmd" --lookback-days 1 --houses BofA JPM GS Citi HSBC %*
set "MACRO_DAILY_EXIT=%ERRORLEVEL%"
exit /b %MACRO_DAILY_EXIT%
