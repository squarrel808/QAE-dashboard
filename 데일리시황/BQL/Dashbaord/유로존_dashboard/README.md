# 유로존·글로벌 로테이션 대시보드

## 운영 파일

- `Market_Rotation_Dashboard_17_Indices.html`: 통합 최종 HTML. 파일명은 기존 링크 호환을 위해 유지하며, 화면에는 현재 사용 가능한 모든 지수(원자료에 있을 경우 TOPIX 포함)가 표시된다.
- `market_rotation_dashboard.incremental.fragment.html`: 다른 HTML에 삽입 가능한 대시보드 본문
- `..\build_regional_dashboards.py`: 유럽·미국·일본 공통 집계 및 HTML 생성 코드. 이 폴더의 동명 Python 파일은 이전 실행 명령을 위한 얇은 연결기다.
- `market_rotation_dashboard.template.html`: 화면 템플릿
- `build_market_rotation_dashboard.py`: 현재 Master로 통합 화면을 재생성하고 로컬 Macro Hub 표시본까지 동기화하는 기본 실행 파일
- `..\test_stock_map.py`, `..\test_dashboard_refresh.py`: 수익률 날짜·결측 처리 및 반복 실행·동기화 검증
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

`Stock Map`은 별도 첫 페이지로, 지수별 종목을 Sector → Industry group → Stock 순서로 묶은 트리맵이다. 초기 지수는 S&P 500, 초기 기간은 1D다. 사각형 면적은 마지막 유효 가격 세션의 종목 시가총액 비중이고, 색상은 선택한 기간의 배당 제외 주가 수익률이다. 종목 선택·마우스·키보드 포커스로 회사명, 티커, 업종, 수익률, 비중과 비교 날짜를 확인한다.

Stock Map의 기간은 1D·1W·1M·MTD·3M·6M·YTD다. 1D/1W는 1/5 유효 세션 전, 1M/3M/6M은 달력상 해당 개월 전 날짜(말일 보정) 또는 그 이전 마지막 유효 세션을 사용한다. MTD/YTD는 전월 말/전년 말 또는 그 이전 마지막 유효 세션 대비다. 기준일은 지수별 마지막 유효 세션으로 표시한다. 비교 기준점 또는 종목의 양 끝 주가가 없으면 N/A(회색)로 남긴다. 현재 시총이 있는 종목의 면적은 수익률 결측과 무관하게 유지하며, 현재 시총이 없는 종목은 제외 수를 표시한다. 원본 주가 수익률은 기존 기여도 집계의 이상치 제한이나 기초 시총 요건을 적용하지 않는다. 이 독립 계산은 `stockMap` 데이터에 저장하며 기존 `Stocks`/집계 차트 계산에는 영향을 주지 않는다. 색상 범례는 기간별로 바뀌고 그 범위를 넘는 값은 끝 색상으로 표시한다.

통합 화면의 `Index Heatmap`은 지수를 전환할 수 있으며 가격수익률은 1D·5D·1M·3M·6M로 전환한다. 아래 상대수익률은 선택한 지수 대비 각 섹터의 수익률을 그 섹터의 첫 유효 관측일에 맞춰 재기준화한다. `Index EPS I`의 지수 수익률 막대도 동일한 기간 선택을 지원한다.

### Stock Map의 달력 기간 선택

기간 토글 옆 **시작일 → 종료일** 달력에서 날짜를 선택하고 **기간 적용**하면, 해당 두 날짜의 원자료 주가 사이 수익률로 색상·종목 표시·상세정보를 다시 계산한다. `1D`·`1W`·`1M`·`MTD`·`3M`·`6M`·`YTD`를 누르면 기본 기간으로 돌아가며 달력에도 해당 비교 날짜가 표시된다.

