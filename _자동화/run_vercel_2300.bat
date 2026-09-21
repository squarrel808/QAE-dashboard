@echo off
setlocal
chcp 65001 > nul
cd /d "%~dp0.."
set "QAE_PYTHON=C:\Users\infomax\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%QAE_PYTHON%" exit /b 2
call "%~dp0..\전체업데이트.bat" /nightly /nohouseviews /dataonly /nopause %*
exit /b %errorlevel%
