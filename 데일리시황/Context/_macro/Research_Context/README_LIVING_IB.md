# 살아있는 IB 리서치 모듈

현재 다운받아 둔 자료에서 **GS·JPM·Citi·BofA·HSBC의 국가별 견해와 변경 이력**을 보관합니다. 일상적인 화면 입구는 [기존 메인 INDEX](../../../표_업데이트/index.html)의 **IB 거시 맥락 뷰**입니다. [모듈 상세 출력](output/living_ib/START_HERE.md)은 해당 파일에 표시된 기준일의 근거·이력 스냅샷입니다.

2026-09-09 초기 상태는 원본 검색 DB 2,270개 중 **48개 원본의 선택한 페이지, 견해 이력 72건, 현재 견해 55건, 근거 인용 114개**입니다. 미국·유로존·영국·캐나다·호주·일본을 포함하고 글로벌 에너지 등은 별도로 연결했습니다. 모든 견해는 사용자 검토 전 초안입니다. 9개월 전체 보고서의 의미 분석을 완료한 상태는 아닙니다.

## 지표 해석과 거시 맥락은 별도 화면으로 함께 유지

- `WECO/index.html`은 개별 지표의 결과·짧은 요약·IB별 요약·AI 비교를 보여줍니다. PMI라면 지역과 제조업/서비스/종합 구분까지 일치하는 원문을 먼저 찾습니다. 일반 growth/inflation 문구를 지표 코멘트로 대신 쓰지 않습니다.
- `WECO/macro_views.html`은 국가/지역별로 5개 IB의 **Growth / Inflation / 통화정책**을 나란히 비교합니다. 핵심 견해와 전제·리스크/확인 질문·이전 견해와의 변화·제한·출처 날짜를 먼저 보이고, 긴 원문과 과거 이력은 펼쳐 봅니다. 지표 화면의 보조 배경을 접더라도 이 독립 메뉴를 없애지 않습니다.
- 정상 데일리 달력 빌드는 `ecocal_dashboard/build_macro_views.py`를 통해 두 번째 화면도 생성합니다. `living_ib.sqlite3`의 현재/이전 견해·수치 전망과 `ecocal_dashboard/reviewed_comments.json`의 보강 견해를 읽기 전용으로 조합합니다. 원문·견해 ID·이력을 보존하고 새로운 견해를 DB에 자동 입력하지 않습니다.
- 지표 해석 요청으로 작성한 `authored_commentary.json`은 지표용입니다. 이를 새 하우스뷰로 승격하거나 기존 living 상태를 덮어쓰지 않습니다. 거시 견해 최신화는 아래의 원문 대조·새 ID 입력 절차를 따르는 별도 작업입니다.

2026-09-15 복원 기록: living 현재 55건 + 보강 3건 = 화면 현재 견해 58건, 이전 견해 17건(전체 75건), 저장 수치 전망 10건, 6개 국가/지역 + 글로벌입니다. 이는 저장 뷰 복원이며 신규 보고서 전체 분석이 아닙니다. 거시 견해 최신 자료일은 9월 8일, 검색 DB 최신 보고서일은 9월 15일이었습니다. 최신 수량은 메인 옆 `latest.json`의 `weco.macro_views`를 확인합니다. `historical_views`는 이전 견해만이 아니라 현재를 포함한 전체 이력 수이며, 이전 견해만의 수는 `prior_views`입니다.

화면 생성일·지표 코멘트 검토일·거시 견해 자료일·검색 DB 최신 보고서일을 혼동하지 않습니다. 새 PDF가 검색 가능해져도 아직 검토하지 않은 새 전망은 화면에 생기지 않습니다. 모든 작성물은 사용자 검토 전 초안입니다.

## 파일 역할

