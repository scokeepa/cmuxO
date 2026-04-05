#!/bin/bash
# cmux-claude-bridge.sh — Claude Code ↔ cmux 자동 연결 브릿지
# 공식 문서 기반 (https://cmux.dev/docs/notifications)
#
# Claude Code hooks에서 호출되어 cmux claude-hook + notify + set-status 전달.
# settings.json에 등록하면 Claude 세션 라이프사이클이 cmux에 자동 반영.
#
# 등록 위치 (settings.json hooks):
#   SessionStart: bash cmux-claude-bridge.sh session-start
#   Stop:         bash cmux-claude-bridge.sh stop
#   Notification: bash cmux-claude-bridge.sh notification
#   PostToolUse:  bash cmux-claude-bridge.sh post-tool  (stdin에 JSON)

# cmux 소켓이 없으면 무시 (cmux 외 터미널)
[ -S "${CMUX_SOCKET_PATH:-$HOME/Library/Application Support/cmux/cmux.sock}" ] || exit 0
[ -n "$CMUX_WORKSPACE_ID" ] || exit 0
command -v cmux &>/dev/null || exit 0

variable_event="${1:-session-start}"  # $1 = 이벤트 타입

case "$variable_event" in
  session-start|active)
    echo '{"event":"session-start"}' | cmux claude-hook session-start > /dev/null 2>&1
    cmux set-status "claude" "Running" --icon "bolt" --color "#22c55e" > /dev/null 2>&1
    cmux log --level info --source claude "Session started" > /dev/null 2>&1
    ;;
  stop|idle)
    echo '{"event":"stop"}' | cmux claude-hook stop > /dev/null 2>&1
    cmux set-status "claude" "Idle" --icon "circle" --color "#6b7280" > /dev/null 2>&1
    cmux notify --title "Claude Code" --body "Session complete" > /dev/null 2>&1
    cmux log --level success --source claude "Session stopped" > /dev/null 2>&1
    ;;
  notification|notify)
    variable_body=$(cat 2>/dev/null || echo '{}')
    echo "$variable_body" | cmux claude-hook notification > /dev/null 2>&1
    ;;
  prompt-submit)
    echo '{}' | cmux claude-hook prompt-submit > /dev/null 2>&1
    cmux set-status "claude" "Working" --icon "loader" --color "#f59e0b" > /dev/null 2>&1
    ;;
  post-tool)
    # PostToolUse: Agent/Task 완료 시 알림
    variable_json=$(cat 2>/dev/null || echo '{}')
    variable_tool=$(echo "$variable_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")
    if [ "$variable_tool" = "Agent" ] || [ "$variable_tool" = "Task" ]; then
      cmux notify --title "Claude Code" --body "Agent finished: $variable_tool" > /dev/null 2>&1
      cmux log --level success --source claude "Agent completed: $variable_tool" > /dev/null 2>&1
    fi
    ;;
  *)
    echo '{}' | cmux claude-hook "$variable_event" > /dev/null 2>&1
    ;;
esac

exit 0
