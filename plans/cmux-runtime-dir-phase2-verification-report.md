# cmux-runtime-dir-phase2 Verification Report

- **Ticket**: cmux-runtime-dir-phase2
- **Branch / Commit**: `main` / `dc2128c`
- **Date**: 2026-04-12
- **Author**: Codex

## 1. Root cause / 문제 원인

1단계에서 control-plane 파일은 runtime SSOT로 이동했지만, hook-local state, watcher/JARVIS operational marker, queue/socket/scratch 파일, active references, archive 문서에는 legacy temp cmux 경로가 남아 있었다. 이 상태는 producer와 consumer의 경로 권한을 다시 분기시키고, 문서 예시를 복사하는 다음 구현에서 같은 temp 경로가 재도입될 위험을 만든다.

## 2. Change / 수정 내용

- `cmux-orchestrator/scripts/cmux_paths.py` — runtime path SSOT를 hook state, watcher state, JARVIS marker, socket/pid, queue, scratch, pause/mute/help/welcome 플래그까지 확장했다.
- `cmux-orchestrator/scripts/cmux-paths.sh` — shell 소비자를 위한 동일 runtime 변수와 directory helper를 추가했다.
- `cmux-orchestrator/hooks/*`, `cmux-orchestrator/scripts/*`, `cmux-watcher/**`, `cmux-jarvis/**` — legacy temp cmux 경로를 `CMUX_*` 변수 또는 `cmux_runtime_path` 기반으로 이관했다.
- `tests/test_hooks.py`, `tests/test_cmux_utils.py`, `tests/test_redaction.py` — temp cmux fixture 의존을 제거하고 `CMUX_RUNTIME_DIR`/일반 temp fixture로 교체했다.
- `docs/**`, `cmux-*/SKILL.md`, `cmux-*/references/**`, `docs/99-archive/**` — 실행 예시와 과거 기록의 legacy temp cmux 문자열을 현행 runtime 변수 또는 archive-safe 표현으로 갱신했다.
- `cmux-orchestrator/scripts/task-queue.sh` — queue 파일 이관 중 발견한 `next_task` 필터 인자 미전달을 최소 수정했다.

## 3. Recurrence prevention / 재발 방지

- [x] Root-cause fix: 새 runtime 파일은 `cmux_paths.py`/`cmux-paths.sh`를 거쳐야 하도록 경로 SSOT를 확장했다.
- [x] Guardrail added: split-literal `rg` search로 legacy temp cmux 문자열과 archive 치환 오류를 검색했다.
- [x] Regression test updated: `tests/test_hooks.py`, `tests/test_cmux_utils.py`, `tests/test_redaction.py`를 새 runtime 경로 기준으로 실행했다.

## 4. Verification / 검증 결과

| Item | Command | Result |
|---|---|---|
| Static search | split-literal search for legacy cmux temp path and archive corruption marker | ✅ no matches, exit 1 |
| Python compile | `find cmux-orchestrator cmux-watcher cmux-jarvis tests -name '*.py' -print0 \| xargs -0 /usr/bin/python3 -m py_compile` | ✅ pass |
| Shell syntax | `find cmux-orchestrator cmux-watcher cmux-jarvis cmux-start cmux-stop cmux-pause cmux-help cmux-uninstall -name '*.sh' -print0 \| xargs -0 bash -n` | ✅ pass |
| Diff whitespace | `git diff --check` | ✅ pass |
| Focused tests | `/usr/bin/python3 -m pytest tests/test_hooks.py tests/test_cmux_utils.py tests/test_redaction.py -q` | ✅ 23 passed in 4.32s |
| Full tests | `/usr/bin/python3 -m pytest tests -q` | ✅ 79 passed, 532 warnings in 8.29s |
| Queue runtime simulation | `CMUX_RUNTIME_DIR=<temp> bash cmux-orchestrator/scripts/task-queue.sh add/list/next ...` | ✅ files written under `<temp>/queue/` |
| Runtime helper simulation | `CMUX_RUNTIME_DIR=<temp> /usr/bin/python3 - <<'PY' ...` | ✅ state/socket/watcher/scratch dirs resolved under temp runtime dir |
| Config validation | `bash cmux-orchestrator/scripts/validate-config.sh` (escalated for local cmux socket) | ✅ exit 0, `errors: []`, warnings: `surface-map.json not found`, `orphan surfaces: surface:3, surface:4` |
| Report checker | `test -f verification-kit.config.json && node /Users/csm/.codex/leceipts/scripts/check-reports.ts --config ./verification-kit.config.json || echo ...` | 검증 불가: `verification-kit.config.json` missing |

Key output excerpts:

```text
23 passed in 4.32s
79 passed, 532 warnings in 8.29s
errors: []
warnings: surface-map.json not found; orphan surfaces: surface:3, surface:4
```

### Unverifiable items

- Real cmux GUI end-to-end dispatch/watch/JARVIS session behavior — 검증 불가: 실제 여러 cmux surface를 생성하고 사용자 세션을 조작하는 GUI harness는 현재 검증 범위를 벗어난다.
- leceipts report checker — 검증 불가: 프로젝트 루트에 `verification-kit.config.json`이 없다.

## 5. Remaining risk / 남은 리스크

- 기존 로컬 runtime에 이미 생성된 legacy temp 파일이 있을 경우, 이번 변경은 코드를 새 SSOT로 돌릴 뿐 과거 temp 파일을 자동 migration하지 않는다.
- `validate-config.sh`는 통과했지만 현재 watcher가 실행 중이 아니라 `surface-map.json not found`와 orphan surface warning이 남았다.

## DoD Checklist

- [ ] Changed files committed
- [ ] Commit SHA present on base branch
- [x] Build / test suite passed, or unverifiable reason given
- [ ] Result pasted into the ticket/issue comment
