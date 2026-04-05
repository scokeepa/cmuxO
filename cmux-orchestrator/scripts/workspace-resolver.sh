#!/bin/bash
# workspace-resolver.sh v2 — Shared workspace resolution for all cmux scripts.
#
# Source this file, then call function_resolve_workspace <surface_number>
# Returns workspace reference (e.g., "workspace:3") to stdout.
#
# Resolution order:
#   1. orchestra-config.json (fast, file-based)
#   2. cmux tree --all parsing (fallback, requires cmux running)
#
# Returns empty string and exit code 1 if resolution fails.
#
# Usage:
#   source "${SCRIPT_DIR}/workspace-resolver.sh"
#   WS=$(function_resolve_workspace 7)   # → "workspace:3"
#   WS=$(function_resolve_workspace 13)  # → "workspace:4"
#   if [ -z "$WS" ]; then echo "Failed"; fi

# Cache for tree-based resolution (avoid calling cmux tree repeatedly)
_WR_TREE_CACHE=""
_WR_CONFIG_CACHE=""

_WR_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_WR_SKILL_DIR="${SKILL_DIR:-$(dirname "$_WR_SCRIPT_DIR")}"
_WR_CONFIG_FILE="${_WR_SKILL_DIR}/config/orchestra-config.json"

# Build config cache on first call
_function_wr_init_config_cache() {
  if [ -n "$_WR_CONFIG_CACHE" ]; then
    return 0
  fi

  if [ ! -f "$_WR_CONFIG_FILE" ]; then
    _WR_CONFIG_CACHE="NONE"
    return 1
  fi

  # Extract surface→workspace mapping from config as "sid:wsN" lines
  _WR_CONFIG_CACHE=$(python3 - "$_WR_CONFIG_FILE" 2>/dev/null <<'PY'
import json
import sys

config_file = sys.argv[1]
with open(config_file, encoding="utf-8") as f:
    config = json.load(f)

# Build surface→workspace index mapping from workspaces
ws_map = {}
for ws_key, ws_info in config.get("workspaces", {}).items():
    ws_index = ws_key.replace("ws", "")
    for sid in ws_info.get("surfaces", []):
        ws_map[str(sid)] = ws_index

# Also check surfaces map for workspace key
for sid, info in config.get("surfaces", {}).items():
    if str(sid) not in ws_map:
        ws_key = info.get("workspace", "")
        if ws_key:
            ws_index = ws_key.replace("ws", "")
            ws_map[str(sid)] = ws_index

for sid, ws_idx in sorted(ws_map.items(), key=lambda x: int(x[0])):
    print(f"{sid}:{ws_idx}")
PY
  )

  if [ -z "$_WR_CONFIG_CACHE" ]; then
    _WR_CONFIG_CACHE="NONE"
    return 1
  fi

  return 0
}

# Build tree cache on first call
_function_wr_init_tree_cache() {
  if [ -n "$_WR_TREE_CACHE" ]; then
    return 0
  fi

  if ! command -v cmux >/dev/null 2>&1; then
    _WR_TREE_CACHE="NONE"
    return 1
  fi

  local variable_tree_output=""
  local variable_current_ws=""
  local variable_line=""

  variable_tree_output=$(cmux tree --all 2>&1)

  _WR_TREE_CACHE=""
  while IFS= read -r variable_line; do
    local variable_ws_ref=""
    variable_ws_ref=$(printf '%s\n' "$variable_line" | sed -n 's/.*\(workspace:[0-9][0-9]*\).*/\1/p')
    if [ -n "$variable_ws_ref" ]; then
      variable_current_ws="${variable_ws_ref#workspace:}"
    fi

    local variable_sf_ref=""
    variable_sf_ref=$(printf '%s\n' "$variable_line" | sed -n 's/.*surface:\([0-9][0-9]*\).*/\1/p')
    if [ -n "$variable_sf_ref" ] && [ -n "$variable_current_ws" ]; then
      _WR_TREE_CACHE="${_WR_TREE_CACHE}${variable_sf_ref}:${variable_current_ws}
"
    fi
  done <<< "$variable_tree_output"

  if [ -z "$_WR_TREE_CACHE" ]; then
    _WR_TREE_CACHE="NONE"
    return 1
  fi

  return 0
}

