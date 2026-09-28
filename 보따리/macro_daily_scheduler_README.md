# 매크로 PDF 데일리 다운로드 — 스케줄러 실행

## 실행 파일

`C:\Users\infomax\Documents\python\QAE\보따리\macro_daily.bat`

매번 실행일의 한국 날짜를 기준으로 전날 하루치만 조회한다. 예를 들어 2026-09-15에 실행하면 2026-09-14 발행분을 조회한다. 월요일에도 직전 일요일 하루만 조회하며 이전 영업일로 바꾸지 않는다. 대상은 BofA·JPM·GS·Citi·HSBC 5개 IB다. 이미 정상 저장된 PDF는 중복 검사 후 건너뛴다. 특정 날짜를 고정하지 않았으므로 계속 데일리로 사용할 수 있다.

이 배치는 기존 `macro_daily.cmd` → `macro_daily.py`를 호출하고, 실제 작업이 끝날 때까지 기다린 뒤 종료 코드를 스케줄러에 전달한다. 키 입력 대기나 자동 반복 재실행은 없다. 예약 작업 자체는 사용자가 등록한다.

## Windows 작업 스케줄러의 동작

| 항목 | 입력값 |
|---|---|
| 프로그램/스크립트 | `C:\Windows\System32\cmd.exe` |
| 인수 추가 | `/d /c macro_daily.bat` |
| 시작 위치 | `C:\Users\infomax\Documents\python\QAE\보따리` |

Chrome 로그인 프로필을 사용하는 작업이다. 해당 프로필을 쓰는 Windows 사용자로, **사용자가 로그온할 때만 실행**하도록 설정하고 원하는 아침 시각을 지정한다. 이미 작업이 실행 중일 때는 새 인스턴스를 시작하지 않는 설정을 사용한다.

## 로그인과 결과

수집 전용 Chrome은 포트 9223과 `_macro\.collector\chrome-profile`을 사용한다. 평소 Chrome의 로그인과 별개이며, 세션이 만료되면 전용 창에서 다시 로그인해야 한다.

- PDF: `C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\outdated\<IB>`
- 최신 결과: `C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\.collector\logs\latest_daily.json`
- 실행별 로그: 같은 `logs` 아래 `daily\YYYY-MM-DD`.
- 종료 코드 0은 수집기가 해당 실행 범위를 완료로 확인한 경우다. 0이 아니면 최신 JSON과 로그의 원인을 확인한다.

다운로드 없이 입력 설정·디스크 공간·실행 중복 여부만 확인하려면 이 폴더에서 `macro_daily.bat --check`를 실행한다. 이는 로그인 성공이나 다운로드 성공을 검증하는 명령이 아니다.

이 파일은 PDF 다운로드용이다. 표 갱신용 `데일리시황\데일리_표_업데이트.cmd`는 별도 실행 경로다.

## GS 웹 게시물

원문 PDF가 없는 것으로 검증된 GS research blog는 GS\html 폴더에 HTML 원문, 읽을 수 있는 텍스트, 출처 JSON으로 보관한다. 일반 PDF 보고서와 구분하며, HTML 파일 무결성을 확인해 중복 보관을 건너뛴다. 로그인 실패나 로딩 미완료 화면은 이 예외로 처리하지 않는다.

최근 보충 수집 결과: [2026-09-09~15 결과](macro_backfill_20260909_20260915_result.md).
