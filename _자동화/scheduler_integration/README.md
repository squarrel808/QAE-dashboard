# IB 해석 실행 모니터

사용자 입구: `C:/Users/infomax/Documents/python/scheduler_dashboard.html`

`스케줄러_로그_확인.cmd`를 실행하면 기존 감사 기록을 읽어 갱신하고 화면을 연다.
HTML은 정적 스냅샷이며 60초마다 파일을 다시 읽는다. 오늘 실행 기록 여부는
한국시간으로 판단한다. 컴퓨터나 Codex가 실행되지 않아 기록이 없으면 성공/실패를
추정하지 않고 '실행 기록 없음'으로 표시한다. 시작 후 6시간이 지나도 종료 기록이
없으면 '종료 미확인'으로 표시하며 실제 프로세스 생존을 단정하지 않는다.

07:20 Codex 예약에는 다음 명령을 연결했다. 시작 명령이 출력한 run-id를 사용한다.

```
python -X utf8 "_자동화/ib_interpretation_monitor.py" begin --refresh
python -X utf8 "_자동화/ib_interpretation_monitor.py" finish --run-id ID --record RECORD --refresh
python -X utf8 "_자동화/ib_interpretation_monitor.py" fail --run-id ID --message REASON --refresh
```

기록은 `QAE/logs/ib_interpretation/events.jsonl`, `status.json`, `run_history.csv`에
남는다. 기존 실행별 run_record.json은 원본을 변경하지 않고 읽는다. 9월 19~21일은 Codex 예약 첫 턴의 사용량 한도 초과 실패로 확인했다.
모델 실행 전 실패도 Codex 로컬 감사 기록을 읽기 전용으로 조회하여 표시한다. 수집 일부 실패와 해석 게시 성공은 다른 상태다.

Vercel 예약은 2026-09-21 조회 당시 매일 07:00 활성, 마지막 종료 0x40010004였다.
실제 실행파일은 `QAE/전체업데이트.bat`, 인자는 `/nohaver /dataonly /nopause`다.
`_자동화/run_all_0830.bat`도 있지만 현재 예약은 전체업데이트.bat을 직접 호출한다.
마지막 파이프라인 성공·git push 로그는 9월 15일이다. 이 기록만으로 Vercel의
배포 완료 또는 오늘의 정확한 종료 원인을 확정할 수 없다.

Vercel 동기화는 `macro_hub/scripts/sync_embeds.py`에서 예전 경제지표 화면을
복사한다. `데일리시황/표_업데이트/WECO`는 현재 배포 경로에 포함되지 않는다.
이 작업에서는 배포나 수집, git, 기존 Windows 예약 변경을 실행하지 않았다.
