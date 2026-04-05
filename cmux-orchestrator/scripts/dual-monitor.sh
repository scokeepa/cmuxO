#!/bin/bash
# dual-monitor.sh — Dual layer monitoring: text analysis + 60s screen diff
# Usage: bash dual-monitor.sh
# Output: JSON with each surface status
#
# v2: Uses workspace-resolver.sh for dynamic workspace resolution (no hardcoded pairs)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/workspace-resolver.sh"

SNAP_DIR="/tmp/cmux-dual-monitor"
mkdir -p "$SNAP_DIR"

# Dynamic surface→workspace pairs from config/tree (replaces hardcoded array)
SURFACE_PAIRS=$(function_get_all_surface_pairs)
if [ -z "$SURFACE_PAIRS" ]; then
    echo '{"error":"No surfaces found"}' >&2
    exit 1
fi

# === PASS 1: Capture + Text Analysis ===
while IFS=' ' read -r WSN SN; do
    [ -n "$SN" ] || continue
    cmux read-screen --workspace "workspace:${WSN}" --surface "surface:${SN}" --lines 12 2>/dev/null > "$SNAP_DIR/pass1_${SN}.txt"
done <<< "$SURFACE_PAIRS"

echo "waiting 60s..." >&2
sleep 60

# === PASS 2: Capture again + Compare ===
echo '{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","surfaces":{'

FIRST=true
while IFS=' ' read -r WSN SN; do
    [ -n "$SN" ] || continue
    cmux read-screen --workspace "workspace:${WSN}" --surface "surface:${SN}" --lines 12 2>/dev/null > "$SNAP_DIR/pass2_${SN}.txt"

    PASS1=$(cat "$SNAP_DIR/pass1_${SN}.txt")
    PASS2=$(cat "$SNAP_DIR/pass2_${SN}.txt")

    # Layer 1: Text pattern analysis
    RL=$(echo "$PASS2" | grep -ciE "hit your limit|rate.?limit|429")
    WORKING=$(echo "$PASS2" | grep -cE "Working \(|Ionizing|Forming|Simmering|Crunching|Ebbing|Mustering|Blanching")
    DONE=$(echo "$PASS2" | grep -c "^DONE$\|^  DONE$")
    QUEUED=$(echo "$PASS2" | grep -cE "TASK:|summary→|⛔no subagent|/clear[A-Z]")

    # Layer 2: 60s screen diff
    SCREEN_CHANGED="false"
    if [ "$PASS1" != "$PASS2" ]; then
        SCREEN_CHANGED="true"
    fi

    # Final status determination
    STATUS="UNKNOWN"
    if [ "$RL" -gt 0 ]; then
        STATUS="RATE_LIMITED"
    elif [ "$WORKING" -gt 0 ]; then
        STATUS="WORKING"
    elif [ "$SCREEN_CHANGED" = "true" ]; then
        STATUS="ACTIVE"  # screen changed = something happened
    elif [ "$DONE" -gt 0 ]; then
        STATUS="DONE"
    elif [ "$QUEUED" -gt 0 ]; then
        STATUS="QUEUED"
    else
        STATUS="STALLED"  # no change, no working, no done = stuck
    fi

    $FIRST || echo ","
    FIRST=false
    echo -n "\"${SN}\":{\"workspace\":\"workspace:${WSN}\",\"status\":\"${STATUS}\",\"screen_changed\":${SCREEN_CHANGED}}"
done <<< "$SURFACE_PAIRS"

echo '}}'
