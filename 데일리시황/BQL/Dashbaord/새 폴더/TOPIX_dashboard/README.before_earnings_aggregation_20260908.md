# TOPIX 로테이션 대시보드

## 운영 파일

- `TOPIX_Rotation_Dashboard.html`: 최종 HTML
- `build_market_rotation_dashboard.py`: TOPIX 집계 및 HTML 생성 코드
- `market_rotation_dashboard.template.html`: 유로존 대시보드와 동일한 시각 체계의 화면 템플릿
- `topix_rotation_dashboard.incremental.fragment.html`: 다른 HTML에 삽입 가능한 대시보드 본문

원자료는 상위 폴더의 `Rawfile\BQuant_Master.xlsx`에서 `TPX500` 데이터를 읽는다. 화면 표기는 `TOPIX`로 통일한다.

현재 TOPIX 원자료 구간은 2026-09-02부터 2026-09-07까지다. `Price & Attribution II`는 1D·5D·1M·3M·6M 선택지를 유지한다. 1D는 직전 거래일, 5D는 최근 5개 평일을 사용하며 충분한 거래일이 쌓이기 전에는 가장 이른 가용일을 사용한다. 1M·3M·6M은 해당 기간의 원자료가 쌓이기 전까지 값이 없는 상태로 표시된다.

## 갱신

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\TOPIX_dashboard'
.\update_dashboard.ps1
```
