# 매크로 Research Context — 로컬 원문 기반 워크플로우

**아침 실행:** [데일리시황 README](../../../README.md)의 `데일리_표_업데이트.cmd`를 사용한다. 새 AI 해석은 별도 요청 단계다.

**현재 사용할 결과:** [기존 메인 INDEX](../../../표_업데이트/index.html)에서 `지표별 요약·IB 코멘트`와 `IB 거시 맥락 뷰`를 함께 연다. 전자는 개별 발표의 수치·요약·IB 반응/전망·AI 비교, 후자는 5개 IB의 국가별 Growth / Inflation / 통화정책과 전제·변화 이력이다. 한 화면이 다른 화면을 대체하지 않는다. [살아있는 IB 모듈](output/living_ib/START_HERE.md)은 별도 기준일로 생성된 상세 근거·이력 출력이며, [모듈 안내](README_LIVING_IB.md)와 [화면 안내](ecocal_dashboard/README.md)를 참조한다.

2026-09-15에 기존 지표 요약·코멘트를 유지하면서 거시 맥락 페이지를 복원했다. 당시 현재 견해 58건은 living DB 55건과 검토 연결 파일의 보강 견해 3건을 합한 값이고, 이전 견해는 17건이다. 거시 견해 최신 자료일은 9월 8일로 검색 DB 최신 보고서일 9월 15일과 다르다. 자세한 고정 시점 기록과 날짜 원칙은 [데일리 README](../../../README.md)에 있다. 현재 수량은 `../../../표_업데이트/latest.json`을 확인한다.

목적: **원문 → IB × 국가별 견해 이력 → 국가별 쟁점 비교 → WECO와 대조 → 검토·승인된 판단 메모**.

현재 구현된 것은 원문 적재·검색, 국가별 검토 묶음, 원문 근거가 검증되는 견해·수치 전망 이력, WECO 숫자와 검토된 IB 근거를 연결하는 대시보드다. 모든 PDF를 AI가 읽고 견해를 확정한 단계는 아니며, 새 지표 해석은 별도 요청 시 원문 검토를 거쳐 작성한다.

## 위치와 원칙

- 입력: 이 폴더 옆 `../outdated/`의 PDF. 원본을 이동·수정·삭제하지 않는다.
- 데이터: `data/research.sqlite3` — 문서, 페이지, 검색용 본문 조각, 국가·주제 태그, 견해 초안, 실행 기록.
- 지표 작성물: `ecocal_dashboard/authored_commentary.json` — 원문 검토 후 작성한 지표 요약·IB 요약·AI 비교와 수치 스냅샷. 대화창에만 남기지 않고 기존 INDEX의 WECO에 반영한다. `reviewed_comments.json`은 기존 직접 연결·보강 견해를 별도로 유지한다.
- 거시 화면: `ecocal_dashboard/build_macro_views.py`·`macro_views.html`이 living DB와 보강 견해를 읽어 실행별 `WECO/macro_views.html`·`macro_views_data.json`을 생성한다. 매번 저장 뷰를 재선택/검증하는 것이며 새 하우스뷰를 자동 작성하지 않는다.
- 결과: `output/01_적재현황.md`, `output/country_packets/`.
- 첫 분석 예시: `output/02_유로존_IB견해_초기검토.md` — 4개 IB, 4개 보고서, 8개 원문 확인 주장. 전체 분석 완료본이 아니라 검토 초안이다.
- `pilot_claims.json`과 `build_pilot.py`는 2026-09-09 초기 검토 표본이다. 새 자료로 자동 갱신되는 전망 모델이 아니다. 반복 적재로 기존 검토 초안을 최신 전망으로 바꾸지 않는다.
- 같은 내용의 PDF는 SHA-256으로 하나의 문서에 연결하며 모든 파일 경로를 기록한다.
- 파일 크기와 수정 시각이 같은 기존 파일은 재처리하지 않는다. 메타데이터를 고친 경우에는 별도 재검토가 필요하다.
- 저장 중인 파일은 제외한다. 실행 시작 시 파일 목록을 고정하고 이후 도착한 PDF는 다음 실행에서 추가한다.
- API 키, 유료 임베딩, 뉴스 호출, 브라우저 조작, 외부 게시 기능 없음.
- 검색은 로컬 SQLite FTS5이며, 의미 기반 임베딩 검색은 아직 없다.
- 다른 `macro_hub` 게시 파이프라인 및 수집 코드와 독립적이다. 이 폴더를 공개 저장소에 업로드하지 않는다.

## 반복 실행

```powershell
python -X utf8 .\research_context.py ingest
python -X utf8 .\research_context.py packet --country all
python -X utf8 .\research_context.py status
```

현재 `ingest` 기본 입력은 `outdated`다. 날짜별 신규 폴더를 만들면 명시적으로 해당 경로를 입력해 같은 DB에 추가할 수 있다.

