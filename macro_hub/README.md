# Macro Hub — QAE 통합 대시보드 (Next.js)

기존 `master_dashboard.html`(여러 정적 HTML을 iframe으로 끼워넣던 방식)을 하나의 Next.js 앱으로 다시 만든 것.

탭은 두 종류다.
- **네이티브 React** (Equity / Policy / Consensus / PCA / CAI·MAP / Report) — `public/data/*.json` 을 읽어 Recharts·Canvas 로 직접 그린다. 호버 툴팁이 있다.
- **임베드** (Market Rotation / 경제지표 / 실적 캘린더 / CPI 분포) — 원본 대시보드 HTML 을 `public/embeds/` 로 복사해 그대로 띄운다.

네이티브 탭도 JSON 이 없으면 임베드로 자동 폴백한다.

배포는 **[DEPLOY.md](./DEPLOY.md)**, 매일 돌리는 전체 파이프라인은 저장소 루트의 **[README.md](../README.md)** 참고.

---

## 1. 모듈

### Market Rotation (2026-09-23 추가)

`/market-rotation` 탭은 `데일리시황/BQL/Dashbaord/유로존_dashboard/Market_Rotation_Dashboard_17_Indices.html`을 표시합니다.
첫 페이지 `Stock Map`은 Industry와 별개의 종목 트리맵이며, 면적은 시가총액 비중, 색상은 주가 수익률입니다. 1D·1W·1M·MTD·3M·6M·YTD를 선택할 수 있습니다. 계산 코드와 화면 템플릿에 포함되어 HTML 생성 때마다 다시 만들어집니다.

기간 버튼 옆 시작일·종료일 달력과 **기간 적용**으로 임의 기간의 원자료 주가 수익률도 볼 수 있습니다. 주말·휴일은 직전 유효 거래일을 사용하고 실제 비교 날짜를 표시합니다. 가격이 없으면 회색 N/A이며, 면적은 과거 기간 선택 시에도 최신 시가총액 기준입니다. 가용 이력과 날짜 검증은 지수별로 적용됩니다. 이 기능의 가격 이력도 기존 Master → HTML → embed 갱신에 포함됩니다.

Master가 최신이면 이 `macro_hub` 폴더에서 아래 명령으로 통합 화면과 로컬 웹용 파일을 함께 갱신합니다.

```powershell
python ..\데일리시황\BQL\Dashbaord\유로존_dashboard\build_market_rotation_dashboard.py
```

기본 운영 경로 실행은 생성 성공 후 `public/embeds/market_rotation.html`만 동기화하며, 내용이 같으면 다시 쓰지 않습니다. `--no-sync-embed`는 HTML만 생성합니다. 별도 `--asset-root`, `--output-root`, `--region`을 지정하면 자동 동기화는 생략하며, 필요한 경우 `--sync-embed PATH`로 대상을 직접 지정합니다. 공통 생성기의 동기화 옵션은 `--region europe|all`에서만 지원하며 요청한 대시보드가 모두 성공한 뒤 실행합니다.

QAE 전체 갱신은 `AfterHTML_master.py` 다음에 기존 BQuant Master로 이 화면을 다시 생성합니다. `/webonly`와 `/nightly`는 이 생성 단계를 생략합니다. 새 BQuant 파일의 Master 병합은 BQL의 `Rawfile/update_all.ps1` 등으로 별도 수행합니다. 두 BQL 갱신 파일(`Rawfile/update_all.ps1`, `Dashbaord/유로존_dashboard/update_dashboard.ps1`)도 통합 화면의 로컬 웹용 HTML을 동기화합니다.

기존 `scripts/sync_embeds.py`는 모든 모듈의 원본 HTML을 `public/embeds/`로 복사하며, 원본을 재계산하지 않습니다. 위 대시보드 생성·동기화 명령 자체는 Git push나 배포를 실행하지 않습니다. 배포는 기존 QAE 전송 절차를 따릅니다. 자세한 실행 방법과 계산 기준은 [통합 대시보드 README](../데일리시황/BQL/Dashbaord/유로존_dashboard/README.md)를 참고합니다.

| 탭 | 내용 | 차트 | 데이터 |
|---|---|---|---|
| **Market Rotation** `/market-rotation` | Stock Map · Industry · Valuation · Earnings | 임베드 | `embeds/market_rotation.html` |
| **Equity Factors** `/equity` | GS Pair Baskets 섹터×팩터 히트맵·추이·TOP/BOTTOM | Recharts + 히트맵 | `pairbaskets.json` |
| **Policy Tone** `/policy` | 중앙은행 hawk/dove 막대 + 추세 + 위원 코멘트 | Recharts(ComposedChart) | `policy.json` |
| **Consensus** `/consensus` | 2026·2027 CPI/GDP 브로커 예측 분포 (연도 토글, Ridge plot + Median/IQR) | Canvas 포팅(`lib/consensus-draw.ts`) | `consensus_{cpi,gdp}.json` |
| **PCA** `/pca` | 활동지수 요인 분해 (GDP proxy / LEI) | Recharts(스택 기여도+라인) | `pca.json` |
| **CAI · MAP** `/caimap` | GS Current Activity Indicator & MAP | Recharts(섹터 스택+headline) | `caimap.json` |
| **Report** `/reports` | 리서치 목록 + 하우스뷰 | 목록·필터 | `reports.json`, `houseviews.json` |
| **경제지표** `/econ` | 블룸버그 이코노믹 캘린더 | 임베드 | `embeds/econ.html` |
| **실적 캘린더** `/earnings` | 최신 `실적발표*.txt`의 예상 일정 | 임베드 | `embeds/earnings.html` |
| **CPI 분포** `/cpidist` | Haver CPI 항목별 분포 | 임베드 | `embeds/cpi_dist.html` |
| (홈 하단) | 실시간 주가 데모 | — | `/api/quote` (serverless) |

