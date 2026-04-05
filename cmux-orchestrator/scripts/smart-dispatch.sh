#!/bin/bash
# smart-dispatch.sh — Send task + verify execution + 30s stall check
# Usage: bash smart-dispatch.sh <workspace> <surface> "task prompt"
# Returns: 0=executing, 1=stalled, 2=rate_limited

WS="$1"; SF="$2"; TASK="$3"
[ -z "$WS" ] || [ -z "$SF" ] || [ -z "$TASK" ] && { echo "Usage: smart-dispatch.sh workspace:N surface:N 'task'"; exit 1; }

FOOTER='⛔no subagent/git. ⛔no questions. ⛔you are worker not orchestrator. After: summary→5blank→DONE→2blank→DONE'

# Step 1: Pre-check — rate limit?
PRE=$(cmux read-screen --workspace "$WS" --surface "$SF" --lines 8 2>&1)
if echo "$PRE" | grep -qiE "hit your limit|rate.?limit|429"; then
    echo '{"status":"RATE_LIMITED","surface":"'$SF'"}'
    exit 2
fi

# Step 2: Send task (set-buffer for long, send for short)
if [ ${#TASK} -gt 150 ]; then
    cmux set-buffer --name "sd_$(echo $SF | tr -d ':')" -- "TASK: ${TASK} ${FOOTER}" 2>/dev/null
    cmux paste-buffer --name "sd_$(echo $SF | tr -d ':')" --workspace "$WS" --surface "$SF" 2>/dev/null
else
    cmux send --workspace "$WS" --surface "$SF" "TASK: ${TASK} ${FOOTER}" 2>/dev/null
fi
cmux send-key --workspace "$WS" --surface "$SF" enter 2>/dev/null

# Step 3: Immediate check (3s) — did it start?
sleep 3
SNAP_A=$(cmux read-screen --workspace "$WS" --surface "$SF" --lines 10 2>&1)
IMMEDIATE_WORK=$(echo "$SNAP_A" | grep -cE "Working|Ionizing|Forming|Simmering|Crunching|Ebbing|Mustering|Blanching")

if [ "$IMMEDIATE_WORK" -gt 0 ]; then
    echo '{"status":"EXECUTING","surface":"'$SF'","detected_at":"immediate"}'
    exit 0
fi

# Step 4: 30s diff check — screen changed?
sleep 27  # total 30s from send
SNAP_B=$(cmux read-screen --workspace "$WS" --surface "$SF" --lines 10 2>&1)

if [ "$SNAP_A" = "$SNAP_B" ]; then
    # Screen unchanged 30s — check if it completed fast (DONE visible)
    if echo "$SNAP_B" | grep -q "DONE"; then
        echo '{"status":"DONE_FAST","surface":"'$SF'"}'
        exit 0
    fi
    echo '{"status":"STALLED","surface":"'$SF'"}'
    exit 1
else
    echo '{"status":"EXECUTING","surface":"'$SF'","detected_at":"30s_diff"}'
    exit 0
fi
