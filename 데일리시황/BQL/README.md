> **2026-09-11 데일리 작업 기준 변경**
> 원본 4개를 넣은 후 `QAE\데일리시황\데일리_표_업데이트.cmd`를 실행합니다.
> AI 밸류체인·섹터는 표와 숫자만 갱신하고, WECO는 실제값과 검토된 기존 IB 근거를 연결합니다.
> 새 AI 해석은 별도 요청 시 작성합니다. 아래 보고서 실행 예시는 과거 수동 경로입니다.
> 결과: `QAE\데일리시황\표_업데이트\index.html` · 상세 규칙: `데일리시황\데일리_작업규칙.md`

# BQL 작업 폴더

현재 운영 구조는 세 부분이다.

- `Rawfile`: 새 일별 입력과 단일 통합 Master
- `Dashbaord\유로존_dashboard`, `Dashbaord\US_dashboard`, `Dashbaord\TOPIX_dashboard`: 지역별 주식 로테이션 HTML
- `Dashbaord\build_regional_dashboards.py`: 세 대시보드를 한 번에 생성하는 공통 계산 코드
- `Theme`: AI, Top10/Down10, 유럽·미국·일본 섹터/산업 HTML 산출물

새 BQuant 자료로 대시보드를 갱신할 때는 `Rawfile\update_all.ps1`을 실행한다. Master 병합과 지역별 HTML 생성 후 통합 화면의 로컬 웹용 `macro_hub/public/embeds/market_rotation.html`도 동기화한다. 자세한 방법은 [Rawfile README](Rawfile/README.md)를 참고한다.

Master를 바꾸지 않고 지역별 대시보드만 다시 만들려면 BQL 폴더에서 `python Dashbaord\build_regional_dashboards.py --region all`을 실행한다. `--region europe|us|japan`으로 한 지역만 선택할 수도 있다. 상세 경로와 집계 기준은 `REGIONAL_DASHBOARDS.md`를 참고한다.

통합 화면과 로컬 웹용 파일만 함께 다시 만들 때는 BQL 폴더에서 `python Dashbaord\유로존_dashboard\build_market_rotation_dashboard.py`를 실행한다. 기본 운영 경로에서는 자동 동기화하며 `--no-sync-embed`를 붙이면 HTML만 생성한다. 공통 생성기를 직접 사용할 때의 `--sync-embed PATH` 및 검증용 경로 설정은 [공통 생성 설명서](REGIONAL_DASHBOARDS.md)에 정리되어 있다. 이 명령들은 Git push나 웹 배포를 실행하지 않는다.

통합 화면의 첫 페이지 `Stock Map`은 Industry와 별개이며, 종목별 시가총액 면적과 주가 수익률 색상을 매번 원자료에서 다시 계산한다. 기간은 1D·1W·1M·MTD·3M·6M·YTD다. 계산 기준과 화면 설명은 [통합 대시보드 README](Dashbaord/유로존_dashboard/README.md)를 참고한다.

## 섹터·산업 HTML 보고서

VS Code에서 아래 Python 파일만 실행한다.

- 데일리 1D: `Theme\Material\Sector_Industry\Reports\run_sector_report_daily_1d.py`
- 주초 5D: `Theme\Material\Sector_Industry\Reports\run_sector_report_weekly_5d.py`

두 실행기는 STOXX Europe 600, S&P 500, TOPIX를 모두 처리한다. 세 시장은 HTML 하나의 상단 탭으로 이동한다. 최종 HTML은 Master의 마지막 실제 거래일을 기준으로 다음 위치에 저장된다.

```text
Theme\output\YYYYMMDD\Sector_Industry\글로벌_섹터_산업_<1D|5D>_보고서_YYYYMMDD.html
```

새 Raw 파일 병합까지 함께 수행하려면 `--update-raw`, 생성 결과를 바로 열려면 `--open`을 사용한다.
