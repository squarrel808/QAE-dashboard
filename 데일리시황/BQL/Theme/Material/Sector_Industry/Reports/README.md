# STOXX600 · TOPIX 아침 섹터 스냅샷

`Daily_Input`에 새 Bloomberg/BQuant 원본을 넣은 뒤, 사용자의 표현에 따라 같은 계산 규칙으로 두 시장의 섹터 요약표 이미지와 상세 계산 JSON을 만듭니다.

- `daily`, `일간`, `하루치` 요청: `1D`
- `weekly`, `주간`, `주보` 요청: `5D`
- 기본 대상: STOXX Europe 600과 TOPIX 모두
- 기본 기준일 cutoff: 실행일의 전날. 해당 날짜가 휴일이면 그 이전의 최신 실제 거래 세션으로 자동 이동
- 결과 이미지: `BQL\Theme\output\YYYYMMDD\Sector_Industry`
- 계산 JSON: `BQL\Theme\Material\Sector_Industry\YYYYMMDD`

## 운영 위치

다음 파일을 아래 운영 폴더에서 사용합니다.

`C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Sector_Industry\Reports`

- `build_sector_snapshot.py`
- `test_sector_snapshot.py`

실행 진입점은 다음 위치에 `run_sector_rotation.ps1` 이름으로 둡니다.

`C:\Users\infomax\Documents\python\QAE\데일리시황\BQL\Theme\Material\Sector_Industry\run_sector_rotation.ps1`

## 아침 실행 순서

1. 새 `.xlsb` 또는 `.xlsx`를 `BQL\Rawfile\Daily_Input`에 넣습니다.
2. `run_sector_snapshot.ps1`을 실행합니다. 이 진입점은 먼저 `update_master.py`를 호출해 새 원본을 `BQuant_Master.xlsx`에 병합합니다.
3. `daily`이면 마지막 두 실제 종가, `weekly`이면 마지막 여섯 실제 종가를 사용합니다.
4. STOXX600과 TOPIX 표 이미지는 `Theme\output\YYYYMMDD\Sector_Industry`, 전체 계산 JSON은 `Theme\Material\Sector_Industry\YYYYMMDD`에 저장합니다.
5. `Material\Sector_Industry\latest_1D.json` 또는 `latest_5D.json`에서 가장 최근 결과의 정확한 경로를 확인합니다.

## 실행 예시

```powershell
# 어제 하루치
.\run_sector_rotation.ps1 -Period 1D

# 최근 5거래일
.\run_sector_rotation.ps1 -Period 5D

# 기준일을 직접 고정
.\run_sector_rotation.ps1 -Period 1D -AsOf '2026-09-07'

# Master가 이미 갱신됐을 때 재계산만
.\run_sector_rotation.ps1 -Period 5D -SkipMasterUpdate
```

## 계산 기준

- `1D = 최신 실제 종가 / 직전 실제 종가 - 1`
- `5D = 최신 실제 종가 / 5거래 세션 전 실제 종가 - 1`
- 섹터·산업그룹 수익률: 유효 종목 현지통화 가격수익률의 동일가중 산술평균
- 중앙값: 유효 종목 수익률 중앙값
- 상승 비율: 유효 종목 중 수익률이 0보다 큰 종목 비율
- 분산: 유효 종목 수익률의 모집단 표준편차
- 시장 대비: 섹터/산업그룹 동일가중 평균에서 전체 유효 종목 동일가중 평균 차감
- 산업그룹 수: 해당 섹터에서 유효 수익률이 있는 GICS Industry Group 개수
- 상승 상위·하락 하위: 각 섹터 안에서 실제 플러스/마이너스 종목만 각각 최대 8개; JSON에 저장

주말·휴일·미래 날짜의 이월값은 거래일로 세지 않습니다. 첫 번째 충분한 종가를 기준점으로 포함한 뒤, 직전 실제 세션 대비 유효 쌍의 2% 이상이 실제로 변한 열만 새 세션으로 인정합니다. 기준일 이후 열은 계산 전에 제거합니다.

가격이 35% 이상 움직이면서 가격 변화와 시가총액 변화가 크게 어긋나는 종목, -90% 이하 또는 +300% 이상 극단값은 기업행위 의심치로 제외합니다. 시장 유효 커버리지가 80% 미만이면 결과를 만들지 않습니다.

## 생성 파일

예를 들어 `1D`, 기준일 `2026-09-07`이면 다음과 같습니다.

```text
Theme\output\20260907\Sector_Industry\
  STOXX600_섹터_1D_20260907.png
  TOPIX_섹터_1D_20260907.png
Theme\Material\Sector_Industry\20260907\
  STOXX600_TOPIX_Sector_Industry_1D_20260907.json
Theme\Material\Sector_Industry\latest_1D.json
```

`5D`도 같은 날짜 우선 구조와 `latest_5D.json`을 사용합니다. PNG는 사용자 예시처럼 제목이나 설명문 없이 숫자 표만 담습니다. JSON에는 섹터, GICS 산업그룹, 전체 구성종목, 계산 구간, 제외 사유, 섹터별 상·하위 종목 최대 8개가 모두 남습니다.

## 배포 전 검증

```powershell
python .\test_sector_snapshot.py
python -m py_compile .\build_sector_snapshot.py
```

운영 반영 뒤에는 실제 원본으로 다음 두 명령을 각각 실행합니다.

```powershell
.\run_sector_rotation.ps1 -Period 1D -AsOf '2026-09-07' -SkipMasterUpdate
.\run_sector_rotation.ps1 -Period 5D -AsOf '2026-09-07' -SkipMasterUpdate
```

검수 항목은 다음과 같습니다.

- 이미지의 섹터 행 수와 JSON 섹터 수 일치
- 섹터·산업그룹 `N` 합계와 현재 구성종목 수 일치
- `1D`는 종가 2개, `5D`는 종가 6개가 `sessionDates`에 기록
- 기준일 이후 또는 가격이 동일한 이월 날짜가 `sessionDates`에 없음
- 섹터별 상·하위 종목이 각각 8개 이하이고 서로 겹치지 않음
- STOXX600과 TOPIX의 `asOf`가 다르면 기본 실행 중단

TOPIX Master에 실제 종가가 여섯 개 미만이면 `5D`는 실패하는 것이 정상입니다. 오래된 별도 원천을 자동으로 이어 붙이지 말고, `Daily_Input`에 필요한 거래일 원본을 추가한 뒤 Master를 다시 갱신해야 합니다.
