# Global Equity Rotation Monitor — 최종 인수인계 문서

> 경로 구조가 2026-09-02에 단순화되었다. 현재 운영 경로와 갱신법은 상위 폴더의 `README.md` 및 `BQL\Rawfile\README.md`를 우선 적용한다. 아래 문서는 화면·방법론 이력 참고용이다.

최종 업데이트: 2026-08-25 (Asia/Seoul)  
목적: 지금까지의 리서치·Bloomberg 데이터 수집·Python 집계·HTML 대시보드 개발 흐름을 한 문서로 정리하여 로컬 환경에서 바로 이어서 작업할 수 있게 한다.

---

## 1. 가장 먼저 볼 최종 결과물

현재 권위 있는 최종 대시보드는 아래 파일이다.

`C:\Users\infomax\Documents\python\BQL\Market_Rotation_Dashboard_17_Indices.html`

- 단독 실행 가능한 로컬 HTML이다.
- Chrome/Edge에서 열면 된다.
- 화면이 이전 버전처럼 보이면 기존 탭을 닫고 파일을 다시 연 뒤 `Ctrl+F5`로 새로고침한다.
- `Earnings Breadth` 탭은 최종본에서 삭제됐다. 예전 스크린샷이나 preview PNG에는 남아 있을 수 있다.

대시보드를 직접 수정할 때 사용하는 권위 파일은 다음 세 개다.

| 역할 | 파일 |
|---|---|
| 데이터 파싱·집계·최종 HTML 생성 | `C:\Users\infomax\Documents\python\BQL\build_market_rotation_dashboard.py` |
| 화면 구조·CSS·D3 차트 코드 | `C:\Users\infomax\Documents\python\BQL\market_rotation_dashboard.template.html` |
| 오프라인 D3 라이브러리 | `C:\Users\infomax\Documents\python\BQL\d3.v7.9.0.min.js` |

2026-08-25 현재 파일 식별값:

| 파일 | 크기 | SHA-256 |
|---|---:|---|
| `Market_Rotation_Dashboard_17_Indices.html` | 1,340,672 bytes | `8D6659AB395C5F9D722C7B5BEB06EC8D83F1F4EF17EE032D6B469F322CDB7416` |
| `build_market_rotation_dashboard.py` | 43,383 bytes | `7062FD720142B491A4BCEA3B394A81231AAEA6A0D8ADBD3C3B5D909D73157EAC` |
| `market_rotation_dashboard.template.html` | 92,610 bytes | `63915448ED32C128C0520D324B3A5BDA311BC656D0FD2F01AFC8BF7C03A756F7` |
| `d3.v7.9.0.min.js` | 279,706 bytes | `F2094BBF6141B359722C4FE454EB6C4B0F0E42CC10CC7AF921FC158FCEB86539` |

위 해시는 이 문서를 작성한 시점의 기준값이다. 코드를 수정하고 재생성하면 당연히 달라진다.

---

## 2. 프로젝트의 출발점과 리서치 질문

사용자는 국민연금의 지수 중심 펀드매니저이며, 15~20분 모닝미팅 발표를 준비했다. 최초 주제 후보는 다음 두 가지였다.

1. 미국 내 AI 집중주에서 비-AI 영역으로의 로테이션
2. 미국에서 유럽으로의 지역 로테이션

이후 분석의 중심은 유럽으로 이동했다. 핵심 질문은 단순히 “유럽이 올랐다”가 아니라 다음과 같이 정리됐다.

- 유럽 강세는 매크로·통화정책·업종·종목 중 무엇이 만들었는가?
- 강세 업종은 앞으로도 지속될 수 있는가?
- STOXX Europe 600, EURO STOXX 50, DAX 같은 지수 단위에서 투자 매력이 있는가?
- 주가 상승이 EPS 개선인지 P/E 리레이팅인지 구분할 수 있는가?
- 유럽의 싼 밸류에이션은 단순한 업종구성 효과인가, 동일 업종 안에서도 실제로 싼가?
- 은행·에너지 이후 리더십이 산업재·자본재·건설자재·반도체 등으로 확산되는가?

