# Bloomberg BQL Europe Research Project Memory

Last updated: 2026-09-02 (Asia/Seoul) — production raw-data structure simplified.

## Current production storage

- Reusable deliverables live under `C:\Users\infomax\Documents\python\BQL`.
- New daily files go to `Rawfile\Daily_Input`.
- The single consolidated production source is `Rawfile\BQuant_Master.xlsx`.
- Run `Rawfile\update_all.ps1` to append new data and rebuild the Europe/global, AI, and Top10/Down10 outputs.
- The old formula workbooks described below are historical notes only; their files were removed from the production folder after the Master was validated.

## 2026-08-18 Excel formula-record fix (empirically verified)

- Bloomberg `_xll.BQL` formulas are stored as single-cell array formulas (`t="array"`, `ref=anchor`).
- Long BQL arguments must not contain an individual Excel quoted string literal longer than 255 characters. The generator now emits long arguments as multiple literals joined with `&`; Bloomberg receives the same reconstructed string.
- `Europe_Index_Sector_Stock_Fundamentals_BQL_v3.xlsx` passed an actual Microsoft Excel COM open test in manual calculation mode: 9 sheets opened without recovery and representative BQL anchors on all 8 data sheets retained `HasArray=True`.
- Comparative Excel open test: v3 PASS, Simple v4 PASS, `Europe_Fundamentals_v5.xlsx` FAIL (`0x800A03EC`).

## 2026-08-18 refresh failure: root cause found (CRITICAL)

The audited workbook failed on Bloomberg refresh. Diagnosis from the user's refreshed copy (`..._Audited_error.xlsx`):

**Root cause (confirmed from file evidence): every BQL formula was written by openpyxl as a legacy CSE array formula (`<f t="array" ref="...">` spanning the whole reserved range). Bloomberg BQL is a dynamic-array function. On open/refresh, Excel/the add-in exploded each CSE range into thousands of independent single-cell copies of the same formula** (e.g. EUROSTOXX50_Sectors BA30:BD3030 became ~12,000 individual `_xll.BQL` cells, each firing the full query). Observed consequences:

1. Ranges filled with `#VALUE!`; the true result spilled only where a cell had free space (e.g. the 21-row sector snapshot spilled from the bottom-right corner cell BD3030).
2. Per-cell copies shifted the row-relative `$A7`-style references (e.g. `$A16` became `$A28` = empty), producing `#N/A Invalid Security: ... Input failed to evaluate: ""`.
3. Query flooding produced `#N/A Invalid Parameter: Function MEMBERS encountered an unexpected error while processing request.` on the Top-10 blocks.
4. Bloomberg then offered to delete faulty functions; the three Stocks sheets lost their BQL formulas entirely.

