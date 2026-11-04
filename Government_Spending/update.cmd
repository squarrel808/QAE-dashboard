@echo off
cd /d "%~dp0"
python fetch_data.py
if errorlevel 1 exit /b 1
python build_dashboard.py
if errorlevel 1 exit /b 1
echo Fiscal dashboard updated: %~dp0index.html
