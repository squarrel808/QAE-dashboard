@echo off
REM ============================================================
REM  QAE 대시보드 일일 자동 갱신 (매일 08:30, 작업 스케줄러가 호출)
REM   1) 셀레니움용 크롬(디버그 포트 9222) 실행
REM   2) 리서치 PDF 수집(download_reports) + 요약(summarize)
REM   3) 원본 데이터 갱신 (BeforeHTML_master: 경제지표/PCA/gs_api/Consensus/policytone)
REM   4) HTML 재생성 (AfterHTML_master + master_dashboard)
REM   5) macro_hub 대시보드 JSON 빌드 (5개 모듈 + embeds 동기화)
REM   6) git 커밋 + push -> Vercel 자동 재배포
REM  로그: _자동화\logs\YYYY-MM-DD.log
REM ============================================================

set ROOT=C:\Users\infomax\Documents\python\QAE
set LOGDIR=%ROOT%\_자동화\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
call :main >> "%LOGDIR%\%date:~0,10%.log" 2>&1
exit /b

:main
echo ================= %date% %time% 시작 =================

REM (0) 파이썬 출력 인코딩 고정(cp949 콘솔에서 특수문자로 죽는 것 방지) + venv 활성화
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if exist "%ROOT%\ACMTP\.venv\Scripts\activate.bat" call "%ROOT%\ACMTP\.venv\Scripts\activate.bat"

REM (1) 셀레니움용 크롬 실행 - 크롬_연동.bat 과 동일 (이미 떠 있으면 기존 창에 붙음)
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium_profile"
ping -n 8 127.0.0.1 > nul

REM (2) 리서치 PDF 수집 + 요약 (한 단계 실패해도 다음 단계 계속)
echo. & echo [2/6] 리서치 PDF 수집
python "%ROOT%\report_pipeline\download_reports.py"
echo. & echo [2/6] 새 PDF 요약 - reports.json
python "%ROOT%\report_pipeline\summarize.py"

REM (3) 원본 데이터 갱신 (폴더별 실패해도 계속 진행하도록 이미 설계됨)
echo. & echo [3/6] BeforeHTML_master (데이터 수집,가공)
python "%ROOT%\BeforeHTML_master.py"

REM (4) HTML 재생성
echo. & echo [4/6] AfterHTML_master (HTML 생성,통합)
python "%ROOT%\AfterHTML_master.py"

REM (5) macro_hub 대시보드 JSON 빌드
echo. & echo [5/6] macro_hub JSON 빌드
python "%ROOT%\macro_hub\scripts\build_pairbaskets_json.py"
python "%ROOT%\macro_hub\scripts\build_policy_json.py"
python "%ROOT%\macro_hub\scripts\build_consensus_json.py"
python "%ROOT%\macro_hub\scripts\build_pca_json.py"
python "%ROOT%\macro_hub\scripts\build_caimap_json.py"
python "%ROOT%\macro_hub\scripts\sync_embeds.py"

REM (6) git 커밋 + push -> Vercel 자동 재배포
echo. & echo [6/6] git push
cd /d "%ROOT%"
git add -A
git commit -m "auto: daily data %date:~0,10%"
git push

echo ================= %date% %time% 끝 =================
exit /b