초기에는 STOXX 600, EURO STOXX 50, DAX, FTSE 등을 모두 보려 했지만 작업량과 지수구성 차이를 고려해 유럽 핵심은 STOXX 600과 EURO STOXX 50에 두고, 글로벌 비교용으로 전체 17개 지수를 유지하는 구조로 정리했다.

---

## 3. 리서치 논리의 발전

### 3.1 유럽 강세의 PRO 논리

- 미국 AI·대형 기술주 집중에 대한 분산 수요가 유럽으로 이동했다.
- 유럽은 금융·산업재·소재·에너지·방산 등 미국과 다른 업종구성을 제공한다.
- ECB 완화 및 금융여건 개선은 금리민감 업종과 내수 회복에 우호적이다.
- 독일 재정확대, 인프라·국방·전력망·공급망 투자 기대가 자본재와 산업재의 중기 수요를 지지한다.
- 초기 상승은 낮은 기대와 빈 포지션에서 시작됐지만 이후 실제 EPS 개선이 랠리를 일부 정당화했다.
- 은행뿐 아니라 산업재·IT·헬스케어 등으로 실적 개선이 확산되는지가 다음 단계의 핵심이다.

### 3.2 CON 논리

- STOXX 600은 미국보다 싸더라도 자기 역사 대비로는 더 이상 극단적으로 싸지 않을 수 있다.
- 은행·에너지의 실적과 주가 상승은 이미 상당 부분 반영됐을 수 있다.
- 정책 발표가 실제 예산 집행·수주·백로그·EPS 상향으로 연결되는지 확인해야 한다.
- 유럽 전용 펀드로의 자금 유입을 과장하면 안 된다. 당시 검토한 EPFR 계열 자료에서는 Europe ex-UK 전용 펀드가 여전히 순유출인 구간도 있었다.
- 수출·중국 노출, 유로화, 에너지 가격, 정치·재정 집행 지연이 위험요인이다.
- 지수 수준 EPS 개선이 일부 금융·반도체·에너지 대형주의 추정치 변화에 집중될 수 있다.

### 3.3 JPM 스타일의 선택적 업종배분 논리

검토한 보고서에서 다음과 같은 선택적 배분 프레임이 중요했다.

- Overweight: 소재, 산업재, 자본재, 건설자재, 광산, 반도체, 경기소비재
- Neutral: 은행, 자동차, 헬스케어, 유틸리티, 통신, 기술 하드웨어
- Underweight: 에너지, 필수소비재, 보험, 미디어, 소프트웨어

핵심 해석은 “은행과 에너지가 계속 지수를 끌어올린다”가 아니라 다음과 같다.

> 은행·에너지가 만들어 준 첫 실적회복 이후 리더십이 전력망·자본재·건설자재·반도체 장비·현대화 방산으로 이동하는가를 본다.

### 3.4 참고한 주요 보고서

- `C:\Users\infomax\Downloads\Europe Weekly Kickstart_ Data only update.pdf`
- `C:\Users\infomax\Downloads\Europe Weekly Kickstart_ A Stronger Earnings Story.pdf`
- `C:\Users\infomax\Downloads\JPM_Equity_Strategy_Upda_2026-08-17_5387322 (1).pdf`
- `C:\Users\infomax\Downloads\JPM eurozone equity strategy.pdf`
- `C:\Users\infomax\Downloads\독일 재정 관련.pdf`
- `C:\Users\infomax\Downloads\Global_Equity_Presentation_The_Case_for_Continued_Broadening-Global_Equity_Presentation.pdf`
- `C:\Users\infomax\Downloads\Global_Quantitative_Insights_The_Momentum_Sell-off_Style_Rotation_or_Crowded_Unwind-Global_Quantitative_Insights.pdf`
- `C:\Users\infomax\Downloads\Equity_Markets_Positioning_Model_Rebuild_continues_for_Europe_KOSPI_capitulates-Equity_Markets_Positioning_Model.pdf`

작성된 PRO/CON 보고서:

- `C:\Users\infomax\Documents\python\BQL\STOXX600_로테이션_PRO_ERR기여도보강_20260825.docx`
- `C:\Users\infomax\Documents\python\BQL\STOXX600_로테이션_CON_ERR기여도보강_20260825.docx`

---

## 4. Bloomberg Excel 단계에서 Python 집계로 전환한 이유

### 4.1 최초 시도