- 선택 가능한 날짜는 지수별 가용 가격 이력의 첫 유효 세션부터 마지막 유효 세션까지다.
- 주말·휴일은 선택일 또는 그 이전의 마지막 유효 세션으로 해석한다. 요청한 날짜와 실제 가격을 사용한 두 날짜를 화면에 표시한다.
- 수익률은 `종료일 주가 / 시작일 주가 - 1`이다. 시작일 당일의 일간 수익률을 포함하는 기간 누적 방식이 아니며, 같은 거래일끼리 비교하면 유효한 가격이 있는 종목은 0%다.
- 시작일이 종료일보다 늦거나, 날짜가 비어 있거나, 해당 지수 이력 범위 밖이면 오류를 표시하고 잘못된 기간으로 다시 계산하지 않는다.
- 종목의 양 끝 가격 중 하나라도 없거나 0 이하이면 N/A(회색)다. 종목별 결측 주가를 직전 값으로 임의 채우지 않는다.
- **면적은 항상 최신 유효 세션의 시가총액 비중**이다. 과거 종료일을 선택해도 면적 기준은 바뀌지 않으며, 선택 기간은 수익률 색상에 적용된다.

공통 생성기의 `build_stock_map()`은 `stockMap[지수].dates`와 각 종목의 같은 길이 `prices` 배열을 내보낸다. 이력은 Master에서 읽은 유효 세션만 포함하며, 화면은 이 원본 가격으로 선택 기간을 계산한다. 별도 서버 호출이나 임시 캐시 없이 기존 갱신 명령으로 매번 동일 기능이 재생성된다.

`Stocks`에서는 지수와 분류 수준(`Sector`·`Industry group`·`Stock`)을 선택하고 1D·5D·1M·3M·6M 성과를 본다. 표 머리글의 `Sector`, `Industry group`, 수익률·기여도 열을 누르면 해당 기준의 오름차순·내림차순을 전환한다. `Current index mkt-cap share`는 각 섹터·산업그룹·종목의 최신 시가총액을 선택 지수의 유효 전체 시가총액으로 나눈 값이다. `Performance`는 각 그룹 또는 종목 자체의 가격수익률이고, `Index contribution`은 비교기간 시작일의 유효 종목 시가총액 비중에 가격수익률을 곱한 값이다. 기여도 화면에서는 현재 시총 비중과 기간 시작 비중을 함께 표시한다.

```text
Index contribution(i) = Start-date valid-universe market-cap weight(i) × Price return(i)
```

기여도는 원자료의 유효 종목만으로 재구성한 값이며 지수 제공기관의 공식 성과기여도는 아니다. `Industry group`은 GICS Industry Group을 뜻한다. 가격수익률에는 배당이 포함되지 않는다.

`Valuation I`과 `Valuation II`도 지수를 전환한다. STOXX Europe 600에는 별도 최대 15년 섹터 P/E 이력을 사용하고, 통계는 각 섹터의 최근 최대 10년 가용 기간을 기준으로 계산한다. 일부 섹터는 10년보다 짧다. 다른 지수는 Master에 있는 실제 가용 이력만 사용하며, 이를 10년 통계로 표시하지 않는다. 월별 P/E 관측이 6개 미만인 TOPIX 등의 경우 비교 차트를 만들지 않고 이력 부족을 표시한다. Master 기반 과거 섹터 P/E는 현재 구성종목을 재집계한 값이지 과거 시점의 실제 지수 구성 이력이 아니다.

## 반복 실행 방법

Master가 이미 최신이면 아래 명령 하나로 **계산 → Stock Map을 포함한 전체 화면 생성 → 로컬 웹 표시본 동기화**를 실행한다. 어느 작업 폴더에서 실행해도 스크립트 위치를 기준으로 입력과 템플릿을 찾는다.

```powershell
python "C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Dashbaord\유로존_dashboard\build_market_rotation_dashboard.py"
```

이 실행 파일은 공통 생성기 `..\build_regional_dashboards.py --region europe`를 호출한다. `--region europe`는 기존 실행 방식과의 호환용 이름이며 산출물은 글로벌 통합 화면이다. 기본 실행은 `QAE\macro_hub\public\embeds\market_rotation.html`도 갱신한다. 웹앱의 `/market-rotation`이 읽는 파일이다. `/equity`의 GS Pair Baskets 화면과는 별개다.

