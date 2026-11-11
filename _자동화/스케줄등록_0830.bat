@echo off
setlocal
REM Preserve the existing 08:00 and 23:00 triggers and update their refresh actions.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_qae_refresh.ps1"
exit /b %errorlevel%