# Check if surface exists in tree cache (for validation)
function_surface_exists() {
  local variable_sid="$1"

  if [ -z "$variable_sid" ]; then
    return 1
  fi

  # Strip "surface:" prefix
  variable_sid="${variable_sid#surface:}"

  _function_wr_init_tree_cache
  if [ "$_WR_TREE_CACHE" != "NONE" ]; then
    if printf '%s\n' "$_WR_TREE_CACHE" | grep -q "^${variable_sid}:"; then
      return 0
    fi
  fi

  _function_wr_init_config_cache
  if [ "$_WR_CONFIG_CACHE" != "NONE" ]; then
    if printf '%s\n' "$_WR_CONFIG_CACHE" | grep -q "^${variable_sid}:"; then
      return 0
    fi
  fi

  return 1
}

function_resolve_workspace() {
  local variable_sid="$1"

  if [ -z "$variable_sid" ]; then
    echo ""
    return 1
  fi

  # Strip "surface:" prefix
  variable_sid="${variable_sid#surface:}"

  # Strategy 1: Tree cache (always accurate when cmux is running — preferred)
  _function_wr_init_tree_cache
  if [ "$_WR_TREE_CACHE" != "NONE" ]; then
    local variable_ws_idx=""
    variable_ws_idx=$(printf '%s\n' "$_WR_TREE_CACHE" | grep "^${variable_sid}:" | head -1 | cut -d: -f2)
    if [ -n "$variable_ws_idx" ]; then
      echo "workspace:${variable_ws_idx}"
      return 0
    fi
  fi

  # Strategy 2: Config cache (fallback — may be stale from previous session)
  _function_wr_init_config_cache
  if [ "$_WR_CONFIG_CACHE" != "NONE" ]; then
    local variable_ws_idx=""
    variable_ws_idx=$(printf '%s\n' "$_WR_CONFIG_CACHE" | grep "^${variable_sid}:" | head -1 | cut -d: -f2)
    if [ -n "$variable_ws_idx" ]; then
      echo "workspace:${variable_ws_idx}"
      return 0
    fi
  fi

  # Resolution failed — return empty string
  echo ""
  return 1
}

# Convenience: get all surface→workspace pairs as "WS SF" lines
# Useful for replacing hardcoded arrays in dual-monitor.sh etc.
function_get_all_surface_pairs() {
  _function_wr_init_config_cache
  if [ "$_WR_CONFIG_CACHE" != "NONE" ]; then
    printf '%s\n' "$_WR_CONFIG_CACHE" | while IFS=: read -r sid ws_idx; do
      [ -n "$sid" ] && [ -n "$ws_idx" ] && echo "${ws_idx} ${sid}"
    done
    return 0
  fi

  _function_wr_init_tree_cache
  if [ "$_WR_TREE_CACHE" != "NONE" ]; then
    printf '%s\n' "$_WR_TREE_CACHE" | while IFS=: read -r sid ws_idx; do
      [ -n "$sid" ] && [ -n "$ws_idx" ] && echo "${ws_idx} ${sid}"
    done
    return 0
  fi

  return 1
}

# Convenience: read screen for any surface (auto-resolves workspace)
function_read_any_surface() {
  local variable_sid="$1"
  local variable_lines="${2:-20}"
  local variable_scrollback="${3:-false}"

  local variable_ws=""
  variable_ws=$(function_resolve_workspace "$variable_sid")

  if [ "$variable_scrollback" = "true" ] || [ "$variable_scrollback" = "--scrollback" ]; then
    cmux read-screen --workspace "$variable_ws" --surface "surface:${variable_sid}" --scrollback --lines "$variable_lines" 2>&1
  else
    cmux read-screen --workspace "$variable_ws" --surface "surface:${variable_sid}" --lines "$variable_lines" 2>&1
  fi
}
