# 기존 Chrome 세션 다운로드 결과

검사 구간: **2026-09-01 ~ 2026-09-07, 양끝 포함, 사이트 목록 표시일 기준**.
이번 결과는 이 7일 구간에 한정합니다. **9개월 전체 backfill 완료 결과가 아닙니다.**

기존 로그인된 Chrome을 연결된 브라우저 확장으로 조작하여 사이트 원본 PDF를 받았습니다. 독립 `macro_bulk_downloader.py`가 기존 일반 Chrome에 연결되어 실행된 것은 아닙니다.

## 최종 수량

| 하우스 | 목록 내 고유 항목 | 저장·검증한 원본 PDF | 별도 원본 PDF 없음 | 미확인 |
|---|---:|---:|---:|---:|
| HSBC | 62 | 40 | 22 | 0 |
| GS | 118 | 109 | 8 | 1 |
| JPM | 71 | 71 | 0 | 0 |
| Citi | 39 | 39 | 0 | 0 |
| BofA | 26 | 26 | 0 | 0 |
| 합계 | 316 | **285** | 30 | 1 |

총 160,796,542바이트, 2,739페이지. 최종 저장 위치는 `outdated/<하우스>/`.

285개 모두 PDF 시그니처·EOF, 페이지 및 콘텐츠 스트림 읽기, 파일 크기, SHA-256과 이력 일치를 검사했습니다. 최종 검증 오류 0건, 하우스 내 동일 내용 중복 0건, 미등록 PDF 0건입니다. PDF를 재인쇄하거나 재작성하지 않았습니다.

## 발견한 문제와 처리

- 다운로드 요청의 성공 응답만으로 파일 저장이 끝난 것은 아닙니다. 탭을 일찍 닫거나 이동하면 저장이 취소될 수 있어, 파일 완성을 확인한 후 탭을 정리했습니다. HSBC 목록의 연속 다운로드 일부가 저장되지 않아 보고서별 목록 탭에서 단건 다운로드했습니다.
- HSBC에서 본문에 인용된 보고서 제목으로 파일을 잘못 연결한 3건을 최종 중복 검사에서 발견했습니다. 표지 제목 영역으로 식별을 강화하고, German competitiveness / Bank Negara Malaysia review / The RBA Observer의 정확한 원본을 다시 받아 교정했습니다. 이번 작업에서 만든 잘못된 사본은 삭제하지 않고 `.collector/rejected_title_matches/`로 격리했습니다. 교정 기록은 `.collector/title_match_repairs_20260907.json`입니다.
- HSBC의 일부 목록 페이지 수는 표지를 제외해 실제 PDF보다 1페이지 작습니다. 목록과 실제 페이지 수를 별도로 기록했습니다.
- GS의 긴 제목은 다운로드 파일명과 PDF 메타데이터에서 잘리므로, 고유한 긴 제목 접두부와 실제 페이지 수를 함께 대조했습니다. 발표자료는 PowerPoint 제작 PDF여서 일반 Quark 제작 보고서와 메타데이터가 다릅니다.
- GS/Citi의 사이트 표시일과 PDF 본문 발행일은 시간대 차이로 하루 다를 수 있습니다. 본 실행의 기간 판정은 수집한 사이트 목록 표시일을 사용했습니다.
- BofA는 Global, US/Can, Eur, Jpn, Aus/NZ의 최신 More 목록을 확인했습니다. 여러 지역에 나온 동일 보고서 번호는 한 번만 저장했습니다. 새로 확인한 Eur 4건, Jpn 3건, Aus/NZ 4건 중 1건은 기존 Global 보고서와 중복이었습니다.
- HSBC의 HTML 뉴스레터 15건·영상 6건·팟캐스트 1건과 GS의 블로그 5건·컨퍼런스 오디오 3건은 별도 원본 PDF가 제공되지 않는 화면을 확인했습니다. 영상에서 연결한 별도 보고서는 해당 보고서 항목으로 저장했으며, 영상 웹페이지를 PDF로 대체하지 않았습니다.

## 남은 예외 1건

GS `f2bb28c1-bdf3-48c2-b8d1-8e0c57442e1c`:
**GS Weekend Macro Call: Fed Pricing, Bond Market Volatility, European Gas, Mid-Terms, M&A & the Next Wave of AI**.

53분 9초 오디오와 HTML 안건을 확인했습니다. 화면에 `Print PDF` 버튼이 있으나 실행 중 UI 타임아웃이 발생했고 원본 PDF는 확보되지 않았습니다. `unresolved_print_control`로 남겼으며 전체 항목 다운로드 완료로 표시하지 않았습니다.

## 재개 및 검증 기록

- `.collector/manifest.csv`: 문서별 상태·경로·해시·출처.
- `.collector/downloads.sqlite3`: 기존 수집기와 공유하는 문서 이력. 정상 저장 파일은 재실행 시 중복 검사에 사용됩니다.
- `.collector/browser_run_20260901_20260907_audit.json`: 이번 구간 전체 316개 항목, 최종 파일 검증 결과.
- `.collector/browser_hsbc_verified_20260901_20260907.json`, `.collector/browser_gs_20260901_20260907.json`, `.collector/browser_citi_20260901_20260907.json`: 회사별 원본 대조 결과.
- `.collector/manual_jpm_20260907_manifest.csv`, `.collector/manual_bofa_20260907_manifest.json`: JPM·BofA 원본 대조 결과.

브라우저의 기존 사용자 탭과 로그인은 유지했습니다. Downloads 폴더의 원본 파일도 임의 삭제하지 않았습니다.

독립 Python 프로그램은 기본적으로 별도 Chrome 프로필을 엽니다. 브라우저 확장 연결이 일반 Chrome의 CDP 디버깅 포트를 열어 주는 것은 아니므로, 이 실행을 독립 Python의 기존 Chrome 연결 검증으로 해석하면 안 됩니다. 기존 실행 예제와 실제 파일 경로는 `README_macro.md`에 있습니다.
