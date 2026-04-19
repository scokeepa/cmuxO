# cmux Hook Runtime SSOT Verification Report

## 1. 문제 원인

- Orchestrator hook들이 repo sibling `scripts`가 아니라 설치본 `~/.claude/skills/cmux-orchestrator/scripts`를 우선 import하여, repo의 `is_boss_surface()`와 설치본의 `is_main_surface()`가 충돌했다.
- `tests/test_hooks.py`가 hook 실패를 `FAIL`로 출력만 하고 pytest 실패로 올리지 않아 import 회귀를 숨겼다.
- watcher notify enforcer는 `cmux set-buffer`만 dispatch pending으로 추적했지만, workflow state machine과 문서는 `cmux send`를 dispatch 경로로 정의했다.
- watcher heartbeat는 현재 로컬에 없는 plugin 경로의 `role-register.sh`만 확인했다.
- watcher 프로토콜 문서에는 `BOSS_DOWN`, 코드에는 `BOSS_DEAD`가 남아 enum SSOT가 갈라졌다.
- `validate-config.sh`는 control tower 제외를 runtime role/surface-map이 아니라 legacy config 기반으로 계산해 orphan surface 경고를 과하게 만들었다.

## 2. 수정 내용

- `cmux-orchestrator/hooks/*.py`의 cmux helper import를 repo sibling `../scripts` 우선으로 변경했다.
- `tests/test_hooks.py`에 fake `cmux identify` + `CMUX_ROLES_FILE` Boss fixture를 추가하고, 실패 출력 후 통과하던 예외 처리 구조를 실제 assertion 실패로 변경했다.
- `cmux-watcher-notify-enforcer.py`가 `cmux send`와 `cmux set-buffer`를 모두 dispatch로 추적하고, `cmux send-key`는 제외하도록 변경했다.
- `cmux-workflow-state-machine.py`도 `cmux send-key`를 dispatch로 오인하지 않도록 `cmux send(?!-)` 감지로 변경했다.
- `watcher-scan.py`의 `role-register.sh` 경로를 canonical `~/.claude/skills/...` 우선, plugin 경로 fallback으로 변경했다.
- watcher 문서 enum을 `BOSS_DEAD`로 통일했다.
- `validate-config.sh`의 control tower 제외를 `CMUX_ROLES_FILE` 우선, `CMUX_SURFACE_MAP_FILE` 보조, legacy config 최후 fallback으로 변경했다.

## 3. 재발 방지 조치

- hook 테스트가 `FAIL` 텍스트를 출력하고도 통과하지 못하도록 assertion 기반으로 강화했다.
- `test_watcher_notify_tracks_cmux_send`를 추가해 `cmux send` pending 생성, watcher 알림 해소, `cmux send-key` 제외를 고정했다.
- import 경로가 설치본 drift에 의존하지 않도록 hook 파일 위치 기준으로 helper 모듈을 로드한다.
- 문서/코드 enum을 `BOSS_DEAD`로 정렬했다.

## 4. 검증 결과

- `python3 -m pytest tests/test_hooks.py -q` → `6 passed in 2.00s`
- `python3 tests/test_hooks.py` → `=== ALL PASSED ===`
- `python3 -m pytest tests -q` → `79 passed, 532 warnings in 6.66s`
- `find cmux-orchestrator cmux-watcher cmux-jarvis tests -name '*.py' -print0 | xargs -0 python3 -m py_compile` → 통과
- `find cmux-orchestrator cmux-watcher cmux-jarvis cmux-start -name '*.sh' -print0 | xargs -0 bash -n` → 통과
- `bash cmux-orchestrator/scripts/validate-config.sh` → JSON 출력, `errors: []`, warning `orphan surfaces (no department): surface:4`
- `rg -n "BOSS_DOWN|sys\\.path\\.insert\\(0, os\\.path\\.expanduser\\(\\"~/.claude/skills/cmux-orchestrator/scripts\\"\\)\\)" cmux-orchestrator/hooks cmux-watcher cmux-orchestrator/scripts -S` → 매칭 없음
- leceipts report checker → 검증 불가: 프로젝트 루트에 `verification-kit.config.json`이 없음

## 5. 남은 리스크 또는 확인 필요 사항

- `CMUX_ROLES_FILE`이 없는 현재 로컬 상태에서는 `validate-config.sh`가 `surface:4`를 department/control tower 어디에도 속하지 않은 surface로 경고한다. 실제 역할이면 `CMUX_ROLES_FILE` 또는 `CMUX_SURFACE_MAP_FILE`의 control tower 필드를 생성하는 bootstrap 경로를 별도로 확인해야 한다.
