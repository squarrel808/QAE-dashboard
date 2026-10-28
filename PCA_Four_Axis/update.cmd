@echo off
cd /d "%~dp0"
python -X utf8 run_update.py %*
exit /b %errorlevel%
