#!/bin/bash
# read-surface.sh v2 — Auto-resolve workspace for any surface, then read-screen.
#
# Usage:
#   bash read-surface.sh <surface_number> [--lines N] [--scrollback]
#
# Resolves workspace from orchestra-config.json, then runs:
#   cmux read-screen --workspace workspace:N --surface surface:N --lines N
#
# If config not found, falls back to cmux tree --all parsing.

set -u

variable_script_dir="$(cd "$(dirname "$0")" && pwd)"
variable_skill_dir="${SKILL_DIR:-$(dirname "$variable_script_dir")}"
variable_config_file="${variable_skill_dir}/config/orchestra-config.json"

variable_surface_num="${1:-}"
variable_lines=20
variable_scrollback=false

if [ -z "$variable_surface_num" ]; then
  echo "Usage: read-surface.sh <surface_number> [--lines N] [--scrollback]" >&2
  exit 1
fi

# cmux 실행 여부 확인
if ! command -v cmux >/dev/null 2>&1; then
  echo "ERROR: cmux command not found" >&2
  exit 2
fi

# Strip "surface:" prefix if provided
variable_surface_num="${variable_surface_num#surface:}"

shift
while [ $# -gt 0 ]; do
  case "$1" in
    --lines)
      variable_lines="${2:-20}"
      shift 2
      ;;
    --scrollback)
      variable_scrollback=true
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# Strategy 1: Resolve workspace from orchestra-config.json
function_resolve_from_config() {
  local variable_sid="$1"

  if [ ! -f "$variable_config_file" ]; then
    return 1
  fi

  python3 - "$variable_config_file" "$variable_sid" <<'PY'
import json
import sys

config_file = sys.argv[1]
sid = sys.argv[2]

with open(config_file, encoding="utf-8") as f:
    config = json.load(f)

# Check surfaces map for workspace key
surface_info = config.get("surfaces", {}).get(sid)
if not surface_info:
    sys.exit(1)

ws_key = surface_info.get("workspace")
if not ws_key:
    # Surface exists but no workspace assigned (e.g., main surface)
    # Try workspaces map
    for ws_name, ws_info in config.get("workspaces", {}).items():
        if sid in [str(s) for s in ws_info.get("surfaces", [])]:
            ws_key = ws_name
            break

if not ws_key:
    sys.exit(1)

# Map ws_key (e.g., "ws4") to workspace index
# Convention: ws1→workspace:1, ws2→workspace:2, etc.
ws_index = ws_key.replace("ws", "")
print(f"workspace:{ws_index}")
PY
}

# Strategy 2: Resolve from cmux tree --all output
function_resolve_from_tree() {
  local variable_sid="$1"
  local variable_tree_output=""
  local variable_current_workspace=""
  local variable_line=""

  variable_tree_output=$(cmux tree --all 2>&1)

  while IFS= read -r variable_line; do
    # Extract workspace reference
    local variable_ws_ref=""
    variable_ws_ref=$(printf '%s\n' "$variable_line" | sed -n 's/.*\(workspace:[0-9][0-9]*\).*/\1/p')
    if [ -n "$variable_ws_ref" ]; then
      variable_current_workspace="$variable_ws_ref"
    fi

    # Check if this line has our surface
    if printf '%s\n' "$variable_line" | grep -q "surface:${variable_sid}[^0-9]"; then
      if [ -n "$variable_current_workspace" ]; then
        printf '%s' "$variable_current_workspace"
        return 0
      fi
    fi
  done <<< "$variable_tree_output"

  return 1
}

# Resolve workspace
variable_workspace=""

# Tree-based resolution first (always accurate when cmux running), config as fallback
variable_workspace=$(function_resolve_from_tree "$variable_surface_num" 2>/dev/null)
if [ -z "$variable_workspace" ]; then
  variable_workspace=$(function_resolve_from_config "$variable_surface_num" 2>/dev/null)
fi

if [ -z "$variable_workspace" ]; then
  echo "ERROR: Cannot resolve workspace for surface:${variable_surface_num}" >&2
  echo "HINT: Ensure surface exists and cmux is running. Try 'cmux tree --all' to verify." >&2
  exit 3
fi

# Build read-screen command
variable_cmd="cmux read-screen --workspace \"${variable_workspace}\" --surface \"surface:${variable_surface_num}\" --lines ${variable_lines}"
if [ "$variable_scrollback" = true ]; then
  variable_cmd="cmux read-screen --workspace \"${variable_workspace}\" --surface \"surface:${variable_surface_num}\" --scrollback --lines ${variable_lines}"
fi

# Execute — capture-pane 우선 (input buffer 포함), 실패 시 read-screen fallback
if [ "$variable_scrollback" = true ]; then
  variable_output=$(cmux capture-pane --workspace "$variable_workspace" --surface "surface:${variable_surface_num}" --scrollback --lines "$variable_lines" 2>/dev/null)
  if [ -z "$variable_output" ]; then
    variable_output=$(cmux read-screen --workspace "$variable_workspace" --surface "surface:${variable_surface_num}" --scrollback --lines "$variable_lines" 2>&1)
  fi
else
  variable_output=$(cmux capture-pane --workspace "$variable_workspace" --surface "surface:${variable_surface_num}" --lines "$variable_lines" 2>/dev/null)
  if [ -z "$variable_output" ]; then
    variable_output=$(cmux read-screen --workspace "$variable_workspace" --surface "surface:${variable_surface_num}" --lines "$variable_lines" 2>&1)
  fi
fi
echo "$variable_output"
