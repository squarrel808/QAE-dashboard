# Material 보관 규칙

`Material`은 계산 근거와 재현 가능한 실행 코드를 보관한다.

- `AI`, `Sector_Industry`, `Top10_Down10`의 루트: 날짜에 상관없이 다시 쓰는 실행 코드, README, 최신 포인터
- 각 카테고리의 `YYYYMMDD`: 해당 날짜의 JSON, 계산용 XLSX, 차트 재료, 검증 이미지, 과거 코드 스냅샷
- `YYYYMMDD_shared`: 둘 이상의 카테고리가 함께 사용한 날짜별 계산자료
- `Material` 바로 아래: 카테고리 공용 코드와 이관 기록

같은 파일명을 날짜 폴더 안에서 납작하게 합치지 않는다. `verification`, `references`, `legacy_output`, `code_snapshot` 같은 원래 하위 구조를 보존해 내용이 다른 동명 파일이 덮어써지지 않게 한다.

## 공용 계산기

`build_report_datasets.py`는 기존 `BQL\Rawfile\BQuant_Master.xlsx`를 읽고 날짜별 계산자료를 생성합니다.

```powershell
python .\build_report_datasets.py
python .\build_report_datasets.py --ai-only
```

기본 저장 위치는 다음과 같습니다.

```text
Material/AI/YYYYMMDD/
Material/Top10_Down10/YYYYMMDD/
```

다른 Master 또는 staging Material 루트를 검사할 때만 `--master`, `--material-root`를 명시합니다.
두 인자는 테스트·이관용이며 운영 기본값은 기존 `BQL\Rawfile` Master와 현재 `Theme\Material`입니다.

이 스크립트가 만드는 JSON과 계산용 XLSX는 최종 배포 보고서가 아니라 보고서 생성에 사용하는 Material입니다.