초기에는 Bloomberg Excel에서 BDP·BDH·BQL을 사용해 지수·섹터·종목 데이터를 한 통합 파일로 만들려고 했다. 필요한 주요 필드는 다음 10개였다.

1. 12MF P/E Blended
2. 12MF EPS Blended
3. FY1 EPS
4. FY2 EPS
5. Price
6. Market Cap (Daily)
7. Current ROE
8. Current Operating Margin
9. 12MF ROE
10. 12MF Operating Margin

### 4.2 Excel/Bloomberg에서 발생한 문제

- BQL 동적배열 수식을 legacy CSE 배열로 저장하면 Excel/Bloomberg가 동일 쿼리를 범위 전체에 복제해 `#VALUE!`, `#SPILL!`, query flooding을 일으켰다.
- `_xll.BQL` 수식을 일반 `<f>`로 저장하면 Excel 복구 과정에서 수식 레코드가 삭제되는 사례가 있었다.
- `@`가 붙은 암시적 교차 연산자가 동적배열 spill을 막았다.
- 긴 BQL 수식, 구성종목 수 변화, 날짜가 늘어날 때의 고정 셀 배치가 매우 불안정했다.
- Sector/Industry 가중평균과 장기 시계열을 Excel 안에서 동시에 구현하면 파일 크기와 계산부하가 커졌다.
- P/E는 단순 시가가중 평균을 하면 안 되며 earnings yield로 집계해야 했다.

### 4.3 최종 전환

Bloomberg에서는 종목별 원천 시계열만 받아오고, Sector·Industry·Index 집계는 Python에서 수행하는 구조로 전환했다.

이 방식의 장점:

- 구성종목 수와 날짜 길이가 바뀌어도 셀 spill 구조에 의존하지 않는다.
- 일별 시가총액으로 매일 가중치를 다시 계산할 수 있다.
- 동일 코드로 Index·Sector·Industry를 일관되게 집계한다.
- HTML은 데이터가 내장된 단독 파일이므로 Bloomberg 없이 열 수 있다.

Bloomberg/BQL 실험의 상세 기록은 기존 `memory.md`와 `SKILL.md`에 남아 있지만, 현재 대시보드 작업의 권위 문서는 이 파일이다.

---

## 5. 원천 데이터와 지수 유니버스

원천 보관 폴더:

`C:\Users\infomax\Documents\python\BQL\Raw_Source_Files`

종목 시계열 원본:

`C:\Users\infomax\Documents\python\BQL\Raw_Source_Files\Constituent_Raw`

| 파일 | 주요 지수 |
|---|---|
| `1.xlsb` | EURO STOXX 50, Dow Jones Industrial Average |
| `4.xlsx` | CAC 40, DAX 40, IBEX 35, AEX |
| `5.xlsx` | Nikkei 225, Hang Seng |
| `spx.xlsb` | S&P 500, NASDAQ 100, S&P/TSX 60 |
| `csi300.xlsb` | CSI 300, STAR 50 |
| `spx2.xlsb` | FTSE 100, Bovespa |
| `cis22.xlsb` | STOXX Europe 600 |
| `cis3.xlsb` | S&P/ASX 200 |

장기 STOXX 600 지수·섹터 P/E 원천:

`C:\Users\infomax\Documents\python\BQL\Raw_Source_Files\Valuation_Revision\Dashboard_Global Equity_2606 (1).xlsx`

최종 가용 지수 17개:

`SX5E, SXXP, DAX, CAC, IBEX, AEX, UKX, SPX, NDX, INDU, SPTSX60, IBOV, NKY, HSI, SHSZ300, STAR50, AS51`

- TPX는 사용자 결정에 따라 제외했다.
- MEXBOL은 최종 원천에 유효 데이터가 없어 화면에 표시하지 않는다.
- 공통 대시보드 기준일은 2026-08-21이다.
- 공통 종목 원천 시계열 창은 대체로 2025-06-01 이후다.
- Valuation I의 STOXX 600 장기 P/E는 별도 원천을 사용해 2011-08-26부터 2026-08-21까지 월말 181개 관측치를 보유한다.

---

## 6. RAW 파일 구조 가정

`build_market_rotation_dashboard.py`는 각 지수 시트를 다음 구조로 읽는다.

