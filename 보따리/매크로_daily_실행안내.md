# 매크로 리포트 Daily 실행

실행 파일: `macro_daily.cmd` (Python 본체: `macro_daily.py`). 스케줄러는 등록하지 않았다.

기존 `크롬_연동.bat`의 **크롬 실행 → 준비 확인 → 수집** 방식을 사용한다. 기존 보따리 원본 파일은 변경하지 않았으며, 매크로 수집 엔진과 로그인 기록은 `_macro`의 것을 재사용한다. 보따리의 인기 리포트 상위 N개가 아니라, 벌크 수집과 동일한 매크로 검색 조건을 매일 확인한다.

## 실행

```powershell
& 'C:\Users\infomax\Documents\python\QAE\보따리\macro_daily.cmd'
```

기본 대상은 HSBC, BofA, JPM, GS, Citi이며, 한국 날짜로 오늘을 포함한 최근 7일을 다시 확인한다. 이미 받은 정상 파일은 IB·문서 ID와 파일 검증으로 건너뛴다. 일시 실패나 주말 누락을 다음 실행에서 재시도하기 위한 중첩 기간이다. 7일보다 오래 실행하지 못했다면 `--lookback-days 14` 등으로 늘릴 수 있다(최대 31일).

다운로드 없이 설정·공간·중복 실행 상태만 확인:

```powershell
& 'C:\Users\infomax\Documents\python\QAE\보따리\macro_daily.cmd' --check
```

## 브라우저와 저장 위치

- 매크로 전용 Chrome 포트: **9223**. 닫혀 있으면 자동 실행하고, 이미 열려 있으면 소유 프로필을 확인 후 재사용한다.
- 로그인 프로필: `데일리시황\Context\_macro\.collector\chrome-profile`.
- 기존 보따리의 **9222 / C:\selenium_profile** 및 다른 Python·ChromeDriver 프로세스는 종료하거나 재사용하지 않는다.
- PDF 저장: `데일리시황\Context\_macro\outdated\<IB>`.
- 중복 방지 이력: 기존 `.collector\downloads.sqlite3` 그대로 유지.
- 실행 중 Chrome 창은 최소화한다. 로그인 만료/MFA는 사람이 다시 인증해야 하며, 무인 실행이 입력을 기다리며 멈추지 않는다.

로그인이 필요하면 벌크 수집이 끝난 뒤 다음 명령으로 전용 로그인 창을 연다:

```powershell
python 'C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\run_macro_separate_chrome.py' --open-login --houses HSBC BofA JPM GS Citi
```

## 로그와 보호 장치

- 최신 Daily 결과: `_macro\.collector\logs\latest_daily.json`. 중복 실행으로 거부된 시도는 실행별 로그에만 남기며, 진행 중인 Daily의 최신 결과를 덮어쓰지 않는다.
- 실행기 로그: `_macro\.collector\logs\daily\YYYY-MM-DD\daily_<id>.log`, `.json`, `.console.log`.
- 보고서별 상세 기록: `_macro\.collector\logs\YYYY-MM-DD\run_<id>.log`, `.json`.
- 진행 중인 벌크 캠페인 또는 다른 수집기가 있으면 브라우저를 건드리지 않고 종료 코드 **3**으로 끝난다. 백필을 자동 중단하거나 강제로 동시에 실행하지 않는다.
- 디스크 여유 **5 GiB** 미만이면 중단한다. 기본 최대 실행 시간은 **120분**, 수집 로그에 **15분**간 변화가 없으면 자신이 시작한 수집 프로세스만 종료하고 사유를 남긴다.
- 원본 PDF가 확인되지 않은 웹페이지를 PDF로 인쇄해 대체하지 않는다. 확인된 뉴스레터·미디어는 별도 상태로 기록하고, 로그인/권한 오류를 정상 처리하지 않는다.

| 종료 코드 | 의미 |
|---|---|
| 0 | 요청한 Daily 수집 완료 (`--check`에서는 실행 준비 상태만 뜻함) |
| 2 | 일부 IB/보고서 미완료 |
| 3 | 벌크 캠페인 또는 다른 수집기가 실행 중 |
| 4 | 디스크 여유 부족 |
| 5 | 실행 준비·수집기·환경 오류 |
| 6 | 최대 실행 시간 또는 무진행 제한 초과 |
| 130 | 사용자 중단 |

## 스케줄러에 등록할 때

등록 대상은 이 폴더의 `macro_daily.cmd`다. 작업 폴더가 달라도 스크립트 자신의 위치를 기준으로 경로를 찾는다. 현재 사용자의 설치된 Python 3.13을 우선 사용하고, 없으면 PATH의 `python`을 사용한다. 이 Python에 기존 수집기의 Playwright가 설치되어 있어야 한다.

로그인 상태를 이용하는 Chrome 작업이므로 **같은 Windows 계정의 로그인된 세션에서 실행**하는 설정을 사용한다. 벌크 종료 전에는 실행 코드 3으로 보류되는 것이 정상이다. 이 Daily 코드를 만들었다는 사실은 과거 6개월 수집 완료를 의미하지 않는다.