동기화는 빌드가 성공한 뒤에만 수행한다. 동일한 파일이면 복사하지 않으며, 새 내용은 임시 파일 작성이 끝난 뒤 교체한다. 이 대시보드 명령은 Git commit/push 또는 웹 배포를 실행하지 않는다.

| 상황 | 실행 |
|---|---|
| 현재 Master로 재계산하고 웹 표시본 동기화 | `python build_market_rotation_dashboard.py` |
| HTML만 재생성 | `python build_market_rotation_dashboard.py --no-sync-embed` |
| 새 BQuant 병합 + 통합 화면 + 표시본 동기화 | `./update_dashboard.ps1` 또는 `./update_dashboard.ps1 '새원본.xlsb'` |
| Master + 지역별·AI·Top10까지 전체 BQL 갱신 | `..\..\Rawfile\update_all.ps1` |
| 웹 표시본만 복사 | `QAE\macro_hub\scripts\sync_embeds.py` 실행. 다른 모듈도 복사하며, 원본을 재계산하지 않는다 |

표의 상대 경로 명령은 이 README가 있는 폴더 기준이다. 새 원본의 자동 수거 위치는 `QAE\____Rawdata___\Bquant_*`다. 화면 문구·디자인만 바꿨다면 Master 병합을 다시 실행할 필요가 없다.

기존 QAE 전체 갱신(`전체업데이트.bat` → `run_qae.py`)에도 Market Rotation 재생성 단계가 연결되어 있다. 기존 Master를 읽어 Stock Map을 다시 생성한 뒤 웹 산출물을 동기화한다. 이 단계 자체는 새 BQuant 파일을 병합하지 않으므로 새 원본을 반영하려면 먼저 위 BQL 갱신 명령을 실행한다. `/webonly`는 기존처럼 재계산을 생략한다. 전체 갱신의 Git·배포 동작은 QAE 루트 README의 옵션을 따른다.

### 미리보기와 개발

완성 HTML을 직접 수정하지 않고 `market_rotation_dashboard.template.html`을 수정한 뒤 재생성한다. 종목 계산은 공통 생성기의 `build_stock_map()`과 `stock_map_month_back()`을 수정한다. `stockMap` 데이터와 화면 코드는 매 실행 시 원본 코드에서 만들어지므로 임시 작업 폴더나 과거 캐시 JSON이 필요 없다.

```powershell
# 이 README 폴더에서 실행: 별도 경로에 만들며 운영 표시본은 변경하지 않음
python build_market_rotation_dashboard.py --output-root '.\preview'
# 별도 미리보기 HTML 복사본도 필요한 경우 대상 경로를 명시
python build_market_rotation_dashboard.py --output-root '.\preview' --sync-embed '.\preview\market_rotation.html'
```

`--output-root`, `--asset-root`, `--europe-template`, `--region`을 지정하면 기본 실행 파일의 자동 운영 표시본 동기화가 꺼진다. 명시적인 `--sync-embed HTML_PATH`는 해당 경로를 사용한다. 공통 생성기를 직접 호출할 때도 `--sync-embed HTML_PATH`를 붙여 동기화할 수 있으며 `--region europe|all`만 지원한다.

### 확인 방법

```powershell
python '..\test_stock_map.py'
python '..\test_dashboard_refresh.py'
node '..\test_stock_map_dates.cjs'
```

출력에서 `standalone=`, `region=europe`, `embed_synced=` 또는 `embed_unchanged=`를 확인한다. 화면에는 첫 탭 `Stock Map`, 1D·1W·1M·MTD·3M·6M·YTD, 지수별 기준일과 실제 비교 날짜가 보여야 한다. 동일한 입력·템플릿으로 재실행하면 같은 결과가 나오며, 이력이 부족한 기간은 회색 N/A로 남는다.