- 지수 Bloomberg ticker: 시트 `B4`
- 현재 구성종목 수: `F3`
- 구성종목 목록 시작: 8행
- 구성종목 열:
  - A: ticker
  - B: company name
  - C: GICS sector
  - D: GICS industry group
- 각 지표 블록의 anchor는 G열이며 `필드명 | ...` 형식이다.
- 날짜는 각 블록 header의 H열 이후에 놓인다.

필드명이 아래 prefix와 일치해야 자동 인식된다.

| Excel 필드명 | Python 내부키 |
|---|---|
| `12MF P/E Blended` | `pe` |
| `12MF EPS Blended` | `eps12` |
| `FY1 EPS` | `eps_fy1` |
| `FY2 EPS` | `eps_fy2` |
| `Price` | `price` |
| `Market Cap (Daily)` | `mcap` |
| `Current ROE` | `roe_current` |
| `Current Operating Margin` | `opm_current` |
| `12MF ROE` | `roe_12m` |
| `12MF Operating Margin` | `opm_12m` |

같은 지수가 여러 파일에 있으면 유효 숫자 셀이 더 많은 원천을 선택한다.

---

## 7. 핵심 집계 방법론

### 7.1 일별 시가총액 가중평균

일반 지표는 유효한 종목만 대상으로 다음처럼 집계한다.

\[
\bar{x}_t=\frac{\sum_i MCAP_{i,t}x_{i,t}}{\sum_i MCAP_{i,t}}
\]

ROE·margin 등은 현재 시가총액으로 가중한다. Operating margin은 매출이 0에 가까운 기업에서 수천 %가 나오는 문제를 막기 위해 절대값 200% 초과 관측치를 제외한다.

### 7.2 EPS와 가격 변화

- 1M/4W: 최종일에서 28일 이전의 가장 가까운 관측일
- 3M/13W: 91일 이전
- 6M/26W: 182일 이전
- EPS는 현재 시가총액 가중, 종목별 변화율을 ±100%로 제한한다.
- 가격은 시작시점 시가총액 가중, 종목별 변화율 범위를 -95%~+500%로 제한한다.
- 수익률은 배당을 포함하지 않는 price return이다.

### 7.3 P/E 집계

P/E는 `시가총액 × P/E`로 평균내면 안 된다. Earnings yield를 집계한다.

\[
P/E_{group,t}=\frac{\sum_i MCAP_{i,t}}{\sum_i MCAP_{i,t}/(P/E_{i,t})}
\]

- 1배 미만의 P/E는 데이터 품질 이상치로 제외한다.
- 음수 이익·음수 P/E 종목은 이 방식의 유효집합에서 빠진다.

### 7.4 4W와 13W 비교

Index EPS I의 왼쪽 차트는 기간을 동일하게 맞추기 위해 다음을 비교한다.

- 막대: `13W EPS 변화 × 4/13`
- X 표시: 실제 4W EPS 변화

Momentum은 다음과 같다.

\[
Momentum_{4W}=Actual\ 4W-\frac{4}{13}(13W\ change)
\]

13W 변화 자체를 연율화한 것이 아니라 4주 속도로 선형 환산한 값이다.

### 7.5 Price/EPS/P-E 분해

기본 항등식:

\[
1+R_P=(1+g_{EPS})(1+g_{PE})
\]

\[
g_{PE}=\frac{1+R_P}{1+g_{EPS}}-1
\]

상호작용항을 절반씩 배분한다.

\[
C_{EPS}=g_{EPS}+\frac{1}{2}g_{EPS}g_{PE}
\]

\[
C_{PE}=g_{PE}+\frac{1}{2}g_{EPS}g_{PE}
\]

따라서 `C_EPS + C_PE = R_P`가 된다.

### 7.6 Industry→Sector 연결

원천의 C열 Sector와 D열 Industry Group을 연결한다. GICS상 Industry Group은 통상 하나의 Sector에 속한다. 예외적으로 같은 Industry 이름이 여러 Sector에 나타나면 현재 시가총액 합이 가장 큰 Sector를 부모로 선택한다.

표시 예시:

`Banks — Financials`

---

## 8. 최종 대시보드 탭별 기능

### 8.1 Europe Heatmap

