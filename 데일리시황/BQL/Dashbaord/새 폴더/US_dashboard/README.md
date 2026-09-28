# 미국 주식 로테이션 대시보드

## 갱신

공통 생성기는 `BQL\Dashbaord\build_regional_dashboards.py` 하나다. BQL의 `Rawfile\BQuant_Master.xlsx`를 읽어 유럽·미국·일본 화면을 한 번에 갱신한다.

```powershell
python "C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Dashbaord\build_regional_dashboards.py" --region all
```

미국만 갱신하려면 `--region us`를 사용한다. 원자료를 Master에 추가하는 작업은 이 명령에 포함되지 않는다. 원자료 병합부터 전체 산출물까지 갱신하려면 `Rawfile\update_all.ps1`을 사용한다.

## 파일

- `US_Rotation_Dashboard.html`: 미국 전용 완성 화면
- `us_rotation_dashboard.incremental.fragment.html`: 다른 HTML에 삽입할 본문
- `market_rotation_dashboard.template.html`: 유럽 화면과 같은 시각 체계의 미국 템플릿

미국 화면은 S&P 500을 기본으로 NASDAQ 100과 Dow Jones Industrial Average를 함께 선택할 수 있다. 섹터 heatmap과 상대수익률의 기준은 S&P 500이다. 수익률은 시작일 시가총액가중 가격수익률이며 배당은 제외한다. EPS 변화는 `EPS × (시가총액 ÷ 가격)`으로 복원한 구성종목 이익을 합산해 계산한다. P/E는 총시총을 총예상 이익으로 나눈다.

밸류에이션 장기 보조 파일은 미국에 없으므로, 밸류에이션 화면은 Master에 실제로 들어 있는 구간만 사용한다. 6개월·1년·전체 보기는 각 선택 구간의 평균과 ±2 표준편차를 다시 계산하며, 없는 10년/15년 이력을 만들지 않는다.
