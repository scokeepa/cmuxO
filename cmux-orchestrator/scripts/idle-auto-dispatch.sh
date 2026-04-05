#!/bin/bash
# idle-auto-dispatch.sh — Auto-dispatch queued tasks to matching IDLE cmux surfaces.
#
# Usage:
#   bash idle-auto-dispatch.sh --once
#   bash idle-auto-dispatch.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/workspace-resolver.sh"

EAGLE_WATCHER="${SCRIPT_DIR}/eagle_watcher.sh"
VISION_MONITOR="${SCRIPT_DIR}/vision-monitor.sh"
TASK_QUEUE="${SCRIPT_DIR}/task-queue.sh"
LOG_FILE="/tmp/cmux-auto-dispatch.log"
DISPATCH_LOG="/tmp/cmux-dispatch-log.jsonl"
INTERVAL=15
RUN_ONCE=false
DRY_RUN=false
BATCH_SIZE=4

for arg in "$@"; do
  case "$arg" in
    --once)
      RUN_ONCE=true
      ;;
    --dry-run)
      DRY_RUN=true
      RUN_ONCE=true
      ;;
  esac
done

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log_line() {
  printf '%s\n' "$1" >> "$LOG_FILE"
}

log_dispatch() {
  local timestamp="$1"
  local surface_id="$2"
  local workspace="$3"
  local ai_type="$4"
  local difficulty="$5"
  local task_id="$6"
  local task_desc="$7"

  printf '%s | DISPATCH | surface:%s | workspace:%s | ai:%s | difficulty:%s | task:%s | %s\n' \
    "$timestamp" "$surface_id" "$workspace" "$ai_type" "$difficulty" "$task_id" "$task_desc" >> "$LOG_FILE"
}

log_skip() {
  local timestamp="$1"
  local message="$2"
  printf '%s | SKIP | %s\n' "$timestamp" "$message" >> "$LOG_FILE"
}

log_dispatch_json() {
  local timestamp="$1"
  local surface_id="$2"
  local workspace="$3"
  local ai_type="$4"
  local difficulty="$5"
  local task_id="$6"

  # JSONL format: timestamp, surface, workspace, ai, task, difficulty
  printf '{"timestamp":"%s","surface":"surface:%s","workspace":"%s","ai":"%s","task":"%s","difficulty":"%s"}\n' \
    "$timestamp" "$surface_id" "$workspace" "$ai_type" "$task_id" "$difficulty" >> "$DISPATCH_LOG"
}

check_vision_monitor_ane_idle() {
  local surface_id="$1"

  if [ ! -x "$VISION_MONITOR" ]; then
    echo "true"  # No vision-monitor, allow dispatch
    return 0
  fi

  # Get previous vision-monitor data to check ANE OCR completion
  local prev_file="/tmp/cmux-vision-monitor-prev.json"
  if [ ! -f "$prev_file" ]; then
    echo "true"  # No previous data, allow dispatch
    return 0
  fi

  # Check if surface has recent vision data (ANE OCR completed)
  local last_update
  last_update=$(python3 - "$prev_file" "$surface_id" <<'PY' 2>/dev/null
import json
import sys
from datetime import datetime, timezone

prev_file = sys.argv[1]
target_sid = sys.argv[2]

try:
    with open(prev_file, encoding="utf-8") as f:
        data = json.load(f)

    surfaces = data.get("surfaces", {})
    if target_sid in surfaces:
        last_seen = surfaces[target_sid].get("last_seen", "")
        if last_seen:
            # Parse timestamp and check if recent (within 2 minutes)
            try:
                ts = datetime.strptime(last_seen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age_seconds = (now - ts).total_seconds()
                # ANE OCR data is valid for 2 minutes
                if age_seconds < 120:
                    print("true")
                else:
                    print("false")
            except:
                print("true")
        else:
        print("true")
except:
    print("true")
PY
)

  if [ "$last_update" = "true" ]; then
    return 0
  else
    return 1
  fi
}

get_valid_surfaces_from_config() {
  python3 - "${SCRIPT_DIR}/../config/orchestra-config.json" 2>/dev/null <<'PY'
import json
import sys
config_file = sys.argv[1]
try:
    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)
    surfaces = config.get("surfaces", {})
    print(json.dumps(list(surfaces.keys())))
except Exception:
    print("[]")
PY
}

get_surface_candidates() {
  local status_json="$1"

  # Get list of valid surfaces from config
  local valid_surfaces_json
  valid_surfaces_json=$(get_valid_surfaces_from_config)
  local valid_surfaces
  valid_surfaces=$(printf '%s' "$valid_surfaces_json" | python3 -c "import json,sys; print(' '.join(json.loads(sys.stdin.read())))" 2>/dev/null || echo "")

  python3 - "$status_json" "$valid_surfaces" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
surfaces = payload.get("surfaces", {})
valid_surfaces = set(sys.argv[2].split()) if len(sys.argv) > 2 else set()
priority = {"high": 0, "mid": 1, "low": 2}

def difficulty_for_ai(ai_name: str) -> str:
    normalized = ai_name.strip().lower()
    if normalized == "codex":
        return "high"
    if normalized in {"sonnet", "glm"}:
        return "mid"
    if normalized == "minimax":
        return "low"
    return ""

def sort_key(item):
    sid, info = item
    ai_name = str(info.get("ai", ""))
    difficulty = difficulty_for_ai(ai_name)
    try:
        sid_key = int(str(sid))
    except ValueError:
        sid_key = 10**9
    return (priority.get(difficulty, 99), sid_key)

for sid, info in sorted(surfaces.items(), key=sort_key):
    if str(info.get("status", "")).upper() != "IDLE":
        continue
    # Filter: only dispatch to surfaces defined in orchestra-config
    if valid_surfaces and str(sid) not in valid_surfaces:
        continue
    # Filter: only dispatch if ANE OCR data is recent (vision-monitor check)
    if ! check_vision_monitor_ane_idle "$sid" 2>/dev/null; then
        continue
    ai_name = str(info.get("ai", "")).strip().lower()
    difficulty = difficulty_for_ai(ai_name)
    if not difficulty:
        continue
    print(f"{sid}\t{ai_name}\t{difficulty}")
PY
}

