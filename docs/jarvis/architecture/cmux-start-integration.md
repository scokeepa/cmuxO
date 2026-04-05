# cmux-start JARVIS 통합 상세

> cmux-start/SKILL.md 수정 시 참조.

## Step 2.5: JARVIS pane 생성 (Watcher 직후)

```bash
# E5: 중복 방지
EXISTING=$(jq -r '.jarvis.surface // ""' /tmp/cmux-roles.json 2>/dev/null)
if [ -n "$EXISTING" ]; then
  echo "⚠️ JARVIS 이미 실행 중: $EXISTING. 스킵."
else
  # JARVIS pane 생성 (Main과 같은 workspace)
  RESULT=$(cmux new-pane --direction right)
  JARVIS_SID=$(echo "$RESULT" | awk '{for(i=1;i<=NF;i++) if($i ~ /surface:/) print $i}')

  # Claude Code 시작
  cmux send --surface $JARVIS_SID "claude"

  # 30초 폴링 (Claude 시작 대기)
  for i in $(seq 1 10); do
    sleep 3
    SCREEN=$(cmux read-screen --surface $JARVIS_SID --lines 5 2>/dev/null)
    if echo "$SCREEN" | grep -qE "❯|shortcuts|trust"; then break; fi
  done
  cmux send-key --surface $JARVIS_SID Enter
  sleep 2

  # roles.json에 jarvis 등록
  python3 -c "
import json, os
from datetime import datetime, timezone
roles_file = '/tmp/cmux-roles.json'
with open(roles_file) as f: roles = json.load(f)
roles['jarvis'] = {
    'surface': '$JARVIS_SID',
    'workspace': '$MAIN_WS',
    'started_at': datetime.now(timezone.utc).isoformat(),
    'last_heartbeat': datetime.now(timezone.utc).isoformat()
}
with open(roles_file, 'w') as f: json.dump(roles, f, indent=2)
"
  echo "✅ JARVIS 시작: $JARVIS_SID"
fi
```

## 복구 체크 (JARVIS 재시작 시)
```bash
# CURRENT_LOCK 확인
LOCK_FILE="$HOME/.claude/cmux-jarvis/.evolution-lock"
if [ -f "$LOCK_FILE" ]; then
  TTL=$(jq -r '.ttl_minutes' "$LOCK_FILE")
  CREATED=$(jq -r '.created_at' "$LOCK_FILE")
  # TTL 초과 → stale lock 해제 + 롤백
  # Worker 살아있음 → 대기
  # Worker 죽음 → Circuit Breaker
fi
```

## config.json 초기화 (M1)
```json
{
  "obsidian_vault_path": null,
  "poll_interval_seconds": 300,
  "max_consecutive_evolutions": 3,
  "max_daily_evolutions": 10,
  "queue_max_size": 5,
  "approval_timeout_minutes": 30,
  "lock_ttl_minutes": 60,
  "debounce_seconds": 60
}
```
