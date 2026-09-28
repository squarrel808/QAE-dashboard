# Theme 폴더 재구성 검증 기록 — 2026-09-08

## 이관 결과

- 원본: 347파일, 53,140,277 bytes
- 새 `output`으로 분류: 62파일
- 새 `Material`로 분류: 285파일
- 목적지 이름 충돌: 0건
- 복사 해시 불일치: 0건
- 원본 정리 실패: 0건
- 원본 백업: `C:\Users\infomax\Documents\ChatGPT\컨텍스트매크로\Theme_before_reorg_20260908.zip`
- 상세 이동표: `migration_manifest_20260908_182849.json`

## 최종 구조

- Theme 루트에는 `output`, `Material`, `README.md`만 남겼다.
- 모든 `output\YYYYMMDD`에는 `AI`, `Sector_Industry`, `Top10_Down10` 세 폴더가 있다.
- 날짜 폴더 루트에는 파일을 두지 않았다.
- `BQuant_Master.xlsx`, `Daily_Input`, 갱신 코드는 기존 `BQL\Rawfile`에 유지했다.

## 실데이터 검증

- Sector / Industry 1D: STOXX600·TOPIX 모두 2026-09-07 기준 실행 성공. PNG 2개와 상세 JSON의 분리 저장 및 육안 검수 완료.
- AI 1D: 미국 마지막 실제 거래일 2026-09-04 기준 실행 성공. 계산 JSON/XLSX는 Material, Word는 output에 저장.
- Top10 / Down10: 배치 태그 2026-09-07 기준 실행 성공. SPX 실제 종료일은 2026-09-04, CSI300·STOXX600은 2026-09-07. Excel 수식 60개, 오류 0개, Word 생성 성공.
- `latest_1D.json`, `latest_data.json`, `latest_outputs.json`이 가리키는 모든 파일의 존재 확인 완료.
- 설치된 Python, Node, PowerShell 코드 구문검사와 Sector 회귀검사 4개 통과.
- Codex 개인 스킬 `bql-theme-sector-rotation` 검증 통과.

## 참고

과거 코드·검증 이미지·동명 스냅샷은 삭제하지 않고 날짜별 Material의 `legacy_code`, `legacy_output`, `verification`, `historical_output` 등 원래 의미를 유지하는 하위 폴더에 보존했다.
