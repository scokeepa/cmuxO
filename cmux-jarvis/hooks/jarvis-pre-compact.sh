#!/bin/bash
# jarvis-pre-compact.sh — PreCompact hook
# 역할: compact 직전 진화 컨텍스트 보존 지시 주입 (S9)
# stdout → compact 지시에 추가됨

set -u
cat > /dev/null 2>&1

LOCK_FILE="$HOME/.claude/cmux-jarvis/.evolution-lock"

if [ -f "$LOCK_FILE" ]; then
  EVO_ID=$(jq -r '.evo_id // ""' "$LOCK_FILE" 2>/dev/null)
  NAV_FILE="$HOME/.claude/cmux-jarvis/evolutions/$EVO_ID/nav.md"
  if [ -n "$EVO_ID" ] && [ -f "$NAV_FILE" ]; then
    echo "중요: JARVIS 진화 $EVO_ID 진행 중. 다음 정보를 요약에 반드시 포함하세요:"
    cat "$NAV_FILE"
  fi
fi
