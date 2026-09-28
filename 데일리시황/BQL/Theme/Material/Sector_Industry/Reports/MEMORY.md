# Sector / Industry HTML Report Memory

이 문서는 유럽·미국·일본 섹터/산업 HTML 보고서를 다른 로컬 작업에서도 즉시 이어가기 위한 운영 메모다.

## Entry points

- Daily: `run_sector_report_daily_1d.py`
- Weekly: `run_sector_report_weekly_5d.py`
- Shared engine: `build_sector_rotation_html.py`

세 파일의 운영 위치는 `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Sector_Industry\Reports`다.

사용자는 Daily 또는 Weekly Python 파일만 실행한다. `--market`의 기본값은 `ALL`이며 STOXX600, SP500, TOPIX를 모두 만든다. `--update-raw`는 `Rawfile\update_all.ps1`을 먼저 호출하고, `--open`은 결과 HTML을 연다.

## Output contract

`Theme\output\YYYYMMDD\Sector_Industry\글로벌_섹터_산업_<1D|5D>_보고서_YYYYMMDD.html`

YYYYMMDD는 실행일이 아니라 마지막 실제 시장 데이터 날짜다. 시장별 마지막 날짜가 다르면 결합 실행을 중단한다. STOXX600, SP500, TOPIX는 하나의 HTML에 들어가며 상단 탭으로 전환한다.

## Report contract

- 첫 표와 breadth 및 종목 순위는 runner의 primary 기간을 사용한다. 첫 표 마지막 행에는 BM 전체 수익률과 BM 전체 상승 종목 비율을 표시한다.
- 전체 섹터·산업그룹 표에는 1D, 5D, 1M, 3M, 6M을 함께 표시한다.
- BM은 전체 구성종목 동일가중 가격수익률이다.
- 종목은 섹터별 상승 5개와 하락 5개다.
- HTML은 외부 라이브러리·이미지 없이 self-contained로 생성한다.
- 표는 내용 폭에 맞춰 압축하고 모든 셀에 경계선을 둔다. 숫자 헤더와 값은 오른쪽 정렬한다.
- `N`은 첫 전체 섹터 성과표에만 표시하고 다른 표에서는 제거한다.
- 종목 상·하위 표는 티커 없이 순위, 종목명, 수익률만 표시한다.
- 종목 2줄 설명 마스터는 `Theme\Material\Sector_Industry\stock_descriptions.xlsx`다. `Market + Ticker`로 조회하며 `Business Summary (KR)`가 HTML에 표시된다. `build_stock_descriptions.py --web`은 최신 1D·5D 종목 합집합을 동기화하고 공개 Wikipedia 프로필과 출처를 보강한다.
- Word와 PNG 생성기는 신규 운영에서 사용하지 않는다.

## Current limitation

2026-09-09 기준 Master에서 STOXX600과 SP500은 1D~6M이 모두 계산된다. TOPIX는 1D·5D만 가능하다. 장기 기간은 원자료 누적 후 자동 활성화된다.
