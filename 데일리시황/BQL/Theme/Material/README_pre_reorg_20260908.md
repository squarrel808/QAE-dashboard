# BQL Theme 아침 섹터 로테이션 워크플로우

이 폴더의 섹터 로테이션 워크플로우는 사용자가 Bloomberg/BQuant 원자료를 추가한 뒤 Codex에 `daily` 또는 `weekly`라고 요청하면 STOXX Europe 600과 TOPIX의 섹터·산업 성과를 같은 형식으로 다시 계산한다.

## 요청어와 기간

| 사용자 요청 | 계산 기간 | 비교 방식 |
|---|---|---|
| `daily`, `일간`, `어제`, `1D` | 1D | 최신 실제 거래일 종가 ÷ 직전 실제 거래일 종가 − 1 |
| `weekly`, `주간`, `주보`, `5D` | 5D | 최신 실제 거래일 종가 ÷ 5거래일 전 종가 − 1 |

`weekly`는 달력상 7일이 아니라 정확히 다섯 번의 거래 세션 변화를 뜻한다. 따라서 5D 계산에는 실제 종가 여섯 개가 필요하다.

## 매일 순서

1. 새 `.xlsb` 또는 `.xlsx` 파일을 다음 폴더에 넣는다.

   `C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Rawfile\Daily_Input`

2. Codex에 `BQL Theme daily 실행해줘` 또는 `BQL Theme weekly 실행해줘`라고 요청한다.
3. 실행기는 새 원자료를 `BQuant_Master.xlsx`에 병합한 뒤 기간별 섹터 스냅샷을 만든다. 이미 처리한 원자료는 해시로 중복 확인한다.
4. Codex는 실제 비교 시작일과 종료일을 확인하고 생성된 표 이미지를 검수한 뒤 대화에 표시한다.

원자료 파일은 수정하거나 삭제하지 않는다. 최신 날짜 열이 주말·휴일·장 마감 전 이월값이면 그대로 사용하지 않는다. 직전 유효 세션 대비 비교 가능한 구성종목 가격의 2% 이상이 바뀐 날짜만 실제 거래 세션으로 인정한다.

## 산출물

모든 결과는 다음 폴더 아래에 저장한다.

`C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\output\Sector_Industry`

실행별 폴더와 파일 예시는 다음과 같다.

```text
Sector_Industry/
├─ Daily_YYYYMMDD/
│  ├─ STOXX600_섹터_1D_YYYYMMDD.png
│  ├─ TOPIX_섹터_1D_YYYYMMDD.png
│  └─ STOXX600_TOPIX_Sector_Industry_1D_YYYYMMDD.json
├─ Weekly_YYYYMMDD/
│  ├─ STOXX600_섹터_5D_YYYYMMDD.png
│  ├─ TOPIX_섹터_5D_YYYYMMDD.png
│  └─ STOXX600_TOPIX_Sector_Industry_5D_YYYYMMDD.json
├─ latest_1D.json
└─ latest_5D.json
```

PNG 표는 `섹터, N, 산업 그룹, 1D/5D 평균, 중앙값, 상승 비율, 분산, 시장 대비` 열을 사용하며 평균수익률 내림차순으로 정렬한다. JSON에는 섹터와 GICS Industry Group별 계산값, 전 종목 수익률, 섹터별 상승·하락 상위 종목을 각각 최대 8개까지 남긴다.

## 계산 기준

- 종목 수익률: 현지통화 가격의 단순수익률
- 섹터·산업 평균: 유효 종목 수익률의 동일가중 산술평균
- 중앙값: 유효 종목 수익률의 중앙값
- 상승 비율: 유효 종목 중 수익률이 0보다 큰 종목의 비율
- 분산: 유효 종목 수익률의 모집단 표준편차
- 시장 대비: 섹터 동일가중 평균 − 해당 시장 전체 동일가중 평균
- 분류: `GICS Sector > GICS Industry Group > 종목`

동일가중 결과는 공식 STOXX Europe 600 또는 TOPIX 지수 수익률이 아니다. 배당과 환율 변환 효과는 포함하지 않는다.

## 직접 실행

PowerShell에서 다음 실행 파일을 사용한다. 기본값은 두 시장 모두이며, 실행 전 Master를 갱신한다.

```powershell
Set-Location -LiteralPath 'C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme'
.\run_sector_rotation.ps1 -Period Daily
.\run_sector_rotation.ps1 -Period Weekly
```

기본 계산 기준일은 실행일의 전날(한국 로컬 날짜)이다. 해당 날짜가 휴장일이거나 가격 이월 열이면 그 이전의 가장 최근 실제 종가를 자동으로 사용한다. 재현용으로 날짜를 고정하려면 `-AsOf '2026-09-07'`처럼 지정한다.

시장 하나만 계산할 수도 있다.

```powershell
.\run_sector_rotation.ps1 -Period 1D -Market STOXX600
.\run_sector_rotation.ps1 -Period 5D -Market TOPIX
```

새 원자료가 없고 기존 Master로 이미지만 다시 만들 때만 `-SkipMasterUpdate`를 사용한다.

```powershell
.\run_sector_rotation.ps1 -Period 1D -SkipMasterUpdate
```

5D에 필요한 실제 종가가 여섯 개 미만이면 짧은 기간을 5D로 표시하지 않고 실행을 중단한다.

두 시장의 마지막 실제 종가일이 다르면 합쳐진 결과를 기본적으로 중단한다. 휴장 차이임을 확인한 경우에만 `-AllowMixedAsOf`를 명시해 시장별 서로 다른 기준일로 생성한다.

## Codex 스킬

이 워크플로우는 다음 개인 스킬로 등록한다.

`C:\Users\infomax\.codex\skills\bql-theme-sector-rotation\SKILL.md`

이후 새 raw를 넣고 `BQL Theme daily 실행해줘`, `유럽·토픽스 주간 표 만들어줘`, `TOPIX 1D 이미지만`처럼 요청하면 같은 계산·검증·저장 규칙을 사용한다. 이 섹터 작업은 예약 실행이 아니라 요청할 때 실행하는 방식이다.
