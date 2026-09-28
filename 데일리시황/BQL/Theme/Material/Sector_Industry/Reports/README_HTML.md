> **2026-09-11 데일리 작업 기준 변경**
> 원본 4개를 넣은 후 `QAE\데일리시황\데일리_표_업데이트.cmd`를 실행합니다.
> AI 밸류체인·섹터는 표와 숫자만 갱신하고, WECO는 실제값과 검토된 기존 IB 근거를 연결합니다.
> 새 AI 해석은 별도 요청 시 작성합니다. 아래 보고서 실행 예시는 과거 수동 경로입니다.
> 결과: `QAE\데일리시황\표_업데이트\index.html` · 상세 규칙: `데일리시황\데일리_작업규칙.md`

# 섹터·산업 HTML 보고서

Word와 PNG를 만들지 않고 HTML 표를 직접 생성하는 빠른 버전이다.

## 실행 코드 (VS Code에서 Python으로 실행)

- 데일리: `run_sector_report_daily_1d.py`
- 주초/주간: `run_sector_report_weekly_5d.py`

기본 실행은 STOXX Europe 600, S&P 500, TOPIX 세 시장을 모두 처리한다. 세 시장은 별도 파일·폴더가 아니라 완성 HTML 하나의 상단 탭으로 전환한다.

```powershell
python .\run_sector_report_daily_1d.py --update-raw --open
python .\run_sector_report_weekly_5d.py --update-raw --open
```

원자료 업데이트 없이 Master만 다시 읽을 때는 `--update-raw`를 생략한다. 결과를 바로 열려면 `--open`을 붙인다.

## 보고서 구성

1. 전체 섹터 성과표: 실행 코드에 따라 1D 또는 5D
2. 섹터 로테이션 표: 1D, 5D, 1M, 3M, 6M 및 BM 행
3. 섹터별 상승 종목 비율: 실행 코드에 따라 1D 또는 5D
4. Key Findings: 산업그룹 상위 5개와 하위 5개, 다섯 기간
5. 전체 산업그룹 표: 다섯 기간
6. 섹터별 산업그룹 표와 상승·하락 종목 각 5개

양수는 파란색, 음수는 빨간색이다. 데이터가 모자란 기간은 `데이터 부족`으로 표시하며 다른 기간으로 대체하지 않는다.

`N`은 첫 전체 섹터 성과표에만 표시하고, 나머지 로테이션·상승 비율·산업그룹 표에서는 제외한다.

상승·하락 종목 표는 `순위 / 종목명 / 수익률`만 표시하며 티커는 화면에서 제외한다.

종목명 아래의 2줄 사업 설명은 `Theme\Material\Sector_Industry\stock_descriptions.xlsx`를 `Market + Ticker`로 조회한다. Excel의 `Business Summary (KR)`를 수정하면 다음 생성부터 HTML에 반영된다. 설명 마스터 갱신 코드는 `Reports\build_stock_descriptions.py`다.

최종 파일은 `Theme\output\YYYYMMDD\Sector_Industry\글로벌_섹터_산업_<1D|5D>_보고서_YYYYMMDD.html`이다. 각 셀에 경계선을 넣고 숫자 제목과 값은 오른쪽 정렬하며, 표 폭은 화면 전체가 아니라 내용에 맞춰 배치한다.
