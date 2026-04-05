#!/bin/bash
# verify-plugins/settings-change.sh — settings_change 유형 전용 검증
EVO_ID="${1:?}"
EVO_DIR="$HOME/.claude/cmux-jarvis/evolutions/$EVO_ID"
PROPOSED="$EVO_DIR/proposed-settings.json"

# 1. proposed가 현재 settings.json에 merge 가능한지 dry-run
jq -s '.[0] * .[1]' "$HOME/.claude/settings.json" "$PROPOSED" > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "✗ jq merge 실패"
  exit 1
fi

# 2. merge 결과가 유효한 JSON인지
MERGED=$(jq -s '.[0] * .[1]' "$HOME/.claude/settings.json" "$PROPOSED" 2>/dev/null)
echo "$MERGED" | python3 -c "import json,sys;json.load(sys.stdin)" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "✗ merge 결과 JSON 유효하지 않음"
  exit 1
fi

echo "✓ settings-change 플러그인 검증 통과"
