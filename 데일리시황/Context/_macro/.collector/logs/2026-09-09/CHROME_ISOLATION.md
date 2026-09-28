# 15시 기존 작업과 매크로 수집 환경 분리

사용자 요청에 따라 2026-09-09 14:48경 실행 중이던 매크로 수집을 중단했다.
중단 후 매크로 launcher/collector Python 프로세스가 없음을 확인했다.
중단 시 누적 PDF는 Citi 212, BofA 32, HSBC 79, JPM 537, GS 1,295개(합계 2,155개)였다.
실행 `20260909_133207_4bb1f1`은 `incomplete`로 정리했고 중단 감사 JSON을 보존했다.

확인한 Chrome 구성:

| 용도 | 포트 | 프로필 | 확인 시 PID |
|---|---:|---|---:|
| 기존 보따리 자동화 | 9222 | `C:\selenium_profile` | 820 |
| 매크로 전용 | 9223 | `_macro\.collector\chrome-profile` | 4120 |

`run_macro_separate_chrome.py`의 기본 연결을 9223/매크로 전용 프로필로 변경했다.
기존 9222 Chrome을 종료하거나 프로필을 복사하지 않았다. 예약 작업은 추가하지 않았다.

14:51 로그인 점검 결과: GS/BofA/HSBC는 로그인 화면, Citi/JPM은 보고서 목록 확인 실패.
점검 JSON은 `isolated_login_check_145126.json`에 있다.
`--open-login`으로 새 전용 Chrome의 로그인 탭을 표시했다. 인증을 마치기 전까지 수집은 중단 상태다.

로그인 후 재개 명령:

```powershell
python run_macro_separate_chrome.py --mode backfill --start 2026-06-08 --end 2026-09-09 --houses Citi BofA HSBC JPM GS --retries 1 --pdf-timeout 45 --delay 0.7
```

위 명령은 기존 DB와 PDF를 이어받으며 저장·검증된 보고서는 건너뛴다.
