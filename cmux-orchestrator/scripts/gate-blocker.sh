#!/bin/bash
# gate-blocker.sh — PreToolUse hook: WORKING surface 있을 때 커밋 차단
#
# Claude Code PreToolUse hook에서 실행.
# git commit 시도 시 WORKING surface가 있으면 block decision 반환.
#
# stdin: {"tool_name":"Bash","tool_input":{"command":"git commit ..."}}
# stdout: {"decision":"block","reason":"..."} 또는 빈 출력 (허용)

# macOS 호환: timeout이 없으면 직접 실행
if ! command -v timeout &>/dev/null; then
    timeout() { shift; "$@"; }
fi

# cmux 소켓 없으면 무시
[ -S "${CMUX_SOCKET_PATH:-$HOME/Library/Application Support/cmux/cmux.sock}" ] || exit 0

# stdin에서 tool_input 읽기
variable_input=$(cat 2>/dev/null || echo "")
variable_command=$(echo "$variable_input" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('tool_input',{}).get('command',''))
except json.JSONDecodeError as e:
    print('', file=sys.stderr)
    print('')
except Exception:
    print('')
" 2>/dev/null || echo "")

# git commit만 감지 — 다른 모든 명령은 즉시 통과
echo "$variable_command" | grep -qE "^git commit|&&\s*git commit" || exit 0

# === GATE 0: 디스패치 미수집 시 커밋 차단 ===
variable_dispatch_file="/tmp/cmux-dispatch-registry.json"
if [ -f "$variable_dispatch_file" ]; then
    variable_gate0_result=$(DISPATCH_FILE="$variable_dispatch_file" python3 -c "
import json, os, sys
path = os.environ.get('DISPATCH_FILE', '')
if not path or not os.path.isfile(path):
    sys.exit(0)
d = json.load(open(path))
dispatched = d.get('dispatched', {})
pending = [sid for sid, info in dispatched.items() if info.get('status') != 'done']
if pending:
    print('|'.join(pending))
" 2>/dev/null)

    if [ -n "$variable_gate0_result" ]; then
        echo "{\"decision\":\"block\",\"reason\":\"⛔ HARD GATE 0: 미수집 surface 있음 — $variable_gate0_result. 모든 디스패치 결과 수집 전 커밋 금지.\"}"
        exit 0
    fi
fi

# eagle 상태 확인 (WORKING + ERROR + WAITING 모두 차단)
variable_eagle_file="/tmp/cmux-eagle-status.json"
if [ -f "$variable_eagle_file" ]; then
    variable_blocking=$(EAGLE_FILE="$variable_eagle_file" python3 -c "
import json, os, sys
path = os.environ.get('EAGLE_FILE', '')
if not path or not os.path.isfile(path):
    sys.exit(0)
try:
    d = json.load(open(path))
    blocking = []
    for k, v in d.get('surfaces', {}).items():
        st = v.get('status', '')
        if st in ('WORKING', 'ERROR', 'WAITING'):
            blocking.append(f'surface:{k}({st})')
    if blocking:
        print('|'.join(blocking))
except Exception:
    pass
" 2>/dev/null)

    if [ -n "$variable_blocking" ]; then
        echo "{\"decision\":\"block\",\"reason\":\"⛔ GATE 1: 활성 surface 있음 — $variable_blocking. 커밋 전에 모든 surface 완료/처리 필수.\"}"
        exit 0
    fi
fi

# === GATE 2: 코드리뷰 미완료 시 커밋 차단 ===
variable_review_file="/tmp/cmux-review-status.json"
if [ -f "$variable_dispatch_file" ]; then
    # 디스패치가 있었으면 (= 다른 AI가 작업했으면) 리뷰 필수
    variable_review_missing=$(python3 -c "
import json
from pathlib import Path
dispatch = Path('$variable_dispatch_file')
review = Path('$variable_review_file')
if not dispatch.exists():
    exit(0)  # 디스패치 없었으면 리뷰 불필요
d = json.loads(dispatch.read_text())
done_surfaces = [s for s, i in d.get('dispatched',{}).items() if i.get('status')=='done']
if not done_surfaces:
    exit(0)  # 완료된 surface 없으면 리뷰 불필요
# 리뷰 상태 확인
if not review.exists():
    print('NO_REVIEW')
else:
    r = json.loads(review.read_text())
    if r.get('status') not in ('APPROVE','PASS','approved','pass'):
        print(f\"REVIEW_{r.get('status','MISSING')}\")
" 2>/dev/null)

    if [ -n "$variable_review_missing" ]; then
        echo "{\"decision\":\"block\",\"reason\":\"⛔ GATE 2: 코드리뷰 미완료 ($variable_review_missing). cmux surface 작업 후 반드시 검증 에이전트(code-reviewer) 실행 필수. 리뷰 통과 후 커밋 가능.\"}"
        exit 0
    fi
fi

# === GATE 3: FSM — DONE이지만 VERIFIED 아닌 surface 차단 ===
variable_fsm_script="$HOME/.claude/skills/cmux-orchestrator/scripts/surface-fsm.py"
if [ -f "$variable_fsm_script" ] && [ -f "/tmp/cmux-surface-fsm.json" ]; then
    variable_unverified=$(python3 "$variable_fsm_script" unverified 2>/dev/null)
    variable_fsm_exit=$?

    if [ "$variable_fsm_exit" -ne 0 ] && [ -n "$variable_unverified" ]; then
        echo "{\"decision\":\"block\",\"reason\":\"⛔ GATE 3: FSM 미검증 surface 존재. $variable_unverified. DONE surface를 verify 후 커밋 가능 (python3 $variable_fsm_script verify surface:N).\"}"
        exit 0
    fi
fi

# speckit tracker 확인
variable_tracker="/tmp/cmux-speckit-tracker.json"
if [ -f "$variable_tracker" ]; then
    variable_incomplete=$(TRACKER_FILE="$variable_tracker" python3 -c "
import json, os, sys
path = os.environ.get('TRACKER_FILE', '')
if not path or not os.path.isfile(path):
    sys.exit(0)
d = json.load(open(path))
inc = [tid for tid, info in d.get('tasks', {}).items() if info.get('status') not in ('done',)]
if inc:
    print(','.join(inc))
" 2>/dev/null)

    if [ -n "$variable_incomplete" ]; then
        echo "{\"decision\":\"block\",\"reason\":\"⛔ GATE 5: speckit 미완료 태스크 $variable_incomplete. 재배정 후 완료해야 커밋 가능.\"}"
        exit 0
    fi
fi

# 통과
exit 0