- 선택 지수: STOXX Europe 600 또는 EURO STOXX 50
- 기간: 1M·3M·6M
- 타일 면적: 현재 Sector 시가총액 비중
- 색상: 선택 기간 price return
- 왼쪽 목록: Sector명, 비중, 수익률
- 하단: 2025-07-01 이후 Sector의 STOXX 600 대비 누적 상대수익률
- 상대수익률 미니차트는 각각 독립 Y축, 0% 포함, 최소 10%p 범위를 사용한다.

상대수익률:

\[
Relative=\frac{1+R_{sector}}{1+R_{SXXP}}-1
\]

### 8.2 Index EPS I

- 왼쪽: 13W EPS를 4W basis로 환산한 막대와 실제 4W EPS X 표시
- 오른쪽: 실제 4W EPS에서 13W 추세의 4W 환산값을 뺀 momentum
- 하단: 17개 지수의 1M·3M·6M price return 순위

### 8.3 Index EPS II

두 하위 화면으로 분리했다.

1. `FY1 / FY2 Strength`
   - FY1·FY2 EPS 강도 순위를 좌우 바차트로 표시
   - 1M·3M·6M 토글
   - 선택 기간 변화율 기준 내림차순
   - 누적 시계열의 단순 차가 아니라 `(1+현재 누적변화)/(1+과거 누적변화)-1`로 계산
   - 선택 월수 이전의 가장 가까운 주간 관측치를 기준으로 사용
2. `FY1 / FY2 History`
   - 2026-01-01 이후 FY1·FY2 추정치 변화 누적선

### 8.4 Sector / Industry

- 지수와 Sector/Industry Group을 선택한다.
- 13W EPS를 4W basis로 환산한 값과 실제 4W 변화를 비교한다.
- `EPS contribution` 토글을 켜면 지수 비중을 곱한 기여도로 전환한다.
- 아래 표에서 weight, EPS 변화, momentum, P/E 등을 확인한다.

### 8.5 Price & Attribution I

- 선택 지수의 2025-07-01 이후 누적 EPS/P-E attribution
- Index, 모든 Sector, 모든 Industry Group을 월말 기준으로 표시
- Industry는 Sector별로 묶고 `Banks — Financials` 형식으로 표시
- 시작시점 시가총액 고정 가중치와 종목단 분해를 사용한다.

중요한 현재 구현상 주의:

- 차트의 분홍색 점은 현재 `EPS contribution + P/E contribution`으로 그린다.
- 별도로 계산된 더 넓은 가격 유효집합의 actual price return은 history 배열의 9번째 값(`v[8]`)에 들어 있지만 점에 사용하지 않는다.
- STOXX 600 Energy 최신값은 attribution 합계 +48.97%지만 별도 actual price return은 +50.79%다. 차이 1.82%p는 EPS 유효집합과 가격 유효집합 차이에서 나온다.
- 로컬에서 “실제 가격선”을 우선하려면 `drawContributionHistory()`에서 `price:v[8]`을 사용하고, `price-(EPS+P/E)`를 coverage residual로 별도 표시하는 것이 가장 투명하다.

### 8.6 Price & Attribution II

- 왼쪽: 선택한 Index의 Sector 또는 Industry price return과 EPS change 산점도
- 오른쪽: 선택한 Index의 Sector별 EPS effect와 P/E effect
- 기간: 1M·3M·6M
- 오른쪽 바차트는 실제 total price return 기준 내림차순
- Industry 선택 시 `Industry — Sector` 이름을 사용한다.
- 최근 기간의 aggregate price와 aggregate EPS 변화에 항등식을 적용한 근사분해다.

### 8.7 Valuation I

- STOXX Europe 600 Full Index를 첫 번째 그래프로 표시한다.
- 이후 STOXX 600 Sector 10개를 표시한다.
- 기간 토글: 5Y·10Y·15Y
- 데이터: 별도 `Dashboard_Global Equity_2606 (1).xlsx`의 실제 12MF P/E
- 평균과 ±2 표준편차: 선택한 화면기간과 무관하게 trailing 10Y 기준
- 전체지수 15Y는 2011-08-26~2026-08-21 월말 181개 관측치다.

### 8.8 Valuation II

- 장기 원천에 Industry 데이터가 없으므로 STOXX 600 Sector만 표시한다.
- 최근 10년 P/E 분포, IQR, whisker, 현재 P/E, percentile을 표시한다.

