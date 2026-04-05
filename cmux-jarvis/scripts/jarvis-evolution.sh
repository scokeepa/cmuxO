#!/bin/bash
# jarvis-evolution.sh — JARVIS 진화 CLI
# Usage: jarvis-evolution.sh <detect|backup|apply|rollback|status|cleanup|lock-phase> [evo-id] [args]

set -euo pipefail

JARVIS_DIR="$HOME/.claude/cmux-jarvis"
LOCK_FILE="$JARVIS_DIR/.evolution-lock"
COUNTER_FILE="$JARVIS_DIR/.evolution-counter"
CONFIG="$JARVIS_DIR/config.json"
SETTINGS="$HOME/.claude/settings.json"
METRIC_DICT="$HOME/.claude/skills/cmux-jarvis/references/metric-dictionary.json"

mkdir -p "$JARVIS_DIR/evolutions"

# --- config 읽기 ---
get_config() { jq -r ".$1 // \"$2\"" "$CONFIG" 2>/dev/null || echo "$2"; }
MAX_CONSECUTIVE=$(get_config max_consecutive_evolutions 3)
MAX_DAILY=$(get_config max_daily_evolutions 10)
LOCK_TTL=$(get_config lock_ttl_minutes 60)

case "${1:-help}" in

detect)
  # eagle-status에서 메트릭 읽기 + 임계값 비교
  EAGLE="/tmp/cmux-eagle-status.json"
  [ ! -f "$EAGLE" ] && echo '{"threshold_exceeded":false,"reason":"eagle-status 없음"}' && exit 0

  python3 -c "
import json
eagle = json.load(open('$EAGLE'))
metrics = json.load(open('$METRIC_DICT'))
stats = eagle.get('stats', {})
exceeded = []
for name, cfg in metrics.get('metrics', {}).items():
    key = name.replace('_count', '')
    val = stats.get(key, 0)
    warn = cfg.get('threshold', {}).get('warning', 0)
    if warn > 0 and val >= warn:
        exceeded.append({'metric': name, 'value': val, 'warning': warn})
result = {'threshold_exceeded': len(exceeded) > 0, 'exceeded': exceeded, 'stats': stats}
print(json.dumps(result, indent=2))
" 2>/dev/null || echo '{"threshold_exceeded":false,"reason":"파싱 오류"}'
  ;;

backup)
  EVO_ID="${2:?evo-id 필요}"
  EVO_DIR="$JARVIS_DIR/evolutions/$EVO_ID"
  mkdir -p "$EVO_DIR/backup"

  # 안전 체크
  TODAY=$(date +%Y-%m-%d)
  CONSECUTIVE=$(jq -r '.consecutive // 0' "$COUNTER_FILE" 2>/dev/null || echo 0)
  DAILY=$(jq -r ".daily[\"$TODAY\"] // 0" "$COUNTER_FILE" 2>/dev/null || echo 0)

  if [ "$CONSECUTIVE" -ge "$MAX_CONSECUTIVE" ]; then
    echo "WARNING: 연속 $CONSECUTIVE회. 사용자 확인 필요." >&2
    exit 1
  fi
  if [ "$DAILY" -ge "$MAX_DAILY" ]; then
    echo "ERROR: 일일 상한 $MAX_DAILY 도달." >&2
    exit 2
  fi

  # CURRENT_LOCK 체크
  if [ -f "$LOCK_FILE" ]; then
    # TTL 체크
    CREATED=$(jq -r '.created_at // ""' "$LOCK_FILE" 2>/dev/null)
    if [ -n "$CREATED" ]; then
      CREATED_EPOCH=$(python3 -c "from datetime import datetime;print(int(datetime.fromisoformat('$CREATED'.replace('Z','+00:00')).timestamp()))" 2>/dev/null || echo 0)
      NOW_EPOCH=$(date +%s)
      AGE_MIN=$(( (NOW_EPOCH - CREATED_EPOCH) / 60 ))
      if [ "$AGE_MIN" -gt "$LOCK_TTL" ]; then
        echo "WARNING: stale lock ($AGE_MIN분). 해제." >&2
        rm -f "$LOCK_FILE"
      else
        echo "ERROR: 진화 진행 중 ($(jq -r '.evo_id' "$LOCK_FILE")). 큐에 추가하세요." >&2
        exit 3
      fi
    fi
  fi

  # 백업 (2세대)
  [ -f "$EVO_DIR/backup/settings.json" ] && mv "$EVO_DIR/backup/settings.json" "$EVO_DIR/backup/settings.json.prev"
  cp "$SETTINGS" "/tmp/jarvis-backup-$$.json"
  mv "/tmp/jarvis-backup-$$.json" "$EVO_DIR/backup/settings.json"

  # LOCK 생성
  cat > "$LOCK_FILE" << LOCK
{
  "evo_id": "$EVO_ID",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "ttl_minutes": $LOCK_TTL,
  "phase": "planning",
  "surface_id": "jarvis"
}
LOCK

  # /freeze warn 활성화
  echo "warn" > /tmp/cmux-jarvis-freeze-mode

  # before-metrics 수집
  python3 -c "
