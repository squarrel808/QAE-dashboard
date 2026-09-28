# Top10 / Down10 운영 워크플로우

S&P 500, CSI 300, STOXX Europe 600의 최근 10거래일 상승·하락 상위 10종목을 계산하고 차트, Excel, Word 보고서를 생성한다. 코드와 계산 근거는 `Theme\Material`, 사용자가 보는 완성본은 날짜별 `Theme\output`에 분리한다.

## 새 폴더 계약

```text
BQL\
├─ Rawfile\
│  ├─ Daily_Input\
│  └─ BQuant_Master.xlsx
└─ Theme\
   ├─ Material\Top10_Down10\
   │  ├─ 실행 코드와 README
   │  ├─ Market_10D_Rankings_latest.json
   │  ├─ Market_10D_Enriched_latest.json
   │  ├─ latest_outputs.json
   │  └─ YYYYMMDD\
   │     ├─ Market_10D_Rankings_YYYYMMDD.json
   │     ├─ Market_10D_Enriched_YYYYMMDD.json
   │     ├─ manifest.json
   │     └─ charts\*.png
   └─ output\YYYYMMDD\Top10_Down10\
      ├─ SPX_CSI300_STOXX600_10D_Top10_Down10_YYYYMMDD.xlsx
      └─ SPX_CSI300_STOXX600_최근10거래일_Top10_Down10_YYYYMMDD.docx
```

`BQuant_Master.xlsx`는 이동하거나 복제하지 않는다. 모든 계산은 계속 `BQL\Rawfile\BQuant_Master.xlsx`를 읽는다.

## 실행

새 원본을 먼저 `BQL\Rawfile\Daily_Input`에 넣고 Master를 갱신한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile'
python .\update_master.py
```

Top10 / Down10을 만든다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Top10_Down10'
.\run_top10_update.ps1
```

다른 원본을 명시할 때만 위치 인수로 전달한다.

```powershell
.\run_top10_update.ps1 'C:\path\to\BQuant_workbook.xlsb'
```

`-BqlRoot`, `-OutputRoot`, `-MaterialOutputRoot`는 staging·회귀검증에서만 쓰는 경로 override다. 일상 운영에서는 지정하지 않는다.

## 실행 단계

1. `compute_10d_rankings.py`가 Master에서 SPX·SHSZ300·SXXP를 읽고 최근 10거래구간 순위를 계산한다.
2. 계산 JSON은 `Material\Top10_Down10\YYYYMMDD`에 보존하고 category root의 `Market_10D_Rankings_latest.json`을 갱신한다.
3. `build_market_10d_outputs.py`가 enriched JSON과 차트를 같은 날짜별 Material 폴더에 저장한다.
4. Excel은 `Theme\output\YYYYMMDD\Top10_Down10`에 생성한다.
5. `build_market_10d_report.js`가 날짜별 Material 차트를 읽어 같은 최종 output 폴더에 Word 보고서를 만든다.
6. Excel 수식과 캐시값을 검증한 뒤 `Material\Top10_Down10\latest_outputs.json`을 최신 포인터로 사용한다.

## 경로 원칙

- 최종 배포물: `Theme\output\<YYYYMMDD>\Top10_Down10`
- 계산 JSON·차트·날짜별 manifest: `Theme\Material\Top10_Down10\<YYYYMMDD>`
- 최신 포인터: `Theme\Material\Top10_Down10\latest_outputs.json`
- 최신 계산 호환본: category root의 `Market_10D_Rankings_latest.json`, `Market_10D_Enriched_latest.json`
- 원자료: `BQL\Rawfile\BQuant_Master.xlsx`

산출물의 정확한 경로를 임의로 재검색하지 말고 항상 `latest_outputs.json`을 읽는다. 이 포인터에는 `materialDir`, `publishDir`, `manifest`, `rankings`, `datedEnriched`, `workbook`, `chartDir`, `docx`, `pdf`가 기록된다.

## 계산 원칙

1. Master에서 지수별 마지막 유효 거래일을 찾는다.
2. 전일 대비 가격이 실제로 변한 구성종목 비율로 휴일·반복 행을 걸러낸다.
3. 마지막 유효일부터 최근 11개 종가를 사용해 10개 거래구간 수익률을 계산한다.
4. 시작일과 종료일 가격이 모두 있고 시작가격이 양수인 종목만 순위에 포함한다.
5. 개별 종목 순위는 현지통화 단순 가격수익률로 정하며 배당은 포함하지 않는다.
6. 파일 날짜는 세 시장의 마지막 유효 거래일 중 가장 최근 날짜로 정한다.

국가·시장 참고가격을 표시할 때는 `Σ(Price × Shares) / ΣShares`를 사용한다. Shares가 없으므로 `Market Cap / Price`로 역산한다.

## 검증

운영 반영 전에 다음을 실행한다.

```powershell
python -m py_compile .\compute_10d_rankings.py .\build_market_10d_outputs.py .\validate_market_10d_workbook.py .\render_market_10d_report.py
node --check .\build_market_10d_report.js
```

실데이터 실행 후 확인할 항목:

- `latest_outputs.json`의 모든 경로가 새 Material/output 구조 안에 있는지
- 계산 JSON과 charts가 최종 output 폴더에 섞이지 않았는지
- Excel과 Word만 `Theme\output\YYYYMMDD\Top10_Down10`에 있는지
- 날짜별 `manifest.json`과 category root의 `latest_outputs.json` 내용이 일치하는지
- Excel 검증 결과가 `formulas=60`, `formula_errors=0`인지

## 파일 역할

- `compute_10d_rankings.py`: Master 로딩, 실제 거래일 판정, 10D 순위 JSON
- `build_market_10d_outputs.py`: enriched JSON, charts, manifest, 최종 Excel
- `build_market_10d_report.js`: 최종 Word 보고서
- `validate_market_10d_workbook.py`: Excel 구조·수식 검증
- `render_market_10d_report.py`: manifest가 가리키는 PDF를 페이지 이미지로 렌더링
- `run_top10_update.ps1`: 전체 실행과 경로 연결
