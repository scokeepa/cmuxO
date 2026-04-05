#!/bin/bash
# cmux-logger.sh — 중앙 집중 로깅 유틸리티
# source 해서 cmux_log 함수 사용

CMUX_LOG_DIR="$HOME/.cmux-logs"
mkdir -p "$CMUX_LOG_DIR"

cmux_log() {
    local level="${1:-INFO}"
    local msg="${2:-}"
    local log_file="$CMUX_LOG_DIR/cmux-$(date +%Y%m%d).log"
    echo "[$(date '+%H:%M:%S')] [$level] $msg" >> "$log_file"
}

# 7일 이상 된 로그 자동 삭제
cmux_log_rotate() {
    find "$CMUX_LOG_DIR" -name "cmux-*.log" -mtime +7 -delete 2>/dev/null
}
