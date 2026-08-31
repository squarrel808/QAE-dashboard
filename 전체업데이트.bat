@echo off
chcp 65001 > nul
REM ============================================================
REM  QAE 대시보드 전체 업데이트 -> git push -> Vercel 자동 재배포
REM  이 파일 하나만 더블클릭하면 끝.
REM
REM  실제 작업은 run_qae.py 가 합니다. 이 배치는 창을 띄우고 넘겨주는 역할.
REM  (run_qae.py 가 실행 이력을 CSV/로그로 남겨서
REM   상위 폴더의 scheduler_dashboard.html 에 자동으로 반영됩니다)
REM
REM  [실행 순서]
REM    1) Haver 수집     : PCA용 / CPI분포용 엑셀 받아오기 (DLX Direct 로그인 필요)
REM    2) 리포트 수집    : 크롬(디버그포트 9222) -> PDF 다운로드 -> 요약 -> reports.json
REM    3) BeforeHTML     : 각 폴더 데이터 단계 (Consensus 병합, policytone 수집 등)
REM    4) AfterHTML      : 각 폴더 대시보드 HTML 생성 + master_dashboard.html
REM    5) macro_hub      : JSON 5종 재생성 + embeds HTML 동기화
REM    6) git            : 커밋 + push  (Vercel이 1~2분 뒤 자동 재배포)
REM
REM  [옵션]  여러 개 같이 써도 됨.  예) 전체업데이트.bat /nohaver /noreport
REM    /nohaver    1)번 생략 - Haver 로그인 하기 싫을 때 (기존 엑셀 그대로 사용)
REM    /noreport   2)번 생략 - 셀레니움 리포트 수집 생략
REM    /webonly    1~4 전부 생략 - 이미 만들어둔 HTML로 JSON/embeds만 다시 굽기
REM    /nopush     6)번에서 커밋만 하고 push 안 함
REM    /nogit      6)번을 아예 건너뜀 - git 을 전혀 건드리지 않음 (로컬 갱신/테스트용)
REM    /dryrun     실제로 돌리지 않고 '무엇이 실행될지'만 미리 보기
REM    /nopause    끝에서 키 입력을 기다리지 않음 (작업 스케줄러 무인 실행용)
REM    /dataonly   git add 를 산출물(macro_hub\public 등)로 제한.
REM                작업 중인 코드까지 딸려 올라가는 게 싫을 때 사용.
REM                (기본값은 기존 자동화와 동일하게 git add -A)
REM
REM  로그: QAE\logs\qae_YYYYMMDD.log  (콘솔에도 똑같이 나옴)
REM  이력: QAE\logs\run_history.csv / run_steps.csv / run_failures.csv
REM        -> python\scheduler_dashboard.html 의 "QAE 대시보드 갱신" 항목에 반영
REM ============================================================
setlocal

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

REM /nopause 가 있으면 끝에서 키 입력을 기다리지 않는다 (작업 스케줄러 무인 실행용)
set "NOPAUSE="
for %%A in (%*) do (
    if /i "%%~A"=="/nopause" set "NOPAUSE=1"
)

python "%~dp0run_qae.py" %*
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
    echo [OK] 전체 단계 정상 완료
) else (
    echo [X] 일부 단계 실패 - 위 로그의 [실패] 줄을 확인하세요.
)
echo 로그 폴더 : %~dp0logs
echo 대시보드  : %~dp0..\scheduler_dashboard.html
echo.
if not defined NOPAUSE pause
exit /b %RC%
