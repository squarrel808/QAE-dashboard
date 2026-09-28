# 5개 하우스 매크로 리서치 수집기

HSBC · GS · JPM · Citi · BofA를 한 Python 파일에서 실행합니다. 원본 PDF만 저장하며, 발행일 기준 기간 필터와 중복 검사, 실패 기록을 포함합니다.

2026-09-07 기존 Chrome 세션으로 **9월 1~7일 구간의 원본 PDF 285건**을 저장·검증했습니다. PDF 미제공 30건과 GS 오디오의 PDF 미확인 1건은 별도로 기록했습니다. [구간별 실제 다운로드 결과](DOWNLOAD_REPORT_20260907.md)를 참고하세요. 이 결과는 독립 Python 연결 검증이나 9개월 전체 backfill 완료를 의미하지 않습니다.

**코드는 작성·로컬 테스트를 마쳤지만, 실제 계정으로 9개월 전체 다운로드를 완료한 상태는 아닙니다.** 로그인된 Chrome에서 각 사이트의 목록·페이지 이동·PDF 메뉴를 확인했고, 테스트에서는 가짜 보고서 페이지와 PDF로 동작을 검증했습니다. 특히 Citi의 피드가 9개월 전까지 계속 제공되는지는 실제 실행에서 확인해야 합니다. 목록이 일찍 끝나거나 PDF를 못 받으면 `incomplete`로 남깁니다.

## 저장 위치

```text
C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\
    macro_bulk_downloader.py
    requirements_macro.txt
    README_macro.md
    test_macro_bulk_downloader.py
    .collector\                 ← 최초 실행 때 생성: 로그인 프로필·이력·로그
        logs\
            latest_run.json      ← 마지막 수집 결과 바로가기
            YYYY-MM-DD\
                run_....log      ← 해당 실행의 상세 진행·오류
                run_....json     ← 해당 실행의 회사별 완료 여부·수량
    outdated\
        HSBC\
        GS\
        JPM\
        Citi\
        BofA\
```

파일명은 `발행일_제목__문서번호해시.pdf`입니다. BofA의 지역별 중복도 BofA 폴더에 한 번만 저장합니다. 같은 제목의 다른 문서는 문서번호로 구분합니다.

## 최초 준비

Windows PowerShell에서 다음을 실행합니다. Chrome과 Python 3.10 이상이 필요합니다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro'
python -m pip install -r requirements_macro.txt
python macro_bulk_downloader.py --mode login
```

수집용 Chrome이 뜨면 다섯 사이트에 직접 로그인하고, 원래 검색 목록이 나오는지 확인한 뒤 터미널에서 Enter를 누릅니다. 비밀번호를 코드에 넣지 않습니다. 로그인 상태는 `.collector\chrome-profile`에 남습니다.

**Codex에 연결한 `@Chrome` 세션과 독립 Python 프로그램의 Chrome은 별개입니다.** 기본 설정은 전용 Chrome 프로필을 새로 사용하므로 처음에는 다시 로그인해야 합니다. 사이트의 로그인 만료나 추가 인증이 나타나면 `--mode login`으로 갱신해야 합니다.

이미 자동화용 Chrome을 디버깅 포트로 열어 둔 경우에만 `--cdp-url http://127.0.0.1:9222`를 각 명령에 추가할 수 있습니다. 확장 프로그램을 연결했다는 이유만으로 이 포트가 열리는 것은 아닙니다. 기존 자동화 전용 프로필을 재사용하려면 `--profile-dir '프로필 경로'`를 사용하고, 그 프로필로 열린 Chrome은 먼저 닫으세요.

## 실행

우선 짧은 기간의 목록만 확인할 수 있습니다. `scan`은 보고서 PDF를 저장하지 않고 목록과 상태만 기록합니다.

```powershell
python macro_bulk_downloader.py --mode scan --start 2026-09-01 --end 2026-09-07
```

