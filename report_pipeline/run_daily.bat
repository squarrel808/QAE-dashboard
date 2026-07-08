@echo off
REM -- 리서치 리포트: 크롬 실행 -> 수집 -> 요약 -> 게시 (수동 1회 실행용) --
REM    전체 파이프라인 자동 실행은 ..\_자동화\run_all_0830.bat 사용
cd /d "%~dp0"
set PYTHONUTF8=1

echo [0/3] 셀레니움용 크롬 실행 (디버그 포트 9222)
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium_profile"
ping -n 8 127.0.0.1 > nul

echo [1/3] PDF 수집 (Selenium)
python download_reports.py

echo [2/3] 새 PDF 요약 - reports.json
python summarize.py

echo [3/3] 사이트에 게시 (git push)
cd /d "%~dp0\.."
git add macro_hub/public/data/reports.json macro_hub/public/report_files report_pipeline/state.json 2>nul
git commit -m "reports %date:~0,10%"
git push

echo 완료.
pause
