# 유로존·글로벌 로테이션 대시보드

## 운영 파일

- `Market_Rotation_Dashboard_17_Indices.html`: 최종 HTML
- `market_rotation_dashboard.incremental.fragment.html`: 다른 HTML에 삽입 가능한 대시보드 본문
- `build_market_rotation_dashboard.py`: 집계 및 HTML 생성 코드
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

단순 주가 평균이 아니다. 각 비교기간 시작일의 시가총액 비중으로 종목 가격수익률을 가중하며 배당은 포함하지 않는다. 1D는 직전 평일 관측치, 5D는 5개 전 평일 관측치를 사용한다. 1M·3M·6M은 각각 28일·91일·182일 전 또는 그 이전의 가장 가까운 관측치를 사용한다.

### 유의사항

STOXX Europe 600은 원자료 통화가 혼합되어 있어 시가총액 및 이익 비중은 근사치다. 정확한 공식 지수 EPS가 필요하면 지수 제공기관의 집계 EPS 또는 동일 통화로 변환한 종목 이익과 공식 유동주식 수를 사용해야 한다.

## 갱신

전체 원자료와 산출물을 함께 갱신하려면 상위 BQL 폴더의 갱신 스크립트를 사용한다. Master를 바꾸지 않고 이 HTML만 다시 만들려면 다음을 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\유로존_dashboard'
.\update_dashboard.ps1
```

생성 코드는 같은 폴더의 템플릿을 읽어 최종 HTML과 삽입용 fragment를 함께 갱신한다.
