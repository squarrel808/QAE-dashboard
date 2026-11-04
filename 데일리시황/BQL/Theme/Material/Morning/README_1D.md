
> **2026-11-03 사용자 지정 공통 기준:** 5D·1W·주간·주보는 시장별 최신 유효 종가 ÷ 5거래일 전 유효 종가 − 1로 통일한다(6개 종가, 5개 수익률 구간). 휴장·주말·미마감 이월 열은 제외한다. 시장별 실제 시작일·종료일과 원본 SHA256을 표시하고, 6개 종가가 부족하면 5D를 산출하지 않는다. 사용자가 특정 달력 주간을 명시한 경우에만 별도 기간으로 계산하고 5D와 구분한다.
> 공통 상세 지침: `C:/Users/infomax/Documents/python/QAE/데일리시황/BQL/PERIOD_POLICY.md`

# BQL 아침시황 1D 실행

사용자가 최신 거래일 1D를 선택한 경우 사용하는 경로다. 월요일 완료 주간용 `build_morning_bql.py`를 대신 호출하지 않는다.

2026-10-14부터 미국·유럽·일본·항생 섹터·산업그룹 및 AI 밸류체인의 모든 기간 수익률은 **기간 시작일 시가총액 가중평균**으로 통일한다. 섹터 로테이션 표 옆에는 같은 기간의 시작일 시총비중을 반영한 **전체 지수 수익률 기여도(%p)** 표를 표시한다. 산식·유효종목 범위·공식 Index Level BM과의 차이는 [Morning README](README.md)의 최신 기준을 따른다. 상승 종목 비율은 종목 수 기준을 유지한다.

이 일간 경로의 5D 비교열은 최근 5개 실제 거래구간이다. 월요일 완료 주간 보고서의 캘린더 5D와 바꾸어 사용하지 않는다.

1. 최신 BQuant 원본을 `Rawfile/update_master.py <원본> --no-rawdata`로 병합한다.
2. `build_morning_daily.py --qae <QAE> --source <원본> --cutoff YYYY-MM-DD --output <run>/quant`를 실행한다. cutoff는 분석 상한일이며, 실제 관측일은 manifest로 확인한다.
3. `complete_daily_tables.py --qae <QAE> --quant <run>/quant`로 산업그룹 시총비중·순위 및 AI 상하위 표기를 완성한다. 전체 AI 종목표는 유지하고 상위/하위를 중복 없이 표시한다. 섹터 기여도와 기간별 가중 계산은 정량 생성기 값을 그대로 유지한다.
4. 현재 Bloomberg 원문만으로 서술 JSON과 날짜별 종목 해석 파일을 작성한다. 예시는 `runs/20261001_1D`에 있다. 예시 내용을 다음 날 재사용하지 않는다. 숫자·표는 정량 단계 결과가 기준이다.
5. `finalize_morning_daily.py --qae <QAE> --run <run> --content <서술JSON> --observations <종목해석TXT> --source <현재Bloomberg원문>`으로 기존 슬롯에 코멘트를 결합한다. 결합 전후 정량 DOM의 불변성을 확인한다.

현재 1D finalizer는 기존 `runs/20260928_20260925_calendar/finalize_morning_bql.py`의 서술 렌더링/검증 함수만 import한다. 기존 날짜의 main 또는 서술 콘텐츠는 실행하지 않는다. 이관 시 해당 helper와 `build_morning_bql.py`, 유지관리 중인 Sector_Industry/AI 모듈도 보존해야 한다.

완성본은 실제 가격일 기준 `Theme/output/YYYYMMDD`에 저장한다. 입구는 `표_업데이트/index.html`이며 1D 링크만 최신으로 바꾸고 5D·Theme·Consensus·WECO·IB는 이전 상태로 보존한다. 전역 latest.json은 덮어쓰지 않는다. 이번 요청처럼 Theme Rotation이 제외되면 새 테마 페이지를 만들지 않는다.

2026-10-01 실행: 2026-09-29→09-30 1D, 섹터·산업 및 AI 두 보고서. Bloomberg 종목 관측 65개(미국22, 유럽19, 일본9, 홍콩·중국15). 일본 1M 이상은 유효 이력이 짧아 결측을 유지한다. 웹 뉴스·매크로·IB 갱신·Vercel 배포는 수행하지 않는다.
