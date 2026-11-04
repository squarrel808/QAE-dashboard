# 국가별 재정 현황

`update.cmd`를 실행하면 Haver에서 읽기 전용으로 조회하고 `index.html`을 갱신한다. Haver Python 패키지와 해당 데이터베이스 이용 권한이 필요하다. PCA 계산 및 배포는 실행하지 않는다.

- 미국·영국·프랑스·독일·캐나다·일본: CANADA DB의 국제비교 자료. 원출처 캐나다 재무부, 기초자료 IMF WEO/Fiscal Monitor. 2026-10-28 조회 시 최신 2024년, 원자료 빈티지 2025년 10월.
- 호주: ANZ DB의 ABS 일반정부 GFS 수입, 순융자/순차입 및 NSA 명목 GDP. 달력연도 4분기 합계의 비율. 최신 흐름은 최근 4분기 합계 비율로 별도 표시.
- 총지출/GDP와 재정수지/GDP는 서로 다른 지표다. 재정수지는 수입−지출이며 음수는 적자다.
- 호주 총지출은 공표 수입−공표 순융자/순차입으로 산출한다. 비용+비금융자산 순취득의 별도 계열과 과거 일부 분기 차이가 있으며, 원인을 확정하지 않은 상태에서 강제로 수정하지 않는다. 차이는 australia_identity_audit.csv에 기록한다.
- 동일 연도 비교는 7개국 모두 값이 있는 연도로 제한한다. 결측 보간, 월별 복제, 전망치 추가 없음. 원출처의 역사적 추정치·잠정치는 포함될 수 있다.
- IMFWEO DB는 현재 Haver 연결에서 databaseAccess 오류가 발생하여 사용하지 않았다. 향후 이용 가능 시 동일 빈티지 국제비교 자료로 교체할 수 있다.

산출물: index.html, annual_fiscal_gdp.csv, australia_trailing_four_quarters.csv, dashboard_data.json. 원자료: values.csv, metadata.json, fetch_log.json.
