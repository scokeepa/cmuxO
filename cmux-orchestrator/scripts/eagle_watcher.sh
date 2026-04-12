#!/bin/bash
# eagle_watcher.sh — multi-workspace cmux surface watcher
#
# Requirements:
# - Run with bash, avoid mapfile for zsh-friendly usage patterns
# - Parse `cmux tree --all` text output to map every workspace:surface
# - Probe each surface with `cmux read-screen --workspace ... --surface ... --lines 5`
# - Write JSON to /tmp/cmux-eagle-status.json

set -u

variable_status_file="${EAGLE_STATUS_FILE:-/tmp/cmux-eagle-status.json}"
variable_activity_file="${EAGLE_ACTIVITY_FILE:-/tmp/cmux-eagle-activity.json}"
variable_interval="${EAGLE_INTERVAL:-20}"
variable_once=false
variable_stalled_threshold=300

variable_script_dir="$(cd "$(dirname "$0")" && pwd)"
variable_skill_dir="${SKILL_DIR:-$(dirname "$variable_script_dir")}"
variable_config_file="${variable_skill_dir}/config/orchestra-config.json"
variable_ane_tool="${ANE_TOOL:-$HOME/Ai/System/11_Modules/ane-cli/ane_tool}"

for variable_arg in "$@"; do
  case "$variable_arg" in
    --once)
      variable_once=true
      ;;
  esac
done

function_append_surface_id() {
  local variable_current="$1"
  local variable_sid="$2"

  if [ -z "$variable_current" ]; then
    printf '%s' "$variable_sid"
  else
    printf '%s %s' "$variable_current" "$variable_sid"
  fi
}

function_compact_text() {
  printf '%s' "$1" \
    | tr '\011\015\012' '   ' \
    | tr -d '\000-\010\013\014\016-\037' \
    | sed 's/[[:space:]][[:space:]]*/ /g; s/^ //; s/ $//'
}

function_find_session_snapshot_file() {
  local variable_session_file=""

  if [ -n "${EAGLE_SESSION_FILE:-}" ] && [ -f "${EAGLE_SESSION_FILE}" ]; then
    printf '%s\n' "${EAGLE_SESSION_FILE}"
    return 0
  fi

  variable_session_file="${HOME}/Library/Application Support/cmux/session-com.cmuxterm.app.json"
  if [ -f "$variable_session_file" ]; then
    printf '%s\n' "$variable_session_file"
    return 0
  fi

  return 1
}

function_read_tree_output() {
  if [ -n "${EAGLE_TREE_FILE:-}" ] && [ -f "${EAGLE_TREE_FILE}" ]; then
    cat "${EAGLE_TREE_FILE}"
    return 0
  fi

  if ! command -v cmux >/dev/null 2>&1; then
    echo "cmux not found"
    return 127
  fi

  cmux tree --all 2>&1
}

function_detect_surfaces() {
  local variable_mapping_file="$1"
  local variable_tree_file="$2"
  local variable_current_workspace=""
  local variable_line=""
  local variable_workspace_ref=""
  local variable_surface_ref=""
  local variable_surface_id=""
  local variable_title=""

  : > "$variable_mapping_file"

  while IFS= read -r variable_line; do
    variable_workspace_ref=$(printf '%s\n' "$variable_line" | sed -n 's/.*\(workspace:[0-9][0-9]*\).*/\1/p')
    if [ -n "$variable_workspace_ref" ]; then
      variable_current_workspace="$variable_workspace_ref"
    fi

    # 브라우저 surface 스킵 (read-screen 불가)
    case "$variable_line" in *"[browser]"*) continue ;; esac

    variable_surface_ref=$(printf '%s\n' "$variable_line" | sed -n 's/.*\(surface:[0-9][0-9]*\).*/\1/p')
    [ -n "$variable_surface_ref" ] || continue
    [ -n "$variable_current_workspace" ] || continue

    variable_surface_id="${variable_surface_ref#surface:}"
    variable_title=$(printf '%s\n' "$variable_line" | sed -n 's/.*"\([^"]*\)".*/\1/p')
    variable_title=$(function_compact_text "$variable_title")

    if awk -F '\t' -v sid="$variable_surface_id" '$1 == sid { found=1 } END { exit(found ? 0 : 1) }' "$variable_mapping_file" 2>/dev/null; then
      continue
    fi

    printf '%s\t%s\t%s\t%s\n' \
      "$variable_surface_id" \
      "$variable_current_workspace" \
      "$variable_surface_ref" \
      "$variable_title" >> "$variable_mapping_file"
  done < "$variable_tree_file"
}

