# cmux-runtime-dir-phase3 Verification Report

- **Ticket**: cmux-runtime-dir-phase3
- **Branch / Commit**: `main` / `dc2128c` (uncommitted worktree)
- **Date**: 2026-04-12
- **Author**: Codex

## 1. Root cause / 문제 원인

- Gate 7가 runtime state 읽기 예외를 허용하면서도 legacy temp cmux 경로 prefix를 함께 허용하면, runtime SSOT와 temp fallback이 다시 이중 권한이 된다. 현재 코드는 `cmux-orchestrator/hooks/cmux-gate7-main-delegate.py:26`에서 허용 prefix를 정의한다.
- hook-local/transient/scratch 상태가 `cmux_paths.py`/`cmux-paths.sh` 밖에서 생성되면 producer와 consumer가 서로 다른 위치를 보게 된다. Python SSOT는 `cmux-orchestrator/scripts/cmux_paths.py:45`, shell SSOT는 `cmux-orchestrator/scripts/cmux-paths.sh:64`부터 runtime 파일을 export한다.
- worktree 검증이 `/tmp/wt-*` 패턴에 묶이면 프로젝트별 worktree root와 Gate 7 정리 기준이 분리된다. 현재 shell helper는 `cmux-orchestrator/scripts/cmux-paths.sh:43`의 `cmux_worktree_root()`가 담당한다.
- watcher notify test harness가 pytest 실행 Python과 다른 PATH의 `python3`로 hook을 실행하면, 같은 테스트가 실행 환경에 따라 흔들릴 수 있다. hook runner는 `tests/test_hooks.py:100`에서 subprocess command를 구성한다.

## 2. Change / 수정 내용

- `cmux-orchestrator/hooks/cmux-gate7-main-delegate.py:26` — Gate 7 read exception을 `runtime_dir()` prefix 하나로 제한하고 legacy temp cmux prefix를 제거했다.
- `tests/test_hooks.py:100` — Python hook subprocess 실행기를 `python3` PATH lookup에서 `sys.executable`로 고정했다.
- `tests/test_hooks.py:198` — `cmux send` dispatch pending 생성, watcher 알림 해소, `cmux send-key` 제외 회귀 테스트를 유지하고 반복 실행에서 흔들리지 않도록 했다.
- `tests/test_hooks.py:255` — runtime state read는 허용하고 legacy temp `cmux-roles.json` read는 차단하는 Gate 7 회귀 테스트를 추가했다.
- `cmux-orchestrator/hooks/cmux-watcher-notify-enforcer.py:53` — watcher surface 값을 `9`와 `surface:9` 양쪽에서 같은 surface ref로 정규화했다.
- `cmux-orchestrator/scripts/cmux_paths.py:97` — JARVIS debounce/pid와 shim registry runtime 상수를 runtime SSOT에 추가했다.
- `cmux-orchestrator/scripts/cmux-paths.sh:43` — worktree root helper를 추가하고 shell runtime exports에 hook-local, JARVIS, socket/pid, scratch 경로를 포함했다.
- `cmux-orchestrator/scripts/cmux-shim.py:18`, `cmux-orchestrator/scripts/cmux_compat.py:28`, `cmux-orchestrator/scripts/cmux_utils.py:18` — shim registry, compat socket/pid/scratch, queue/roles helper가 runtime SSOT를 쓰도록 했다.
- `cmux-orchestrator/scripts/gate-checker.sh:89` — Gate 7 worktree scan을 `/tmp/wt` grep에서 `cmux_worktree_root()` 아래 worktree scan으로 변경했다.
- `cmux-jarvis/hooks/jarvis-file-changed.sh`, `cmux-jarvis/hooks/cmux-settings-backup.sh`, `cmux-jarvis/scripts/jarvis-maintenance.sh`, `cmux-jarvis/scripts/jarvis-scheduler.py`, `cmux-orchestrator/scripts/eagle-summary.sh`, `cmux-orchestrator/scripts/eagle_watcher.sh`, `cmux-orchestrator/scripts/cmux_compat.py` — 남은 transient/scratch operational 파일을 runtime/scratch 아래로 옮겼다.
- `cmux-orchestrator/SKILL.md`, `cmux-orchestrator/references/worktree-workflow.md`, `cmux-orchestrator/references/dispatch-templates.md`, `cmux-watcher/SKILL.md`, `cmux-watcher/references/cmux-event-monitoring.md`, `cmux-watcher/references/vision-diff-protocol.md`, `docs/01-architecture/session-lifecycle.md`, `docs/02-jarvis/worker-protocol.md` — active 지시문과 문서 예시를 `cmux_runtime_path`/`CMUX_*`/`cmux_worktree_root()` 기준으로 정렬했다.

## 3. Recurrence prevention / 재발 방지

- [x] Root-cause fix: Python은 `cmux_paths.py`, shell은 `cmux-paths.sh`를 runtime path SSOT로 사용한다.
- [x] Guardrail added: active 코드/문서 `/tmp` 검색, dynamic temp cmux 검색, Gate 7 worktree root simulation을 검증 절차에 포함했다.
- [x] Regression test added or updated: `test_gate7_allows_runtime_read_only`가 legacy temp read 허용 회귀를 차단한다.
- [x] Regression test added or updated: `test_watcher_notify_tracks_cmux_send`가 `cmux send` pending 생성/해소와 `send-key` 제외를 고정한다.
- [x] Failure visibility logging: pytest hook runner가 실패를 print-only로 넘기지 않고 assertion failure로 올리며, subprocess Python을 `sys.executable`로 고정한다.