| 위치 | 역할 |
|---|---|
| `../outdated/<IB>/` | 기존 원본 PDF. 원본 파일을 그대로 참조합니다. |
| `data/research.sqlite3` | 기존 페이지·본문 검색 DB. 기존 8개 시험 주장과 판단 메모도 유지합니다. |
| `data/living_ib.sqlite3` | 신규 견해 이력과 지표 입력을 보관합니다. 기존 견해 ID를 덮어쓰지 않습니다. |
| `initial_views_20260909.json` | 이번에 원문 근거를 확인하여 작성한 초기 견해입니다. |
| `initial_forecasts_20260910.json` | GDP·물가 등 수치 전망을 대상 기간·단위·시나리오·원문 근거와 함께 보관합니다. |
| `output/living_ib/<IB>/MODULE.md` | 사람이 읽는 IB별 현재 견해·전제·확인 질문·원문 페이지입니다. |
| `output/living_ib/<IB>/state.json` | AI가 필요한 견해만 불러올 수 있는 현재 상태입니다. |
| `output/living_ib/<IB>/history.json` | 근거를 포함한 해당 IB의 누적 견해 이력입니다. |
| `output/living_ib/<IB>/forecasts.json` | 해당 IB의 현재 수치 전망입니다. |
| `output/living_ib/FORECASTS.md` | IB 수치 전망을 비교하는 표입니다. |
| `output/living_ib/CHANGELOG.md` | 이전 원본과 직접 대조한 유지·변경 기록입니다. |
| `output/living_ib/COVERAGE.md` | 근거 공백과 검토할 보고서입니다. |
| `event_template.json` | 지표 발표 입력 양식입니다. 빈 실제값을 채워야 실행됩니다. |
| `MODULE_RULES.md` | 향후 AI 해석과 견해 갱신에 적용할 공통 규칙입니다. |
| `ecocal_dashboard/authored_commentary.json` | 지표 요약·IB 요약·AI 비교와 검토 당시 수치 스냅샷입니다. 거시 견해 DB와 분리합니다. |
| `ecocal_dashboard/reviewed_comments.json` | 기존 지표-원문 연결과 보강 견해입니다. 거시 화면은 이 파일의 `views`도 읽습니다. |
| `../../../표_업데이트/runs/<요청시각>/WECO/macro_views.html` | 국가별 거시 맥락 비교 화면. 같은 폴더의 `macro_views_data.json`에 표시 데이터를 저장합니다. |

## 앞으로 이 앱에서 요청할 방법

다음과 같이 요청하면 됩니다.

> 이번 미국 CPI를 해석해줘. 국가·CPI 세부지표·대상 기간에 맞는 각 IB 원문을 먼저 검색하고 직접 코멘트를 요약해줘. 실제값·컨센서스·수정치를 대조하고, 직접 근거가 부족한 경우에만 기존 거시 전제에 대한 AI 추론으로 구분해줘. 짧은 요약과 IB별 코멘트를 기존 INDEX 대시보드에 저장해줘.

또는 새 보고서가 쌓인 뒤 다음과 같이 요청할 수 있습니다.

> 새 보고서를 적재하고 GS·JPM·Citi·BofA·HSBC의 최신 국가별 견해를 갱신해줘. 이전 원본과 비교해 유지와 변경을 나누고, 근거 없는 금리 경로는 채우지 마.

이때 AI는 `MODULE_RULES.md`를 읽고 지표별 검색 후보의 전체 근거 페이지와 필요한 기존 상태를 불러옵니다. 모든 PDF나 과거 대화를 매번 대화 컨텍스트에 넣을 필요가 없습니다. 로컬 적재·검색·저장 뷰 출력에는 모델 API 호출이 없지만, 사용자가 요청한 새 원문 요약·해석은 이 앱의 모델 작업이므로 사용량을 씁니다. 결과는 대화에만 남기지 않고 저장 데이터와 기존 대시보드에 반영합니다. 개별 IB의 견해와 사용자의 종합 국가 판단은 별개입니다.

## 반복 실행

