#!/bin/bash
# cmux-dispatch-notify.sh — cmux 디스패치 시 와쳐 자동 알림
# PostToolUse:Bash hook — cmux send/set-buffer 감지 시 display-message
#
# 출력 스키마: Claude Code SyncHookJSONOutputSchema (coreSchemas.ts:907).
# pass-through는 exit 0 + 빈 stdout (PostToolUse는 차단 불가, 부가 정보만 주입).

# 오케스트레이션 모드 아니면 패스
[ -f /tmp/cmux-orch-enabled ] || exit 0
# jq로 tool_input.command 파싱
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

# cmux send 또는 set-buffer 감지
if echo "$COMMAND" | grep -qE 'cmux (send|set-buffer|paste-buffer)'; then
  # surface 번호 추출
  SURFACE=$(echo "$COMMAND" | grep -oE 'surface:[0-9]+' | head -1)

  if [ -n "$SURFACE" ]; then
    # 와쳐에 알림 (비동기, 실패해도 무시)
    cmux display-message "📡 작업 전송: $SURFACE" 2>/dev/null &
  fi
fi

# pass-through (exit 0 + 빈 stdout)
exit 0
