# PCA 파이프라인 사용법 (다국가 버전)

최종 수정: 2026-08-04 · 대상 국가: AU(호주) CA(캐나다) DE(독일) JP(일본) UK(영국) US(미국)

## 전체 구조

```
[0] tickerlist_confirmed.xlsx 편집 (국가별 시트)              ← 수동. 여기가 유일한 원본
      ↓ python haver\haver-api_PCA\build_tickers_from_confirmed.py
    tickers.xlsx (Ticker / Category / Country)               ← 자동 생성. 직접 고치지 말 것
[1] haver\haver-api_PCA\fetch_haver_to_excel.py             ← 수동/별도 실행 (08:30 bat에 없음!)
      → Meta data_Raw data.xlsx  Wide/Metadata 시트 갱신 (전처리 시트는 건드리지 않음)
      ↓ python haver\haver-api_PCA\fill_preprocess_rules.py  ← 전처리 시트 누락행 채우기
[2] PCA\pca_gdp.py  (run_dashboard.bat = 이거 + HTML 열기)   ← 매일 08:30 bat이 자동 실행
      → pca_result.xlsx + pca_dashboard.html (국가 드롭다운 포함)
[3] macro_hub\scripts\build_pca_json.py                      ← 매일 08:30 bat이 자동 실행
      → public/data/pca.json → git push → Vercel 반영
```

- 계산: 국가별 → 카테고리별 Time-Varying PCA(EWM 상관행렬) → 카테고리 지수(EWM z-score)
  → lei 제외 동일가중 평균 = GDP 프록시, lei는 별도 LEI 지수
- 버전 2개: YoY(반감기 24개월) / Momentum 3m3m(반감기 12개월)
- 카테고리: `capex` `consumer` `export` `housing` `labor` `lei` (국가마다 있는 것만)

## tickerlist_confirmed.xlsx 작성 규칙

시트 = 국가코드 소문자(`au` `de` `jp` `uk` `us` `ca`) + 안내용 `읽어줘`.
컬럼 = 카테고리 / 지표명 / Ticker / 시작 / 상태 / 비고.

`build_tickers_from_confirmed.py` 가 아래를 자동 제외하고 **제외 사유를 전부 로그로 출력**한다:

| 조건 | 처리 |
|---|---|
| 카테고리가 대문자(CAPEX 등)이고 Ticker 비어 있음 | 섹션 헤더 → 제외 |
| Ticker 가 `-` | 확보 실패 → 제외 |
| Ticker 에 `/` 포함 (한 셀에 코드 2개) | 제외 — 쪼개서 두 줄로 넣을 것 |
| 상태 = `제외` 또는 `보류` | 티커가 적혀 있어도 제외 |

- 상태 `확정[wage]` `확정[price]` 처럼 대괄호 태그가 붙어도 **확정으로 취급**한다 (태그는 메모용).
- 같은 티커를 여러 국가 시트에 넣으면 Country 가 `US,CA` 로 합쳐지고 **양쪽 국가 PCA에 모두 들어간다**
  (예: US ISM을 캐나다 스필오버 지표로 재사용). 카테고리는 첫 번째 값을 쓰고, 국가마다 다르면 WARN.

## 신규 지표(티커) 추가 체크리스트

1. **tickerlist_confirmed.xlsx** 해당 국가 시트에 한 줄 추가 (Ticker = `CODE@DATABASE`)
2. `python build_tickers_from_confirmed.py` → tickers.xlsx 재생성. 로그에서 제외된 게 없는지 확인
3. `python fetch_haver_to_excel.py` (신규 티커는 2005년부터 통으로 수집)
4. `python fill_preprocess_rules.py` → 전처리 시트 누락행 확인 후 `--write`
   - level = 성장률로 변환할 수준 지표 (생산·수출·고용자수 등)
   - diffusion = 그대로 쓰는 서베이·비율 지표 (PMI·실업률 등)
   - ⚠️ 이 줄이 없으면 **에러 없이 WARN만 찍고 조용히 제외됨** — 로그 확인 필수

## 국가 추가/구분 규칙

- 국가 구분은 tickers.xlsx의 **Country 열**이 유일한 기준. fetch가 Metadata 시트에 country로 병기하고,
  pca_gdp.py가 이 값으로 지표를 국가별로 나눠 각각 PCA를 돌린다.
- Country 가 `US,CA` 처럼 콤마로 오면 split 해서 **두 국가 모두**에 포함시킨다.
- Country 열이 아예 없거나 빈 칸이면 → **US로 간주** (구버전 호환 폴백)
- 6개국 외 코드를 넣으면 돌아는 가지만 라벨 없이 코드 그대로 표시됨.
  새 국가를 정식 추가하려면 pca_gdp.py의 `COUNTRIES` 딕셔너리와
  macro_hub\components\Pca.tsx의 `PCA_COUNTRIES` 목록에 라벨을 추가할 것.
- 새 카테고리를 추가하면 pca_gdp.py의 `CAT_LABEL` 과
  macro_hub\components\Pca.tsx의 `CONTRIB_COLORS` 에도 넣을 것 (없으면 회색으로 표시됨).
- 한 국가에서 카테고리가 지수로 성립하려면 **지표 2개 이상 + 충분한 표본** 필요.
  미달 카테고리는 WARN 후 스킵, GDP·LEI가 모두 빈 국가는 대시보드에서 제외됨.
  `build_tickers_from_confirmed.py` 가 2개 미만 카테고리를 미리 경고한다.

