@echo off
REM ── 리서치 리포트: 수집 → 요약 → 게시 (매일 1회) ──
cd /d "%~dp0"

echo [1/3] PDF 수집 (Selenium)
python download_reports.py

echo [2/3] 새 PDF 요약 -^> reports.json
python summarize.py

echo [3/3] 사이트에 게시 (git push)
cd /d "%~dp0\..\macro_hub"
git add public/data/reports.json public/report_files 2>nul
git commit -m "reports %date%" 2>nul
git push

echo 완료.
