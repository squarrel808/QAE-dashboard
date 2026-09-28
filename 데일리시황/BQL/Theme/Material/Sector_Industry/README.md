# Sector / Industry HTML 운영 워크플로우

STOXX Europe 600, S&P 500, TOPIX, Hang Seng의 섹터·GICS Industry Group 성과를 빠른 HTML 표로 만든다. Word와 PNG는 만들지 않는다.

## 저장 위치

```text
데일리시황\표_업데이트\runs\<요청시각>\Sector_Industry\sector_<1D|5D>.html
데일리시황\표_업데이트\runs\<요청시각>\Sector_Industry\sector_<1D|5D>.json
데일리시황\표_업데이트\latest.json
Theme\Material\Sector_Industry\Reports\             # 실행 코드
```

원자료와 Master는 계속 `BQL\Rawfile`에 둔다.

## 실행

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황'
python -X utf8 .\update_daily_tables.py --check
python -X utf8 .\update_daily_tables.py --period 1D
# 주간 표가 필요할 때만 --period 5D
```

최신 원본 4개를 `QAE\____Rawdata___`에서 선택하고 BQuant Master 병합 후 표를 만든다. `--check`는 입력 확인만 한다. 성공한 실행은 `latest.json`과 `표_업데이트\index.html`에 반영된다. 예전 `run_sector_report_daily_1d.py`/`run_sector_report_weekly_5d.py`는 새 4개 원본을 동기화하지 않는 수동 경로다.

## 보고서 구성

1. 전체 섹터 성과표: 1D 실행기는 1D, 5D 실행기는 5D
2. 섹터 로테이션 표: 1D·5D·1M·3M·6M과 BM
3. 섹터별 상승 종목 비율: 실행기의 기준 기간
4. Key Findings: 산업그룹 상위 5개·하위 5개와 다섯 기간
5. 전체 산업그룹 성과표: 다섯 기간
6. 섹터별 산업그룹 표 및 수익률 상위·하위 종목 각각 5개

종목 표는 `순위, 종목명, 수익률`만 표시하고 티커 열은 두지 않는다.

종목명 아래에는 `Theme\Material\Sector_Industry\stock_descriptions.xlsx`의 `Business Summary (KR)`를 두 줄로 표시한다. 조회 키는 `Market + Ticker`이며, Excel 문구를 직접 수정하면 다음 HTML 생성부터 그대로 반영된다. `Reports\build_stock_descriptions.py`는 최신 1D·5D 상·하위 종목 합집합을 Excel에 동기화하고, `--web` 옵션 사용 시 공개 Wikipedia 기업 프로필과 출처 URL을 보강한다.

첫 성과표에는 `섹터, N, 기준 기간 시총가중 수익률, 상승 종목 비율, BM 대비`만 둔다. 마지막 행에는 해당 기간의 `BM 전체 (시작일 시총가중)` 수익률과 상승 종목 비율을 넣고 BM 대비는 0.0%로 표시한다. 산업그룹 수, 중앙값, 분산, 판정은 표시하지 않는다. 모든 수익률 표에서 양수는 파란색, 음수는 빨간색이다. 숫자 제목과 값은 같은 오른쪽 정렬선을 쓰고, 모든 셀에 경계선을 표시한다. 표 폭은 내용에 맞춰 압축한다.

`N` 열은 1번 전체 섹터 성과표에만 둔다. 섹터 로테이션, 상승 종목 비율, Key Findings, 전체 및 섹터별 산업그룹 표에서는 제거한다.

네 시장은 별도 폴더로 나누지 않는다. 완성 HTML 상단의 시장 탭으로 전환하며 하나의 파일에서 확인한다.

## 계산 기준과 검증

- 현 구성종목의 현지통화 가격수익률을 각 기간 시작일 일별 시가총액으로 가중한다. 가격·시총이 모두 유효한 종목만 가중치를 재정규화한다.
- BM은 각 시장 전체 구성종목의 같은 방식으로 계산한 합성 가격수익률이며 공식 지수 수익률이 아니다.
- STOXX Europe 600의 시가총액 통화는 혼합돼 있으므로 가중치와 합성 BM은 근사치다.
- 배당과 환율은 포함하지 않는다.
- 1D·5D는 실제 거래 세션 기준, 1M·3M·6M은 달력 기준일 이전의 가장 가까운 실제 거래일 종가를 사용한다.
- 유효 가격 또는 가격·시총 결합 커버리지가 80% 미만이면 생성하지 않는다.
- 이력이 부족한 장기 기간은 다른 기간으로 대체하지 않고 `데이터 부족`으로 표시한다.
- 현재 TOPIX Master는 1D·5D만 계산 가능하며, 1M·3M·6M은 원자료가 누적되면 자동으로 채워진다.

공통 계산·HTML 엔진은 `Reports\build_sector_rotation_html.py`다. 사용자는 이 파일을 직접 실행할 필요가 없다. 구형 `run_sector_rotation.ps1`, Word 생성기와 PNG 생성기는 과거 재현용이며 신규 HTML 운영에는 사용하지 않는다.
