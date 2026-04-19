#!/bin/bash
# vision-monitor.sh — Apple Vision OCR dual detection for cmux surfaces
# Captures surface screenshots and analyzes text to detect STUCK/QUEUED/RL states
# Usage: bash vision-monitor.sh [surface_list]
#
# v3: IDLE duration tracking — reads prev status, calculates idle_seconds, alerts after 120s

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/workspace-resolver.sh"
source "${SCRIPT_DIR}/cmux_compat.sh" 2>/dev/null || true
# shellcheck source=cmux-paths.sh
[ -f "${SCRIPT_DIR}/cmux-paths.sh" ] && . "${SCRIPT_DIR}/cmux-paths.sh"

SURFACES="${1:-2 3 4 5 6 10 11 7 8 13 14 15 16 19 20}"
if command -v cmux_ane_tool >/dev/null 2>&1; then
  ANE_TOOL="$(cmux_ane_tool || true)"
  [ -z "$ANE_TOOL" ] && ANE_TOOL="$HOME/Ai/System/11_Modules/ane-cli/ane_tool"
else
  ANE_TOOL="${CMUX_ANE_TOOL:-${ANE_TOOL:-$HOME/Ai/System/11_Modules/ane-cli/ane_tool}}"
fi
SCREENSHOT_DIR="/tmp/cmux-vision-monitor"
PREV_FILE="/tmp/cmux-vision-monitor-prev.json"
IDLE_THRESHOLD=120
mkdir -p "$SCREENSHOT_DIR"

# Rate limited pool (skip these)
RL_POOL="${RL_SURFACES:-}"

# Read previous status if exists
declare PREV_STATUS_MAP=""
declare PREV_EPOCH_TS=0
if [ -f "$PREV_FILE" ]; then
    PREV_EPOCH_TS=$(compat_json_get "$PREV_FILE" timestamp 2>/dev/null)
    PREV_STATUS_MAP=$(python3 -c "
import json
try:
    d=json.load(open('$PREV_FILE'))
    surfs=d.get('surfaces',d)
    for k,v in surfs.items():
        if isinstance(v,dict) and 'status' in v:
            print(f'{k}:{v[\"status\"]}',end=' ')
except: pass
" 2>/dev/null)
fi

CURRENT_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
CURRENT_EPOCH=$(compat_epoch "$CURRENT_TIMESTAMP" 2>/dev/null || echo "0")

echo '{"timestamp":"'"$CURRENT_TIMESTAMP"'","surfaces":{'

FIRST=true
IDLE_ALERT=false
for SN in $SURFACES; do
    # Skip rate limited
    echo "$RL_POOL" | grep -q "$SN" && continue

    # Dynamic workspace resolution
    WS=$(function_resolve_workspace "$SN")

    # Method 1: cmux read-screen (text-based)
    TEXT=$(cmux read-screen --workspace "$WS" --surface "surface:${SN}" --lines 8 2>&1)

    # Detect states from text
    STATUS="IDLE"
    if echo "$TEXT" | grep -qiE "hit your limit|rate.?limit|429"; then
        STATUS="RATE_LIMITED"
    elif echo "$TEXT" | grep -qE "Working \(|Ionizing|Crunching|Forming|Ebbing"; then
        STATUS="WORKING"
    elif echo "$TEXT" | grep -qE "TASK:|summary→|⛔no subagent|/clear[A-Z]"; then
        STATUS="QUEUED"
    elif echo "$TEXT" | grep -q "^DONE$\|^  DONE$"; then
        STATUS="DONE"
    fi

    # Method 2: Screenshot + Vision OCR (if available and status unclear)
    if [ "$STATUS" = "IDLE" ] && [ -x "$ANE_TOOL" ]; then
        SHOT="$SCREENSHOT_DIR/s${SN}.png"
        cmux browser screenshot --surface "surface:${SN}" --out "$SHOT" 2>/dev/null
        if [ -f "$SHOT" ]; then
            OCR=$("$ANE_TOOL" ocr "$SHOT" 2>/dev/null)
            if echo "$OCR" | grep -qiE "hit your limit|rate limit"; then
                STATUS="RATE_LIMITED_VISION"
            elif echo "$OCR" | grep -qE "TASK:|DONE→"; then
                STATUS="QUEUED_VISION"
            fi
        fi
    fi

    # Calculate idle duration if IDLE
    IDLE_SECONDS=""
    if [ "$STATUS" = "IDLE" ] && [ -n "$PREV_EPOCH_TS" ] && [ "$PREV_EPOCH_TS" != "0" ]; then
        PREV_STATUS=""
        for entry in $PREV_STATUS_MAP; do
            if [ "${entry%%:*}" = "$SN" ]; then
                PREV_STATUS="${entry##*:}"
                break
            fi
        done
        if [ "$PREV_STATUS" = "IDLE" ]; then
            IDLE_SECONDS=$((CURRENT_EPOCH - PREV_EPOCH_TS))
            if [ "$IDLE_SECONDS" -gt "$IDLE_THRESHOLD" ]; then
                IDLE_ALERT=true
            fi
        fi
    fi

    # Build output
    [ "$FIRST" = "true" ] || echo -n ","
    if [ -n "$IDLE_SECONDS" ]; then
        echo "\"${SN}\":{\"workspace\":\"${WS}\",\"status\":\"${STATUS}\",\"idle_seconds\":${IDLE_SECONDS}}"
    else
        echo "\"${SN}\":{\"workspace\":\"${WS}\",\"status\":\"${STATUS}\"}"
    fi
    FIRST=false
done

echo '}}'

# Add IDLE_ALERT if any surface exceeded threshold
if [ "$IDLE_ALERT" = true ]; then
    echo ""
    echo "IDLE_ALERT: One or more surfaces idle for more than ${IDLE_THRESHOLD} seconds"
fi

# Save current status to prev file for next run
echo "{\"timestamp\":\"$CURRENT_TIMESTAMP\",\"surfaces\":{" > "$PREV_FILE"
FIRST=true
for SN in $SURFACES; do
    echo "$RL_POOL" | grep -q "$SN" && continue
    WS=$(function_resolve_workspace "$SN")
    TEXT=$(cmux read-screen --workspace "$WS" --surface "surface:${SN}" --lines 8 2>&1)
    STATUS="IDLE"
    if echo "$TEXT" | grep -qiE "hit your limit|rate.?limit|429"; then
        STATUS="RATE_LIMITED"
    elif echo "$TEXT" | grep -qE "Working \(|Ionizing|Crunching|Forming|Ebbing"; then
        STATUS="WORKING"
    elif echo "$TEXT" | grep -qE "TASK:|summary→|⛔no subagent|/clear[A-Z]"; then
        STATUS="QUEUED"
    elif echo "$TEXT" | grep -q "^DONE$\|^  DONE$"; then
        STATUS="DONE"
    fi
    [ "$FIRST" = "true" ] || echo -n "," >> "$PREV_FILE"
    echo -n "\"${SN}\":{\"status\":\"${STATUS}\"}" >> "$PREV_FILE"
    FIRST=false
done
echo "}}" >> "$PREV_FILE"
