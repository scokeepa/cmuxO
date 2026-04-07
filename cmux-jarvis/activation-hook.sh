#!/bin/bash
# cmux-jarvis activation hook
# 설치 시 hook 심링크 + settings.json 등록 + 초기 디렉토리 생성

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_SOURCE="$SKILL_DIR/hooks"
HOOKS_TARGET="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
JARVIS_DIR="$HOME/.claude/cmux-jarvis"

# 초기 디렉토리 생성
mkdir -p "$JARVIS_DIR/evolutions"
mkdir -p "$HOOKS_TARGET"

# === Hook 심링크 ===
INSTALLED=0
SKIPPED=0
for f in "$HOOKS_SOURCE"/*.sh; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  link="$HOOKS_TARGET/$fname"
  if [ -L "$link" ] || [ -f "$link" ]; then
    SKIPPED=$((SKIPPED + 1))
  else
    ln -s "$f" "$link"
    chmod +x "$f"
    INSTALLED=$((INSTALLED + 1))
  fi
done
echo "  JARVIS hooks: 설치 $INSTALLED, 스킵 $SKIPPED"

# === scripts 실행 권한 ===
for f in "$SKILL_DIR/scripts/"*.sh; do
  [ -f "$f" ] && chmod +x "$f"
done

# === settings.json Hook 등록 ===
[ ! -f "$SETTINGS" ] && echo "  settings.json 없음 — 건너뜀" && exit 0

python3 << 'PYEOF'
import json, os

settings_path = os.path.expanduser("~/.claude/settings.json")
with open(settings_path) as f:
    data = json.load(f)

if "hooks" not in data:
    data["hooks"] = {}

hooks = data["hooks"]

HOOK_MAP = {
    "cmux-jarvis-gate.sh": ("PreToolUse", "Edit|Write|Bash", 3000),
    "cmux-settings-backup.sh": ("ConfigChange", None, 3000),
    "jarvis-session-start.sh": ("SessionStart", None, 3000),
    "jarvis-file-changed.sh": ("FileChanged", "cmux-eagle-status.json|cmux-watcher-alerts.json", 3000),
    "jarvis-pre-compact.sh": ("PreCompact", None, 3000),
    "jarvis-post-compact.sh": ("PostCompact", None, 3000),
}

added = 0
for filename, (event, matcher, timeout) in HOOK_MAP.items():
    if event not in hooks:
        hooks[event] = []

    # 중복 체크 (모든 그룹의 모든 hook에서 파일명 검색)
    exists = False
    for group in hooks[event]:
        if isinstance(group, dict):
            for h in group.get("hooks", []):
                if filename in h.get("command", ""):
                    exists = True
                    break
    if exists:
        continue

    entry = {
        "type": "command",
        "command": f"bash ~/.claude/hooks/{filename}" if filename.endswith(".sh") else f"python3 ~/.claude/hooks/{filename}",
        "timeout": timeout,
    }

    if matcher:
        # 새 그룹으로 추가
        hooks[event].append({"matcher": matcher, "hooks": [entry]})
    else:
        # 빈 matcher 그룹 찾기 또는 생성
        found = False
        for group in hooks[event]:
            if isinstance(group, dict) and group.get("matcher", "") == "":
                group.setdefault("hooks", []).append(entry)
                found = True
                break
        if not found:
            hooks[event].append({"matcher": "", "hooks": [entry]})
    added += 1

with open(settings_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"  JARVIS settings.json: {added}개 hook 등록")
PYEOF

# === config.json 초기화 ===
CONFIG="$JARVIS_DIR/config.json"
if [ ! -f "$CONFIG" ]; then
  cat > "$CONFIG" << 'JSON'
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
JSON
  echo "  JARVIS config.json 초기화"
fi

echo "  JARVIS activation 완료"