import json
eagle = json.load(open('/tmp/cmux-eagle-status.json'))
metrics = {k: eagle.get('stats', {}).get(k, 0) for k in ['stalled','error','idle','working','ended','total']}
metrics['timestamp'] = eagle.get('timestamp', '')
metrics['stalled_surfaces'] = eagle.get('stalled_surfaces', '')
metrics['error_surfaces'] = eagle.get('error_surfaces', '')
with open('$EVO_DIR/before-metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
" 2>/dev/null

  echo "OK: $EVO_ID 백업 완료. LOCK 생성."
  ;;

apply)
  EVO_ID="${2:?evo-id 필요}"
  EVO_DIR="$JARVIS_DIR/evolutions/$EVO_ID"
  PROPOSED="$EVO_DIR/proposed-settings.json"

  [ ! -f "$PROPOSED" ] && echo "ERROR: proposed-settings.json 없음" >&2 && exit 1
  [ ! -f "$EVO_DIR/evidence.json" ] && echo "ERROR: evidence.json 없음" >&2 && exit 1
  [ ! -f "$LOCK_FILE" ] && echo "ERROR: CURRENT_LOCK 없음" >&2 && exit 1

  # E4 방어: proposed에 hooks 키 포함 시 거부
  if jq -e '.hooks' "$PROPOSED" >/dev/null 2>&1; then
    echo "ERROR: proposed에 hooks 키 포함. 기존 hooks 덮어쓰기 위험. 거부." >&2
    exit 1
  fi

  # LOCK phase를 applying으로 변경 (gate.sh 3조건 충족)
  jq --arg p "applying" '.phase = $p' "$LOCK_FILE" > "/tmp/lock-$$.json" && mv "/tmp/lock-$$.json" "$LOCK_FILE"

  # jq deep merge + 원자적 쓰기
  jq -s '.[0] * .[1]' "$SETTINGS" "$PROPOSED" > "/tmp/jarvis-merge-$$.json"
  mv "/tmp/jarvis-merge-$$.json" "$SETTINGS"

  # /freeze 해제
  rm -f /tmp/cmux-jarvis-freeze-mode

  # LOCK 해제
  rm -f "$LOCK_FILE"

  # counter 업데이트
  TODAY=$(date +%Y-%m-%d)
  CONSECUTIVE=$(jq -r '.consecutive // 0' "$COUNTER_FILE" 2>/dev/null || echo 0)
  DAILY=$(jq -r ".daily[\"$TODAY\"] // 0" "$COUNTER_FILE" 2>/dev/null || echo 0)
  python3 -c "
import json
counter = {'consecutive': $((CONSECUTIVE + 1)), 'daily': {'$TODAY': $((DAILY + 1))}}
with open('$COUNTER_FILE', 'w') as f: json.dump(counter, f)
"
  echo "OK: $EVO_ID 반영 완료."
  ;;

rollback)
  EVO_ID="${2:?evo-id 필요}"
  EVO_DIR="$JARVIS_DIR/evolutions/$EVO_ID"
  BACKUP="$EVO_DIR/backup/settings.json"

  [ ! -f "$BACKUP" ] && echo "ERROR: 백업 없음" >&2 && exit 1

  cp "$BACKUP" "/tmp/jarvis-restore-$$.json"
  mv "/tmp/jarvis-restore-$$.json" "$SETTINGS"
  rm -f "$LOCK_FILE"
  rm -f /tmp/cmux-jarvis-freeze-mode

  # consecutive 리셋 (롤백은 실패이므로)
  python3 -c "
import json
counter = {'consecutive': 0, 'daily': $(jq '.daily // {}' "$COUNTER_FILE" 2>/dev/null || echo '{}')}
with open('$COUNTER_FILE', 'w') as f: json.dump(counter, f)
" 2>/dev/null

  echo "OK: $EVO_ID 롤백 완료."
  ;;

status)
  echo "{"
  echo "  \"lock\": $([ -f "$LOCK_FILE" ] && cat "$LOCK_FILE" || echo 'null'),"
  echo "  \"counter\": $([ -f "$COUNTER_FILE" ] && cat "$COUNTER_FILE" || echo '{}'),"
  echo "  \"queue\": $([ -f "$JARVIS_DIR/evolution-queue.json" ] && cat "$JARVIS_DIR/evolution-queue.json" || echo '[]')"
  echo "}"
  ;;

cleanup)
  EVO_ID="${2:?evo-id 필요}"
  rm -f /tmp/cmux-jarvis-worker-*
  rm -f "/tmp/cmux-jarvis-$EVO_ID-done"
  echo "OK: $EVO_ID 정리 완료."
  ;;

lock-phase)
  EVO_ID="${2:?evo-id 필요}"
  PHASE="${3:?phase 필요 (planning|implementing|applying)}"
  [ ! -f "$LOCK_FILE" ] && echo "ERROR: LOCK 없음" >&2 && exit 1
  jq --arg p "$PHASE" '.phase = $p' "$LOCK_FILE" > "/tmp/lock-$$.json" && mv "/tmp/lock-$$.json" "$LOCK_FILE"
  echo "OK: phase=$PHASE"
  ;;

help|*)
  echo "Usage: jarvis-evolution.sh <detect|backup|apply|rollback|status|cleanup|lock-phase> [evo-id] [args]"
  ;;
esac
