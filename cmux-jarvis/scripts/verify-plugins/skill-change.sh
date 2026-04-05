#!/bin/bash
# verify-plugins/skill-change.sh — skill_change 유형 전용 검증
EVO_ID="${1:?}"
EVO_DIR="$HOME/.claude/cmux-jarvis/evolutions/$EVO_ID"

# file-mapping에서 SKILL.md 경로 추출
SKILL_FILES=$(jq -r 'to_entries[] | select(.value | contains("SKILL.md")) | .key' "$EVO_DIR/file-mapping.json" 2>/dev/null)

for sf in $SKILL_FILES; do
  PROPOSED="$EVO_DIR/$sf"
  [ ! -f "$PROPOSED" ] && echo "✗ SKILL 파일 없음: $sf" && exit 1
  # YAML frontmatter 체크
  head -1 "$PROPOSED" | grep -q "^---" || { echo "✗ frontmatter 없음: $sf"; exit 1; }
  grep -q "^name:" "$PROPOSED" || { echo "✗ name: 필드 없음: $sf"; exit 1; }
done

echo "✓ skill-change 플러그인 검증 통과"
