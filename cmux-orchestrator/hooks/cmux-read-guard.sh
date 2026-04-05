#!/bin/bash
# cmux-read-guard.sh — PreToolUse hook
# cmux read-screen/send/send-key/paste-buffer에 --workspace 누락 시 자동 주입
# 같은 workspace면 그냥 허용, 다른 workspace면 --workspace 자동 추가
# workspace 해석 실패 시에만 차단 (fallback)

# 오케스트레이션 모드 아니면 패스
[ -f /tmp/cmux-orch-enabled ] || { echo '{"decision":"allow"}'; exit 0; }
# cmux 환경 아니면 패스
[ -n "${CMUX_WORKSPACE_ID:-}" ] || { echo '{"decision":"allow"}'; exit 0; }

# stdin에서 hook payload 읽기
PAYLOAD=$(cat)

TOOL_NAME=$(echo "$PAYLOAD" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('tool_name',''))" 2>/dev/null)
[ "$TOOL_NAME" = "Bash" ] || { echo '{"decision":"allow"}'; exit 0; }

COMMAND=$(echo "$PAYLOAD" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('tool_input',{}).get('command',''))" 2>/dev/null)

# cmux read-screen 또는 cmux send/send-key/paste-buffer가 아니면 패스
echo "$COMMAND" | grep -qE "cmux (read-screen|capture-pane|send |send-key |paste-buffer )" || { echo '{"decision":"allow"}'; exit 0; }

# --workspace가 이미 포함되어 있으면 OK
echo "$COMMAND" | grep -q "\-\-workspace" && { echo '{"decision":"allow"}'; exit 0; }

# read-surface.sh를 사용하고 있으면 OK (이미 workspace 자동 해석)
echo "$COMMAND" | grep -q "read-surface.sh" && { echo '{"decision":"allow"}'; exit 0; }

# detect-surface-models.py를 사용하고 있으면 OK
echo "$COMMAND" | grep -q "detect-surface-models" && { echo '{"decision":"allow"}'; exit 0; }

# target surface 추출
TARGET_SF=$(echo "$COMMAND" | grep -oE 'surface:[0-9]+' | head -1)

# surface가 없으면 (cmux tree --all 같은 명령) 그냥 허용
[ -z "$TARGET_SF" ] && { echo '{"decision":"allow"}'; exit 0; }

# === workspace 해석 함수 ===
function_resolve_workspace() {
    local variable_surface="$1"  # surface:N

    # 방법 1: /tmp/cmux-surface-scan.json에서 조회 (빠름)
    local variable_scan_file="/tmp/cmux-surface-scan.json"
    if [ -f "$variable_scan_file" ]; then
        local variable_ws
        variable_ws=$(python3 -c "
import json, sys
data = json.load(open('$variable_scan_file'))
info = data.get('surfaces', {}).get('$variable_surface', {})
ws = info.get('workspace', '')
if ws:
    print(ws)
" 2>/dev/null)
        if [ -n "$variable_ws" ]; then
            echo "$variable_ws"
            return 0
        fi
    fi

    # 방법 2: cmux tree --all에서 동적 해석
    local variable_ws_from_tree
    variable_ws_from_tree=$(cmux tree --all 2>/dev/null | python3 -c "
import sys, re
tree = sys.stdin.read()
target = '$variable_surface'
current_ws = ''
for line in tree.splitlines():
    wm = re.search(r'workspace:\d+', line)
    if wm: current_ws = wm.group(0)
    if target in line and current_ws:
        print(current_ws)
        break
" 2>/dev/null)
    if [ -n "$variable_ws_from_tree" ]; then
        echo "$variable_ws_from_tree"
        return 0
    fi

    return 1
}

# 현재 내 workspace 확인
MY_WS=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['workspace_ref'])" 2>/dev/null)

# target의 workspace 해석
TARGET_WS=$(function_resolve_workspace "$TARGET_SF")

if [ -z "$TARGET_WS" ]; then
    # workspace 해석 실패 시에만 차단 (fallback)
    ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"
    cat << JSON
{"decision":"block","reason":"cmux --workspace 자동 주입 실패: $TARGET_SF 의 workspace를 해석할 수 없음. cmux-surface-scan.json 및 cmux tree --all 모두 실패.\n대안: bash $ORCH_DIR/scripts/read-surface.sh N --lines 20"}
JSON
    exit 0
fi

# 같은 workspace면 그냥 허용 (workspace 추가 불필요)
if [ "$TARGET_WS" = "$MY_WS" ]; then
    echo '{"decision":"allow"}'
    exit 0
fi

# 다른 workspace → --workspace 자동 주입하여 명령어 수정
# 각 cmux 서브명령어 앞에 --workspace를 삽입
MODIFIED_COMMAND=$(echo "$COMMAND" | TARGET_WS="$TARGET_WS" python3 -c "
import re, sys, os
cmd = sys.stdin.read().strip()
ws = os.environ.get('TARGET_WS', '')

# cmux <subcommand> 패턴 뒤에 --workspace 삽입
# 'cmux read-screen', 'cmux send', 'cmux send-key', 'cmux paste-buffer', 'cmux capture-pane'
def inject_ws(m):
    return m.group(0) + ' --workspace ' + ws

result = re.sub(
    r'cmux\s+(read-screen|capture-pane|send(?:-key)?|paste-buffer)',
    inject_ws,
    cmd
)
print(result)
" 2>/dev/null)

if [ -z "$MODIFIED_COMMAND" ] || [ "$MODIFIED_COMMAND" = "$COMMAND" ]; then
    # 수정 실패 시 차단
    cat << JSON
{"decision":"block","reason":"cmux --workspace 자동 주입 실패: 명령어 파싱 오류. --workspace $TARGET_WS 를 수동 추가하세요."}
JSON
    exit 0
fi

# tool_input 수정하여 반환 — allow + 수정된 command
# 환경변수로 전달하여 셸 이스케이프 문제 방지
CMUX_MODIFIED_CMD="$MODIFIED_COMMAND" python3 -c "
import json, os
cmd = os.environ.get('CMUX_MODIFIED_CMD', '')
result = {
    'decision': 'allow',
    'tool_input': {
        'command': cmd
    }
}
print(json.dumps(result, ensure_ascii=False))
" 2>/dev/null || echo '{"decision":"allow"}'
