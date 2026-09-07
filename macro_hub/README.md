# Macro Hub — QAE 통합 대시보드 (Next.js)

기존 `master_dashboard.html`(여러 정적 HTML을 iframe으로 끼워넣던 방식)을 하나의 Next.js 앱으로 다시 만든 것.

탭은 두 종류다.
- **네이티브 React** (Equity / Policy / Consensus / PCA / CAI·MAP / Report) — `public/data/*.json` 을 읽어 Recharts·Canvas 로 직접 그린다. 호버 툴팁이 있다.
- **임베드** (경제지표 / 실적 캘린더 / CPI 분포) — 원본 대시보드 HTML 을 `public/embeds/` 로 복사해 그대로 띄운다.

네이티브 탭도 JSON 이 없으면 임베드로 자동 폴백한다.

배포는 **[DEPLOY.md](./DEPLOY.md)**, 매일 돌리는 전체 파이프라인은 저장소 루트의 **[README.md](../README.md)** 참고.

---

## 1. 모듈

| 탭 | 내용 | 차트 | 데이터 |
|---|---|---|---|
| **Equity Factors** `/equity` | GS Pair Baskets 섹터×팩터 히트맵·추이·TOP/BOTTOM | Recharts + 히트맵 | `pairbaskets.json` |
| **Policy Tone** `/policy` | 중앙은행 hawk/dove 막대 + 추세 + 위원 코멘트 | Recharts(ComposedChart) | `policy.json` |
| **Consensus** `/consensus` | CPI/GDP 브로커 예측 분포 (Ridge plot + Median/IQR) | Canvas 포팅(`lib/consensus-draw.ts`) | `consensus_{cpi,gdp}.json` |
| **PCA** `/pca` | 활동지수 요인 분해 (GDP proxy / LEI) | Recharts(스택 기여도+라인) | `pca.json` |
| **CAI · MAP** `/caimap` | GS Current Activity Indicator & MAP | Recharts(섹터 스택+headline) | `caimap.json` |
| **Report** `/reports` | 리서치 목록 + 하우스뷰 | 목록·필터 | `reports.json`, `houseviews.json` |
| **경제지표** `/econ` | 블룸버그 이코노믹 캘린더 | 임베드 | `embeds/econ.html` |
| **실적 캘린더** `/earnings` | 어닝 릴리스 일정 | 임베드 | `embeds/earnings.html` |
| **CPI 분포** `/cpidist` | Haver CPI 항목별 분포 | 임베드 | `embeds/cpi_dist.html` |
| (홈 하단) | 실시간 주가 데모 | — | `/api/quote` (serverless) |

네이티브 탭 데이터는 `public/data/*.json` 으로 분리되어 있고, `scripts/build_*.py`(및 `report_pipeline/`)가
원본에서 생성합니다. 임베드 탭 HTML 은 `scripts/sync_embeds.py` 가 원본 대시보드에서 복사합니다.

> Consensus 6M median 패널에는 **1M/3M/6M/12M/All 구간 토글**이 있습니다.
> PCA·CAI·MAP·Policy 차트는 **호버 시 값/지표명 툴팁**을 제공합니다.

---

## 2. 데이터 빌드

| 스크립트 | 출처 | 비고 |
|---|---|---|
| `build_pairbaskets_json.py` | GS Marquee (gs_api/.env, CSV) | `--mock` 지원 |
| `build_policy_json.py` | policytone CSV/JSON | 잘린 JSON 자동 복구 |
| `build_consensus_json.py` | ECFC 엑셀 (원본 추출 로직 재사용) | `--mock` 지원, median 24M 윈도우 |
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