function_read_surface_screen() {
  local variable_workspace_ref="$1"
  local variable_surface_ref="$2"
  local variable_lines="${3:-8}"
  local variable_output=""

  # First attempt with lines 8 for snapshot
  variable_output=$(cmux read-screen \
    --workspace "$variable_workspace_ref" \
    --surface "$variable_surface_ref" \
    --lines "$variable_lines" 2>&1)

  # If snapshot is empty, retry with more lines (for ANE_TOOL / deeper content)
  if [ -z "$(printf '%s' "$variable_output" | tr -d '[:space:]')" ]; then
    variable_output=$(cmux read-screen \
      --workspace "$variable_workspace_ref" \
      --surface "$variable_surface_ref" \
      --lines 20 2>&1)
  fi

  printf '%s\n' "$variable_output"
}

function_extract_reset_time() {
  local variable_screen="$1"
  local variable_reset_time=""

  # Try to extract reset time in various formats
  # Common formats: "reset in Xs", "resets at HH:MM:SS", ISO timestamps
  variable_reset_time=$(printf '%s\n' "$variable_screen" | grep -oiE "reset [0-9]+s" | head -n 1)
  if [ -n "$variable_reset_time" ]; then
    printf '%s' "$variable_reset_time"
    return
  fi

  # Try HH:MM:SS format
  variable_reset_time=$(printf '%s\n' "$variable_screen" | grep -oiE "[0-9]{2}:[0-9]{2}:[0-9]{2}" | head -n 1)
  if [ -n "$variable_reset_time" ]; then
    printf '%s' "$variable_reset_time"
    return
  fi

  # Try ISO timestamp format
  variable_reset_time=$(printf '%s\n' "$variable_screen" | grep -oiE "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}" | head -n 1)
  if [ -n "$variable_reset_time" ]; then
    printf '%s' "$variable_reset_time"
    return
  fi

  printf ''
}

function_detect_status() {
  local variable_screen="$1"
  local variable_clean=""
  local variable_status=""

  variable_clean=$(printf '%s\n' "$variable_screen" | tr -d '\000-\010\013\014\016-\037' | sed 's/\r//g')

  if [ -z "$(printf '%s' "$variable_clean" | tr -d '[:space:]')" ]; then
    echo "UNKNOWN"
    return
  fi

  # Check for rate limit patterns FIRST (before other error patterns)
  if printf '%s\n' "$variable_clean" | grep -qiE "hit your limit|rate limit|429|quota exceeded|too many requests"; then
    variable_status="RATE_LIMITED"
  elif printf '%s\n' "$variable_clean" | grep -qiE "Would you like|Do you want|Shall I|confirm|proceed\\?|continue\\?|\\[Y/n\\]|\\[y/N\\]"; then
    variable_status="WAITING"
  elif printf '%s\n' "$variable_clean" | grep -qiE "invalid_params|Operation not permitted|Failed to connect|quota|insufficient.balance|authentication.failed|unauthorized|overloaded|Bad Gateway|Service Unavailable|timed out|timeout|ECONNREFUSED|No such file or directory|not found"; then
    variable_status="ERROR"
  elif printf '%s\n' "$variable_clean" | grep -qiE "(^|[[:space:]])DONE([[:space:]]|$)|검증 완료|완료됨|완료 ✓|✅ 완료"; then
    # GLM/CMUX completion markers should override any stale working footer text.
    variable_status="DONE"
  elif printf '%s\n' "$variable_clean" | grep -qiE "esc to interrupt|thinking|auto-compact|Press up to edit queued|Working ?\\(|Working|Churned for|Sautéed for|Cogitated for|⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏"; then
    # Active footer/spinner text indicates the surface is still working.
    variable_status="WORKING"
  fi

  # Check ENDED/IDLE after higher-confidence states have been determined.
  if [ -z "$variable_status" ]; then
    if printf '%s\n' "$variable_clean" | grep -qiE "(Brewed|Cooked|Baked|Crunched|Worked|Completed|Finished)"; then
      # Has completion marker but no DONE keyword → ENDED (task done, waiting at prompt)
      variable_status="ENDED"
    elif printf '%s\n' "$variable_clean" | grep -qiE "❯|\$ |> |# "; then
      # Prompt character detected → IDLE (actively waiting for input)
      variable_status="IDLE"
    else
      variable_status="IDLE"
    fi
  fi

  # Default fallback if still undetermined
  if [ -z "$variable_status" ]; then
    variable_status="IDLE"
  fi

  echo "$variable_status"
}

function_extract_snippet() {
  local variable_screen="$1"
  local variable_snippet=""

  variable_snippet=$(
    printf '%s\n' "$variable_screen" \
      | tr -d '\000-\010\013\014\016-\037' \
      | sed 's/\r//g' \
      | awk '/[^[:space:]]/ { last = $0 } END { print last }'
  )
  variable_snippet=$(function_compact_text "$variable_snippet")
  printf '%s' "$(printf '%s' "$variable_snippet" | cut -c1-120)"
}

