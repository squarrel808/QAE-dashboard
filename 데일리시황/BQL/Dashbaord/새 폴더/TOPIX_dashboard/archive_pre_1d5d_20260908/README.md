# TOPIX 로테이션 대시보드

## 운영 파일

- `TOPIX_Rotation_Dashboard.html`: 최종 HTML
- `build_market_rotation_dashboard.py`: TOPIX 집계 및 HTML 생성 코드
- `market_rotation_dashboard.template.html`: 유로존 대시보드와 동일한 시각 체계의 화면 템플릿
- `topix_rotation_dashboard.incremental.fragment.html`: 다른 HTML에 삽입 가능한 대시보드 본문

원자료는 상위 폴더의 `Rawfile\BQuant_Master.xlsx`에서 `TPX500` 데이터를 읽는다. 화면 표기는 `TOPIX`로 통일한다.

현재 TOPIX 원자료 구간은 2026-09-02부터 2026-09-07까지다. 따라서 수익률과 EPS 변화는 이 가용 5일 구간을 사용한다. 1개월·3개월·장기 밸류에이션 화면은 충분한 히스토리가 들어온 뒤 확장한다.

## 갱신

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\TOPIX_dashboard'
.\update_dashboard.ps1
```