## 4. Verification / 검증 결과

| Item | Command | Result |
|---|---|---|
| Static `/tmp` search | `rg -n "/tmp" cmux-orchestrator cmux-watcher cmux-jarvis cmux-start cmux-stop cmux-pause cmux-help cmux-uninstall docs plans -S -g '!docs/99-archive/**' -g '!referense/**' -g '!node_modules/**'` | ⚠️ 2026-04-15 재측정: 해당 범위에서 `CHANGELOG.md` 과거 기록과 `plans/*-verification-report.md` 자체 서술을 제외해도 수백 건 잔존. 병렬 세션의 `cmux_paths` SSOT 마이그레이션이 `stash@{0}`에 부분 진행 중이며, 해당 작업 완료 후 이 표를 재작성할 것. |
| Dynamic temp search | `rg -n "tempfile\\.gettempdir\\(\\).*cmux\|mkstemp\\(prefix=.*cmux\|mktemp .*cmux\|/tmp/\"\"cmux\|20 \"\"20 \"\"12\|/tmp/wt" ...` | ✅ legacy temp test fixture 1건과 `$CMUX_SCRATCH_DIR` 기반 mktemp만 남음 |
| Python compile | `find cmux-orchestrator cmux-watcher cmux-jarvis tests -type f -name '*.py' -not -path '*/referense/*' -print0 \| xargs -0 /usr/bin/python3 -m py_compile` | ✅ pass |
| Shell syntax | `find cmux-orchestrator cmux-watcher cmux-jarvis -type f -name '*.sh' -not -path '*/referense/*' -print0 \| xargs -0 -I{} bash -n {}` | ✅ pass |
| Diff whitespace | `git diff --check` | ✅ pass |
| Focused repeat tests | `for i in 1 2 3 4 5; do /usr/bin/python3 -m pytest tests/test_hooks.py tests/test_cmux_utils.py tests/test_redaction.py -q || exit 1; done` | ✅ 5회 모두 `24 passed` |
| Full tests | `/usr/bin/python3 -m pytest tests -q` | ✅ `80 passed, 532 warnings in 9.11s` |
| Runtime helper simulation | `CMUX_RUNTIME_DIR=<temp> /usr/bin/python3 -c '... from cmux_paths import CMUX_SHIM_REGISTRY_FILE, JARVIS_SCHEDULER_PID_FILE, JARVIS_FILE_CHANGED_DEBOUNCE_FILE ...'` | ✅ all resolved under `<temp>/state` or `<temp>/jarvis` |
| Compat scratch simulation | `CMUX_RUNTIME_DIR=<temp> bash -c 'source cmux-orchestrator/scripts/cmux-paths.sh; ... cmux_compat.py --inline {"cmd":"mktemp"...}; case "$compat_tmp" in "$CMUX_SCRATCH_DIR"/*) ...'` | ✅ `mktemp` output under `<temp>/scratch/` |
| Gate simulation | `CMUX_RUNTIME_DIR=<temp> bash cmux-orchestrator/scripts/gate-checker.sh` | ✅ Gate 1/5/7 pass, leceipts skipped because orchestration inactive |
| Report checker | `test -f verification-kit.config.json && node /Users/csm/.codex/leceipts/scripts/check-reports.ts --config ./verification-kit.config.json || echo 'verification-kit.config.json missing'` | 검증 불가: `verification-kit.config.json` missing |

Key output excerpts:

```text
24 passed in 4.19s
24 passed in 3.68s
24 passed in 3.89s
24 passed in 3.76s
24 passed in 3.92s
80 passed, 532 warnings in 9.11s
GATE 7 PASS: 미정리 워크트리 = 0
compat_tmp=<temp>/scratch/cmux-test-_ffbvrry.json
```

### Unverifiable items

- Real cmux GUI end-to-end dispatch/watch/JARVIS session behavior — 검증 불가: 실제 여러 cmux surface를 생성하고 사용자 GUI 세션을 조작하는 harness는 현재 실행하지 않았다.
- leceipts report checker — 검증 불가: 프로젝트 루트에 `verification-kit.config.json`이 없다.

## 5. Remaining risk / 남은 리스크

- `docs/99-archive/**`는 active 실행 경로가 아니라서 이번 static `/tmp` gate에서 제외했다. 과거 기록 검색 용도로 보존되어 있으며, 실행 문서로 재사용하면 별도 정리가 필요하다.
- 실제 cmux GUI multi-surface E2E는 실행하지 않았다. 현재 검증은 코드/문서 검색, unit tests, hook/runtime helper simulation, Gate checker 수준이다.
- 작업 전부터 worktree에 다수의 수정 파일이 있었다. 이번 보고서는 현재 uncommitted worktree 기준이며 커밋 SHA는 변경 완료 커밋이 아니다.

## DoD Checklist

- [ ] Changed files committed
- [ ] Commit SHA present on base branch
- [x] Build / test suite passed, or unverifiable reason given
- [ ] Result pasted into the ticket/issue comment
