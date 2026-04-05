#!/bin/bash
# validate-config.sh — Compare orchestra-config.json vs cmux tree --all output.
#
# Reports missing/mismatched surfaces as JSON:
#   {
#     "valid": ["surface:1", ...],
#     "missing_in_tree": ["surface:2", ...],
#     "missing_in_config": ["surface:3", ...],
#     "workspace_mismatch": [{"surface": "surface:4", "config": "workspace:1", "tree": "workspace:2"}]
#   }
#
# Exit code: 0 if valid (all match), 1 if any mismatches found.
#
# Usage:
#   ./validate-config.sh

set -euo pipefail

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="${SKILL_DIR:-$(dirname "$SCRIPT_DIR")}"
CONFIG_FILE="${SKILL_DIR}/config/orchestra-config.json"

# Temporary storage for parsing results
CONFIG_PARSED="/tmp/cmux_config_parsed_$$"
TREE_PARSED="/tmp/cmux_tree_parsed_$$"
trap "rm -f $CONFIG_PARSED $TREE_PARSED" EXIT

# =============================================================================
# Parse orchestra-config.json
# =============================================================================
parse_config() {
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "[]" > "$CONFIG_PARSED"
    return 1
  fi

  python3 - "$CONFIG_FILE" 2>/dev/null <<'PY' | sort > "$CONFIG_PARSED"
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

for sid, ws_idx in ws_map.items():
    print(f"{sid}:{ws_idx}")
PY
}

# =============================================================================
# Parse cmux tree --all output
# =============================================================================
parse_tree() {
  if ! command -v cmux >/dev/null 2>&1; then
    echo "[]" > "$TREE_PARSED"
    return 1
  fi

  local variable_tree_output=""
  local variable_current_ws=""
  local variable_line=""

  variable_tree_output=$(cmux tree --all 2>&1)

  > "$TREE_PARSED"
  while IFS= read -r variable_line; do
    local variable_ws_ref=""
    variable_ws_ref=$(printf '%s\n' "$variable_line" | sed -n 's/.*\(workspace:[0-9][0-9]*\).*/\1/p')
    if [ -n "$variable_ws_ref" ]; then
      variable_current_ws="${variable_ws_ref#workspace:}"
    fi

    local variable_sf_ref=""
    variable_sf_ref=$(printf '%s\n' "$variable_line" | sed -n 's/.*surface:\([0-9][0-9]*\).*/\1/p')
    if [ -n "$variable_sf_ref" ] && [ -n "$variable_current_ws" ]; then
      echo "${variable_sf_ref}:${variable_current_ws}" >> "$TREE_PARSED"
    fi
  done <<< "$variable_tree_output"

  sort "$TREE_PARSED" -o "$TREE_PARSED"
}

# =============================================================================
# Compare and generate JSON report
# =============================================================================
generate_report() {
  python3 - "$CONFIG_PARSED" "$TREE_PARSED" <<'PY'
import json
import sys

config_file = sys.argv[1]
tree_file = sys.argv[2]

# Parse config: sid:ws_idx format
config_map = {}
try:
    with open(config_file) as f:
        for line in f:
            line = line.strip()
            if line and ':' in line:
                sid, ws_idx = line.split(':', 1)
                config_map[sid] = ws_idx
except FileNotFoundError:
    pass

# Parse tree: sid:ws_idx format
tree_map = {}
try:
    with open(tree_file) as f:
        for line in f:
            line = line.strip()
            if line and ':' in line:
                sid, ws_idx = line.split(':', 1)
                tree_map[sid] = ws_idx
except FileNotFoundError:
    pass

# Analyze
valid = []
missing_in_tree = []
missing_in_config = []
workspace_mismatch = []

all_sids = sorted(set(config_map.keys()) | set(tree_map.keys()), key=int)

for sid in all_sids:
    config_ws = config_map.get(sid)
    tree_ws = tree_map.get(sid)

    if config_ws is None:
        missing_in_config.append(f"surface:{sid}")
    elif tree_ws is None:
        missing_in_tree.append(f"surface:{sid}")
    elif config_ws != tree_ws:
        workspace_mismatch.append({
            "surface": f"surface:{sid}",
            "config": f"workspace:{config_ws}",
            "tree": f"workspace:{tree_ws}"
        })
    else:
        valid.append(f"surface:{sid}")

report = {
    "valid": valid,
    "missing_in_tree": missing_in_tree,
    "missing_in_config": missing_in_config,
    "workspace_mismatch": workspace_mismatch
}

print(json.dumps(report, indent=2, ensure_ascii=False))

# Exit code: 0 if all valid, 1 if any issues
if not missing_in_tree and not missing_in_config and not workspace_mismatch:
    sys.exit(0)
else:
    sys.exit(1)
PY
}

# =============================================================================
# Main
# =============================================================================
main() {
  parse_config
  parse_tree
  generate_report
}

main "$@"
