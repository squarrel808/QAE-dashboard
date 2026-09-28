# 유로존·글로벌 로테이션 대시보드

## 운영 파일

- `Market_Rotation_Dashboard_17_Indices.html`: 최종 HTML
- `build_market_rotation_dashboard.py`: 집계 및 HTML 생성 코드
- `market_rotation_dashboard.template.html`: 화면 템플릿
- `data/Dashboard_Global Equity_2606 (1).xlsx`: STOXX 600 섹터 장기 밸류에이션 전용 보조 자료

구성종목·가격·시가총액·EPS·P/E·ROE·영업이익률 원자료는 모두 다음 한 파일만 읽는다.

`C:\Users\infomax\Documents\python\BQL\Rawfile\BQuant_Master.xlsx`

## 갱신

전체 산출물을 함께 갱신하려면 다음을 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\BQL\Rawfile'
.\update_all.ps1
```

Master를 바꾸지 않고 이 HTML만 다시 만들려면 다음을 실행한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\BQL\유로존_dashboard'
.\update_dashboard.ps1
```