이 폴더(`Research_Context`)에서 실행합니다. 신규 도구는 Python 표준 라이브러리만 사용합니다. 새 PDF를 적재하는 기존 도구에는 PyMuPDF가 필요합니다. 모델 API를 호출하거나 과금하는 코드가 없습니다.

```powershell
# 새 PDF를 기존 검색 DB에 적재하고 검토 대기·모듈 출력을 갱신
python -X utf8 .\living_ib.py refresh

# 원본 적재 없이 견해 출력만 재생성
python -X utf8 .\living_ib.py build --as-of 2026-09-09

# 특정 IB·국가의 근거 묶음 출력
python -X utf8 .\living_ib.py context --house GS --country US --as-of 2026-09-09

# 현재 저장된 견해의 원문 인용·하우스·이력·파일 검증
python -X utf8 .\living_ib.py verify
```

`refresh`는 새 PDF를 읽어 검색 대상으로 만들고 대기 목록을 갱신합니다. **새 PDF의 의미를 자동 추론하지 않습니다.** 원문을 검토한 AI가 새 견해 입력을 작성한 뒤 아래 명령을 실행해야 현재 견해가 바뀝니다. 최신 미검토 원본이 있어도 기존 견해를 확인한 최신 견해로 남기며, 그 출처 날짜를 표시합니다.

`build`의 기본 기준일은 실행하는 PC의 오늘입니다. 과거 날짜를 지정하면 그 날짜까지의 견해만 선택합니다. 최신 결과와 과거 결과를 나란히 보려면 별도 출력 폴더를 지정하세요.

```powershell
python -X utf8 .\living_ib.py --output .\output\living_ib_20260831 build --as-of 2026-08-31
```

## 새 IB 견해 추가

`initial_views_20260909.json`의 구조로 새 견해를 만듭니다. 원문에서 실제로 확인한 한국어 요약·영문 근거·문서 ID·PDF 페이지·전제를 기록합니다. 같은 문서의 새 쟁점은 새 `track`으로, 같은 쟁점의 후속 보고서는 새 `view_id`로 추가합니다. 지원 쟁점은 `living_ib.py`의 `TRACKS`에 있습니다.

```powershell
python -X utf8 .\living_ib.py import-views .\new_views.json
python -X utf8 .\living_ib.py import-forecasts .\new_forecasts.json
python -X utf8 .\living_ib.py build
python -X utf8 .\living_ib.py verify
```

- 입력 묶음은 `schema_version: 1`, `as_of: YYYY-MM-DD`, `views: [...]`를 포함합니다.
- 동일 ID·동일 내용은 건너뜁니다. 동일 ID의 내용 변경은 오류입니다. 일부 인용이 틀리면 입력 묶음 전체를 취소합니다.
- 이전 원본과 직접 비교했다면 `prior_view_id`를 연결하고 `change`를 `maintained` 또는 `revised`로 적습니다. 다른 국가·쟁점·IB를 이전 견해로 연결할 수 없습니다.
- `uncompared`는 이전 원본과 미대조입니다. 새 보고서 자체가 과거 변경을 언급한 경우에도 직접 대조 이력과 구별합니다.
- 인용은 해당 IB 원본의 해당 페이지와 일치해야 합니다. 공백·독립된 문단 기호는 정규화하지만 숫자나 단어 차이는 허용하지 않습니다. PDF 줄바꿈으로 단어가 하이픈 다음에서 나뉘었다면 원문의 줄바꿈을 보존하세요.
- `effective_date`는 모든 근거 원본의 발행일보다 이르면 안 됩니다. 표지일이 수집 메타데이터보다 늦으면 늦은 날짜를 쓰고 이유를 제한 사항에 적습니다.
- 기준일이 같은 두 견해에 선후 연결이 없으면 복수 견해로 표시합니다. 자동으로 하나를 고르지 않습니다.
- 가져오는 견해는 항상 `review_status: draft`, `origin: assistant_review_of_local_reports`입니다. 프로그램이 사용자의 승인을 대신 기록하지 않습니다.
- 글자 단위 근거 검증은 **한국어 요약이 근거 전체를 정확히 해석했다는 보증은 아닙니다.** 의미·시나리오 구분은 원문 검토와 사용자 검토가 필요합니다.

