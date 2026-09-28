# 벌크 수집 연결 단절 복구 — 2026-09-09

사용자가 20:14경 기존 파일을 유지한 재시작을 승인했다.

## 확정된 원인과 미확정 사항

기존 실행 `20260909_150452_83614f`의 표준 오류에서 다음 원인이 확인됐다. 표준 오류는 이전 실행의 개별 `.log`에 포함되지 않았고, 보존된 실행 콘솔에서 복구했다.

```text
ProtocolError: Protocol error (Page.handleJavaScriptDialog): No dialog is showing
Dialog._onHandle -> Dialog._dismiss -> Dialog._close -> DialogManager.dialogDidOpen
Node.js v24.18.1
17:31:12 Page.close: Connection closed while reading from the driver
17:31:13 [GS] incomplete: Locator.count: Connection closed while reading from the driver
```

직접 실패는 팝업 처리 중 Playwright Node 드라이버 종료다. 크롬은 살아 있었다. 당시 부모 실행기와 실제 수집기가 각각 같은 9223 Chrome에 Playwright로 연결했고, 둘이 같은 팝업을 자동으로 닫으려 한 경합이 유력하다. 정확한 동시 호출 순서는 재현 또는 스택 덤프가 없어 추정이며, 포트 9222 작업과 충돌했다고 입증된 것은 아니다.

[Playwright 공식 문서](https://playwright.dev/python/docs/api/class-dialog)는 별도 dialog 리스너가 없으면 자동으로 닫는다고 설명한다. 중복 제어 연결을 제거하고, 단일 수집기 쪽에서 이미 사라진 팝업의 dismiss 오류를 잡도록 변경했다.

오류 후 수집기가 종료되지 않아 OS 수집 잠금이 남았고, 기존 부모/후속 실행기는 수집기 생존 여부만 보고 기다렸다. 정확히 어느 동기 정리 호출에서 대기했는지는 확정하지 못했다.

## 보존 및 정리

- supervisor PID4500, launcher PID6660, collector PID48352만 중단했고 실제 종료를 확인했다.
- Chrome 9222 PID820 및 Chrome 9223 PID4120은 유지했다.
- 이미 저장한 PDF 2,790개와 보고서 DB 행은 변경·삭제하지 않았다.
- 이전 run의 `running`/미도달 표시를 `incomplete`로 정리하고 중단 사유와 로그 근거를 남겼다. JPM의 이미 완료된 3개월 결과 등 정상 체크포인트는 보존했다.
- 상세 전후 이력: `run_20260909_150452_83614f.interruption.json`.
- 이전 campaign은 `interrupted_for_recovery`로 종료 표시했다.

## 재발 방지

- 부모 실행기는 Playwright로 붙지 않는다. 수집기 1개만 Chrome을 제어하며 최소화도 같은 연결에서 처리한다.
- 팝업이 이미 닫힌 경우 예외를 처리하며 팝업 메시지 내용은 로그에 기록하지 않는다.
- 연결 단절이 확인되면 동기 페이지 닫기를 다시 시도하지 않고 현재·미도달 IB의 실패 상태를 확정한다.
- 새 벌크 감독 실행기는 실제 수집/콘솔 로그에 15분간 변화가 없거나 한 IB가 6시간을 초과하면 자신의 자식만 종료한다. 종료와 잠금 해제를 확인한 뒤 실패 기록을 정리하고 재시도 정책을 따른다.
- 표준 오류도 실행별 `.console.log`에 보존한다. 감독 실행기 heartbeat는 수집 진전으로 간주하지 않는다.
- 요청 범위는 2026-03-09~09-09, 기존 파일 중복 생략, 잔여 공간 5 GiB 하한, 스케줄러 미등록을 유지한다.

이 기록은 원인·복구 조치를 설명하며 전체 수집 완료를 뜻하지 않는다. 실제 재시작 상태는 `../latest_campaign.json`을 확인한다.

## 재개 확인

- 20:20:16 새 캠페인 `20260909_202016_864eeb` 시작. 감독 PID52076, 현재 HSBC launcher PID51848, collector PID51672, 유일한 Playwright Node 자식 PID44316을 확인했다. PID는 추후 재사용될 수 있으므로 중단 시 명령줄을 다시 검증한다.
- `HSBC` 3개월 재검증 run: `20260909_202017_9f185e`.
- 20:20:56 `20260909_US-Canada tensions escalate_Retaliation and import bans__26e9117be08e.pdf` 새 원본 저장 확인(240 KB).
- HSBC·BofA·JPM·GS·Citi 모두 이번 재개 전 로그인 및 목록 준비 확인을 통과했다.
- 오프라인 수집/복구 테스트 103개, Daily 테스트 22개(합계125개) 통과.
- 이번 3개월 재검증은 미통과 IB당 최대2회, 앞선3개월 확장은 최대2회 시도한다. 원본이 저장된 문서는 재다운로드하지 않는다.
