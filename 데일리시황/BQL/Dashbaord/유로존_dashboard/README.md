# 유로존·글로벌 로테이션 대시보드

## 운영 파일

- `Market_Rotation_Dashboard_17_Indices.html`: 통합 최종 HTML. 파일명은 기존 링크 호환을 위해 유지하며, 화면에는 현재 사용 가능한 모든 지수(원자료에 있을 경우 TOPIX 포함)가 표시된다.
- `market_rotation_dashboard.incremental.fragment.html`: 다른 HTML에 삽입 가능한 대시보드 본문
- `..\build_regional_dashboards.py`: 유럽·미국·일본 공통 집계 및 HTML 생성 코드. 이 폴더의 동명 Python 파일은 이전 실행 명령을 위한 얇은 연결기다.
- `market_rotation_dashboard.template.html`: 화면 템플릿
- `data/Dashboard_Global Equity_2606 (1).xlsx`: STOXX Europe 600 섹터 장기 밸류에이션 보조 자료

구성종목·가격·시가총액·EPS·P/E·ROE·영업이익률 원자료는 다음 파일을 읽는다.

`C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx`

## 집계 방법

### EPS와 이익 변화

대시보드의 `EPS change`는 종목별 EPS 변화율의 시가총액 가중평균이 아니다. 종목별 암묵 주식 수와 총이익을 먼저 복원한 뒤 합산한다.

```text
Implied shares(i,t) = Market cap(i,t) / Price(i,t)
Earnings(i,t) = EPS(i,t) × Implied shares(i,t)
Group earnings change = Σ Earnings(i,t1) / Σ Earnings(i,t0) - 1
```

구현에서는 종목별 총이익 변화율을 기준일 총이익으로 가중한다. 양(+)의 EPS·가격·시가총액이 두 시점에 모두 있는 종목만 포함하며, 1D·5D·4W·13W·6M 비교에서 종목별 이익 변화율은 데이터 이상치 영향을 줄이기 위해 ±100%로 제한한다. EPS breadth는 집계 이익이 아니라 종목별 주당 EPS의 상승·하락 방향으로 계산한다.

섹터·산업의 지수 EPS 기여도는 현재 시가총액 비중이 아니라 해당 비교기간 시작일의 이익 비중을 사용한다.

### P/E

```text
Group P/E = Σ Market cap(i) / Σ [Market cap(i) / P/E(i)]
```

`Market cap / P/E`가 종목의 예상이익에 해당하므로, 총시총을 총이익으로 나눈 방식이다. 1배 미만의 P/E는 기업행위·추정치 전환 과정에서 발생하는 데이터 이상치로 보고 제외한다.

### 가격수익률

```text
Group price return = Σ [Start-date market-cap weight(i) × Price return(i)]
```

단순 주가 평균이 아니다. 각 비교기간 시작일의 시가총액 비중으로 종목 가격수익률을 가중하며 배당은 포함하지 않는다. 원자료가 주말·휴일·장 마감 전 최신일에 직전 종가를 이월하므로, 1D와 5D는 구성종목 중 최소 2%의 가격이 직전 유효 세션 대비 실제로 바뀐 날짜만 거래 세션으로 인정한다. EPS 변화도 가격수익률과 동일한 유효 세션의 두 날짜를 사용한다. 1M·3M·6M은 각각 28일·91일·182일 전 또는 그 이전의 가장 가까운 관측치를 사용한다.

가격 기여도 차트의 `Residual P/E contribution`은 별도로 관측한 P/E 변화가 아니라, 총 가격수익률에서 집계 이익 변화를 제거해 역산한 잔여 멀티플 변화다. EPS×P/E 교차항은 양쪽에 절반씩 배분해 두 기여도의 합이 가격수익률과 일치하도록 한다.

### 유의사항

STOXX Europe 600은 원자료 통화가 혼합되어 있어 시가총액 및 이익 비중은 근사치다. 정확한 공식 지수 EPS가 필요하면 지수 제공기관의 집계 EPS 또는 동일 통화로 변환한 종목 이익과 공식 유동주식 수를 사용해야 한다.

## 갱신

통합 화면의 `Index Heatmap`은 지수를 전환할 수 있으며 가격수익률은 1D·5D·1M·3M·6M로 전환한다. 아래 상대수익률은 선택한 지수 대비 각 섹터의 수익률을 그 섹터의 첫 유효 관측일에 맞춰 재기준화한다. `Index EPS I`의 지수 수익률 막대도 동일한 기간 선택을 지원한다.

`Stocks`에서는 지수와 분류 수준(`Sector`·`Industry group`·`Stock`)을 선택하고 1D·5D·1M·3M·6M 성과를 본다. 표 머리글의 `Sector`, `Industry group`, 수익률·기여도 열을 누르면 해당 기준의 오름차순·내림차순을 전환한다. `Current index mkt-cap share`는 각 섹터·산업그룹·종목의 최신 시가총액을 선택 지수의 유효 전체 시가총액으로 나눈 값이다. `Performance`는 각 그룹 또는 종목 자체의 가격수익률이고, `Index contribution`은 비교기간 시작일의 유효 종목 시가총액 비중에 가격수익률을 곱한 값이다. 기여도 화면에서는 현재 시총 비중과 기간 시작 비중을 함께 표시한다.

```text
Index contribution(i) = Start-date valid-universe market-cap weight(i) × Price return(i)
```

기여도는 원자료의 유효 종목만으로 재구성한 값이며 지수 제공기관의 공식 성과기여도는 아니다. `Industry group`은 GICS Industry Group을 뜻한다. 가격수익률에는 배당이 포함되지 않는다.

`Valuation I`과 `Valuation II`도 지수를 전환한다. STOXX Europe 600에는 별도 최대 15년 섹터 P/E 이력을 사용하고, 통계는 각 섹터의 최근 최대 10년 가용 기간을 기준으로 계산한다. 일부 섹터는 10년보다 짧다. 다른 지수는 Master에 있는 실제 가용 이력만 사용하며, 이를 10년 통계로 표시하지 않는다. 월별 P/E 관측이 6개 미만인 TOPIX 등의 경우 비교 차트를 만들지 않고 이력 부족을 표시한다. Master 기반 과거 섹터 P/E는 현재 구성종목을 재집계한 값이지 과거 시점의 실제 지수 구성 이력이 아니다.

Master가 이미 최신이고 대시보드 HTML만 다시 만들 때는 이 폴더의 실행 파일을 사용한다.

```powershell
python "C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Dashbaord\유로존_dashboard\build_market_rotation_dashboard.py"
```

이 실행 파일은 공통 생성기 `..\build_regional_dashboards.py --region europe`를 호출한다. `--region europe`는 기존 실행 방식과의 호환용 이름이며 산출물은 글로벌 통합 화면이다.

새 BQuant 원본을 `BQuant_Master.xlsx`에 추가한 뒤 대시보드까지 한 번에 갱신할 때만 `update_dashboard.ps1`을 사용한다. Master가 이미 최신이거나 화면 문구·디자인만 바꾼 경우에는 `update_dashboard.ps1`을 다시 돌릴 필요가 없다.
