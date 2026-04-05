#!/bin/bash
# cmux-watcher activation hook (v4.0)
# 스킬 로드 시 4계층 풀스캔 + adaptive polling 무한 루프 자동 시작
# 강제 수단: 프로세스 죽으면 자동 재시작, 상태 파일로 health check

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SKILL_DIR/scripts/watcher-scan.py"
LOG_FILE="/tmp/cmux-watcher.log"
STATE_FILE="/tmp/cmux-watcher-state.json"
WATCHDOG_PID_FILE="/tmp/cmux-watcher-watchdog.pid"

# Watcher role marker
if command -v cmux >/dev/null 2>&1; then
    WATCHER_SID=$(cmux identify 2>/dev/null | python3 -c "
import json,sys
try:
    data = json.load(sys.stdin)
    print(data.get('caller',{}).get('surface_ref','').replace('surface:',''))
except: pass
" 2>/dev/null)
    if [ -n "$WATCHER_SID" ]; then
        echo "watcher" > "/tmp/cmux-role-s${WATCHER_SID}.txt"
        echo "[cmux-watcher] Role marker: surface:${WATCHER_SID} = watcher"
    fi
fi

# 오케스트레이션 모드 활성화
touch /tmp/cmux-orch-enabled

# 이전 프로세스 전부 정리
pkill -f "watcher-scan.py.*--continuous" 2>/dev/null || true
sleep 1

# 플래그 초기화 (깨끗한 시작)
rm -f /tmp/cmux-vdiff-prev.json /tmp/cmux-pipe-pane-initialized.flag

# =============================================================
# Watchdog: watcher-scan.py가 죽으면 자동 재시작
# 120초 이상 상태 파일 미갱신 시에도 재시작 (멈춤 감지)
# =============================================================
(
    while true; do
        # watcher-scan.py 실행 (foreground in subshell)
        python3 "$SCRIPT" --continuous 60 --notify-main --json >> "$LOG_FILE" 2>&1 &
        SCAN_PID=$!
        echo "$SCAN_PID" > "/tmp/cmux-watcher-scan.pid"
        echo "[$(date)] watcher-scan 시작 PID=$SCAN_PID" >> "$LOG_FILE"

        # Health check loop: 매 30초 상태 파일 확인
        while kill -0 "$SCAN_PID" 2>/dev/null; do
            sleep 30

            # 상태 파일이 120초 이상 오래됐으면 멈춘 것 → 강제 재시작
            if [ -f "$STATE_FILE" ]; then
                FILE_AGE=$(( $(date +%s) - $(stat -f %m "$STATE_FILE" 2>/dev/null || echo 0) ))
                if [ "$FILE_AGE" -gt 180 ]; then
                    echo "[$(date)] WATCHDOG: 상태 파일 ${FILE_AGE}초 미갱신 → 강제 재시작" >> "$LOG_FILE"
                    kill "$SCAN_PID" 2>/dev/null || true
                    sleep 2
                    break
                fi
            fi
        done

        echo "[$(date)] watcher-scan 종료 → 2초 후 재시작" >> "$LOG_FILE"
        sleep 2
    done
) > /dev/null 2>&1 &

WATCHDOG_PID=$!
echo "$WATCHDOG_PID" > "$WATCHDOG_PID_FILE"

echo "[cmux-watcher] v4.0 watchdog 시작 (PID: $WATCHDOG_PID)"
echo "[cmux-watcher] 4계층 강제: L1(Eagle) L2(ANE-OCR) L2.5(VisionDiff) L3(pipe-pane)"
echo "[cmux-watcher] adaptive polling: Main IDLE→120s, WORKING→60s, 배정중→15s"
echo "[cmux-watcher] 로그: $LOG_FILE"
