#!/bin/bash
# cmux-memory-recorder.sh — PostToolUse:Bash Hook (SILENT_EXIT)
# 오케스트레이션 이벤트 자동 기록 → journal.jsonl
#
# 동작: cmux send/set-buffer/create-workspace 등 오케스트레이션 명령 감지 시
#       ~/.claude/memory/cmux/journal.jsonl에 JSONL 이벤트 기록.
#
# 카테고리: SILENT_EXIT — 빈 stdin/에러 시 stdout 없이 exit 0
# 5MB 초과 시 기록 스킵 (drain에서 rotation 처리)
#
# 출력 스키마: Claude Code SyncHookJSONOutputSchema (coreSchemas.ts:907).
# pass-through는 exit 0 + 빈 stdout.

# 1. 모드 게이트
[ -f /tmp/cmux-orch-enabled ] || exit 0

# 2. stdin 읽기 (fail-silent: 빈/에러 → exit 0, stderr 없음)
INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0

# 3. command 추출 (python3 — 90% 패턴 일관성)
COMMAND=$(echo "$INPUT" | python3 -c "
import json,sys
try:
    d=json.loads(sys.stdin.read())
    print(d.get('tool_input',{}).get('command',''))
except: print('')
" 2>/dev/null)
[ -z "$COMMAND" ] && exit 0

# 4. allowlist 매칭 (dispatch + 부서 관리 + 제어탑)
echo "$COMMAND" | grep -qE 'cmux (send|set-buffer|paste-buffer|create-workspace|close-workspace|reorder-workspace)' || exit 0

# 5. 메모리 디렉토리 확인
MEMORY_DIR="$HOME/.claude/memory/cmux"
mkdir -p -m 700 "$MEMORY_DIR" 2>/dev/null
JOURNAL="$MEMORY_DIR/journal.jsonl"

# 6. 5MB 체크
if [ -f "$JOURNAL" ]; then
  SIZE=$(stat -f%z "$JOURNAL" 2>/dev/null || stat -c%s "$JOURNAL" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 5242880 ]; then
    echo "[cmux-memory-recorder] WARN: journal > 5MB, skipping. Run: bash agent-memory.sh drain" >&2
    exit 0
  fi
fi

# 7. 이벤트 기록 (python3)
python3 -c "
import json, re, sys
from datetime import datetime, timezone

cmd = sys.argv[1]
event = 'unknown'
if re.search(r'cmux (send|set-buffer|paste-buffer)', cmd): event = 'dispatch'
elif 'create-workspace' in cmd: event = 'dept_create'
elif 'close-workspace' in cmd: event = 'dept_close'
elif 'reorder-workspace' in cmd: event = 'reorder'

surface = ''
m = re.search(r'surface:(\d+)', cmd)
if m: surface = f'surface:{m.group(1)}'

entry = {
    'ts': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'event': event,
    'surface': surface,
    'cmd_short': cmd[:200],
}
print(json.dumps(entry, ensure_ascii=False))
" "$COMMAND" >> "$JOURNAL" 2>/dev/null

exit 0