function_detect_ai_from_screen() {
  # Detect AI model from live screen content by finding the status bar marker.
  # Strategy:
  #   1. Look for the "🤖" emoji line (awesome-statusline model indicator) — most reliable
  #   2. Fallback: scan last 5 lines for non-Claude AI patterns (Codex/GLM/MiniMax/Gemini)
  # This avoids false positives from conversation text mentioning model names.
  local variable_screen="$1"
  local variable_ai=""

  # Strategy 1: Find the 🤖 marker line (Claude Code awesome-statusline)
  local variable_model_line=""
  variable_model_line=$(printf '%s\n' "$variable_screen" | grep -F '🤖' | tail -1)

  if [ -n "$variable_model_line" ]; then
    if printf '%s\n' "$variable_model_line" | grep -qiE "Opus"; then
      variable_ai="Opus"
    elif printf '%s\n' "$variable_model_line" | grep -qiE "Sonnet"; then
      variable_ai="Sonnet"
    elif printf '%s\n' "$variable_model_line" | grep -qiE "Haiku"; then
      variable_ai="Haiku"
    fi
  fi

  # Strategy 2: If no 🤖 marker, check last 5 lines for non-Claude AI status patterns
  if [ -z "$variable_ai" ]; then
    local variable_tail_lines=""
    variable_tail_lines=$(printf '%s\n' "$variable_screen" | tail -5)

    if printf '%s\n' "$variable_tail_lines" | grep -qiE "gpt-[0-9]"; then
      variable_ai="Codex"
    elif printf '%s\n' "$variable_tail_lines" | grep -qiE "[Gg][Ll][Mm]-[0-9]|chatglm"; then
      variable_ai="GLM"
    elif printf '%s\n' "$variable_tail_lines" | grep -qiE "[Mm]ini[Mm]ax"; then
      variable_ai="MiniMax"
    elif printf '%s\n' "$variable_tail_lines" | grep -qiE "[Gg]emini[- ][0-9.]"; then
      variable_ai="Gemini"
    fi
  fi

  printf '%s' "$variable_ai"
}

function_detect_role_from_screen() {
  # Detect the surface's ROLE: boss (orchestrator), watcher (sentinel), or worker.
  # Checks screen content for distinctive markers.
  local variable_screen="$1"
  local variable_is_caller="$2"  # "true" if this surface is the cmux identify caller
  local variable_role=""

  # The caller surface (where eagle is running from) is always "boss"
  if [ "$variable_is_caller" = "true" ]; then
    variable_role="boss"
  # Watcher markers: ran /cmux-watcher, watcher-scan.py visible, or watcher activation
  elif printf '%s\n' "$variable_screen" | grep -qiE "/cmux-watcher|watcher-scan|WATCHER SCAN|Surface Sentinel"; then
    variable_role="watcher"
  fi

  # Check role-register marker file as fallback
  if [ -z "$variable_role" ]; then
    local variable_surface_id="$3"
    local variable_role_file="/tmp/cmux-role-s${variable_surface_id}.txt"
    if [ -f "$variable_role_file" ]; then
      variable_role=$(cat "$variable_role_file" 2>/dev/null | tr -d '[:space:]')
    fi
  fi

  # Default to worker
  if [ -z "$variable_role" ]; then
    variable_role="worker"
  fi

  printf '%s' "$variable_role"
}

