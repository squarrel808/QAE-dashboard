@echo off
chcp 65001 > nul
cd /d "%~dp0.."
python -X utf8 "%~dp0ib_interpretation_monitor.py" sync --refresh
if errorlevel 1 exit /b %errorlevel%
start "" "%~dp0..\..\scheduler_dashboard.html"
