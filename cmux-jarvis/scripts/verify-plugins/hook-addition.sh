#!/bin/bash
# verify-plugins/hook-addition.sh — hook_change 유형 전용 검증
EVO_ID="${1:?}"
EVO_DIR="$HOME/.claude/cmux-jarvis/evolutions/$EVO_ID"

# file-mapping에서 hook 파일 경로 추출
HOOK_FILES=$(jq -r 'to_entries[] | select(.value | contains("hooks/")) | .key' "$EVO_DIR/file-mapping.json" 2>/dev/null)

for hf in $HOOK_FILES; do
  PROPOSED="$EVO_DIR/$hf"
  [ ! -f "$PROPOSED" ] && echo "✗ hook 파일 없음: $hf" && exit 1
  # 실행 가능 여부
  head -1 "$PROPOSED" | grep -q "^#!" || echo "⚠ shebang 없음: $hf"
  # JSON 출력 테스트 (빈 입력)
  OUTPUT=$(echo '{}' | bash "$PROPOSED" 2>/dev/null || echo "")
  if [ -n "$OUTPUT" ]; then
    echo "$OUTPUT" | python3 -c "import json,sys;json.load(sys.stdin)" 2>/dev/null
    [ $? -ne 0 ] && echo "✗ hook JSON 출력 유효하지 않음: $hf" && exit 1
  fi
done

echo "✓ hook-addition 플러그인 검증 통과"
