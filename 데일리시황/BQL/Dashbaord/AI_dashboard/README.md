# 미국 AI 밸류체인 대시보드

`AI_Value_Chain_Dashboard.html`은 기존 S&P 500 AI 밸류체인 12개 분류를 사용해 가격·12MF EPS·12MF P/E의 유효 거래일 전체 시계열을 표시한다. 왼쪽에서 밸류체인을 눌러 그래프를 켜고 끄며, `Core`/`인접 포함`과 `전체`/`1년`/`6개월`을 전환할 수 있다. 파일은 로컬 브라우저에서 단독으로 열리며 인터넷 연결이 필요 없다.

## 갱신

`BQL\Rawfile\BQuant_Master.xlsx`가 갱신된 뒤 아래 명령을 실행한다.

```powershell
python -X utf8 "C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Dashbaord\AI_dashboard\build_ai_value_chain_dashboard.py"
```

기본 입력은 `BQL\Rawfile\BQuant_Master.xlsx`의 `SPX Raw` 시트, 기본 출력은 이 폴더의 `AI_Value_Chain_Dashboard.html`이다. 원본 엑셀은 읽기만 한다. 분류는 `BQL\Theme\Material\AI\build_sp500_ai_value_chain.py`의 `STAGES`를 직접 불러오므로 기존 AI 보고서와 같은 종목 목록을 쓴다.

## 계산과 해석

- 원본 Price 열의 유효한 실제 가격 갱신 거래일만 사용한다. 주말·휴일 이월값을 별도 관측일로 세지 않는다.
- 주식수는 `일간 시총 ÷ 주가`로 복원한다. 그룹 가격은 `Σ(주가 × 주식수) ÷ Σ주식수`; EPS는 같은 방식으로 가중한 `12MF EPS Blended`다. 두 추이는 그룹별 첫 유효일을 100으로 둔다.
- 그룹 P/E는 종목 P/E의 산술평균이 아니라 `Σ유효 시총 ÷ Σ(유효 시총 / 종목 12MF P/E)`다. 1배 미만 또는 200배 초과 종목값은 데이터 품질 이상치로 제외한다.
- EPS/P/E는 당일 그룹 시총의 60% 이상을 커버할 때만 표시한다. 각 그래프의 마우스 위치에서 커버리지를 볼 수 있다. 가격·EPS·P/E의 유효 종목 집합이 달라 세 값이 정확히 항등식으로 연결되지는 않을 수 있다.
- 현 구성종목을 과거에 적용해 생존편향이 있고, Price는 배당을 제외한다. 가격과 EPS의 기준일이 그룹마다 달라질 수 있으므로 서로 다른 그룹의 100 기준선은 동일한 날짜를 보장하지 않는다.
