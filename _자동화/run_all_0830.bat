@echo off
setlocal
chcp 65001 > nul
REM Existing daily task runs at 08:00 KST.
call "%~dp0..\전체업데이트.bat" /scheduled /nopause %*
exit /b %errorlevel%
