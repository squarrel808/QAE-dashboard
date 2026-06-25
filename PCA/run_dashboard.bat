@echo off
cd /d "%~dp0"
python pca_gdp.py
if %errorlevel%==0 start "" pca_dashboard.html
pause
