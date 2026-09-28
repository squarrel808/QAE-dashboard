# 매크로 수집 실행 로그

새 실행은 날짜별 폴더에 상세 로그(`run_*.log`)와 요약(`run_*.json`)을 함께 남깁니다.
`latest_run.json`은 가장 최근 수집 실행의 요약입니다. `overall_status`가 `incomplete`이면
같은 날짜 폴더의 로그에서 하우스별 오류를 확인합니다.

루트의 `collector.log`와 `run_*.json`은 2026-09-08까지 사용하던 기존 기록이며 삭제하지 않았습니다.
기존 실행 분석은 `HISTORICAL_AUDIT_20260909.md`에 정리했습니다.
