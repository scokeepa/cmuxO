#!/bin/bash
# cmux-gate6-agent-block.sh — PreToolUse hook (GATE 6 L0화)
# IDLE cmux surface가 있으면 Agent(Explore/impl-worker/search-worker 등) 물리 차단
# → cmux send로 해당 surface에 위임 강제

# 오케스트레이션 모드 아니면 패스
[ -f /tmp/cmux-orch-enabled ] || { echo '{"decision":"allow"}'; exit 0; }
# cmux 환경 아니면 패스
[ -n "${CMUX_WORKSPACE_ID:-}" ] || { echo '{"decision":"allow"}'; exit 0; }

PAYLOAD=$(cat)
TOOL_NAME=$(echo "$PAYLOAD" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('tool_name',''))" 2>/dev/null)

# Agent 도구만 검사
[ "$TOOL_NAME" = "Agent" ] || { echo '{"decision":"allow"}'; exit 0; }

AGENT_TYPE=$(echo "$PAYLOAD" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('tool_input',{}).get('subagent_type',''))" 2>/dev/null)

# 허용 에이전트 (코드리뷰, cmux 전용)
ALLOWED="code-reviewer code-reviewer-pro cmux-git cmux-security cmux-reviewer momus"
for a in $ALLOWED; do
    [ "$AGENT_TYPE" = "$a" ] && { echo '{"decision":"allow"}'; exit 0; }
done

# IDLE surface 확인 (eagle 또는 scan 캐시)
IDLE_COUNT=0
SCAN_FILE="/tmp/cmux-surface-scan.json"
EAGLE_FILE="/tmp/cmux-eagle-status.json"

if [ -f "$SCAN_FILE" ]; then
    IDLE_COUNT=$(python3 -c "
import json, os, time
f = '$SCAN_FILE'
if os.path.exists(f) and (time.time() - os.path.getmtime(f)) < 300:
    d = json.load(open(f))
    print(sum(1 for s in d.get('surfaces',{}).values() if s.get('status') == 'IDLE'))
else:
    print(0)
" 2>/dev/null)
elif [ -f "$EAGLE_FILE" ]; then
    IDLE_COUNT=$(python3 -c "
import json
d = json.load(open('$EAGLE_FILE'))
print(d.get('stats',{}).get('idle',0))
" 2>/dev/null)
fi

[ "${IDLE_COUNT:-0}" -eq 0 ] && { echo '{"decision":"allow"}'; exit 0; }

# IDLE surface가 있으면 차단
python3 -c "
import json
msg = 'GATE 6 (L0): IDLE surface ${IDLE_COUNT}개 존재. Agent(${AGENT_TYPE}) 차단. cmux send로 IDLE surface에 위임하세요.'
print(json.dumps({'decision': 'block', 'reason': msg}, ensure_ascii=False))
"
