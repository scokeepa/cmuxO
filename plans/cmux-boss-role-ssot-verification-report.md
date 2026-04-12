# cmux-boss-role-ssot Verification Report

- **Ticket**: cmux-boss-role-ssot
- **Branch / Commit**: `main` / `4bb9b6c`
- **Date**: 2026-04-12
- **Author**: Codex

## 1. Root cause / 문제 원인

- `/cmux-start`가 `roles["boss"]`를 기록하도록 바뀐 뒤에도 watcher, orchestrator hook, role-register, nudge, config, 문서 예제가 여전히 `roles["main"]`, `main_surface`, `--notify-main`, `check-main`을 소비했다. 이 상태에서는 boss-only roles 파일에서 핵심 소비자가 사장 surface를 찾지 못한다.
- `jarvis_nudge.py`가 `main`을 `boss` legacy alias로 해석해 `main`과 `boss`가 다시 공존할 수 있는 경로를 남겼다.
- nudge audit id가 `timestamp` 단독이라 같은 초 안에서 `sent`와 `rate_limited` audit이 충돌할 수 있었다.

## 2. Change / 수정 내용

- `cmux-start/SKILL.md` — 사장 등록/표시 변수를 `BOSS_*`와 `roles["boss"]` 기준으로 정리.
- `cmux-orchestrator/scripts/role-register.sh` — `register/whois/heartbeat/check-boss`와 peer/worker 제외 기준을 `boss`로 변경.
- `cmux-orchestrator/scripts/detect-surface-models.py`, `cmux-orchestrator/hooks/cmux-stop-guard.sh` — watcher enter signal을 `boss_surface/boss_workspace`로 변경.
- `cmux-orchestrator/scripts/cmux_utils.py` 및 관련 hooks — `is_boss_surface()` 기준으로 boss-only role lookup을 사용.
- `cmux-watcher/scripts/watcher-scan.py`, watcher hooks, monitor scripts — `--notify-boss`, `BOSS_DEAD`, `WATCHER→BOSS`, `BOSS→WATCHER`, `roles["boss"]` 기준으로 변경.
- `cmux-jarvis/scripts/jarvis_nudge.py` — `main` alias 제거, boss-only 권한 검증, audit id UUID suffix 추가.
- `tests/test_nudge.py` — `main` alias 미허용, boss→team_lead 허용, same-timestamp audit 비충돌 회귀 테스트 추가.
- `cmux-stop/SKILL.md` — 종료 상태 스캔/컨트롤 타워 workspace 복원 예제를 `boss` 기준으로 변경.
- `cmux-watcher/SKILL.md` — watcher state file 문서 키를 `boss_state`로 변경.
- README 및 docs/reference — runtime role/protocol SSOT를 Boss 기준으로 정렬하고 test count를 78로 갱신.

## 3. Recurrence prevention / 재발 방지

- [x] Root-cause fix (not a symptom patch)
- [x] Guardrail added (validation / quality check / UI constraint)
- [x] Regression test added or updated (must fail on the previous bug)
- [ ] Failure visibility logging
- [ ] Intentional omission

## 4. Verification / 검증 결과

| Item | Command | Result |
|---|---|---|
| Runtime main key scan | `rg -n "roles\\.(get\\|setdefault)\\(\\s*['\\\"]main['\\\"]\\|roles\\[\\s*['\\\"]main['\\\"]\\|\\.main\\.\\|\\['main'\\]\\|\\\"main\\\"\\s*:\\s*\\{\\|main_surface\\|main_workspace\\|main_ai\\|main_state\\|--notify-main\\|check-main\\|whois main\\|heartbeat main\\|WATCHER→MAIN\\|MAIN→WATCHER\\|MAIN_\\|is_main_surface\\|\\brole\\b.*\\bmain\\b\\|\\bmain\\b.*\\brole\\b" cmux-orchestrator cmux-watcher cmux-start cmux-stop cmux-jarvis tests README.md docs/01-architecture docs/02-jarvis docs/04-development docs/CHANGELOG.md -S` | only intentional `roles["main"]` non-alias documentation/test references remained |
| Python syntax | `python3 -m py_compile cmux-jarvis/scripts/jarvis_nudge.py cmux-jarvis/scripts/jarvis_palace_memory.py cmux-orchestrator/scripts/cmux_utils.py cmux-orchestrator/scripts/detect-surface-models.py cmux-watcher/scripts/watcher-scan.py cmux-watcher/scripts/surface-monitor.py cmux-orchestrator/hooks/cmux-completion-verifier.py cmux-orchestrator/hooks/cmux-no-stall-enforcer.py cmux-orchestrator/hooks/cmux-leceipts-gate.py cmux-orchestrator/hooks/cmux-watcher-notify-enforcer.py cmux-orchestrator/hooks/cmux-gate7-main-delegate.py cmux-orchestrator/hooks/cmux-workflow-state-machine.py cmux-orchestrator/hooks/cmux-control-tower-guard.py tests/test_nudge.py` | passed |
| Shell syntax | `bash -n cmux-orchestrator/scripts/role-register.sh cmux-orchestrator/scripts/cmux-orchestra-enforcer.sh cmux-orchestrator/hooks/cmux-main-context.sh cmux-orchestrator/hooks/cmux-gate6-agent-block.sh cmux-orchestrator/hooks/cmux-stop-guard.sh cmux-watcher/activation-hook.sh cmux-watcher/hooks/cmux-watcher-session.sh cmux-watcher/hooks/cmux-watcher-activate.sh cmux-watcher/scripts/surface-monitor.sh cmux-jarvis/hooks/cmux-jarvis-gate.sh cmux-orchestrator/scripts/eagle_watcher.sh` | passed |
| Boss-only simulation | inline Python authority/consumer simulation | `jarvis->boss`, `boss->team_lead`, `team_lead->worker` allowed; `boss->worker` blocked; `main`-only file rejected as missing boss |
| Gap recheck | same runtime scan across `.` | found stale `/cmux-stop` `roles.get("main")` and watcher `main_state` documentation; fixed and rechecked |
| Targeted tests | `python3 -m pytest tests/test_nudge.py -q` | 18 passed, 89 warnings |
| Diff whitespace | `git diff --check` | passed |
| Full tests | `python3 -m pytest tests -v` | 78 passed, 532 warnings |

Key output excerpts:

```text
collected 78 items
======================= 78 passed, 532 warnings in 4.89s =======================
```

### Unverifiable items

- Real cmux pane UI behavior — live cmux surface ownership and SendMessage effects are external runtime behavior and not covered by the local pytest harness.

## 5. Remaining risk / 남은 리스크

- ChromaDB/urllib3/Pydantic third-party warnings remain. They did not fail the current suite, but a future warnings-as-errors CI policy would need dependency-level handling.
- File names such as `cmux-main-context.sh` and Python entrypoints `def main()` remain because they are not runtime role keys. Renaming them would be a separate compatibility change.
- Archive docs and older verification reports still mention historical `main` failures; active runtime code/docs were checked separately.

## DoD Checklist

- [ ] Changed files committed
- [ ] Commit SHA present on base branch (`git branch --contains <sha>`)
- [x] Build / test suite passed, or unverifiable reason given
- [ ] Result pasted into the ticket/issue comment
