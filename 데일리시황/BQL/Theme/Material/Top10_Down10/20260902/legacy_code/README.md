# Top10 / Down10 최신 자동 업데이트

S&P 500, CSI 300, STOXX Europe 600의 최신 유효 거래일을 찾아 최근 10거래일 상승·하락 상위 10종목을 자동 계산한다. 입력 파일명과 날짜는 하드코딩하지 않는다.

운영 원자료는 다음 단일 Master다.

`C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx`

## 계산 원칙

1. Master에서 지수별 마지막 유효 거래일을 찾는다.
2. 전일 대비 가격이 실제로 변한 구성종목 비율로 휴일·반복 행을 걸러낸다.
3. 마지막 유효일부터 최근 11개 종가를 사용해 10개 거래구간 수익률을 계산한다.
4. 시작일과 종료일 가격이 모두 있고 시작가격이 양수인 종목만 순위에 포함한다.
5. 산출물 날짜는 세 지수의 마지막 유효 거래일 중 가장 최근 날짜로 자동 생성한다.

개별 종목 순위는 가격수익률 자체로 정하므로 가중치가 없다. 국가·시장 참고가격을 표시할 때는 시가총액 가중 평균가격을 사용하지 않고 `Σ(Price × Shares) / ΣShares`로 계산한다. 현재 Master에는 Shares가 없으므로 `Shares = Market Cap / Price`로 역산한다.

## 갱신

전체 원자료와 모든 산출물을 함께 갱신한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile'
.\update_all.ps1
```

Top10 / Down10만 다시 만들려면 다음을 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Top10_Down10'
.\run_top10_update.ps1 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\BQuant_Master.xlsx'
```

항상 최신 산출물 경로는 `output/latest_outputs.json`에서 확인한다.
