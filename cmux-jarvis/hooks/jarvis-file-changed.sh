#!/bin/bash
# jarvis-file-changed.sh — FileChanged hook
# matcher: cmux-eagle-status.json|cmux-watcher-alerts.json
# timeout: 5s
# 역할: eagle-status/watcher-alerts 변경 즉시 감지 + 디바운싱 60초 (S7+CA-02)

set -u
INPUT_JSON=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

JARVIS_DIR="$HOME/.claude/cmux-jarvis"
METRIC_DICT="$JARVIS_DIR/metric-dictionary.json"
[ -f "$METRIC_DICT" ] || METRIC_DICT="$HOME/.claude/skills/cmux-jarvis/references/metric-dictionary.json"

# 디바운싱 (CA-02): 60초 내 재실행 무시
DEBOUNCE_FILE="/tmp/jarvis-file-changed-last"
NOW=$(date +%s)
PREV=$(cat "$DEBOUNCE_FILE" 2>/dev/null || echo 0)
DEBOUNCE_SEC=$(jq -r '.debounce_seconds // 60' "$JARVIS_DIR/config.json" 2>/dev/null || echo 60)
if [ $((NOW - PREV)) -lt "$DEBOUNCE_SEC" ]; then
  exit 0
fi
echo "$NOW" > "$DEBOUNCE_FILE"

# eagle-status에서 메트릭 수집
EAGLE="/tmp/cmux-eagle-status.json"
[ -f "$EAGLE" ] || exit 0

# 임계값 읽기 (SS-01: metric-dictionary.json에서)
STALL_WARN=$(jq -r '.metrics.stall_count.threshold.warning // 2' "$METRIC_DICT" 2>/dev/null || echo 2)
ERROR_WARN=$(jq -r '.metrics.error_count.threshold.warning // 1' "$METRIC_DICT" 2>/dev/null || echo 1)
ENDED_WARN=$(jq -r '.metrics.ended_count.threshold.warning // 1' "$METRIC_DICT" 2>/dev/null || echo 1)

# 현재 수치
STALL=$(jq -r '.stats.stalled // 0' "$EAGLE")
ERROR=$(jq -r '.stats.error // 0' "$EAGLE")
ENDED=$(jq -r '.stats.ended // 0' "$EAGLE")
IDLE=$(jq -r '.stats.idle // 0' "$EAGLE")
WORKING=$(jq -r '.stats.working // 0' "$EAGLE")
TOTAL=$(jq -r '.stats.total // 0' "$EAGLE")

# 임계값 초과 체크
EXCEEDED=false
ALERT_MSG=""
[ "$STALL" -ge "$STALL_WARN" ] 2>/dev/null && EXCEEDED=true && ALERT_MSG="${ALERT_MSG}STALL:$STALL "
[ "$ERROR" -ge "$ERROR_WARN" ] 2>/dev/null && EXCEEDED=true && ALERT_MSG="${ALERT_MSG}ERROR:$ERROR "
[ "$ENDED" -ge "$ENDED_WARN" ] 2>/dev/null && EXCEEDED=true && ALERT_MSG="${ALERT_MSG}ENDED:$ENDED "

if [ "$EXCEEDED" = "true" ]; then
  # 임계 초과 → JARVIS 컨텍스트에 주입
  MSG="⚠ ${ALERT_MSG}IDLE:$IDLE WORKING:$WORKING (총 $TOTAL) — 임계 초과. 분석 필요."
  ESCAPED=$(python3 -c "import json;print(json.dumps('$MSG'))" 2>/dev/null || echo "\"$MSG\"")
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"FileChanged\",\"additionalContext\":$ESCAPED}}"
else
  # 정상 → 무소음
  exit 0
fi