2026년 9월 7일 기준 직전 9개월을 고정해서 다운로드하는 명령입니다. **아래 명령을 실행할 때 실제 다운로드가 시작됩니다.**

```powershell
python macro_bulk_downloader.py --mode backfill --start 2025-12-07 --end 2026-09-07
```

날짜를 생략하면 한국 날짜 기준 실행일부터 9개월 전까지 수집합니다. 양끝 날짜를 모두 포함하며, 270일로 환산하지 않습니다.

```powershell
python macro_bulk_downloader.py --mode backfill --months 9
```

일부 회사만 실행하거나 소량으로 실제 저장 경로를 확인할 수도 있습니다.

```powershell
python macro_bulk_downloader.py --mode backfill --houses HSBC --start 2026-09-01 --end 2026-09-07 --limit 3
python macro_bulk_downloader.py --mode status
```

`--limit`은 회사별 시도 수의 제한입니다. 이 제한으로 일찍 멈춘 실행은 전체 완료로 표시하지 않습니다. 실패를 포함한 재시도는 같은 명령을 다시 실행하면 됩니다. 저장된 파일의 내용과 해시가 정상인 문서는 건너뜁니다. 같은 `.collector` 폴더를 유지해야 이전 이력을 이어받습니다.

## 매일 반복할 때

```powershell
python macro_bulk_downloader.py --mode daily
```

기본값은 오늘을 포함한 최근 7일을 다시 확인하고 아직 없는 PDF를 추가합니다. 이 명령도 기본적으로 `outdated` 아래의 회사별 폴더에 저장합니다. 다른 보관 폴더를 쓰려면 `--output '저장 폴더'`를 지정하세요. 이력은 문서 단위이므로 기존에 정상 저장된 문서를 새 출력 위치로 다시 복사하지는 않습니다.

현재 예약 작업은 등록하지 않았습니다. 나중에 이 명령을 Windows 작업 스케줄러 등에서 호출할 수 있습니다. 컴퓨터와 네트워크가 사용 가능하고, 사이트 로그인 세션이 살아 있어야 하며, 추가 인증은 사람이 처리해야 합니다. `--headless`는 로그인 확인이 끝난 뒤 필요할 때만 사용하세요.

전용 Chrome을 사용하는 현재 환경에서는 아래 명령을 데일리 작업으로 사용합니다. 최근 7일을 겹쳐 확인하므로 휴일이나 일시적인 실패 뒤에도 누락을 다시 시도합니다.

2026-09-09부터 이 실행기는 매크로 전용 포트 **9223**, `_macro/.collector/chrome-profile`을 사용합니다. 보따리의 포트 9222 및 `C:\selenium_profile`과 별도입니다. 새 프로필의 로그인 상태는 `python run_macro_separate_chrome.py --check-sites`로 확인합니다. 사용자의 요청에 따라 예약 작업은 등록하지 않았습니다.

```powershell
python run_macro_separate_chrome.py --mode daily --lookback-days 7
```

Windows 작업 스케줄러에서는 같은 폴더의 `run_macro_daily.cmd`를 실행하면 됩니다. 종료 코드 0은 완료, 2는 일부 미완료이므로 작업 기록에서도 실패를 구분할 수 있습니다.

각 실행은 `.collector\logs\YYYY-MM-DD`에 독립 로그와 JSON 요약을 남깁니다. `latest_run.json`의 `overall_status`가 `incomplete`이면 같은 명령을 다시 실행하고, 해당 실행의 `.log`에서 하우스명과 오류를 확인합니다.

## 사이트별 수집 범위와 남은 확인점

