@echo off
REM 매일 오전 8:30 자동 실행 등록 (1회만 더블클릭)
schtasks /Create /F /SC DAILY /ST 08:30 /TN "QAE대시보드갱신" /TR "\"C:\Users\infomax\Documents\python\QAE\_자동화\run_all_0830.bat\""
echo.
echo 등록 완료. 아래 명령으로 관리:
echo   상태 확인 : schtasks /Query /TN "QAE대시보드갱신" /V /FO LIST
echo   즉시 실행 : schtasks /Run   /TN "QAE대시보드갱신"
echo   삭제      : schtasks /Delete /TN "QAE대시보드갱신" /F
pause
