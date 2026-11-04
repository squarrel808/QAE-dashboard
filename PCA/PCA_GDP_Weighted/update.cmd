@echo off
rem New user-facing workflow: four broad PCA axes. Legacy model files preserved.
call "%~dp0..\PCA_Four_Axis\update.cmd"
exit /b %errorlevel%