**Additional evidence-based finding: the spilled sector history result contained no DATE column and only current values — the separate global parameters `"dates=range(...)","per=M","fill=PREV"` appear NOT to have been applied.** (Fact: the spilled output had columns ID/#EPS_NTM/#PE_NTM only. The interpretation that global parameters are unreliable with aliased/derived expressions is inference, not verified fact.)

**Fixes applied in `Europe_Index_Sector_Stock_Fundamentals_BQL_v2.xlsx` (same folder):**

1. All 105 BQL formulas rewritten as plain single-cell formulas (no `t="array"`, no ref range) — the exact form produced by typing BQL in Bloomberg Excel; results spill dynamically into the still-reserved empty ranges.
2. All `$A7`-style row-relative references made fully absolute (`$A$7`), 80 replacements.
3. All 11 history formulas: `dates=range(...)/per=M/fill=PREV` moved inside each data item's parentheses (documented equivalent form, BQLX pp.101/105), global parameter arguments removed.
4. New `BQL_Test` sheet: 9 isolated one-cell tests (T1-T9) ordered from whitepaper-verified syntax to unverified constructs (`grouprank`, `rolling+iterationdates`, `pct_chg`, item names like `free_cash_flow_yield`/`shareholder_yield`/`headline_eps_market`). Refresh this sheet FIRST and record which tests error before trusting the main sheets.

## 2026-08-18 (later): v2 repair failure and the pivot to the user's B22 pattern

1. **v2 (plain `<f>` formulas) failed on open**: Excel's recovery removed the formulas from all 8 data sheets (`recoveryLog: 제거된 레코드 ... 수식`). Empirical rule: openpyxl-generated `_xll.*` calls must be stored as **single-cell array formulas** (`<f t="array" ref="<anchor>">`), which both the original v1 and Excel's own saved files load cleanly; plain `<f>_xll....</f>` triggers repair. (Why Excel-saved plain BDP formulas survive but openpyxl ones don't is unresolved — Excel adds cm/vm cell metadata and calcChain; inference, not verified.)
2. **User's working workbook (`해외 증시 리뷰 version 5.00`) revealed the preferred pattern** ("업종, 종목" sheet, cell B22): ONE BQL array formula returning only the filtered member list — `=BQL("filter(members(['SPX Index'], dates=TODAY()), cur_mkt_cap >= 50000000000)", "name().value")` — then a header row of API field mnemonics (GICS_SECTOR_NAME, CHG_PCT_1D, CHG_PCT_5D, ...) and per-cell `=BDP(ticker, field_header)` formulas stretched across. History via `=BDH(ticker, "PX_LAST", "-1CY", "", "Days=A")`. Notes: `dates=TODAY()` inside the BQL string works in his terminal (contradicts the earlier audit assumption); `cur_mkt_cap` is in raw currency units (50000000000 = $50bn filter on SPX).
3. **`Europe_Index_Sector_Stock_Simple_v4.xlsx` rebuilt in exactly that pattern**: README + Indices (BDP snapshot rows + BDH `-10CY, Per=cm` monthly blocks for SXXP/SX5E/DAX/SPX × PX_LAST/BEST_PE_RATIO) + 2 sector sheets (static sector tickers, BDP grid) + 3 stock sheets (one BQL member list at B7 with editable index C3 / mkt-cap floor F3, then a 14-field BDP grid wrapped in `IF($B8="","",BDP(...))`). All 11,835 `_xll` formulas stored as single-cell arrays. Field mnemonics proven in the user's file: SECURITY_NAME, GICS_SECTOR_NAME, CHG_PCT_1D, CHG_PCT_5D, PX_LAST; the rest (BEST_PE_RATIO, BEST_EPS, PE_RATIO, PX_TO_BOOK_RATIO, EQY_DVD_YLD_IND, RETURN_COM_EQY, COUNTRY_FULL_NAME, CHG_PCT_1M, CHG_PCT_YTD, CUR_MKT_CAP as BDP field) are common but unverified on his terminal — swap via FLDS if any column errors.
4. Going forward: prefer the B22 pattern (BQL only for universe listing; BDP/BDH for data) over complex server-side BQL aggregation. The v1/v3 BQL-everything designs remain in the folder for reference but are NOT the user's preferred style.

**Still unverified (do not treat as working):** `rolling(..., iterationdates=range(..., frq=cm))`, `grouprank()`, `matches(id, ...)`, `pct_chg()`, and several estimate item names do not appear in the BQLX whitepaper at all. If T7 fails, all 40 sector breadth-history blocks need a redesign. The 40 rolling-breadth member queries are also extremely heavy even if syntactically valid.

## User and objective

- User is an institutional/NPS fund manager who primarily invests at the index level.
- Research objective: prepare a 15-20 minute morning-meeting presentation on rotation away from US AI concentration and/or toward Europe.
- Immediate analytical focus: test the attractiveness and durability of European strength at the index, sector, and constituent levels.
- Preferred output: practical Bloomberg-refreshable Excel rather than static prose alone.

## Index universe

| Market | Bloomberg ticker | Main sheet |
|---|---|---|
| STOXX Europe 600 | `SXXP Index` | `STOXX600` |
| EURO STOXX 50 | `SX5E Index` | `EUROSTOXX50` |
| DAX 40 | `DAX Index` | `DAX` |

The STOXX 600 and EURO STOXX universes also have sector comparison sheets. All three indices have constituent stock sheets.

## Current final workbook

Primary deliverable:

`C:\Users\infomax\Documents\python\BQL\Europe_Index_Fundamentals\Europe_Index_Sector_Stock_Fundamentals_BQL_v3.xlsx`

Sheet order:

1. `STOXX600`
2. `STOXX600_Sectors`
3. `STOXX600_Stocks`
4. `EUROSTOXX50`
5. `EUROSTOXX50_Sectors`
6. `EUROSTOXX50_Stocks`
7. `DAX`
8. `DAX_Stocks`
9. `BQL_Audit`

Supporting generated workbooks, kept for rollback:

- `Europe_Index_Fundamentals_Bloomberg.xlsx`: original BDP/BDH/BQL index version.
- `Europe_Index_Fundamentals_with_Sectors_Bloomberg.xlsx`: added sector sheets; Bloomberg-call heavy.
- `Europe_Index_Fundamentals_BQL_Compact.xlsx`: BQL-only compact index/sector version.

## Workbook architecture

### Index sheets

- Latest snapshot and monthly history.
- Fiscal EPS growth, EPS revisions, revision breadth/ERI, sales and EBITDA growth, margin change, P/E, P/B, ROE, yields, leverage, relative P/E, P/E percentile, and Top 10 weight.
- Direct index series use the index ticker.
- Constituent metrics use `members(['Index'])`.

### Sector sheets

- One row per sector subindex in the latest comparison.
- Monthly blended-forward EPS and P/E history.
- Four-week revision breadth/ERI.
- Most sector tickers are batched in one snapshot query and one history query.
- `members()` queries remain sector-specific where exact breadth or Top 10 constituent weight is required.

STOXX Europe 600 sector tickers currently included:

`S600CSP`, `SX3P`, `SX4P`, `SX6P`, `SX7P`, `SX86P`, `SX8P`, `SXAP`, `SXCP`, `SXDP`, `SXEP`, `SXFP`, `SXIP`, `SXKP`, `SXMP`, `SXNP`, `SXOP`, `SXPP`, `SXQP`, `SXRP`, `SXTP` — each with `Index` appended in Bloomberg formulas.

EURO STOXX sector tickers currently included:

`SX3E`, `SX4E`, `SX6E`, `SX7E`, `SX86E`, `SX8E`, `SXAE`, `SXDE`, `SXEE`, `SXFE`, `SXIE`, `SXKE`, `SXME`, `SXNE`, `SXOE`, `SXPE`, `SXQE`, `SXRE`, `SXTE` — each with `Index` appended.

### Stock sheets

- One BQL request per parent index.
- Current members are filtered by minimum market capitalization.
- Default threshold in `D2` is `500`, following the user's example; set it to zero for all members.
- One request returns ticker, name, GICS sector, country, official index weight, market cap, price, EPS, revisions, analyst Up/Down events, valuation, profitability, yields, and leverage.
- Visible Excel formulas calculate contributions.

## Key definitions

- `FY1 EPS Growth = FY1 EPS / FY0 EPS - 1`.
- `FY2 EPS Growth = FY2 EPS / FY1 EPS - 1`.
- `Rev. 1M/3M/6M`: percentage change in consensus EPS over the stated horizon.
- `Analyst Up/Down`: contributor revision-event counts for the specified window.
- `Stock ERI = (Analyst Up - Analyst Down) / (Analyst Up + Analyst Down)`.
- `% Upgrades/% Downgrades` at index/sector level: clearly state whether calculated from member EPS direction or contributor events. In the audited workbook they are event-based measures and a member may appear in both.
- `Expected Margin Delta`: expected forward operating/EBIT margin less latest actual margin, in percentage points.
- `10Y P/E Percentile`: current forward P/E rank within 120 monthly observations.

Do not conflate consensus EPS change with contributor revision-event breadth.

## Contribution framework

Normalize official Bloomberg weights before calculation:

`Normalized Weight = IF(Raw Weight > 1, Raw Weight / 100, Raw Weight)`

Then calculate:

- `1M Revision Contribution = Weight * Rev. 1M`.
- `FY1 Growth Contribution = Weight * FY1 EPS Growth`.
- `Weighted Breadth Contribution = Weight * SIGN(Rev. 1M)`.
- `Earnings Yield = 1 / Forward P/E`, for positive P/E.
- `Earnings Yield Contribution = Weight * Earnings Yield`.
- `Implied Aggregate P/E = 1 / SUM(Earnings Yield Contribution)`.

Reason for the P/E method:

`Index P/E = Total Price / Total Earnings`, so index earnings yield is the price/market-cap-weighted average of constituent earnings yields. A simple weighted average of P/E is mathematically incorrect.

The weight-times-growth contribution is a practical attribution approximation, not necessarily Bloomberg's official aggregate index EPS calculation. Differences can arise from negative earners, float weights, share counts, currency, rebalancing, divisor treatment, and Bloomberg index methodology.

## BQLX whitepaper audit

Source:

`C:\Users\infomax\Downloads\BQLX.pdf`

Relevant pages:

- p.100: `BQL("Universe","Expression",...)` structure and comma-separated tickers.
- p.101: current/historical requests; `dates=range(...)`, `per=M`, and `fill=PREV`.
- p.102: official `members(['SX5E Index'])` example.
- pp.103-106: `BQL.Query`, `let/get/for/with`, and cell/local-variable references.
- pp.107-110: `showdates`, `showheaders`, `showids`, `transpose`, `xlsort`, and `groupbyfields`.
- p.111: `BQL.List()` and `BQL.Date(BToday())`; `BQL.List()` cannot feed ordinary `BQL()`.

Corrections made after the audit:

1. Standardized member universes on `members(['Index'])`.
2. Removed Excel `TODAY()` from quoted BQL strings.
3. Used current membership by default; use `0D` or `BQL.Date(BToday())` when a date expression is genuinely required.
4. Changed ordinary monthly history from global `frq=cm` to separate `dates=range(...)`, `per=M`, `fill=PREV` parameters.
5. Made `showids`, `showdates`, and `showheaders` explicit where the workbook depends on the returned column order.
6. Kept `frq=cm` only inside `iterationdates=range(...)` expressions used by rolling calculations.

## Bloomberg-load optimization

- The first sector workbook had 1,012 Bloomberg array calls.
- The compact BQL design reduced this to 102 calls before stock sheets.
- The final audited workbook has 105 external Bloomberg calls because each of the three stock sheets adds one batch BQL call.
- All external calls in the final workbook are BQL; BDP/BDH calls are zero.
- Structural validation found no overlapping array ranges and no literal `#REF!`, `#DIV/0!`, or `#NAME?` formulas.

## Important operational caveats

- Offline structural validation does not prove a Bloomberg data item is entitled or supported for every security.
- Refresh the final workbook in Bloomberg-enabled Excel.
- Do not recalculate Bloomberg `_xll.BQL` workbooks with LibreOffice; it lacks the Bloomberg add-in and can write `#NAME?` into the file.
- If a data item errors, confirm it through BQLX, FLDS, or Bloomberg Function Builder rather than substituting an API mnemonic such as `BEST_EPS` inside BQL.
- Market-cap units should be confirmed in the Bloomberg output/FLDS before interpreting the `500` filter economically.

## Suggested next work

1. Refresh the audited workbook in Bloomberg Excel and record any entitlement or data-item errors.
2. Confirm whether `SXCP Index` and `S600CSP Index` are both current/non-duplicative sector indices in the user's entitlement.
3. Decide whether the presentation should emphasize STOXX 600 breadth, EURO STOXX 50 concentration, or DAX cyclicality.
4. Use stock-sheet contributions to identify whether European EPS improvement remains after excluding the Top 10 names.
5. Aggregate stock contribution columns by GICS sector and country for presentation-ready tables.
# 2026-09-08 운영 경로 단순화

- 일별 Bloomberg/BQuant 입력: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\Daily_Input`
- 단일 통합 원자료: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx`
- 전체 갱신 명령: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\update_all.ps1`
- 유로존·글로벌 대시보드: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Dashbaord\유로존_dashboard\Market_Rotation_Dashboard_17_Indices.html`
- Theme 완성본: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\output\YYYYMMDD\{AI,Sector_Industry,Top10_Down10}`
- Theme 계산자료: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\{AI,Sector_Industry,Top10_Down10}\YYYYMMDD`
- AI 실행기: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\AI\run_all.ps1`
- 섹터·산업 실행기: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Sector_Industry\run_sector_rotation.ps1`
- Top10/Down10 최신 포인터: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Top10_Down10\latest_outputs.json`
- `Raw_Source_Files`, 루트 구형 Excel, 구형 유럽 수식 통합 폴더는 Master 검증 후 정리했다.
- 새 파일의 이름은 고정하지 않는다. `.xlsb`/`.xlsx` 내부 구조가 유효하면 내용 해시로 중복 검사 후 병합한다.

# 2026-09-10 유럽·미국·일본 섹터/산업 HTML 보고서

## 사용자가 실행할 파일

- 데일리 1D: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Sector_Industry\Reports\run_sector_report_daily_1d.py`
- 주초 5D: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Sector_Industry\Reports\run_sector_report_weekly_5d.py`
- 공통 계산 엔진: 같은 폴더의 `build_sector_rotation_html.py`. 사용자가 직접 실행할 필요는 없다.

VS Code의 `Run Python File`은 기존 Master로 생성한다. 새 Raw 파일을 먼저 병합할 때는 `python <runner.py> --update-raw --open`을 사용한다. PowerShell `.ps1` 래퍼는 호환용으로만 남아 있으며 기본 운영에서는 사용하지 않는다.

## 시장과 입력

단일 Master: `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx`

| 시장 | Master 시트 | 코드 |
|---|---|---|
| 유럽 | `SXXP Raw` | `STOXX600` / `SXXP Index` |
| 미국 | `SPX Raw` | `SP500` / `SPX Index` |
| 일본 | `TPX500 Raw` | `TOPIX` / `TPX500 Index` |

## 출력

최종 HTML과 감사용 JSON은 Master에서 확인된 마지막 실제 거래일로 날짜 폴더를 만든다. 시장별 폴더를 만들지 않고 세 시장을 하나의 HTML 탭으로 묶는다.

`C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\output\YYYYMMDD\Sector_Industry\글로벌_섹터_산업_<1D|5D>_보고서_YYYYMMDD.html`

상단 탭은 STOXX Europe 600, S&P 500, TOPIX 순서다. 2026-09-10 코드 검증 당시 기준일은 2026-09-09이며, 세 시장 1D 또는 5D 전체 생성은 약 18초였다.

## 고정 보고서 사양

1. 첫 섹터 성과표는 실행기 기준 기간만 표시한다. 열은 `섹터, N, 1D/5D 평균, 상승 종목 비율, BM 대비`다. 표 마지막에 `BM 전체 (구성종목 동일가중)` 행을 넣어 해당 기간 BM 수익률과 전체 상승 종목 비율을 보여주며, BM 대비는 0.0%다. 산업그룹 수, 중앙값, 분산, 판정은 삭제했다.
2. 섹터 로테이션은 차트가 아니라 `1D, 5D, 1M, 3M, 6M` 표이며 BM 전체 행을 넣는다.
3. 상승 종목 비율은 데일리 파일에서 1D, 주초 파일에서 5D를 사용한다.
4. Key Findings는 기준 기간 산업그룹 상위 5개와 하위 5개를 다섯 기간 표로 보여준다.
5. 전체 산업그룹과 각 섹터 안의 산업그룹도 다섯 기간 표로 표시한다.
6. 각 섹터 종목 표는 기준 기간 상승 5개와 하락 5개, 총 10개다.
7. 양수는 파란색, 음수는 빨간색이다.
8. 행·열 혼동을 막기 위해 모든 셀에 경계선을 넣고, 숫자 헤더와 값은 오른쪽 정렬한다. 표는 내용 폭에 맞춰 압축하고 최소한의 셀 여백만 둔다.
9. `N`은 1번 전체 섹터 성과표에만 표시한다. 다른 모든 요약·산업그룹 표에서는 표시하지 않는다.
10. 섹터별 상승·하락 종목 표의 티커 열은 제거했다. 화면에는 순위, 종목명, 수익률만 표시한다.
11. 종목명 아래 2줄 설명은 `Theme\Material\Sector_Industry\stock_descriptions.xlsx`에서 `Market + Ticker`로 조회한다. 사용자가 `Business Summary (KR)`를 수정하면 다음 HTML 생성부터 반영된다. 설명 갱신기는 `Reports\build_stock_descriptions.py`다.

## 방법론과 주의사항

- 현 구성종목의 현지통화 Price를 사용하며 섹터·산업·BM 모두 구성종목 단순수익률의 동일가중 평균이다.
- 1D는 두 실제 종가, 5D는 여섯 실제 종가가 필요하다. 주말·휴일·미래 carry 열은 세션으로 세지 않는다.
- 1M·3M·6M은 달력상 목표일 이전의 가장 가까운 유효 거래일을 시작점으로 사용한다.
- 배당과 환율 효과는 제외된다. 현 구성종목을 과거로 적용하므로 생존편향이 있다.
- 극단적인 기업행위 가능 관측치(수익률 -90% 이하 또는 +300% 이상)는 동일가중 집계에서 제외한다.
- 기준 기간 가격 커버리지는 80% 이상이어야 한다.
- 장기 이력이 없으면 `데이터 부족`으로 남기며 짧은 기간을 장기로 재표기하지 않는다.
- 2026-09-09 기준 유럽과 미국은 다섯 기간이 모두 존재한다. TOPIX는 1D·5D만 존재하고 1M·3M·6M은 데이터가 더 쌓여야 한다.
# 2026-09-10 AI·섹터 HTML 최종 실행 구조

- AI 표형 HTML: `Theme\Material\AI\build_ai_value_chain_html.py`
- AI 1D/5D: `run_ai_report_daily_1d.py`, `run_ai_report_weekly_5d.py`
- 섹터+AI 통합 1D/5D: `run_final_daily_1d.py`, `run_final_weekly_5d.py`
- AI 보고서는 기존 12개 S&P 500 AI 밸류체인(Core/Expanded)을 유지한다.
- 표는 전체 밸류체인과 S&P 500 BM, 1D/5D/1M/3M/6M 로테이션, 밸류체인별 종목 성과 및 사업 설명으로 구성한다.
- 최종 HTML은 `Theme\output\YYYYMMDD\AI`와 `Sector_Industry`에 날짜별 저장한다.

## 2026-09-16 · Bloomberg 섹터 원문 해설 보완

- 2026-09-14 최종본 `Theme\output\20260914\Sector_Industry\유럽_미국_일본_섹터_산업_5D_코멘터리_20260914.html`에는 기존 Bloomberg 종목표 전체 번역과 BQL 섹터 카드 요약 외에, 사용자가 제공한 Bloomberg 시황의 **섹터 전체 해설**을 날짜별 독립 섹션으로 추가했다.
- 포함 범위: 9/11 미국 11개 섹터 및 유럽·일본 지수별 해설, 9/14 미국 11개 섹터와 9/14~15 유럽·일본 해설, 기간별 로테이션, 섹터 간·지역 간 비교, 원문 당시 관찰 변수. 기존 BQL 수익률·BM·breadth·종목 순위표는 수정하지 않았다.
- Bloomberg 원문 ETF total return·지수/바스켓 보도치와 BQL 구성종목 가격·시총가중 5D는 산식과 날짜가 다르므로 별도로 표시한다. 원문 작성 시각과 맞지 않는 9/15 아시아 종가, 비표준 Euro Stoxx 50 5D, 표/본문 부호 불일치는 품질 경고로 표시한다.
- `블벅코멘트\DESCRIPTION.md`의 반복 체크리스트도 갱신했다. 이후 Bloomberg 코멘트를 결합할 때 **종목표 전체 번역과 섹터 총평 전체 정리는 별개 필수 작업**이다. 짧은 BQL 섹터 카드가 섹터 원문 해설을 대신하지 않는다.
- 주의: 이 문서 앞부분의 동일가중 표형 1D/5D 자동 생성기 사양과, 이번 2026-09-14 시작일 시총가중 특수 완성본은 서로 다른 파이프라인이다. 기존 동일가중 생성기를 이번 완성본의 base로 덮어쓰지 않는다. 정량 산식을 바꿔야 한다면 해당 정량 생성기부터 수정하고 검증해야 한다.

## 2026-09-17 · 새 4개 원본과 1D 아침시황

- `QAE\____Rawdata___`의 새 BQuant `(6)`, 성장·물가 컨센서스, ecocal 4종을 `update_daily_tables.py --period 1D`로 갱신했다. 마지막 유효 주가일은 2026-09-16이고 1D 가격 비교는 9/15→9/16이다. 결과 입구는 `데일리시황\표_업데이트\index.html`, 검증된 최신 실행은 `runs\20260917_084915_860309`이다.
- 기존 `Reports\build_sector_rotation_html.py`의 동일가중 계산은 2026-09-17에 **각 기간 시작일 일별 시총가중**으로 고쳤다. 가격·시총 블록의 날짜 일치와 둘 다 유효한 종목의 커버리지 80% 이상을 확인한다. STOXX600 혼합통화 시총가중은 근사치, BM은 공식 지수 아닌 구성종목 합성 수익률이다. 이 문서 앞부분의 동일가중 설명은 이전 방식의 기록이며 현재 방식이 아니다. `Sector_Industry\README.md`도 현행화했다.
- 이번 최종 1D HTML 세트는 `Theme\output\20260916\아침시황_1D_세트_20260916.html`이다. 섹터와 AI의 표·숫자는 검증된 실행별 base HTML/JSON이 만들고, `Theme\Material\attach_commentary.py`는 코멘트 JSON의 문장만 결합했다. 새 Bloomberg 시황·팩터 입력이 없어서 이번에는 최신 팩터/테마 페이지를 생성하지 않았고 개별 가격 촉매를 단정하지 않았다.
- S&P 500 AI 12개 밸류체인의 별도 `Σ(Price×Shares)/ΣShares` 방법론은 바꾸지 않았다. 1D 12개 중 7개 상승, 전력·냉각/서버 강세와 소프트웨어/하이퍼스케일러 약세가 관찰됐다. TOPIX 원본은 1M 이상 이력이 부족하므로 장기 값을 만들지 않는다.
