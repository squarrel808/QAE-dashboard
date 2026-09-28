
## Scheduler dashboard integration — 2026-09-21T19:04:35+09:00
- User requested daily visibility in C:/Users/infomax/Documents/python/scheduler_dashboard.html. Added dedicated QAE IB 07:20 item, historical audit import, RUNNING/FAILED/PUBLISHED/NO_RECORD states, six-hour unclosed-run label, KST missing-day checks, 60-second page reload.
- Monitoring tool: QAE/_자동화/ib_interpretation_monitor.py. Logs: QAE/logs/ib_interpretation (events.jsonl, status.json, run_history.csv). Existing automation prompt now calls begin/finish/fail --refresh, keeping schedule/model/project and original evidence rules unchanged.
- September 21 publication: 17 revised/177 retained, 194 drafts and 219 house comments; September 19/20 have no audit evidence. Source numeric date September 17.
- Windows QAE대시보드갱신 task verified enabled daily 07:00; actual action 전체업데이트.bat /nohaver /dataonly /nopause. Last September 21 result 0x40010004, no current pipeline log; last recorded push success September 15. Precise termination cause unconfirmed.
- Dashboard now shows Windows task outcome separately from historical pipeline success; dated cache on query denial. No deployment, git, collector or Windows schedule changes. Current Vercel embed sync excludes new WECO pages.
- Tests: marker transitions, publication deduplication, missing-day classification, rendered integration and JS syntax passed. Launcher: QAE/_자동화/스케줄러_로그_확인.cmd.
