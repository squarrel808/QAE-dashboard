# 유럽·미국·일본 대시보드 — 단일 생성 코드

정량 계산 코드는 `BQL\Dashbaord\build_regional_dashboards.py` 하나다. BQL 폴더의 `Rawfile\BQuant_Master.xlsx`를 한 번 읽고 `Dashbaord` 아래 지역별 템플릿에 데이터를 주입한다. 아래 명령은 BQL 폴더에서 실행한다.

```powershell
python Dashbaord\build_regional_dashboards.py --region all
python Dashbaord\build_regional_dashboards.py --region europe
python Dashbaord\build_regional_dashboards.py --region us
python Dashbaord\build_regional_dashboards.py --region japan
```

`--region all`의 산출물:

| 지역 | 완성 HTML | 기본 벤치마크 |
|---|---|---|
| 유럽·글로벌 | `Dashbaord\유로존_dashboard\Market_Rotation_Dashboard_17_Indices.html` | STOXX Europe 600 |
| 미국 | `Dashbaord\US_dashboard\US_Rotation_Dashboard.html` | S&P 500 |
| 일본 | `Dashbaord\TOPIX_dashboard\TOPIX_Rotation_Dashboard.html` | TOPIX / TPX500 원자료 |

유럽은 기존 17개 지수 화면을 보존한다. 미국은 SPX·NDX·INDU를 선택할 수 있는 전용 화면이다. 일본은 원자료가 2026-09-02부터라 1M·3M·6M 및 장기 밸류에이션은 데이터가 충분해질 때까지 표시하지 않는다. 미국에도 장기 밸류에이션 보조 파일이 없으므로 실제 Master 이력만 사용한다.

`Rawfile\update_all.ps1`은 Master 병합 후 이 공통 코드를 한 번 호출한 다음 AI·Top10을 갱신한다. 기존 유럽·일본 폴더의 `build_market_rotation_dashboard.py`는 이전 명령과의 호환성만 위한 연결기이며 정량 계산을 복제하지 않는다.

집계 원칙: 가격수익률은 기간 시작일 시가총액가중, EPS 변화는 종목별 `EPS × implied shares`의 합산 변화, P/E는 총시총/총예상이익이다. 배당은 제외한다. 유럽 STOXX 600 시총 통화 혼합에 따른 비중 근사는 해당 화면 주석을 유지한다.