```powershell
python -X utf8 .\research_context.py ingest --raw '..\daily\20260910'
```

`packet --country all`은 앞서 정한 우선 국가 미국(US), 영국(GB), 유로존(EA), 캐나다(CA), 호주(AU)의 하우스별 최신 원문 검토 묶음을 만든다. DB에는 그 밖의 제목 식별 국가도 저장한다. 검토 묶음의 짧은 발췌는 결론·전제 전체를 대체하지 않는다.

## 원문 검색

```powershell
python -X utf8 .\research_context.py search --country EA --text 'inflation' --limit 8
python -X utf8 .\research_context.py search --country GB --house GS --topic monetary_policy --text 'wage OR inflation'
python -X utf8 .\research_context.py search --country US --text 'payroll' --asof 2026-08-01
```

`--asof`는 그 날짜까지의 발행일이 수집 기록으로 확인된 문서만 반환한다. 파일명 날짜 후보, 날짜 충돌, 날짜 미상은 제외한다. 이는 발행일 기준 필터이며 **PDF의 최초 배포 시각이나 과거 버전이 그 시점에 실제 존재했다는 완전한 point-in-time 검증은 아니다**.

## 분류와 날짜의 한계

- 제목의 명시적 국가·중앙은행 명칭으로 태그를 만든다. 본문에만 나오는 국가는 빠질 수 있다. 글로벌 보고서는 국가 필터를 빼고 추가 검색해야 한다.
- 독일·프랑스·이탈리아·스페인 제목을 유로존에도 연결한다. 모든 유럽 국가를 유로존으로 취급하지 않는다.
- 국가는 전망 주체가 아니다. 국가 태그가 있다는 이유로 특정 IB의 하우스뷰로 승인하지 않는다.
- 발행일은 수집 DB 값을 우선한다. PDF 표지와 자동 대조한 검증값이 아니다. 파일명과 충돌하면 검토 표시한다. 폴더 작성일·다운로드일을 발행일로 쓰지 않는다.
- 전체 페이지 텍스트는 보존하지만 검색용 조각에서는 명시적으로 시작하는 일부 공시 문구를 제외한다.
- 텍스트가 부족한 스캔본은 `needs_ocr`로 남긴다. 표·그림 숫자를 텍스트만으로 확정하지 않는다.
- 저장 날짜 범위와 문서 수는 원문 누락 여부를 증명하지 않는다.

## 견해 초안: 검증 가능한 원문 근거 필수

JSON 목록에 `claim_id, doc_id, page, country, topic, claim, evidence_quote, assumptions, change_vs_prior`를 넣는다.

```powershell
python -X utf8 .\research_context.py import-claims '.\output\검토견해_초안.json'
```

- `evidence_quote`는 지정 페이지에 실제 존재하는 원문이어야 한다. 다르면 적재를 거부한다.
- 검증 시 공백·줄바꿈과 PDF에서 단독 줄 `n` 또는 글머리표로 추출된 항목 기호만 정규화한다. 원문 페이지 텍스트는 그대로 보존하고 본문 단어·숫자를 바꾸지 않는다.
- 전부 `draft`로 저장한다. 동일 `claim_id`를 덮어쓰지 않는다.
- 원문 인용의 일치는 한국어 해석의 정확성을 자동으로 보장하지 않는다. 해석과 전제는 사람이 검토해야 한다.
- 한 IB의 실제 신규 견해, AI의 기존 논리 적용, 사용자의 판단을 혼합하지 않는다.
- 이전 견해와 비교하지 않았으면 `미확인`으로 남긴다.
- 승인된 국가 판단 메모는 자동 생성·덮어쓰기하지 않는다.

## 이후 단계

1. 검토 묶음 + 검색으로 동일 IB/동일 주제의 시간 순서를 확인한다.
2. 주장·근거·전제·반증 조건을 사람/현재 앱이 검토해 초안으로 기록한다.
3. WECO 연결은 구현되었다. 아침 실행은 `QAE/____Rawdata___/ecocal*.xlsx`의 B~K 또는 Bloomberg A~L 양식과 저장된 요약·IB 근거·거시 뷰를 `데일리시황/표_업데이트`에 갱신한다. [경제지표 대시보드 안내](ecocal_dashboard/README.md)를 참고한다. 숫자 스냅샷이 바뀐 지표 요약은 재검토로 남기며 새 해석을 자동 생성하지 않는다. 새 직접 코멘트·기존 뷰 기반 해석·새 거시 전망 작성은 별도 원문 검토 작업이다.
4. 공식 자료·뉴스 확인은 사건별로 이 앱에서 수행한다. 별도 API 요금이 발생하는 프로그램 호출은 붙이지 않았다.
5. 승인 후 국가별 상태 메모의 새 버전을 추가한다. 기존 버전은 보존한다.

## 테스트

```powershell
python -m unittest test_research_context -v
```