next_task_for_difficulty() {
  local difficulty="$1"
  "$TASK_QUEUE" next "$difficulty" 2>&1 || true
}

parse_task_field() {
  local label="$1"
  local payload="$2"
  printf '%s\n' "$payload" | sed -n "s/^${label}: //p" | head -n 1
}

dispatch_to_surface() {
  local surface_id="$1"
  local task_desc="$2"
  local workspace=""

  # Verify surface exists in tree before dispatching
  if ! cmux tree --all 2>/dev/null | grep -q "surface:${surface_id}"; then
    log_skip "$(timestamp_utc)" "surface:${surface_id} not in cmux tree — skipping dispatch"
    return 1
  fi

  workspace="$(function_resolve_workspace "$surface_id")"

  if [ "$DRY_RUN" = true ]; then
    # Dry-run: log but don't actually dispatch
    printf '[DRY-RUN] Would dispatch to surface:%s workspace:%s - %s\n' \
      "$surface_id" "$workspace" "$task_desc"
  else
    cmux send --workspace "$workspace" --surface "surface:${surface_id}" "$task_desc" >> "$LOG_FILE" 2>&1
    cmux send-key --workspace "$workspace" --surface "surface:${surface_id}" enter >> "$LOG_FILE" 2>&1
    sleep 1  # Prevent socket overload between dispatches
  fi

  printf '%s' "$workspace"
}

dispatch_one_round() {
  local timestamp=""
  local status_json=""
  local pending_count=""
  local candidates=""
  local dispatched_count=0

  timestamp="$(timestamp_utc)"

  if [ ! -x "$EAGLE_WATCHER" ]; then
    log_skip "$timestamp" "missing executable watcher: $EAGLE_WATCHER"
    return 1
  fi

  if [ ! -x "$TASK_QUEUE" ]; then
    log_skip "$timestamp" "missing executable task queue: $TASK_QUEUE"
    return 1
  fi

  status_json="$("$EAGLE_WATCHER" --once 2>>"$LOG_FILE" || true)"
  if [ -z "${status_json//[[:space:]]/}" ]; then
    log_skip "$timestamp" "eagle_watcher produced no JSON"
    return 1
  fi

  pending_count="$("$TASK_QUEUE" count 2>>"$LOG_FILE" || echo "0")"
  if ! [[ "$pending_count" =~ ^[0-9]+$ ]]; then
    pending_count=0
  fi
  if [ "$pending_count" -eq 0 ]; then
    log_skip "$timestamp" "task queue empty"
    return 0
  fi

  candidates="$(get_surface_candidates "$status_json")"
  if [ -z "$candidates" ]; then
    log_skip "$timestamp" "no matching IDLE surfaces"
    return 0
  fi

  while IFS=$'\t' read -r surface_id ai_type difficulty; do
    local task_output=""
    local task_id=""
    local task_desc=""
    local task_diff=""
    local workspace=""

    [ -n "$surface_id" ] || continue

    # Max dispatches limit per batch
    if [ "$dispatched_count" -ge "$BATCH_SIZE" ]; then
      log_skip "$timestamp" "reached batch size limit ($BATCH_SIZE) for this round"
      break
    fi

    task_output="$(next_task_for_difficulty "$difficulty")"
    task_id="$(parse_task_field "ID" "$task_output")"
    task_desc="$(parse_task_field "Task" "$task_output")"
    task_diff="$(parse_task_field "Difficulty" "$task_output")"

    if [ -z "$task_id" ] || [ -z "$task_desc" ]; then
      log_skip "$timestamp" "no ${difficulty} task available for surface:${surface_id} (${ai_type})"
      continue
    fi

    workspace="$(dispatch_to_surface "$surface_id" "$task_desc")"
    log_dispatch "$timestamp" "$surface_id" "$workspace" "$ai_type" "${task_diff:-$difficulty}" "$task_id" "$task_desc"
    log_dispatch_json "$timestamp" "$surface_id" "$workspace" "$ai_type" "${task_diff:-$difficulty}" "$task_id"
    dispatched_count=$((dispatched_count + 1))

    printf '%s | DISPATCHED task:%s (%s) -> surface:%s (%s)\n' \
      "$timestamp" "$task_id" "${task_diff:-$difficulty}" "$surface_id" "$ai_type"
  done <<< "$candidates"

  # Output dispatch count
  printf '%s | ROUND COMPLETE | dispatched:%d | batch_size:%d | dry_run:%s\n' \
    "$timestamp" "$dispatched_count" "$BATCH_SIZE" "$DRY_RUN"

  if [ "$dispatched_count" -eq 0 ]; then
    log_skip "$timestamp" "no matching queued tasks for available IDLE surfaces"
  fi

  # Sleep between batches to prevent socket overload
  if [ "$dispatched_count" -gt 0 ] && [ "$RUN_ONCE" = true ] && [ "$DRY_RUN" = false ]; then
    sleep 5
  fi
}

if [ "$RUN_ONCE" = true ]; then
  dispatch_one_round
else
  while true; do
    dispatch_one_round
    sleep "$INTERVAL"
  done
fi