### 8.9 Quality

- Sector 또는 Industry 단위로 12MF ROE, 12MF operating margin, FY2/FY1 EPS growth를 P/E와 비교한다.
- OPM 절대값 200% 초과 종목은 가중평균에서 제외한다.

### 8.10 Coverage

- 지수별 구성종목 수, 데이터 기간, P/E·EPS·Price coverage, 원천 파일을 확인한다.

### 삭제된 기능

`Earnings Breadth` 탭은 정의와 변동성 해석 문제 때문에 최종 UI에서 통째로 삭제했다.

- 과거 구현은 analyst revision event가 아니라 4주 전 EPS level 대비 상승종목 수와 하락종목 수의 차이였다.
- 적은 유효종목과 unchanged 처리 때문에 변동성이 커질 수 있었다.
- Python payload 내부에 legacy 계산 필드가 남아 있을 수 있지만 최종 화면에서는 사용하지 않는다.

---

## 9. Energy 사례 — 1M·3M·6M과 누적을 구분하는 법

두 Price Attribution 화면에서 Energy 방향이 다르게 보였던 이유는 기간과 방법론이 다르기 때문이다.

### 9.1 Price Attribution II의 Energy

기준일 2026-08-21, STOXX Europe 600 Energy:

| 기간 | Price return | Raw EPS change | Implied P/E factor | EPS effect | P/E effect |
|---|---:|---:|---:|---:|---:|
| 1M | +2.06% | +0.65% | +1.40% | +0.65%p | +1.41%p |
| 3M | +3.58% | -3.99% | +7.88% | -4.15%p | +7.72%p |
| 6M | +23.93% | +51.74% | -18.33% | +47.00%p | -23.07%p |

해석:

- 1M: EPS도 소폭 올랐지만 P/E 상승의 기여가 더 컸다.
- 3M: EPS 추정치는 하락했는데 가격은 상승했으므로 최근 상승은 P/E 리레이팅이 설명한다.
- 6M: EPS가 급증했고 P/E는 압축됐다. 중기 랠리는 earnings-driven이다.

3M 계산 예시:

\[
g_{PE}=\frac{1+3.577\%}{1-3.988\%}-1=+7.879\%
\]

상호작용을 절반씩 배분하면 EPS effect -4.145%p, P/E effect +7.722%p이며 합은 가격수익률 +3.577%다.

### 9.2 Price Attribution I의 누적 Energy

2025-07-01~2026-08-21 누적:

- EPS contribution: +54.71%p
- P/E contribution: -5.74%p
- 화면에 표시되는 attribution 합계: +48.97%
- 별도 actual price return 배열값: +50.79%

누적 EPS contribution은 2026-05-31 +57.88%p에서 2026-08-21 +54.71%p로 낮아졌다. 따라서 “전체 랠리는 EPS가 만들었지만 최근 3개월은 EPS가 둔화되고 P/E가 올랐다”는 두 화면의 해석은 서로 일치한다.

---

## 10. 재생성 방법

