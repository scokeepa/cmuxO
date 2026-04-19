#!/bin/bash
# cmux-idle-reminder.sh — UserPromptSubmit hook
# 매 사용자 메시지마다: IDLE/WAITING surface가 있으면 AI에게 알림
# 부하: eagle_watcher.sh --once (bash only, API 0원, ~1초)

# 오케스트레이션 모드 아니면 패스
[ -f /tmp/cmux-orch-enabled ] || exit 0
# cmux 아니면 무시
[ -n "$CMUX_WORKSPACE_ID" ] || exit 0
command -v cmux &>/dev/null || exit 0

# eagle 스크립트 존재 확인
variable_eagle="$HOME/.claude/skills/cmux-orchestrator/scripts/eagle_watcher.sh"
[ -f "$variable_eagle" ] || exit 0

# eagle --once 실행 (API 0원, bash만 사용)
bash "$variable_eagle" --once > /dev/null 2>&1

# 상태 파일 읽기
variable_status_file="/tmp/cmux-eagle-status.json"
[ -f "$variable_status_file" ] || exit 0

# IDLE surface 확인
variable_idle_info=$(python3 -c "
import json
with open('$variable_status_file') as f:
    d = json.load(f)
idle = d.get('idle_surfaces', '').strip()
if idle:
    parts = []
    for sid in idle.split():
        ai = d.get('surfaces', {}).get(sid, {}).get('ai', '?')
        parts.append(f'surface:{sid}({ai})')
    print(f'{len(parts)}|{', '.join(parts)}')
" 2>/dev/null)

# WAITING surface 확인 (질문 대기 중)
variable_waiting_info=$(python3 -c "
import json
with open('$variable_status_file') as f:
    d = json.load(f)
waiting = d.get('waiting_surfaces', '').strip()
if waiting:
    parts = []
    for sid in waiting.split():
        ai = d.get('surfaces', {}).get(sid, {}).get('ai', '?')
        parts.append(f'surface:{sid}({ai})')
    print(f'{len(parts)}|{', '.join(parts)}')
" 2>/dev/null)

# IDLE 경고 출력 (schema: hookSpecificOutput.additionalContext — coreSchemas.ts:907)
if [ -n "$variable_idle_info" ]; then
  variable_count=$(echo "$variable_idle_info" | cut -d'|' -f1)
  variable_details=$(echo "$variable_idle_info" | cut -d'|' -f2)
  HOOK_CTX="[CMUX-IDLE] ${variable_count}개 IDLE: ${variable_details}. 병렬 가능하면 cmux send 위임." python3 - <<'PY'
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": os.environ.get("HOOK_CTX", ""),
    }
}, ensure_ascii=False))
PY
fi

# WAITING 경고 출력 (별도)
if [ -n "$variable_waiting_info" ]; then
  variable_count=$(echo "$variable_waiting_info" | cut -d'|' -f1)
  variable_details=$(echo "$variable_waiting_info" | cut -d'|' -f2)
  HOOK_CTX="⚠️ WAITING (질문 대기): ${variable_details} — 답변 필요!" python3 - <<'PY'
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": os.environ.get("HOOK_CTX", ""),
    }
}, ensure_ascii=False))
PY
fi
