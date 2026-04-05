#!/bin/bash
# jarvis-session-start.sh — SessionStart hook
# matcher: (전체), timeout: 5s
# 역할: JARVIS surface에만 additionalContext + initialUserMessage + watchPaths

ALLOW='{"continue":true,"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":""}}'
ROLES_FILE="/tmp/cmux-roles.json"
INSTRUCTIONS="$HOME/.claude/skills/cmux-jarvis/references/jarvis-instructions.md"
JARVIS_DIR="$HOME/.claude/cmux-jarvis"

# stdin 소비
cat > /dev/null 2>&1

# jq 없으면 pass
command -v jq >/dev/null 2>&1 || { echo "$ALLOW"; exit 0; }

# 오케스트레이션 모드 아니면 pass
[ -f /tmp/cmux-orch-enabled ] || { echo "$ALLOW"; exit 0; }

# roles.json 없거나 jarvis 미등록 → pass
[ -f "$ROLES_FILE" ] || { echo "$ALLOW"; exit 0; }
JARVIS_SID=$(jq -r '.jarvis.surface // ""' "$ROLES_FILE" 2>/dev/null || echo "")
[ -z "$JARVIS_SID" ] && { echo "$ALLOW"; exit 0; }

# 현재 surface 식별 (cmux 환경이 아니면 빈 문자열)
MY_SID=""
if command -v cmux >/dev/null 2>&1; then
  MY_SID=$(cmux identify 2>/dev/null | python3 -c "
import sys,json
try: print(json.load(sys.stdin)['caller']['surface_ref'])
except: print('')
" 2>/dev/null || echo "")
fi

# JARVIS surface가 아니면 → 빈 context
[ "$MY_SID" != "$JARVIS_SID" ] && { echo "$ALLOW"; exit 0; }

# === JARVIS surface → 전체 지시 주입 ===
CONTEXT=""
[ -f "$INSTRUCTIONS" ] && CONTEXT=$(cat "$INSTRUCTIONS")

# 캐시 저장
mkdir -p "$JARVIS_DIR" 2>/dev/null
echo "$CONTEXT" > "$JARVIS_DIR/.session-context-cache.json" 2>/dev/null

# JSON 이스케이프 + 출력
ESCAPED=$(python3 -c "
import sys, json
text = sys.stdin.read()
print(json.dumps(text))
" <<< "$CONTEXT" 2>/dev/null || echo '""')

echo "{\"continue\":true,\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":$ESCAPED,\"initialUserMessage\":\"JARVIS 초기화. eagle-status + watcher-alerts 확인 후 감지 시작.\",\"watchPaths\":[\"/tmp/cmux-eagle-status.json\",\"/tmp/cmux-watcher-alerts.json\"]}}"
