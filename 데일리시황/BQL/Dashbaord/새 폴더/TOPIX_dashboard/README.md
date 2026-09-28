# TOPIX 로테이션 대시보드

## 운영 파일

- `TOPIX_Rotation_Dashboard.html`: 최종 HTML
- `..\build_regional_dashboards.py`: 유럽·미국·일본 공통 집계 및 HTML 생성 코드. 이 폴더의 동명 Python 파일은 이전 실행 명령을 위한 얇은 연결기다.
- `market_rotation_dashboard.template.html`: 유로존 대시보드와 동일한 시각 체계의 화면 템플릿
- `topix_rotation_dashboard.incremental.fragment.html`: 다른 HTML에 삽입 가능한 대시보드 본문

원자료는 BQL 폴더의 `Rawfile\BQuant_Master.xlsx`에서 `TPX500` 데이터를 읽는다. 화면 표기는 `TOPIX`로 통일한다.

TOPIX 원자료 구간은 실행 시점의 `BQuant_Master.xlsx`에서 자동으로 읽으며 Coverage 탭에서 확인할 수 있다. `Price & Attribution II`는 1D·5D·1M·3M·6M 선택지를 유지한다. 1D와 5D는 구성종목 중 최소 2%의 가격이 직전 유효 세션 대비 실제로 바뀐 날짜만 거래 세션으로 인정하며, EPS 변화도 같은 날짜를 사용한다. 충분한 유효 거래일이 쌓이기 전에는 가장 이른 가용 세션을 사용한다. 1M·3M·6M은 해당 기간의 원자료가 쌓이기 전까지 값이 없는 상태로 표시된다.

## 집계 방법

### EPS와 이익 변화

대시보드의 `EPS change`는 종목별 EPS 변화율의 시가총액 가중평균이 아니다. 다음과 같이 종목별 암묵 주식 수와 총이익을 복원한 뒤 합산한다.

```text
Implied shares(i,t) = Market cap(i,t) / Price(i,t)
Earnings(i,t) = EPS(i,t) × Implied shares(i,t)
Group earnings change = Σ Earnings(i,t1) / Σ Earnings(i,t0) - 1
```

양(+)의 EPS·가격·시가총액이 두 시점에 모두 있는 종목만 포함하고, 종목별 이익 변화율은 데이터 이상치 영향을 줄이기 위해 ±100%로 제한한다. EPS breadth는 집계 이익이 아니라 종목별 주당 EPS의 상승·하락 방향으로 계산한다. 섹터·산업의 지수 EPS 기여도는 현재 시가총액 비중이 아니라 비교기간 시작일의 이익 비중을 사용한다.

### P/E

```text
Group P/E = Σ Market cap(i) / Σ [Market cap(i) / P/E(i)]
```

총시총을 총이익으로 나눈 방식이며, 1배 미만의 P/E는 데이터 이상치로 보고 제외한다.

### 가격수익률

```text
Group price return = Σ [Start-date market-cap weight(i) × Price return(i)]
```

단순 주가 평균이 아니라 비교기간 시작일의 시가총액 가중수익률이다. 배당은 포함하지 않는다.

가격 기여도 차트의 `Residual P/E contribution`은 별도로 관측한 P/E 변화가 아니라, 총 가격수익률에서 집계 이익 변화를 제거해 역산한 잔여 멀티플 변화다. EPS×P/E 교차항은 양쪽에 절반씩 배분해 두 기여도의 합이 가격수익률과 일치하도록 한다.

## 갱신

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Dashbaord\TOPIX_dashboard'
.\update_dashboard.ps1
```

공통 생성 코드는 같은 폴더의 템플릿을 읽어 최종 HTML과 삽입용 fragment를 함께 갱신한다. 원자료 기간이 늘어나면 1M·3M·6M도 동일한 산식으로 자동 계산된다. 세 지역만 다시 만들려면 BQL 폴더에서 `python Dashbaord\build_regional_dashboards.py --region all`을 실행한다. 일본 화면만 필요하면 `--region japan`을 사용한다.
