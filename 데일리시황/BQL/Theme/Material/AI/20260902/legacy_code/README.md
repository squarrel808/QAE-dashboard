# AI Theme 운영 기준

운영 코드는 `build_sp500_ai_value_chain.py`, 최종 화면은 `SP500_AI_Value_Chain_Rotation.html`이다.

원자료는 다음 단일 Master만 사용한다.

`C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx`

특정 기준일이나 입력 파일명은 하드코딩하지 않는다. SPX 가격 패널에서 실제로 가격이 변한 마지막 유효 거래일을 찾아 1W, 1M, 3M, 6M, YTD를 역산한다. 마지막 행이 휴일·시차 때문에 전일 가격을 반복하면 기준일에서 제외한다.

밸류체인 집계가격은 시가총액 가중 평균가격이 아니라 `Σ(Price × Shares) / ΣShares`로 계산한다. 현재 Master에는 Shares가 없으므로 `Shares = Market Cap / Price`로 역산한다. 개별 종목 수익률은 `종료가격 / 시작가격 - 1`이며, 시가총액은 비가격 펀더멘털 집계와 기업행위 검증에만 사용한다.

## 갱신

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile'
.\update_all.ps1
```

AI 화면만 다시 만들려면 다음을 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\AI'
python .\build_sp500_ai_value_chain.py --output .\SP500_AI_Value_Chain_Rotation.html 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx'
```

## 기간별 Word 보고서

`Reports` 폴더에서 1거래일, 1주, 1개월·3개월 보고서를 각각 생성한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\AI\Reports'
.\run_1d.ps1
.\run_1w.ps1
.\run_1m_3m.ps1
```

세 보고서를 한꺼번에 만들려면 `.\run_all.ps1`을 실행한다. 새 Bloomberg 파일도 함께 병합하려면 `-UpdateRaw`를 붙인다. 자세한 구성과 옵션은 `Reports\README.md`를 참고한다.

그 밖의 과거 분석 스크립트·보고서는 과거 분석 재현용이며 운영 자동 갱신에는 호출되지 않는다.
