# 2026-09-09~15 매크로 수집 결과

확인 시각: 2026-09-15T23:02:56.411502+09:00

HSBC 제외, 지정된 현재 리서치 목록 기준 수집 완료. 이번 작업에서 PDF 192개와 GS 웹 원문 5개를 추가했다. 기존 자료를 포함한 해당 기간 확보량은 PDF 220개와 HTML 5개다.

| IB | 이번 추가 PDF | 기간 내 전체 PDF | HTML 원문 |
|---|---:|---:|---:|
| BofA | 29 | 32 | 0 |
| JPM | 37 | 42 | 0 |
| GS | 83 | 98 | 5 |
| Citi | 43 | 48 | 0 |

저장 파일 225건의 존재와 SHA-256을 확인했고, PDF 형식과 HTML 출처·텍스트 동반 파일도 확인했다.

PDF: `C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\outdated\<IB>`
GS 웹 원문: `C:\Users\infomax\Documents\python\QAE\데일리시황\Context\_macro\outdated\GS\html`

## 과거 DB 기록 2건

BofA의 13017021(GEMs Paper), 13017227(Global Emerging Markets Weekly)은 과거 DB에 pending으로 남아 있지만 현재 Global 목록 첫 100건에는 없었다. 같은 9월 10일·제목의 현재 보고서 13018123, 13017596은 저장됐다. 구 기록은 삭제하거나 다운로드 완료로 바꾸지 않았다. 동일 본문 또는 개정판 관계로 단정하지 않는다.

## 앞으로 실행

`macro_daily.bat`은 한국시간 전날 하루치만 수집한다. 월요일은 일요일 자료를 조회한다. 대상은 BofA·JPM·GS·Citi이며 HSBC 제외. 이번 기간은 실행 인수로만 지정했으므로 기본값은 계속 daily다.

작업 스케줄러 등록 방법은 `macro_daily_scheduler_README.md` 참고. 예약 작업 자체는 등록하지 않았다.
