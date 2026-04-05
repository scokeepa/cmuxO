#!/bin/bash
# jarvis-post-compact.sh — PostCompact hook
# 역할: compact 후 현재 진화 nav.md 재주입

set -u
cat > /dev/null 2>&1

LOCK_FILE="$HOME/.claude/cmux-jarvis/.evolution-lock"

if [ -f "$LOCK_FILE" ]; then
  EVO_ID=$(jq -r '.evo_id // ""' "$LOCK_FILE" 2>/dev/null)
  NAV_FILE="$HOME/.claude/cmux-jarvis/evolutions/$EVO_ID/nav.md"
  if [ -n "$EVO_ID" ] && [ -f "$NAV_FILE" ]; then
    NAV_CONTENT=$(cat "$NAV_FILE")
    ESCAPED=$(python3 -c "import json,sys;print(json.dumps(sys.stdin.read()))" <<< "$NAV_CONTENT" 2>/dev/null || echo "\"\"")
    echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PostCompact\",\"additionalContext\":$ESCAPED}}"
    exit 0
  fi
fi

echo '{"continue":true}'
