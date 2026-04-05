#!/bin/bash
# surface-dispatcher.sh v7 — Dynamic workspace resolution
#   v6 fixes: glyph filtering, DONE detection (last 10 lines + fallback)
#   v7 fix: auto workspace resolution via workspace-resolver.sh (no more cross-workspace ERR)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/workspace-resolver.sh"

SURFACES="${1:-39 32 41 42 43 44 27 38}"
REPORT=""

for S in $SURFACES; do
    # v7: Auto-resolve workspace for each surface
    SCREEN=$(function_read_any_surface "$S" 30) || SCREEN=""

    # ── Empty screen fallback ──
    if [ -z "$SCREEN" ]; then
        REPORT="${REPORT}S:${S}=ERR "
        continue
    fi

    # ── Glyph filtering (before ACTIVE detection) ──
    SCREEN_CLEAN=$(echo "$SCREEN" | sed 's/✻/ /g; s/✶/ /g; s/✽/ /g; s/✢/ /g; s/✳/ /g; s/⏺/ /g; s/·/ /g')

    # ── DONE detection (last 10 lines first + full fallback) ──
    LAST10=$(echo "$SCREEN_CLEAN" | tail -n 10)
    REAL_DONE=0
    if echo "$LAST10" | grep -qE "^\s*DONE\s*$"; then
        REAL_DONE=1
    elif echo "$SCREEN_CLEAN" | grep -qE "^\s*DONE\s*$"; then
        REAL_DONE=1
    fi

    # ── Status determination ──
    if [ "$REAL_DONE" -ge 1 ]; then
        STATUS="DONE"
    elif echo "$SCREEN" | grep -q "Press up to edit queued"; then
        STATUS="QUEUED"
    elif echo "$SCREEN" | grep -qE "until auto-compact|until auto-co"; then
        STATUS="COMPACT!"
    elif echo "$SCREEN_CLEAN" | grep -qE "429|Usage limit|Rate limit"; then
        STATUS="RATE_LIM"
    elif echo "$SCREEN_CLEAN" | grep -qE "thinking|thought|tokens|esc to interrupt"; then
        T=$(echo "$SCREEN_CLEAN" | grep -oE "[0-9]+m" | head -1 | tr -d 'm')
        T=${T:-0}
        STATUS="WORK(${T}m)"
    elif echo "$SCREEN_CLEAN" | grep -qE "(Churned|Cooked|Baked|Sautéed|Cogitated|Crunched|Brewed|Worked) for [0-9]+m"; then
        T=$(echo "$SCREEN_CLEAN" | grep -oE "[0-9]+m" | head -1 | tr -d 'm')
        T=${T:-0}
        STATUS="ENDED(${T}m)"
    elif echo "$SCREEN_CLEAN" | grep -qE "• Working|⏺ Working|Working \([0-9]+[ms]"; then
        T=$(echo "$SCREEN_CLEAN" | grep -oE "[0-9]+m" | head -1 | tr -d 'm')
        T=${T:-0}
        STATUS="WORK(${T}m)"
    elif echo "$SCREEN_CLEAN" | grep -qE "[A-Za-z]+\s+[0-9]+m\s+[0-9]+s"; then
        T=$(echo "$SCREEN_CLEAN" | grep -oE "[0-9]+m" | head -1 | tr -d 'm')
        T=${T:-0}
        STATUS="ACTIVE(${T}m)"
    else
        STATUS="IDLE"
    fi

    REPORT="${REPORT}S:${S}=${STATUS} "
done

echo "$REPORT"