function_get_caller_surface_id() {
  # Get the surface ID of the caller (this process) via cmux identify.
  # Cached to avoid repeated calls.
  local variable_cache_file="/tmp/cmux-eagle-caller-sid.txt"
  local variable_sid=""

  # Use cache if fresh (< 60 seconds)
  if [ -f "$variable_cache_file" ]; then
    local variable_age=0
    if command -v stat >/dev/null 2>&1; then
      variable_age=$(( $(date +%s) - $(stat -f %m "$variable_cache_file" 2>/dev/null || echo 0) ))
    fi
    if [ "$variable_age" -lt 60 ]; then
      cat "$variable_cache_file"
      return 0
    fi
  fi

  # Query cmux identify
  if command -v cmux >/dev/null 2>&1; then
    variable_sid=$(cmux identify 2>/dev/null | python3 -c "
import json,sys
try:
    data = json.load(sys.stdin)
    ref = data.get('caller',{}).get('surface_ref','')
    print(ref.replace('surface:',''))
except: pass
" 2>/dev/null)
  fi

  if [ -n "$variable_sid" ]; then
    printf '%s' "$variable_sid" > "$variable_cache_file"
    printf '%s' "$variable_sid"
  fi
}

function_auto_sync_config() {
  # Runtime surface 상태를 /tmp/cmux-surface-map.json에 기록.
  # orchestra-config.json은 읽기 전용(presets만 정본) — 쓰지 않음.
  local variable_rows_file="$1"
  local variable_config="$2"  # presets 참조용으로만 읽기

  [ -f "$variable_rows_file" ] || return 0

  python3 - "$variable_rows_file" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

rows_file = sys.argv[1]
runtime_file = "/tmp/cmux-surface-map.json"

# 기존 runtime state 로드 (있으면)
surfaces = {}
if os.path.isfile(runtime_file):
    try:
        with open(runtime_file) as f:
            surfaces = json.load(f).get("surfaces", {})
    except Exception:
        pass

changed = False
with open(rows_file, encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 8:
            continue
        sid = parts[0]
        screen_ai = parts[7].strip() if len(parts) > 7 else ""
        screen_role = parts[8].strip() if len(parts) > 8 else ""

        if not screen_ai:
            continue

        if sid in surfaces:
            if surfaces[sid].get("ai", "") != screen_ai:
                surfaces[sid]["ai"] = screen_ai
                changed = True
            if screen_role and screen_role != surfaces[sid].get("role", ""):
                surfaces[sid]["role"] = screen_role
                changed = True
        else:
            surfaces[sid] = {"ai": screen_ai, "role": screen_role or "worker"}
            changed = True

if changed:
    runtime_state = {
        "surfaces": surfaces,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "eagle_watcher_auto_sync"
    }
    with open(runtime_file, "w", encoding="utf-8") as f:
        json.dump(runtime_state, f, ensure_ascii=False, indent=2)
PY
}

function_write_status_json() {
  local variable_rows_file="$1"
  local variable_idle_list="$2"
  local variable_working_list="$3"
  local variable_done_list="$4"
  local variable_waiting_list="$5"
  local variable_error_list="$6"
  local variable_error_message="$7"
  local variable_timestamp="$8"
  local variable_output_file="$9"
  local variable_ended_list="${10:-}"
  local variable_prev_activity_file="${11:-}"
  local variable_stalled_list="${12:-}"

  python3 - "$variable_rows_file" "$variable_config_file" "$variable_idle_list" "$variable_working_list" "$variable_done_list" "$variable_waiting_list" "$variable_error_list" "$variable_error_message" "$variable_timestamp" "$variable_ended_list" "$variable_prev_activity_file" "$variable_stalled_threshold" "$variable_stalled_list" > "$variable_output_file" <<'PY'
import json
import os
import sys
from datetime import datetime

rows_file = sys.argv[1]
config_file = sys.argv[2]
idle_list = sys.argv[3]
working_list = sys.argv[4]
done_list = sys.argv[5]
waiting_list = sys.argv[6]
error_list = sys.argv[7]
error_message = sys.argv[8]
timestamp = sys.argv[9]
ended_list = sys.argv[10] if len(sys.argv) > 10 else ""
prev_activity_file = sys.argv[11] if len(sys.argv) > 11 else ""
stalled_threshold = int(sys.argv[12]) if len(sys.argv) > 12 else 300
stalled_list_arg = sys.argv[13] if len(sys.argv) > 13 else ""

ai_map = {}
if config_file and os.path.isfile(config_file):
    try:
        with open(config_file, encoding="utf-8") as fh:
            config = json.load(fh)
        for sid, info in config.get("surfaces", {}).items():
            ai_map[str(sid)] = info.get("ai", "unknown")
    except Exception:
        ai_map = {}

prev_activity = {}
if prev_activity_file and os.path.isfile(prev_activity_file):
    try:
        with open(prev_activity_file, encoding="utf-8") as fh:
            prev_data = json.load(fh)
        for sid, info in prev_data.get("surfaces", {}).items():
            prev_activity[sid] = {
                "last_activity": info.get("last_activity", ""),
                "last_snippet": info.get("last_snippet", ""),
            }
    except Exception:
        prev_activity = {}

current_timestamp_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

surfaces = {}
surfaces_activity = {}
if os.path.isfile(rows_file):
    with open(rows_file, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.rstrip("\n")
            if not raw:
                continue
            parts = raw.split("\t")
            while len(parts) < 10:
                parts.append("")
            sid, workspace, surface, title, status, snippet, reset_time, screen_ai, screen_role, member_req = parts[:10]

            is_stalled = False
            prev_snippet = ""
            if sid in prev_activity:
                prev_info = prev_activity[sid]
                prev_snippet = prev_info.get("last_snippet", "")
                if prev_snippet == snippet:
                    prev_ts_str = prev_info.get("last_activity", "")
                    if prev_ts_str:
                        try:
                            prev_ts_dt = datetime.fromisoformat(prev_ts_str.replace("Z", "+00:00"))
                            diff_seconds = (current_timestamp_dt - prev_ts_dt).total_seconds()
                            if diff_seconds >= stalled_threshold:
                                is_stalled = True
                        except Exception:
                            pass

            if is_stalled:
                status = "STALLED"
            elif status == "IDLE" and prev_snippet == snippet:
                pass

            # Screen-detected AI takes priority over static config
            detected_ai = screen_ai.strip() if screen_ai.strip() else ai_map.get(sid, "unknown")
            detected_role = screen_role.strip() if screen_role.strip() else "worker"

            surface_data = {
                "workspace": workspace,
                "surface": surface,
                "status": status,
                "title": title,
                "ai": detected_ai,
                "role": detected_role,
                "snippet": snippet,
                "last_activity": timestamp,
                "member_request": member_req.strip() == "true",
            }
            if reset_time:
                surface_data["reset_time"] = reset_time
            surfaces[sid] = surface_data
            surfaces_activity[sid] = {
                "last_activity": timestamp,
                "last_snippet": snippet,
                "is_stalled": is_stalled,
            }

def count_ids(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    return len(value.split())

payload = {
    "timestamp": timestamp,
    "surfaces": surfaces,
    "surfaces_activity": surfaces_activity,
    "idle_surfaces": idle_list,
    "working_surfaces": working_list,
    "done_surfaces": done_list,
    "ended_surfaces": ended_list,
    "waiting_surfaces": waiting_list,
    "error_surfaces": error_list,
    "stalled_surfaces": stalled_list_arg,
    "stats": {
        "total": len(surfaces),
        "idle": count_ids(idle_list),
        "working": count_ids(working_list),
        "done": count_ids(done_list),
        "ended": count_ids(ended_list),
        "waiting": count_ids(waiting_list),
        "error": count_ids(error_list),
        "stalled": sum(1 for info in surfaces.values() if info.get("status") == "STALLED"),
        "rate_limited": sum(1 for info in surfaces.values() if info.get("status") == "RATE_LIMITED"),
        "unknown": sum(1 for info in surfaces.values() if info.get("status") == "UNKNOWN"),
    },
}

if error_message:
    payload["error"] = error_message

print(json.dumps(payload, ensure_ascii=False))
PY
}

function_write_session_fallback_status_json() {
  local variable_session_file="$1"
  local variable_error_message="$2"
  local variable_timestamp="$3"
  local variable_output_file="$4"

  python3 - "$variable_session_file" "$variable_config_file" "$variable_error_message" "$variable_timestamp" > "$variable_output_file" <<'PY'
import json
import os
import re
import sys

session_file = sys.argv[1]
config_file = sys.argv[2]
error_message = sys.argv[3]
timestamp = sys.argv[4]

with open(session_file, encoding="utf-8") as fh:
    session = json.load(fh)

config = {}
if config_file and os.path.isfile(config_file):
    try:
        with open(config_file, encoding="utf-8") as fh:
            config = json.load(fh)
    except Exception:
        config = {}

workspace_defs = config.get("workspaces", {})
surface_defs = config.get("surfaces", {})
boss_surface = str(config.get("boss_surface", "1") or "1")

windows = session.get("windows", [])
tab_manager = windows[0].get("tabManager", {}) if windows else {}
workspaces = tab_manager.get("workspaces", [])

group_defs = []
for group_key, group_info in workspace_defs.items():
    surface_ids = [str(value) for value in group_info.get("surfaces", [])]
    group_defs.append(
        {
            "key": group_key,
            "name": group_info.get("name", group_key),
            "ai": group_info.get("ai", "unknown"),
            "surfaces": surface_ids,
        }
    )

remaining_groups = {group["key"]: group for group in group_defs}
assignments = {}


def normalize(text):
    return (text or "").strip().lower()


def match_group_by_ai(expected_ai):
    expected = normalize(expected_ai)
    if not expected:
        return None
    for group in group_defs:
        if group["key"] not in remaining_groups:
            continue
        if normalize(group.get("ai")) == expected:
            return group
    return None


def choose_group(target_count):
    if not remaining_groups:
        return None
    target = max(int(target_count), 0)
    ordered = sorted(
        remaining_groups.values(),
        key=lambda group: (
            abs(len(group.get("surfaces", [])) - target),
            len(group.get("surfaces", [])),
            group.get("key", ""),
        ),
    )
    return ordered[0] if ordered else None


for workspace_index, workspace_info in enumerate(workspaces, 1):
    process_title = normalize(workspace_info.get("processTitle"))
    matched_group = None

    if "codex" in process_title:
        matched_group = match_group_by_ai("codex")
    elif re.search(r"(^|[^a-z])(ccg|glm)([^a-z]|$)", process_title):
        matched_group = match_group_by_ai("glm")

    if matched_group is not None:
        assignments[workspace_index] = matched_group
        remaining_groups.pop(matched_group["key"], None)

if workspaces:
    boss_workspace_index = 1
    if boss_workspace_index not in assignments:
        boss_workspace = workspaces[boss_workspace_index - 1]
        matched_group = choose_group(len(boss_workspace.get("panels", [])) - 1)
        if matched_group is not None:
            assignments[boss_workspace_index] = matched_group
            remaining_groups.pop(matched_group["key"], None)

for workspace_index, workspace_info in enumerate(workspaces, 1):
    if workspace_index in assignments:
        continue
    matched_group = choose_group(len(workspace_info.get("panels", [])))
    if matched_group is not None:
        assignments[workspace_index] = matched_group
        remaining_groups.pop(matched_group["key"], None)

used_surface_ids = set()
synthetic_candidate = 1
reserved_surface_ids = {str(key) for key in surface_defs.keys()}
reserved_surface_ids.add(boss_surface)


def allocate_surface_ids(workspace_index, panel_count):
    global synthetic_candidate
    group = assignments.get(workspace_index)
    proposed = []

    if workspace_index == 1 and boss_surface not in used_surface_ids:
        proposed.append(boss_surface)

    if group is not None:
        for sid in group.get("surfaces", []):
            if sid not in proposed:
                proposed.append(sid)

    assigned = []
    for sid in proposed:
        if len(assigned) >= panel_count:
            break
        if sid in used_surface_ids:
            continue
        assigned.append(sid)
        used_surface_ids.add(sid)

    while len(assigned) < panel_count:
        while (
            str(synthetic_candidate) in used_surface_ids
            or str(synthetic_candidate) in reserved_surface_ids
        ):
            synthetic_candidate += 1
        sid = str(synthetic_candidate)
        synthetic_candidate += 1
        assigned.append(sid)
        used_surface_ids.add(sid)

    return assigned


def status_from_panel(panel_info):
    title = panel_info.get("customTitle") or panel_info.get("title") or ""
    match = re.search(r":([A-Z]+)$", title.strip())
    status = match.group(1) if match else ""
    if status in {"IDLE", "WORKING", "DONE", "WAITING", "ERROR", "UNKNOWN", "RATE_LIMITED"}:
        return status
    return "UNKNOWN"


def compact_text(value):
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


surfaces = {}
idle = []
working = []
done = []
waiting = []
error = []

for workspace_index, workspace_info in enumerate(workspaces, 1):
    panels = [panel for panel in workspace_info.get("panels", []) if panel.get("type") == "terminal"]
    assigned_ids = allocate_surface_ids(workspace_index, len(panels))
    group = assignments.get(workspace_index, {})
    fallback_ai = group.get("ai", "unknown")

    for offset, panel in enumerate(panels):
        sid = assigned_ids[offset]
        status = status_from_panel(panel)
        title = compact_text(panel.get("customTitle") or panel.get("title") or fallback_ai)
        snippet = compact_text(
            " | ".join(
                part for part in [
                    workspace_info.get("processTitle", ""),
                    panel.get("directory", ""),
                ] if part
            )
        )[:120]

        if sid in surface_defs:
            ai_value = surface_defs.get(sid, {}).get("ai", fallback_ai)
        else:
            ai_value = fallback_ai

        surfaces[sid] = {
            "workspace": f"workspace:{workspace_index}",
            "surface": f"surface:{sid}",
            "status": status,
            "title": title,
            "ai": ai_value or "unknown",
            "snippet": snippet,
            "last_activity": timestamp,
        }

        if status == "IDLE":
            idle.append(sid)
        elif status == "WORKING":
            working.append(sid)
        elif status == "DONE":
            done.append(sid)
        elif status == "WAITING":
            waiting.append(sid)
        elif status == "ERROR":
            error.append(sid)

payload = {
    "timestamp": timestamp,
    "surfaces": surfaces,
    "surfaces_activity": {},
    "idle_surfaces": " ".join(idle),
    "working_surfaces": " ".join(working),
    "done_surfaces": " ".join(done),
    "waiting_surfaces": " ".join(waiting),
    "error_surfaces": " ".join(error),
    "stats": {
        "total": len(surfaces),
        "idle": len(idle),
        "working": len(working),
        "done": len(done),
        "waiting": len(waiting),
        "error": len(error),
        "stalled": 0,
        "rate_limited": sum(1 for info in surfaces.values() if info.get("status") == "RATE_LIMITED"),
        "unknown": sum(1 for info in surfaces.values() if info.get("status") == "UNKNOWN"),
    },
}

if error_message:
    payload["error"] = f"{error_message} (session snapshot fallback)"

print(json.dumps(payload, ensure_ascii=False))
PY
}

function_poll_once() {
  local variable_tree_file=""
  local variable_mapping_file=""
  local variable_rows_file=""
  local variable_output_file=""
  local variable_tree_output=""
  local variable_tree_error=""
  local variable_tree_exit=0
  local variable_idle_list=""
  local variable_working_list=""
  local variable_done_list=""
  local variable_waiting_list=""
  local variable_error_list=""
  local variable_ended_list=""
  local variable_stalled_list=""
  local variable_timestamp=""
  local variable_sid=""
  local variable_workspace_ref=""
  local variable_surface_ref=""
  local variable_title=""
  local variable_screen_output=""
  local variable_screen_exit=0
  local variable_status=""
  local variable_snippet=""
  local variable_session_file=""
  local variable_screen_ai=""
  local variable_screen_role=""
  local variable_caller_sid=""

  # Get caller surface ID for role detection (boss = caller)
  variable_caller_sid=$(function_get_caller_surface_id)

  variable_tree_file="$(mktemp /tmp/eagle-watcher-tree.XXXXXX)"
  variable_mapping_file="$(mktemp /tmp/eagle-watcher-map.XXXXXX)"
  variable_rows_file="$(mktemp /tmp/eagle-watcher-rows.XXXXXX)"
  variable_output_file="$(mktemp /tmp/eagle-watcher-json.XXXXXX)"

  variable_tree_output=$(function_read_tree_output)
  variable_tree_exit=$?
  printf '%s\n' "$variable_tree_output" > "$variable_tree_file"

  if [ "$variable_tree_exit" -ne 0 ]; then
    variable_tree_error=$(function_compact_text "$variable_tree_output")
    if variable_session_file=$(function_find_session_snapshot_file); then
      variable_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
      if function_write_session_fallback_status_json \
        "$variable_session_file" \
        "$variable_tree_error" \
        "$variable_timestamp" \
        "$variable_output_file"; then
        mv "$variable_output_file" "$variable_status_file"
        rm -f "$variable_tree_file" "$variable_mapping_file" "$variable_rows_file"
        return
      fi
    fi
  fi

  function_detect_surfaces "$variable_mapping_file" "$variable_tree_file"

  if [ ! -s "$variable_mapping_file" ] && variable_session_file=$(function_find_session_snapshot_file); then
    variable_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    if function_write_session_fallback_status_json \
      "$variable_session_file" \
      "$variable_tree_error" \
      "$variable_timestamp" \
      "$variable_output_file"; then
      mv "$variable_output_file" "$variable_status_file"
      rm -f "$variable_tree_file" "$variable_mapping_file" "$variable_rows_file"
      return
    fi
  fi

  : > "$variable_rows_file"

  while IFS=$'\t' read -r variable_sid variable_workspace_ref variable_surface_ref variable_title; do
    [ -n "${variable_sid:-}" ] || continue

    variable_screen_output=$(function_read_surface_screen "$variable_workspace_ref" "$variable_surface_ref")
    variable_screen_exit=$?
    variable_status=$(function_detect_status "$variable_screen_output")

    if [ "$variable_screen_exit" -ne 0 ] && [ "$variable_status" = "IDLE" -o "$variable_status" = "UNKNOWN" ]; then
      variable_status="ERROR"
    fi

    # GATE 15: Screenshot + OCR for IDLE surfaces (deeper content inspection)
    # When eagle reports IDLE, verify with `cmux browser screenshot` before trusting it.
    # Do not use `cmux screenshot` here: that command is invalid and can emit help text instead of an image.
    if [ "$variable_status" = "IDLE" ] && [ -x "$variable_ane_tool" ]; then
      local variable_shot="/tmp/cmux-screenshot-s${variable_sid}.png"
      if cmux browser screenshot --surface "$variable_surface_ref" --out "$variable_shot" >/dev/null 2>&1; then
        if [ -f "$variable_shot" ]; then
          local variable_ocr_result=$("$variable_ane_tool" ocr "$variable_shot" 2>/dev/null)
          rm -f "$variable_shot"
          # Use OCR to detect patterns not visible in text screen.
          # If eagle says IDLE but OCR still shows work indicators, trust OCR and keep hands off.
          if printf '%s\n' "$variable_ocr_result" | grep -qiE "hit your limit|rate limit"; then
            variable_status="RATE_LIMITED"
          elif printf '%s\n' "$variable_ocr_result" | grep -qiE "Would you like|Do you want|Shall I|confirm|proceed\\?"; then
            variable_status="WAITING"
          elif printf '%s\n' "$variable_ocr_result" | grep -qiE "■■■|Working ?\\(|Ionizing|Crunching|Forming|Ebbing|thinking|Churned for|Sautéed for|Cogitated for|⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏"; then
            variable_status="WORKING"
          fi
        fi
      fi
    fi

    variable_snippet=$(function_extract_snippet "$variable_screen_output")

    # MEMBER REQUEST detection
    variable_member_request="false"
    if echo "$variable_screen_output" | grep -q "MEMBER REQUEST:"; then
      if echo "$variable_screen_output" | grep -qE "^\s*-\s+(high|medium|low):"; then
        variable_member_request="true"
      fi
    fi

    # Detect AI from live screen content (overrides stale config)
    variable_screen_ai=$(function_detect_ai_from_screen "$variable_screen_output")

    # Detect role (boss/watcher/worker)
    local variable_is_caller="false"
    [ "$variable_sid" = "$variable_caller_sid" ] && variable_is_caller="true"
    variable_screen_role=$(function_detect_role_from_screen "$variable_screen_output" "$variable_is_caller" "$variable_sid")

    # DEBUG logging after STATUS decision
    echo "[eagle] s:$variable_sid status=$variable_status ai=${variable_screen_ai:-?} role=${variable_screen_role} snippet=${variable_snippet:0:40}" >&2
    variable_title=$(function_compact_text "$variable_title")

    # Extract reset_time if RATE_LIMITED
    variable_reset_time=""
    if [ "$variable_status" = "RATE_LIMITED" ]; then
      variable_reset_time=$(function_extract_reset_time "$variable_screen_output")
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$variable_sid" \
      "$variable_workspace_ref" \
      "$variable_surface_ref" \
      "$variable_title" \
      "$variable_status" \
      "$variable_snippet" \
      "$variable_reset_time" \
      "$variable_screen_ai" \
      "$variable_screen_role" \
      "$variable_member_request" >> "$variable_rows_file"

    case "$variable_status" in
      IDLE)
        variable_idle_list=$(function_append_surface_id "$variable_idle_list" "$variable_sid")
        ;;
      WORKING)
        variable_working_list=$(function_append_surface_id "$variable_working_list" "$variable_sid")
        ;;
      DONE)
        variable_done_list=$(function_append_surface_id "$variable_done_list" "$variable_sid")
        ;;
      ENDED)
        variable_done_list=$(function_append_surface_id "$variable_done_list" "$variable_sid")
        ;;
      WAITING)
        variable_waiting_list=$(function_append_surface_id "$variable_waiting_list" "$variable_sid")
        ;;
      ERROR)
        variable_error_list=$(function_append_surface_id "$variable_error_list" "$variable_sid")
        ;;
      STALLED)
        variable_stalled_list=$(function_append_surface_id "$variable_stalled_list" "$variable_sid")
        ;;
      RATE_LIMITED)
        variable_error_list=$(function_append_surface_id "$variable_error_list" "$variable_sid")
        ;;
    esac
  done < "$variable_mapping_file"

  variable_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  function_write_status_json \
    "$variable_rows_file" \
    "$variable_idle_list" \
    "$variable_working_list" \
    "$variable_done_list" \
    "$variable_waiting_list" \
    "$variable_error_list" \
    "$variable_tree_error" \
    "$variable_timestamp" \
    "$variable_output_file" \
    "$variable_ended_list" \
    "$variable_activity_file" \
    "$variable_stalled_list"

  mv "$variable_output_file" "$variable_status_file"

  # Auto-sync config with screen-detected AI/role (prevents stale config)
  function_auto_sync_config "$variable_rows_file" "$variable_config_file"

  python3 - "$variable_status_file" "$variable_activity_file" > /dev/null 2>&1 <<'PY'
import json
import sys
output_file = sys.argv[1]
activity_file = sys.argv[2]
try:
    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)
    surfaces_activity = data.get("surfaces_activity", {})
    activity_data = {"surfaces": surfaces_activity, "timestamp": data.get("timestamp", "")}
    with open(activity_file, "w", encoding="utf-8") as f:
        json.dump(activity_data, f, ensure_ascii=False)
except Exception:
    pass
PY

  rm -f "$variable_tree_file" "$variable_mapping_file" "$variable_rows_file"
}

if [ "$variable_once" = true ]; then
  function_poll_once
  cat "$variable_status_file"
else
  while true; do
    function_poll_once
    sleep "$variable_interval"
  done
fi