네이티브 탭 데이터는 `public/data/*.json` 으로 분리되어 있고, `scripts/build_*.py`(및 `report_pipeline/`)가
원본에서 생성합니다. 임베드 탭 HTML 은 `scripts/sync_embeds.py` 가 원본 대시보드에서 복사합니다.

> Consensus에는 **2026/2027 연도 토글**이 있고, 6M median 패널에는 **1M/3M/6M/12M/All 구간 토글**이 있습니다.
> PCA·CAI·MAP·Policy 차트는 **호버 시 값/지표명 툴팁**을 제공합니다.

---

## 2. 데이터 빌드

| 스크립트 | 출처 | 비고 |
|---|---|---|
| `build_pairbaskets_json.py` | GS Marquee (gs_api/.env, CSV) | `--mock` 지원 |
| `build_policy_json.py` | policytone CSV/JSON | 잘린 JSON 자동 복구 |
| `build_consensus_json.py` | ECFC 엑셀 (`국가26`·`국가27` 시트, 원본 추출 로직 재사용) | `--mock` 지원, median 24M 윈도우 |
| `build_pca_json.py` | PCA/pca_dashboard.html 의 `const DATA` 추출 | |
| `build_caimap_json.py` | gs_api/cai_map_dashboard.html 의 `const D` 추출 | |
| `sync_embeds.py` | 원본 대시보드 HTML → `public/embeds/` | `npm run data` 에는 안 들어 있음. 따로 실행 |

`reports.json` / `houseviews.json` 은 여기가 아니라 저장소 루트의 `report_pipeline/`
(`build_reports_json.py`, `extract_houseviews.py`)가 직접 이 폴더에 씁니다.

```bash
npm run data                    # JSON 5종 (실데이터)
npm run data:mock               # GS/엑셀 없이 샘플 (pairbaskets·consensus만 mock)
python scripts/sync_embeds.py   # 임베드 HTML 동기화
```

> 평소에는 이걸 하나씩 치지 말고 저장소 루트의 `전체업데이트.bat` 을 쓴다.
> 수집 → HTML 생성 → JSON → embeds → git push 까지 한 번에 돈다.

---

## 3. 로컬 실행

```bash
cd macro_hub
npm install
npm run data        # 또는 npm run data:mock
npm run dev         # http://localhost:3000
```

---

## 4. "정적 + 실시간 둘 다 섞기"

- **정적(대부분)**: 미리 구운 JSON을 페이지가 읽음. 데이터 갱신 = `npm run data` 후 git push → Vercel 재배포.
- **실시간(`/api/quote`)**: 방문 시 serverless 함수가 외부 API 호출. 키는 서버(환경변수)에만.

> ibreport는 `output: 'export'`(순수 정적)였지만, 이 허브는 `/api`를 쓰려고 `next.config.ts`에서 그 줄을 뺐습니다.

---

## 5. 폴더 구조

```
macro_hub/
├─ app/                 # layout, page(허브), equity/policy/consensus/pca/caimap/reports
│                       #   + econ/earnings/cpidist(임베드), api/quote
├─ components/          # EquityFactors, PolicyTone, Consensus, Pca, CaiMap, Reports,
│                       #   RawDashboard(임베드·폴백), NavTabs, LiveQuote
├─ lib/                 # types.ts, consensus-draw.ts(캔버스 포팅)
├─ scripts/             # build_*.py (데이터 빌더), sync_embeds.py
├─ public/data/*.json   # 네이티브 탭 데이터
└─ public/embeds/*.html # 임베드 탭 원본 대시보드
```

---

## 6. 보안 메모

- `.env`, `.env.local`은 커밋되지 않습니다. 실제 키는 절대 커밋 금지.
- `ibreport_telegram`의 git remote URL에 GitHub 토큰이 박혀 있습니다(권장 X) — 자격증명 관리자로 분리 권장.

## 실적 달력 갱신 — 2026-10-19 변경

`____Rawdata___/실적발표*.txt` 중 수정시각이 최신인 파일로 `/earnings`를 생성합니다. TXT의 기업명·티커·USD 시가총액·예상 발표일을 사용하며, 원본 날짜를 변환하지 않습니다. 시간·시간대·회계분기는 원본에 없어 표시하지 않습니다. 공식 IR 일정 자동 수집 기능은 없습니다.

QAE 루트에서 아래 순서로 실행합니다.

```powershell
python -X utf8 releasecalendar/build_earnings_calendar.py
python -X utf8 macro_hub/scripts/sync_embeds.py
```

생성이 성공한 뒤에만 동기화·배포합니다. `sync_embeds.py`는 복사만 하므로 단독 실행으로 새 TXT가 반영되지 않습니다. 전체 갱신의 AfterHTML 단계에서도 TXT를 읽습니다. `/webonly`와 `/nightly`는 달력 재생성을 생략하므로 먼저 위 생성기를 실행해야 합니다. 로컬 표 전용 `update_daily_tables.py`도 실적 달력을 갱신하지 않습니다.

화면의 원본 파일명·수정시각·예상 일정 범위를 확인하고 변경된 게시 파일만 커밋·push합니다. 코드 변경이 있으면 관련 코드·안내 문서도 함께 커밋합니다. 배포 후 `/earnings`와 `/embeds/earnings.html`의 내용까지 확인합니다. TXT가 없거나 해석에 실패하면 옛 엑셀로 폴백하지 않습니다. 기존 `기업실적.xlsx`·`marketcap.json`은 보관 자료이며 실행에서 사용하지 않습니다.

입력 형식과 검증 방법: [실적 달력 안내](../releasecalendar/README.md).
