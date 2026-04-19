# GATE W-9 — 개입 금지 (send-keys guard)

Worker / Watcher 역할은 동료 surface에 **`/new` 또는 `/clear`** 를
`tmux send-keys` / `cmux send-keys` 로 전송할 수 없다. 세션 리셋·재시작은
Boss 권한이다.

## 차단 대상

- Role: `worker`, `watcher`
- 명령: `tmux send-keys -t <other-surface> ... /new ...` 또는
  `cmux send-keys -t <other-surface> ... /clear ...`
- Target이 자기 자신(`cmux identify` 기준 surface_ref)이 아닌 경우에만 차단.

## 허용 케이스

- Role이 `boss`, `peer` 등 관제 권한: 전부 통과.
- Target이 자기 surface: 통과 (본인 세션 관리).
- `-t "$VAR"` 처럼 변수 치환 포함: fail-open 통과 (훅은 런타임 값을 알 수 없음).
  실제 값이 위반이면 런타임에 재호출 시 차단된다.
- `tmux send-keys` 자체가 없는 일반 Bash 명령: 통과.

## 왜 이 규칙이 필요한가

- **개입 금지 원칙**: Watcher는 감지·기록·보고만, Worker는 본인 작업만.
  타 surface 세션을 임의 리셋하면 진행 중 작업을 파괴할 수 있다.
- **책임 추적**: 세션 생명주기 결정은 Boss가 ledger에 기록해야 한다
  (Phase 2.3 연계).

## 훅

`cmux-orchestrator/hooks/cmux-send-guard.py` — PreToolUse:Bash. 매칭 시
`permissionDecision: deny` 반환, 이유 메시지에 본 문서 경로 포함.

## 관련 게이트

- GATE W-8: 핵심 행동 사이클 (감지→기록→보고)
- GATE W-7: 질문 금지 — Boss에게 결정 요청만
- Phase 2.3 ledger `HOOK_BLOCK` 이벤트로 차단 사례 감사 가능.