## 실행 순서 (요약)

```
1) tickerlist_confirmed.xlsx 편집
2) python haver\haver-api_PCA\build_tickers_from_confirmed.py
3) python haver\haver-api_PCA\fetch_haver_to_excel.py
4) python haver\haver-api_PCA\fill_preprocess_rules.py --write
5) python haver\haver-api_PCA\prune_stale.py --write   ← 뺀 티커 잔여물 정리(선택)
6) PCA\run_dashboard.bat            ← 로컬 확인 (드롭다운으로 국가 전환)
7) Vercel 반영은 다음날 08:30 자동
   (급하면: python macro_hub\scripts\build_pca_json.py 후 git add/commit/push)
```

## ⚠️ 지표 하나가 카테고리 전체 기간을 잘라먹는다

`tv_pca` 는 카테고리 안에서 `dropna()` 를 하므로 **가장 늦게 시작하거나 가장 먼저 끝난 지표 하나**가
그 카테고리 지수 전체의 기간을 결정한다. 그리고 GDP 프록시는 카테고리 지수들의 교집합이라
카테고리 하나가 짧으면 그 나라 전체가 짧아진다. 지표를 추가할 때 반드시 시작·종료일을 확인할 것.

실제로 겪은 사례 (2026-08):

- **S&P Global PMI(AU·CA·JP·UK)가 전부 2021-01 시작** — 구독 내 모든 변형(Flash/SA/NSA/Composite)이
  동일해서 티커 교체로 해결 불가. 넣었더니 AU·UK lei, UK consumer 가 16년치를 잃었다 → 제외함.
  AU 의 구 AiG PMI 계열은 2022-11 단종이라 대체도 안 된다.
- **`intsrvys:n158vro` (JP TDB Economic Trends) 2020-08 단종** — 시작이 아니라 *끝*이 잘려서
  JP LEI 가 최근 6년치를 통째로 잃었다 → 제외함.

점검 방법: 카탈로그 CSV(`haver/haver-api_PCA/db_catalog/*.csv`)에 `startdate` / `enddate`
컬럼이 있으니 티커를 확정하기 전에 여기서 기간을 먼저 볼 것.

카탈로그가 없는 DB 는 덤프해서 만든다:

```
python haver\haver-api_PCA\dump_db_catalog_v2.py    # 여러 DB 를 한 방 호출로 (빠름)
python haver\haver-api_PCA\dump_big_catalog.py UK   # 대형 DB — 청크·중간저장·이어받기
```

`UK` 는 시리즈가 너무 많아 v2 의 한 방 호출이 실패한다(그래서 catalog_UK.csv 만 없었다).
`dump_big_catalog.py` 는 실패하면 청크를 절반씩 줄여가며 받고 청크마다 CSV 에 append 하므로,
중간에 끊겨도 받은 데까지 남고 다시 실행하면 이어받는다.

## 카테고리에 장기 지표가 1개뿐이면 지수가 안 나온다

PCA 는 상관행렬이 필요해서 **그 시점에 지표가 2개 이상**이어야 한다.
1개뿐인 구간은 지수가 만들어지지 않고, 두 번째가 합류한 뒤에도
YoY(12개월) → z-score(12개월) → 상관(12개월)이 겹쳐 약 3년이 더 밀린다.

GDP 프록시는 카테고리 지수들의 **교집합**이라, 나머지가 멀쩡해도 카테고리 하나가 짧으면
그 나라 전체가 끌려간다. 실제로 JP·UK 는 capex 에 장기 지표가 1개뿐이라
GDP 프록시가 2020~2021년부터였고, 자본재 계열을 하나씩 추가해 해소했다.

## 산출물

- `pca_result.xlsx`: 시트명 = `국가_버전_내용` (예: `US_YoY_indices`, `CA_Momentum_gdp_contrib`)
- `pca_dashboard.html`: 우상단 국가 드롭다운, 탭 = 경기지수 / LEI
- `public/data/pca.json`: `{"default":"US","countries":{"US":{"label","label_kr","versions"},...}}`
  - build_pca_json.py는 pca_dashboard.html 안의 `const DATA` 블롭을 추출하는 방식
  - → **pca_gdp.py가 실패하면 에러 없이 옛날 데이터가 그대로 유지됨** (조용한 실패 주의)

## 주의사항

- **엑셀 파일을 열어둔 채 스크립트 실행 금지** — 저장 단계에서 PermissionError로 전체 실패.
  해당 파일: `tickers.xlsx` `Meta data_Raw data.xlsx` `pca_result.xlsx`
  (`~$파일명` 잠금파일이 남아 있으면 열려 있다는 뜻)
- fetch는 증분 수집: last_dates.json 기준 마지막 날짜 −7일부터 다시 받아 수정치(revision)를 흡수.
  전체 재수집이 필요하면 last_dates.json 삭제 후 실행
- fetch는 Wide/Metadata 시트만 교체하고 전처리 시트 등 사용자가 추가한 시트는 보존
- 지표가 전체 기간의 20% 미만이면 자동 제외 (sparse 필터)
- pca_framework.py는 미사용 템플릿 (참조하는 곳 없음, 삭제 가능)
