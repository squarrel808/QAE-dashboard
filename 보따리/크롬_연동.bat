@echo off
setlocal
set PYTHONIOENCODING=utf-8
set "LOG=%~dp0botari_run_%date:~0,4%%date:~5,2%%date:~8,2%.log"

rem [2026-08-19] 지난 실행이 아직 살아 있으면 먼저 정리한다.
rem   수동 로그인 프롬프트에 매달린 프로세스가 로그 파일을 붙잡고 있으면,
rem   다음 실행은 ">> 로그" 리다이렉트가 실패해서 python 이 아예 안 뜬다.
rem   (로그조차 안 남아 "셀레니움이 고장났다"로 보인다 - 실제 08-19 아침 증상)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*_backup_20260622_101003.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
rem   chromedriver 도 같이 정리한다. quit() 을 안 부르는 구조라 고아로 남는데,
rem   이 프로세스가 python 에서 상속받은 로그 핸들을 계속 붙잡고 있어 python 을 죽여도 안 풀린다.
powershell -NoProfile -Command "Get-Process chromedriver -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenium_profile"

rem [2026-08-19] 고정 5초 대기(ping -n 6) -> "붙을 수 있는 탭"이 뜰 때까지 최대 60초 대기.
rem   포트만 열리고 페이지 탭이 없으면 NoSuchWindowException 으로 전 사이트가 전멸한다.
powershell -NoProfile -Command "$e=(Get-Date).AddSeconds(60); while((Get-Date) -lt $e){ try{ $t=Invoke-RestMethod 'http://127.0.0.1:9222/json/list' -TimeoutSec 3; if($t | Where-Object { $_.type -eq 'page' -and $_.url -notlike 'chrome-extension*' }){ exit 0 } }catch{}; Start-Sleep -Seconds 2 }; exit 1" >nul 2>&1

echo ===== run %date% %time% ===== >> "%LOG%"
python "C:\Users\infomax\Desktop\보따리\gs리서치자료모으기_backup_20260622_101003.py" >> "%LOG%" 2>&1
