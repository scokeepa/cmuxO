#!/bin/bash
# stall-detector.sh — Detect stalled surfaces via screen diff (30s interval)
# Captures read-screen output twice, 30s apart. If identical → STALLED.
# Usage: bash stall-detector.sh [surface_list]
#
# v2: Uses workspace-resolver.sh for dynamic workspace resolution (no hardcoded mapping)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/workspace-resolver.sh"

SURFACES="${1:-2 3 4 5 6 10 11 7 8 13 14 15 16 19 20}"
SNAP_DIR="/tmp/cmux-stall-detect"
mkdir -p "$SNAP_DIR"

# Phase 1: Capture all surfaces (snapshot A)
for SN in $SURFACES; do
    # Dynamic workspace resolution (replaces hardcoded case statement)
    WS=$(function_resolve_workspace "$SN")
    cmux read-screen --workspace "$WS" --surface "surface:${SN}" --lines 10 2>/dev/null > "$SNAP_DIR/a_${SN}.txt"
done

echo "Snapshot A captured. Waiting 30s..." >&2
sleep 30

# Phase 2: Capture again (snapshot B) + compare
STALLED=""
WORKING=""
CHANGED=""

for SN in $SURFACES; do
    # Dynamic workspace resolution (replaces hardcoded case statement)
    WS=$(function_resolve_workspace "$SN")
    cmux read-screen --workspace "$WS" --surface "surface:${SN}" --lines 10 2>/dev/null > "$SNAP_DIR/b_${SN}.txt"
    
    # Compare: if identical → STALLED
    if diff -q "$SNAP_DIR/a_${SN}.txt" "$SNAP_DIR/b_${SN}.txt" > /dev/null 2>&1; then
        # Screen unchanged for 30s
        # Check if it's Working (acceptable) or truly stalled
        if grep -qE "Working \(|Ionizing|Forming|Simmering|Crunching" "$SNAP_DIR/b_${SN}.txt"; then
            WORKING="$WORKING $SN"
        else
            STALLED="$STALLED $SN"
        fi
    else
        CHANGED="$CHANGED $SN"
    fi
done

# Output JSON
echo '{'
echo "  \"stalled\": [$(echo $STALLED | sed 's/ /,/g' | sed 's/^,//' | sed 's/\([0-9]*\)/\"\1\"/g')],"
echo "  \"working\": [$(echo $WORKING | sed 's/ /,/g' | sed 's/^,//' | sed 's/\([0-9]*\)/\"\1\"/g')],"
echo "  \"changed\": [$(echo $CHANGED | sed 's/ /,/g' | sed 's/^,//' | sed 's/\([0-9]*\)/\"\1\"/g')]"
echo '}'
