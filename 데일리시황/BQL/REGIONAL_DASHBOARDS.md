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
| 유럽·글로벌 | `Dashbaord\유로존_dashboard\Market_Rotation_Dashboard_17_Indices.html` | Stock Map 첫 화면: S&P 500 / 기존 분석: STOXX Europe 600 |
| 미국 | `Dashbaord\US_dashboard\US_Rotation_Dashboard.html` | S&P 500 |
| 일본 | `Dashbaord\TOPIX_dashboard\TOPIX_Rotation_Dashboard.html` | TOPIX / TPX500 원자료 |

유럽·글로벌 통합 화면에는 Industry와 별개인 `Stock Map` 첫 페이지가 있다. 공통 계산 코드와 화면 템플릿에 포함되어 매번 Master의 종목별 가격·시가총액으로 다시 생성된다. 기간은 1D·1W·1M·MTD·3M·6M·YTD이며 1Y 이상 연간 성과 항목은 없다. 미국은 SPX·NDX·INDU를 선택할 수 있는 전용 화면이다. 일본은 원자료가 2026-09-02부터라 필요한 이력이 부족한 기간은 표시하지 않는다. 미국에도 장기 밸류에이션 보조 파일이 없으므로 실제 Master 이력만 사용한다.

## 반복 갱신과 웹용 HTML 동기화

Master가 최신이면 아래 명령 하나로 통합 화면과 로컬 웹용 `macro_hub/public/embeds/market_rotation.html`을 함께 갱신한다. BQL 폴더 기준 명령이다.

```powershell
python Dashbaord\유로존_dashboard\build_market_rotation_dashboard.py
```

유럽 실행 파일은 공통 생성기를 호출하며 정량 계산을 복제하지 않는다. 기본 운영 경로로 실행할 때만 웹용 HTML을 자동 동기화한다. HTML만 생성하려면 `--no-sync-embed`를 붙인다. `--asset-root`, `--output-root`, `--region`을 명시한 별도 대상 실행에서는 자동 동기화를 끈다. 이 경우에도 `--sync-embed PATH`로 원하는 동기화 대상을 명시할 수 있다.

공통 생성기를 직접 실행하면 기본적으로 HTML만 생성한다. 로컬 웹용 파일까지 갱신하려면 경로를 명시한다.

```powershell
python Dashbaord\build_regional_dashboards.py --region europe --sync-embed ..\..\macro_hub\public\embeds\market_rotation.html
python Dashbaord\build_regional_dashboards.py --region all --sync-embed ..\..\macro_hub\public\embeds\market_rotation.html
```

`--sync-embed`는 `europe` 또는 `all`에서만 사용할 수 있다. 요청한 대시보드가 모두 성공적으로 생성된 뒤 통합 Market Rotation HTML 하나를 복사하며, 내용이 같으면 다시 쓰지 않는다. 다른 모듈의 임베드는 갱신하지 않는다.

`Rawfile\update_all.ps1`은 Master 병합 → 공통 코드로 지역별 HTML 생성 → 통합 화면의 로컬 웹용 HTML 동기화 → AI·Top10 갱신 순서로 실행한다. 유럽 폴더의 `update_dashboard.ps1`도 Master 병합 후 통합 화면 생성과 로컬 웹용 HTML 동기화를 수행한다.

QAE 전체 갱신의 `run_qae.py`는 `AfterHTML_master.py` 다음에 유럽 실행 파일을 호출해 기존 Master에서 통합 화면을 다시 만든다. 새 BQuant 파일의 Master 병합은 별도이며, `/webonly`와 `/nightly`는 이 생성 단계를 생략한다. 대시보드 생성기·두 PowerShell 갱신 파일은 Git push나 웹 배포를 실행하지 않는다. 전체 QAE 실행의 전송 동작은 기존 옵션을 따른다.

Stock Map의 시가총액 비중, 수익률 기준일, 결측 처리 및 자세한 실행 방법은 [통합 대시보드 README](Dashbaord/유로존_dashboard/README.md)를 참고한다.

집계 원칙: 가격수익률은 기간 시작일 시가총액가중, EPS 변화는 종목별 `EPS × implied shares`의 합산 변화, P/E는 총시총/총예상이익이다. 배당은 제외한다. 유럽 STOXX 600 시총 통화 혼합에 따른 비중 근사는 해당 화면 주석을 유지한다.