PowerShell에서:

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\BQL'
python '.\build_market_rotation_dashboard.py'
```

필요 Python 패키지:

```powershell
python -m pip install numpy openpyxl pyxlsb
```

정상 완료 시 대략 다음을 출력한다.

```text
standalone=C:\Users\infomax\Documents\python\BQL\Market_Rotation_Dashboard_17_Indices.html
indices=SX5E,SXXP,DAX,CAC,IBEX,AEX,UKX,SPX,NDX,INDU,SPTSX60,IBOV,NKY,HSI,SHSZ300,STAR50,AS51
missing=MEXBOL
rows=529 boxes=529 histories=529
```

주의:

- 기본 경로가 Python 파일 상단에 절대경로로 박혀 있다. 폴더를 옮기면 `DEFAULT_SOURCES`, `DEFAULT_TEMPLATE`, `DEFAULT_D3`, `DEFAULT_FRAGMENT`, `DEFAULT_STANDALONE`, `DEFAULT_VALUATION_SOURCE`를 수정한다.
- 최종 HTML을 직접 고치지 말고 template 또는 builder를 수정한 뒤 재생성한다.
- standalone 갱신 로직은 기존 HTML 안의 이전 fragment를 찾아 교체한다. 완전히 새 위치에서 시작할 때는 기존 standalone도 함께 복사하는 것이 안전하다.
- Bloomberg 원천 파일의 행·열 구조나 필드 anchor 이름을 바꾸면 parser도 함께 수정해야 한다.

선택 인자를 확인하려면:

```powershell
python '.\build_market_rotation_dashboard.py' --help
```

---

## 11. 로컬에서 수정할 때 자주 건드릴 위치

### 화면·차트 변경

`market_rotation_dashboard.template.html`

- 탭 HTML: 문서 상단 `<nav class="mrd-tabbar">`
- Europe heatmap/relative return: `drawEuropeHeatmap`, `sectorRelativeSeries`, `drawRelativeHistory`, `renderRelativeGrid`
- Index EPS I: `drawBarMarker`, `drawSingleBar`, `drawIndexReturnBar`
- Index EPS II: `estimateStrength`, `drawEstimateStrengthBar`, `renderIndex2Ranking`, `renderEstimateGrid`
- Price Attribution I: `drawContributionHistory`, `renderContributionGrid`, `renderPrice1`
- Price Attribution II: `drawAttribution`, `renderPrice2`
- Valuation I: `drawPEFan`, `renderFanGrid`, `renderValuation1`
- Valuation II: `drawBoxplot`, `renderValuation2`

### 데이터·집계 변경

`build_market_rotation_dashboard.py`

- 원천경로와 지수명: 파일 상단 constants
- raw sheet parser: `parse_raw_rows`
- 가중평균: `safe_weighted_mean`
- 기간변화: `weighted_change`
- P/E 집계: `harmonic_pe`
- 누적 attribution: `pe_fan_history`
- Index/Sector/Industry snapshot: `aggregate_group`
- 전체 지수 집계: `aggregate_index`
- Industry→Sector 연결: `map_industries_to_sectors`
- STOXX 600 장기 valuation: `load_stoxx600_sector_valuation`

---

## 12. 검증 체크리스트

원천을 교체하거나 코드를 수정한 뒤 다음을 확인한다.

1. Python 실행이 오류 없이 끝나는가?
2. 최종 HTML 수정시간이 갱신됐는가?
3. 가용지수 17개가 모두 출력되는가?
4. STOXX 600과 EURO STOXX 50 heatmap에 Sector가 모두 나타나는가?
5. 1M·3M·6M 토글이 데이터와 제목을 함께 바꾸는가?
6. 모든 diverging bar chart에 검은색 0% 선이 보이는가?
7. Price Attribution II는 total price return 내림차순인가?
8. Industry가 `Industry — Sector`로 표시되고 Sector별로 묶이는가?
9. Valuation I 첫 번째가 `STOXX Europe 600 — Full Index`인가?
10. Valuation I의 5Y·10Y·15Y가 각각 약 61·121·181개 월말 관측치를 쓰는가?
11. Energy 1M·3M·6M 값이 이 문서의 표와 대체로 일치하는가?
12. `Earnings Breadth` 탭이 없는가?
13. Price return이 total return으로 잘못 표기되지 않았는가?
14. STOXX 600 Sector weight는 혼합 통화 시총 때문에 근사치임을 주석으로 알리는가?

---

## 13. 알려진 한계와 다음 작업 우선순위

### 우선순위 1 — Price Attribution I의 실제 가격선

현재 점은 EPS+P/E 합계를 사용한다. 실제 price return(`v[8]`)을 점이나 선으로 쓰고 coverage residual을 별도 표시하면 더 정확하고 설명하기 쉽다.

권장 구조:

- 누적 EPS contribution bar
- 누적 P/E contribution bar
- residual bar 또는 회색 영역
- actual price return dot/line

### 우선순위 2 — 가중치와 유효집합 통일

Price Attribution I과 II는 기간뿐 아니라 가중치 시점과 유효종목 집합이 다르다. 화면 제목이나 tooltip에 다음을 명시하면 혼동이 줄어든다.

- `Cumulative since 2025-07 · start-date weights · stock-level`
- `Incremental 1M/3M/6M · current weights · aggregate-level`

### 우선순위 3 — STOXX 600 통화 문제

종목 시총이 현지통화 기준으로 혼재되어 있으면 STOXX 600 Sector weight는 정확한 EUR 환산 시가총액 비중이 아니다. 정확한 비중이 필요하면 종목별 시총을 동일 통화로 변환하거나 Bloomberg 공식 index weight를 받아야 한다.

### 우선순위 4 — 멤버십 point-in-time

현재 원천은 파일에 들어 있는 구성종목 목록을 전체 기간에 사용한다. 엄밀한 과거 백테스트에는 날짜별 point-in-time membership이 필요하다. 현재 대시보드는 현 구성종목의 과거 시계열을 집계한 성격이 강하다.

### 우선순위 5 — Price return과 total return

현재 모든 수익률은 배당 제외 price return이다. 유럽의 고배당 특성을 투자성과로 비교하려면 total return 데이터를 별도로 추가해야 한다.

### 우선순위 6 — Earnings revision event

삭제된 Breadth는 EPS level direction proxy였다. 실제 analyst upgrade/downgrade 또는 ERR을 다시 넣으려면 contributor revision event 원천을 별도로 확보하고 정의를 명확히 해야 한다.

---

## 14. Factor 투자 관련 합의사항

### Value long-short에서 시가가중 평균 P/E만 보면 안 되는 이유

Q1·Q2 종목의 시가가중 평균 P/E가 낮다고 해서 그 포트폴리오가 순수 Value factor라고 말하기 어렵다.

- 대형 저P/E 업종의 영향이 과도하게 커진다.
- P/E는 음수이익 종목을 다루기 어렵다.
- long과 short의 sector·country·beta 차이가 수익을 지배할 수 있다.
- 포트폴리오 수준 P/E는 earnings yield로 집계해야 한다.

일반적인 팩터 구현은 종목별 value score를 만들고 winsorize·표준화한 뒤 sector/country/beta를 중립화하고 quantile long-short를 구성한다.

### Sector-neutral factor

Sector-neutral은 각 Sector 내부에서 종목을 순위화하고, Sector별 long과 short의 순노출을 0에 가깝게 맞추는 방식이다. 목적은 “은행을 많이 사고 기술을 많이 파는 업종베팅”이 아니라 같은 업종 안에서 싼 종목과 비싼 종목의 차이를 추출하는 것이다.

유럽이 Value에 가깝다고 주장하려면 다음을 구분한다.

1. 지수 업종구성이 금융·에너지·소재 등 저평가 업종에 치우쳤는가?
2. 동일 업종 안에서도 유럽 종목이 미국 종목보다 싼가?
3. P/E뿐 아니라 P/B, dividend yield, FCF yield, ROE, growth를 함께 봐도 싼가?

---

## 15. 별도 논의: 중국 모델과 미국 Inference Service Provider

중국 LLM을 쓴다는 것이 중국 서버를 쓴다는 뜻은 아니다.

- 모델 layer: DeepSeek, Qwen 등 중국계 open-weight 모델
- inference provider layer: Groq, Cerebras, Together AI, Fireworks 등
- compute/data-center layer: 미국 또는 서방 데이터센터의 GPU/LPU 등

미국 기업이 Qwen·DeepSeek weight를 미국 ISP에서 돌리면 모델 원산지는 중국이지만 inference와 데이터 처리는 미국 인프라에서 일어난다. 따라서 중국 모델 채택이 곧 중국 클라우드·중국 GPU 매출 증가를 뜻하지 않으며, compute revenue는 미국 인프라 사업자가 가져갈 수 있다.

이 논점은 현재 유럽 대시보드와 직접 연결되지는 않지만 최초의 “AI 밖으로의 로테이션” 논의에서 Model layer와 Inference layer를 분리해야 한다는 중요한 보조 논리였다.

---

## 16. 다음 작업자에게 전달할 한 문장

> 최종 HTML을 직접 편집하지 말고, 이 문서를 먼저 읽은 뒤 `market_rotation_dashboard.template.html`에서 화면을 수정하고 `build_market_rotation_dashboard.py`에서 집계를 수정한 다음 Python builder로 `Market_Rotation_Dashboard_17_Indices.html`을 재생성하라. 특히 Price Attribution I과 II는 기간·가중치·유효집합이 다르므로 같은 개념처럼 비교하지 말고, 실제 가격선과 attribution residual을 분리하라.
