#!/bin/bash
# eagle-summary.sh — Run eagle_watcher and produce a clean status table.
#
# Usage:
#   bash eagle-summary.sh           # Full table
#   bash eagle-summary.sh --brief   # One-line summary only

set -u

variable_script_dir="$(cd "$(dirname "$0")" && pwd)"
variable_brief=false

for variable_arg in "$@"; do
  case "$variable_arg" in
    --brief) variable_brief=true ;;
  esac
done

# Run eagle_watcher --once and capture JSON
variable_eagle_json=$(bash "${variable_script_dir}/eagle_watcher.sh" --once 2>/dev/null)

if [ -z "$variable_eagle_json" ]; then
  echo "ERROR: eagle_watcher produced no output" >&2
  exit 1
fi

# Write JSON to temp file, pass to Python via file path
variable_tmp_json=$(mktemp /tmp/eagle-summary.XXXXXX.json)
printf '%s' "$variable_eagle_json" > "$variable_tmp_json"

python3 - "$variable_brief" "$variable_tmp_json" <<'PY'
import json
import sys

brief = sys.argv[1] == "true"
json_file = sys.argv[2]

with open(json_file, encoding="utf-8") as f:
    data = json.load(f)

surfaces = data.get("surfaces", {})
stats = data.get("stats", {})

sorted_sids = sorted([k for k in surfaces.keys() if k.isdigit()], key=lambda x: int(x))

if brief:
    parts = []
    parts.append(f"{stats.get('total', 0)} total")
    for key in ["idle", "working", "done", "ended", "waiting", "error", "stalled", "rate_limited"]:
        count = stats.get(key, 0)
        if count > 0:
            label = key.upper().replace("_", " ")
            parts.append(f"{count} {label}")
    print(" | ".join(parts))

    working_sids = [sid for sid in sorted_sids if surfaces[sid].get("status") == "WORKING"]
    if working_sids:
        details = ", ".join(f"s:{sid}({surfaces[sid].get('ai', '?')})" for sid in working_sids)
        print(f"WORKING: {details}")

    problem_sids = [sid for sid in sorted_sids if surfaces[sid].get("status") in ("ERROR", "STALLED", "RATE_LIMITED")]
    if problem_sids:
        details = ", ".join(f"s:{sid}({surfaces[sid].get('status', '?')})" for sid in problem_sids)
        print(f"PROBLEMS: {details}")
    sys.exit(0)

# Load vision-monitor prev data for IDLE duration
import os
PREV_FILE = "/tmp/cmux-vision-monitor-prev.json"
IDLE_DURATION_MAP = {}

if os.path.exists(PREV_FILE):
    try:
        with open(PREV_FILE, encoding="utf-8") as f:
            prev_data = json.load(f)

        # Calculate idle duration from prev timestamp
        prev_timestamp_str = prev_data.get("timestamp", "")
        if prev_timestamp_str:
            try:
                from datetime import datetime, timezone
                prev_ts = datetime.strptime(prev_timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                current_ts = datetime.now(timezone.utc)
                idle_seconds_total = int((current_ts - prev_ts).total_seconds())

                # Only count as IDLE duration if prev status was IDLE
                prev_surfaces = prev_data.get("surfaces", {})
                for sid, sid_info in prev_surfaces.items():
                    if sid_info.get("status") == "IDLE":
                        IDLE_DURATION_MAP[sid] = idle_seconds_total
            except ValueError:
                pass
    except (json.JSONDecodeError, KeyError):
        pass

def format_duration(seconds):
    """Format seconds as Xm or Xs."""
    if seconds >= 60:
        mins = seconds // 60
        return f"{mins}m"
    return f"{seconds}s"

# Full table
STATUS_COLORS = {
    "IDLE": "\033[90m",
    "WORKING": "\033[33m",
    "DONE": "\033[32m",
    "ENDED": "\033[32m",
    "WAITING": "\033[36m",
    "ERROR": "\033[31m",
    "STALLED": "\033[31m",
    "RATE_LIMITED": "\033[35m",
    "UNKNOWN": "\033[90m",
}
RESET = "\033[0m"

print(f"{'SF#':>4}  {'AI':<10}  {'Status':<12}  {'WS':<6}  {'Idle':<6}  {'Snippet':<44}")
print(f"{'---':>4}  {'---':<10}  {'---':<12}  {'---':<6}  {'---':<6}  {'---':<44}")

for sid in sorted_sids:
    info = surfaces[sid]
    status = info.get("status", "UNKNOWN")
    ai = info.get("ai", "unknown")
    workspace = info.get("workspace", "?").replace("workspace:", "ws:")
    snippet = info.get("snippet", "")[:44]
    color = STATUS_COLORS.get(status, "")

    # Get IDLE duration from vision-monitor prev data
    idle_dur = ""
    if status == "IDLE" and sid in IDLE_DURATION_MAP:
        idle_dur = format_duration(IDLE_DURATION_MAP[sid])

    print(f"{sid:>4}  {ai:<10}  {color}{status:<12}{RESET}  {workspace:<6}  {idle_dur:<6}  {snippet}")

print()
parts = [f"{stats.get('total', 0)} total"]
for key in ["idle", "working", "done", "ended", "waiting", "error", "stalled", "rate_limited"]:
    count = stats.get(key, 0)
    if count > 0:
        label = key.upper().replace("_", " ")
        parts.append(f"{count} {label}")
print(" | ".join(parts))
PY

rm -f "$variable_tmp_json"