| 회사 | 대상 목록 | 방식 / 확인점 |
|---|---|---|
| HSBC | Economics → All Reports | 달력으로 기간을 주 단위로 나눕니다. 검색 결과가 75개 제한에 닿으면 더 작은 기간으로 재검색합니다. 하루에도 제한에 닿으면 미완료 처리합니다. |
| GS | 사용자가 준 Economics Research 검색 | 최신순 페이지를 순회합니다. 보고서·리서치 블로그를 열고 PDF 메뉴를 찾습니다. 모델 제외·영어 조건은 원래 URL을 유지합니다. |
| JPM | 사용자가 준 Economics Commetary 검색 | iframe 안의 검색 목록을 순회합니다. 기존 로컬 수집기에 있던 원본 PDF 주소를 먼저 시도하고, 안 되면 보고서 화면을 사용합니다. |
| Citi | Economic Analysis → Research | 피드를 스크롤하고 보고서의 Print → Print (PDF) 메뉴를 사용합니다. 9개월 경계 전에 피드가 더 늘지 않으면 미완료입니다. 이 경우 과거 검색 범위를 별도로 확인해야 합니다. |
| BofA | Global Economics → Most Recent Reports | Global, US/Can, Eur, Jpn, Aus/NZ의 More 목록을 순회합니다. 보고서 번호로 지역 간 중복을 제거합니다. |

PDF가 없는 뉴스레터·영상·블로그도 일부 목록에 섞여 있습니다. 원본 PDF를 찾지 못한 항목은 실패로 기록하며, 웹페이지를 인쇄해서 원본 보고서로 대체하지 않습니다. 첫 실행에서는 이런 항목의 종류와 사이트별 권한을 점검해야 합니다. 목록 레이아웃이나 사이트 검색 제한이 바뀌면 수집기 조정이 필요합니다.

검색 링크가 만료되면 로그인 후 새 검색 링크를 JSON에 넣고 `--urls-json '새링크.json'`으로 덮어쓸 수 있습니다. JSON 키는 `HSBC`, `GS`, `JPM`, `Citi`, `BofA`이며, 바꿀 회사만 넣으면 됩니다.

## 결과 확인

- `.collector\manifest.csv`: 문서별 발행일, 출처, 저장 경로, 상태, 오류.
- `.collector\downloads.sqlite3`: 재실행용 이력. 삭제하면 중복 검사 이력이 없어집니다.
- `.collector\logs\YYYY-MM-DD\run_날짜_번호.json`: 실행별 기간, 회사별 수량, 완료/미완료 사유.
- `.collector\logs\YYYY-MM-DD\run_날짜_번호.log`: 실행별 상세 진행 및 오류.
- `.collector\logs\latest_run.json`: 가장 최근 실행 결과.
- `.collector\collector.log`: 이전 버전과의 호환을 위한 전체 누적 로그.

`scan_complete`는 목록 탐색 완료이고 파일 저장 완료를 뜻하지 않습니다. `complete`는 해당 실행에서 탐색한 범위와 PDF 저장에 오류가 없었다는 뜻입니다. 사이트가 공개하지 않은 자료까지 독립적으로 대조했다는 뜻은 아닙니다. `incomplete`는 목록 탐색 실패, 인식할 수 없는 날짜, 다운로드 실패 또는 사용자가 설정한 제한 도달입니다. 종료 코드는 정상 0, 미완료 2입니다. 프로그램 시작 자체가 실패한 경우에는 다른 0이 아닌 코드로 종료할 수 있습니다.

## 개발 검증

```powershell
python -m unittest -v test_macro_bulk_downloader
```

테스트의 Chrome은 별도 임시 세션이며 모든 웹 요청을 가짜 응답으로 처리합니다. 실제 증권사 서버나 사용자 로그인 프로필을 사용하지 않습니다. 날짜·월말·파일명·PDF 판별·회사별 중복·파일 손상·기간 양끝 포함·다섯 목록 추출·페이지 이동·원본 다운로드·Citi 팝업 다운로드·로그인 HTML 거부를 확인합니다.

구현에 사용한 공식 문서: [Playwright 다운로드](https://playwright.dev/python/docs/downloads), [인증된 요청 컨텍스트](https://playwright.dev/python/docs/api/class-apirequestcontext), [Chrome 프로필 실행](https://playwright.dev/python/docs/api/class-browsertype).
