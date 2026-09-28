> **2026-09-11 데일리 작업 기준 변경**
> 원본 4개를 넣은 후 `QAE\데일리시황\데일리_표_업데이트.cmd`를 실행합니다.
> AI 밸류체인·섹터는 표와 숫자만 갱신하고, WECO는 실제값과 검토된 기존 IB 근거를 연결합니다.
> 새 AI 해석은 별도 요청 시 작성합니다. 아래 보고서 실행 예시는 과거 수동 경로입니다.
> 결과: `QAE\데일리시황\표_업데이트\index.html` · 상세 규칙: `데일리시황\데일리_작업규칙.md`

# BQL Theme 아침 워크플로우

## 최종 HTML 일괄 실행

- 데일리 1D: `Theme\Material\AI\run_final_daily_1d.py`
- 주초 5D: `Theme\Material\AI\run_final_weekly_5d.py`
- `--update-raw`를 붙이면 Daily_Input을 Master에 한 번 병합한 뒤 섹터와 AI를 순서대로 생성한다.
- 결과는 `Theme\output\YYYYMMDD\Sector_Industry`와 `Theme\output\YYYYMMDD\AI`에 저장한다.

Bloomberg/BQuant 원자료를 추가한 뒤 AI, STOXX Europe 600·S&P 500·TOPIX 섹터/산업, Top10/Down10 결과를 같은 규칙으로 생성하고 보관한다.

```text
Theme/
├─ Material/
│  ├─ README.md
│  ├─ build_report_datasets.py          # AI·Top10 공용 계산기
│  ├─ AI/
│  │  ├─ 실행 코드·README
│  │  └─ YYYYMMDD/                      # 계산 데이터·검증·재현 자료
│  ├─ Sector_Industry/
│  │  ├─ 실행 코드·README
│  │  └─ YYYYMMDD/
│  ├─ Top10_Down10/
│  │  ├─ 실행 코드·README
│  │  └─ YYYYMMDD/
│  └─ YYYYMMDD_shared/                  # 둘 이상 테마가 함께 쓰는 날짜별 자료
└─ output/
   └─ YYYYMMDD/
      ├─ AI/
      ├─ Sector_Industry/
      └─ Top10_Down10/
```

`output`에는 사람이 바로 보는 완성본만 둔다. 각 날짜 폴더에는 세 카테고리를 항상 만들며, 실행하지 않은 카테고리는 빈 폴더로 남아도 된다. 계산 JSON, 차트용 중간 파일, 검증 이미지, 재현 코드는 `Material`에 둔다. 날짜와 무관하게 여러 테마가 함께 쓰는 실행 코드는 `Material` 바로 아래에 둔다.

공통 `BQuant_Master.xlsx`와 신규 원자료 병합 코드는 Theme로 옮기지 않는다.

```text
BQL/Rawfile/BQuant_Master.xlsx
BQL/Rawfile/Daily_Input/
BQL/Rawfile/update_all.ps1
```

날짜 폴더는 원칙적으로 각 계산 데이터의 마지막 실제 거래일인 `meta.asOf`를 `YYYYMMDD`로 바꿔 사용한다. 두 시장의 실제 기준일이 다른 허용된 혼합 실행은 요청 cutoff 날짜를 공통 저장일로 쓰고, 실제 시장별 기준일은 파일명과 JSON에 남긴다.

## 요청어와 기간

- `daily`, `일간`, `어제`, `하루치`, `1D`: 마지막 두 실제 종가를 비교하는 1D
- `weekly`, `주간`, `주보`, `5D`: 마지막 여섯 실제 종가로 계산하는 최근 5거래일

`weekly`는 달력 7일이 아니라 5개 거래구간이다. 데이터가 부족하면 더 짧은 기간을 5D로 표시하지 않는다.

## 아침 실행 순서

1. 새 `.xlsb` 또는 `.xlsx`를 `BQL\Rawfile\Daily_Input`에 넣는다.
2. Codex에 원하는 범위와 기간을 말한다. 예: `BQL Theme daily 전체 실행`, `유럽·토픽스 weekly`, `AI 1D`, `Top10 업데이트`.
3. 원자료 병합 후 실제 거래일과 데이터 커버리지를 확인한다.
4. 결과는 `output\YYYYMMDD\<카테고리>`, 계산 근거는 `Material\<카테고리>\YYYYMMDD`에 저장한다.
5. 이미지·문서와 manifest의 기준일 및 경로를 검수한 뒤 전달한다.

## 직접 실행

```powershell
# 섹터/산업 HTML: 유럽·미국·일본 1D 데일리
python '.\Material\Sector_Industry\Reports\run_sector_report_daily_1d.py'

# 섹터/산업 HTML: 유럽·미국·일본 5D 주초
python '.\Material\Sector_Industry\Reports\run_sector_report_weekly_5d.py'

# 새 Raw 병합 후 생성하고 결과 열기
python '.\Material\Sector_Industry\Reports\run_sector_report_daily_1d.py' --update-raw --open

# AI 전 기간 또는 기존 날짜 자료 재사용
& '.\Material\AI\run_all.ps1'
& '.\Material\AI\run_1d.ps1' -UseExistingData -DateTag 20260907

# Top10 / Down10
& '.\Material\Top10_Down10\run_top10_update.ps1'
```

각 카테고리의 세부 계산 기준과 옵션은 해당 `Material` 하위 README를 따른다. 원자료는 수정하거나 삭제하지 않는다.

섹터 HTML은 별도 PNG와 Word를 생성하지 않는다. 1회 실행 시 세 시장을 탭으로 묶은 HTML 하나와 감사용 JSON 하나를 만들며, 보통 약 20초 이내에 완료된다. 파일은 `output\YYYYMMDD\Sector_Industry` 바로 아래에 저장한다. 1D·5D 실행 파일의 첫 표와 상승 종목 비율은 각각 해당 기간을 사용하고, 로테이션 및 산업그룹 표는 `1D / 5D / 1M / 3M / 6M`을 함께 보여준다.
