# cmux Runtime Dir Phase 1 Verification Report

## 1. 문제 원인

legacy temp control-plane 파일들이 런타임 control-plane SSOT처럼 사용되고 있었다. temp 디렉터리는 사용자 로컬 설정/상태의 장기 저장 위치가 아니며, producer와 consumer가 하드코딩 경로를 각자 들고 있어 일부만 옮기면 hook 활성화, watcher cache 주입, role authority 검증이 서로 갈라진다.

## 2. 수정 내용

- `cmux-orchestrator/scripts/cmux_paths.py`와 `cmux-orchestrator/scripts/cmux-paths.sh`를 추가해 `CMUX_RUNTIME_DIR` override와 기본 runtime dir을 한 곳에서 계산하도록 했다.
- 1단계 대상 control-plane 파일을 resolver로 이관했다: orchestration flag, roles, surface map, surface scan, eagle status, watcher alerts.
- Python hooks/scripts는 `cmux_paths.py`의 `ORCH_FLAG`, `ROLES_FILE`, `SURFACE_MAP_FILE`, `SURFACE_SCAN_FILE`, `EAGLE_STATUS_FILE`, `WATCHER_ALERTS_FILE`을 사용하도록 바꿨다.
- Shell hooks/scripts는 `cmux-paths.sh`를 source하고 `$CMUX_*` 경로를 사용하도록 바꿨다.
- `/cmux-start`, `/cmux-stop`, architecture docs, active references를 1단계 runtime path 기준으로 갱신했다.
- `tests/test_hooks.py`는 `CMUX_RUNTIME_DIR` 임시 디렉터리 override를 사용해 새 runtime path에서 hook 동작을 검증하도록 바꿨다.

## 3. 재발 방지 조치

- 새 runtime 파일을 추가할 때는 `cmux_paths.py` 또는 `cmux-paths.sh`에 상수를 추가하고 소비자는 helper만 참조한다.
- 1단계 범위 밖의 transient/scratch 파일은 이번 변경에서 섞지 않았다. 다음 단계에서 `cmux-dispatch-pending.json`, `cmux-workflow-state.json`, socket/pid/screenshot/OCR 파일을 별도 분류 후 이관한다.
- 테스트가 `CMUX_RUNTIME_DIR` override를 사용하므로 `CMUX_ORCH_FLAG`만으로 hook이 활성화되는지 회귀 검출할 수 있다.

## 4. 검증 결과

- `python3 -m pytest tests/test_hooks.py -q` → `6 passed in 2.30s`
- `find cmux-orchestrator cmux-watcher cmux-jarvis tests -name '*.py' -print0 | xargs -0 python3 -m py_compile` → 통과
- `find cmux-orchestrator cmux-watcher cmux-jarvis cmux-start cmux-stop -name '*.sh' -print0 | xargs -0 bash -n` → 통과
- `CMUX_RUNTIME_DIR=<temp> ... bash cmux-orchestrator/hooks/cmux-main-context.sh` → runtime dir의 `cmux-orch-enabled`, `cmux-roles.json`, `cmux-surface-scan.json`만으로 `/cmux` context 주입 확인
- `CMUX_RUNTIME_DIR=<temp> ... python3 cmux-orchestrator/hooks/cmux-control-tower-guard.py` → runtime dir의 `cmux-roles.json`만으로 control tower close 차단 확인
- `python3 -m pytest tests -q` → `79 passed, 532 warnings in 7.02s`
- `git diff --check` → 통과
- legacy temp control-plane 경로 검색 → active 코드/문서에서 남은 항목은 `tests/test_redaction.py`의 경로 문자열 보존 fixture 1건뿐
- `bash cmux-orchestrator/scripts/validate-config.sh` (cmux socket 접근을 위해 승인된 escalated 실행) → exit `0`, `errors: []`, warnings: `surface-map.json not found`, `orphan surfaces: surface:3, surface:4`

## 5. 남은 리스크 또는 확인 필요 사항

- `docs/99-archive/**`에는 과거 설계 기록의 legacy temp cmux 참조가 남아 있었다. 실행 경로가 아니므로 1단계에서는 변경하지 않았다.
- hook-local transient 파일과 scratch 파일은 2단계에서 runtime SSOT로 이관됐다. 이 보고서는 1단계 당시의 잔여 리스크 기록이며, 현재 상태는 `plans/cmux-runtime-dir-phase2-verification-report.md`와 이후 phase 보고서를 따른다.
- 실제 `/cmux-start`와 `/cmux-stop`의 전체 cmux GUI 세션 동작은 로컬 cmux socket/GUI 상태가 필요하므로 이번 보고서에서는 `검증 불가`다. 대신 helper-level 경로 계산과 hook-level 시뮬레이션, 전체 pytest를 수행했다.
