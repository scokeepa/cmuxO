#!/bin/bash
# cmux-settings-backup.sh — ConfigChange hook
# matcher: (전체), timeout: 10s
# 역할: 3중 백업(로컬 2세대) + GATE 삭제 exit 2 차단 (S2)

set -u
INPUT_JSON=$(cat)

command -v jq >/dev/null 2>&1 || exit 0
[ -f /tmp/cmux-orch-enabled ] || exit 0

SOURCE=$(echo "$INPUT_JSON" | jq -r '.source // ""')
SETTINGS="$HOME/.claude/settings.json"
BACKUP_DIR="$HOME/.claude/cmux-jarvis/backups"
mkdir -p "$BACKUP_DIR"

# --- GATE 삭제 방어 (META-1, S2) ---
# settings.json 변경 시 jarvis-gate hook이 삭제되었는지 체크
if [ "$SOURCE" = "user_settings" ] && [ -f "$SETTINGS" ]; then
  GATE_EXISTS=$(python3 -c "
import json
try:
    with open('$SETTINGS') as f: data = json.load(f)
    hooks = data.get('hooks', {})
    for event, groups in hooks.items():
        for g in (groups if isinstance(groups, list) else [groups]):
            for h in g.get('hooks', []):
                if 'cmux-jarvis-gate' in h.get('command', ''):
                    print('found')
                    exit()
    print('missing')
except:
    print('error')
" 2>/dev/null)

  if [ "$GATE_EXISTS" = "missing" ]; then
    echo "JARVIS GATE hook 삭제 감지. 변경 차단." >&2
    exit 2  # Claude Code가 변경을 세션에 적용하지 않음
  fi
fi

# --- 설정 백업 (2세대 로테이션) ---
if [ -f "$SETTINGS" ]; then
  # flock으로 1회만 실행 (Boss/Watcher/JARVIS 중복 방지)
  LOCK="/tmp/cmux-jarvis-backup.lock"
  exec 9>"$LOCK"
  flock -n 9 || exit 0

  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  LATEST="$BACKUP_DIR/settings-latest.json"
  PREV="$BACKUP_DIR/settings-prev.json"

  # 로테이션
  [ -f "$LATEST" ] && mv "$LATEST" "$PREV"

  # 원자적 복사
  cp "$SETTINGS" "/tmp/jarvis-backup-$$.json"
  mv "/tmp/jarvis-backup-$$.json" "$LATEST"

  exec 9>&-
fi

echo '{"continue":true,"suppressOutput":true}'