수치 전망은 정성적 견해와 분리해 저장합니다. `indicator`, `reference_period`, `unit`, `value`, `scenario`를 모두 기록해야 하며, 같은 지표명이라도 전월비와 전년비는 별도 전망입니다. 후속 보고서가 같은 대상 기간의 전망을 바꾸면 새 `forecast_id`를 만들고 `prior_forecast_id`로 연결합니다. 지표 발표 준비 파일에는 발표일 전에 확인된 같은 지표의 전망만 자동으로 포함됩니다.

## 지표 발표에 연결

`event_template.json`을 복사해 실제 발표값과 출처를 채웁니다. 이 양식은 미완성 상태라 그대로 실행하면 오류를 내도록 되어 있습니다. 컨센서스 또는 수정치가 없으면 `null`로 남깁니다. 전망 숫자를 실제 발표값으로 넣지 마세요.

```powershell
python -X utf8 .\living_ib.py prepare-event .\my_event.json
```

결과는 `output/living_ib/events/<event_id>/PREPARE.md`와 `context.json`입니다. 일치하는 지표를 감시하는 각 IB의 기존 견해·전제·원문·검토 질문과 사실 비교값을 모읍니다. 이 묶음을 이 앱에서 읽고 AI 해석 초안을 작성할 수 있습니다. 해당 IB의 새 보고서가 없으면 “IB가 전망을 바꿨다”라고 기록하지 않습니다. 기존 IB 상태 DB의 견해는 변경되지 않습니다.

- 지표 ID 목록: `output/living_ib/indicators.json`.
- `pct_mom`은 전월비 %, `pct_yoy`는 전년비 %, `pct_qoq`는 전분기비 %, `pct_qoq_annualized`는 전분기비 연율, `pct_level`은 금리·실업률 등의 % 수준입니다. 0.2%를 `0.2`로 입력합니다.
- 고용 증감은 `thousand_persons` 또는 `persons`, PMI는 `index`, 엔/달러는 `jpy_per_usd`처럼 동일 비교값에 같은 단위를 사용합니다. 단위 간 자동 변환은 하지 않습니다.
- 실제값·컨센서스·종전·수정 종전은 같은 지표 정의와 대상 기간 기준이어야 합니다. 컨센서스 제공처는 `source_label`에 함께 기록합니다.
- `released_at`에는 발표 지역 기준 시각과 UTC offset을 넣습니다. 서머타임 여부를 확인하세요.
- 수정 발표는 새 `event_id`를 씁니다. 기존 이벤트 값을 덮어쓰지 않습니다.
- 발표 당일·이후의 자료는 제외합니다. 출처 날짜만으로 거르는 보수적 방식입니다. 과거 원본의 정확한 배포 시각이나 사후 교체된 PDF까지 복원한 시점별 백테스트 자료는 아닙니다.
- `prepare-event`는 지표 출처를 웹에서 자동 검증하지 않습니다. 실제값 검증은 입력을 준비할 때 수행합니다.

## 점검과 현재 남은 작업

```powershell
python -X utf8 -m unittest test_living_ib.py
python -X utf8 .\living_ib.py verify
python -X utf8 .\verify_context.py
```

현재 반복 실행은 수동 명령 방식입니다. 로컬 ecocal 파일의 WECO 숫자 연결과 저장된 지표 요약·거시 뷰의 대시보드 재생성은 구현되어 있습니다. 실시간 지표/WECO 수신, 새 자료의 자동 AI 해석, 이 로컬 작업의 예약 실행, 국가 판단 승인 화면은 아직 연결하지 않았습니다. 지표 해석은 지표 직접 검색부터 시작하고, 검토 대기 자료에서 **과거 전환점과 현재 근거 공백**을 채우는 순서로 확장합니다.
