@echo off
chcp 65001 > nul
REM ============================================================
REM  QAE 대시보드 매일 자동 갱신 (작업 스케줄러 "QAE대시보드갱신" 이 08:30 에 호출)
REM
REM  내용은 전부 QAE\전체업데이트.bat -> run_qae.py 에 있습니다.
REM  여기서는 '무인 실행에 맞는 옵션'만 붙여서 그걸 부릅니다.
REM
REM    /nohaver   Haver 는 DLX Direct 로그인창(이메일+보안코드)이 떠서 무인 실행이
REM               불가능합니다. 그래서 수집은 건너뛰고, PCA·CPI분포는 기존 엑셀로
REM               다시 그립니다. Haver 까지 새로 받으려면 사람이 있을 때
REM               QAE\전체업데이트.bat 을 직접 더블클릭하세요.
REM    /nopause   끝에서 키 입력을 기다리지 않음 (안 붙이면 스케줄러가 멈춰 있음)
REM
REM  로그·이력 : QAE\logs\   (qae_YYYYMMDD.log / run_history.csv / run_steps.csv)
REM              -> python\scheduler_dashboard.html 에 자동 반영
REM  스케줄 등록: 이 폴더의 스케줄등록_0830.bat 을 관리자 권한으로 1회 실행
REM
REM  뒤에 옵션을 더 붙이면 그대로 전달됩니다. 무엇이 돌아갈지 먼저 보려면:
REM     run_all_0830.bat /dryrun
REM ============================================================

call "%~dp0..\전체업데이트.bat" /nohaver /nopause %*
exit /b %errorlevel%
