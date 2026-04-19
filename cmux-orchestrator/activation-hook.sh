#!/bin/bash
# cmux-orchestrator activation hook
# 스킬 로드 시 자동 실행 — Hook 심링크 + settings.json 등록
# 다른 AI가 이 스킬을 설치/로드할 때 자동으로 강제 수단이 활성화됨

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_SOURCE="$SKILL_DIR/hooks"
HOOKS_TARGET="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
INSTALL_FLAG_DIR="$HOME/.claude/.state"
mkdir -p "$INSTALL_FLAG_DIR" 2>/dev/null
INSTALL_FLAG="$INSTALL_FLAG_DIR/cmux-orch-hooks-installed.flag"

# 이미 이번 세션에서 설치했으면 스킵 (성능)
if [ -f "$INSTALL_FLAG" ]; then
    flag_mtime=$(stat -f %m "$INSTALL_FLAG" 2>/dev/null || stat -c %Y "$INSTALL_FLAG" 2>/dev/null || echo "")
    if [ -n "$flag_mtime" ]; then
        flag_age=$(( $(date +%s) - flag_mtime ))
        if [ "$flag_age" -lt 3600 ]; then
            exit 0
        fi
    fi
fi

# Hook 디렉토리 없으면 설치할 것 없음
if [ ! -d "$HOOKS_SOURCE" ]; then
    exit 0
fi

mkdir -p "$HOOKS_TARGET"

# 메모리 디렉토리 초기화
mkdir -p -m 700 "$HOME/.claude/memory/cmux" 2>/dev/null

# Step 1: 심링크 생성 (없는 것만)
installed=0
for f in "$HOOKS_SOURCE"/*.sh "$HOOKS_SOURCE"/*.py; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    # test 파일은 운영 hooks에 symlink하지 않음
    case "$fname" in test-*) continue ;; esac
    link="$HOOKS_TARGET/$fname"

    if [ ! -L "$link" ] && [ ! -f "$link" ]; then
        ln -s "$f" "$link"
        chmod +x "$f"
        installed=$((installed + 1))
    fi
done

# Watcher hooks도 처리
WATCHER_HOOKS="$HOME/.claude/skills/cmux-watcher/hooks"
if [ -d "$WATCHER_HOOKS" ]; then
    for f in "$WATCHER_HOOKS"/*.sh "$WATCHER_HOOKS"/*.py; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        link="$HOOKS_TARGET/$fname"
        if [ ! -L "$link" ] && [ ! -f "$link" ]; then
            ln -s "$f" "$link"
            chmod +x "$f"
            installed=$((installed + 1))
        fi
    done
fi

# Step 2: settings.json 자동 등록 (없는 것만)
if [ -f "$SETTINGS" ] && command -v python3 >/dev/null 2>&1; then
    python3 - "$SETTINGS" << 'PYEOF'
import json, sys, os

settings_path = sys.argv[1]
with open(settings_path) as f:
    data = json.load(f)

if "hooks" not in data:
    data["hooks"] = {}
hooks = data["hooks"]

HOOK_MAP = {
    "cmux-init-enforcer.py": ("PreToolUse", "Bash", 3),
    "cmux-watcher-notify-enforcer.py": ("PreToolUse", "Bash", 3),
    "cmux-no-stall-enforcer.py": ("PreToolUse", "Bash|Agent", 3),
    "cmux-gate6-agent-block.sh": ("PreToolUse", "Agent", 5),
    "cmux-read-guard.sh": ("PreToolUse", "Bash", 5),
    "cmux-watcher-msg-guard.py": ("PreToolUse", "Bash", 3),
    "cmux-completion-verifier.py": ("PreToolUse", "Bash", 3),
    "cmux-workflow-state-machine.py": ("PreToolUse", "Bash|Agent", 3),
    "cmux-dispatch-notify.sh": ("PostToolUse", "Bash", 3),
    "cmux-idle-reuse-enforcer.py": ("PostToolUse", "Bash", 3),
    "cmux-setbuffer-fallback.py": ("PostToolUse", "Bash", 3),
    "cmux-enforcement-escalator.py": ("PostToolUse", "Bash|Agent", 3),
    "cmux-idle-reminder.sh": ("UserPromptSubmit", None, 5),
    "cmux-main-context.sh": ("UserPromptSubmit", None, 10),
    "cmux-stop-guard.sh": ("Stop", None, 5),
    "cmux-model-profile-hook.sh": ("SessionStart", None, 5),
    "cmux-hook-audit.sh": ("SessionStart", None, 5),
    "cmux-watcher-session.sh": ("SessionStart", None, 5),
    "cmux-watcher-activate.sh": ("UserPromptSubmit", None, 120),
    "cmux-control-tower-guard.py": ("PreToolUse", "Bash", 3),
    "cmux-send-guard.py": ("PreToolUse", "Bash", 3),
    "cmux-leceipts-gate.py": ("PreToolUse", "Bash", 3),
    "cmux-memory-recorder.sh": ("PostToolUse", "Bash", 3),
    "cmux-plan-quality-gate.py": ("PreToolUse", "ExitPlanMode", 5),
}

def _hook_exists_in_group(match_pattern, group):
    """grouped 또는 flat 엔트리에서 hook 존재 여부 + 기존 엔트리 반환."""
    if not isinstance(group, dict):
        return False, None  # 비정상 엔트리 무시
    if "hooks" in group:
        for h in group.get("hooks", []):
            if isinstance(h, dict) and match_pattern in h.get("command", ""):
                return True, h
    elif "command" in group:
        if match_pattern in group.get("command", ""):
            return True, group
    return False, None

added = 0
updated = 0
hooks_dir = os.path.expanduser("~/.claude/hooks")

for filename, (event, matcher, timeout) in HOOK_MAP.items():
    if event not in hooks:
        hooks[event] = []

    # symlink 존재 확인 (#7)
    hook_path = os.path.join(hooks_dir, filename)
    if not os.path.exists(hook_path):
        continue  # symlink 없으면 등록 스킵

    match_pattern = f"/hooks/{filename}"
    matcher_key = "" if matcher is None else matcher  # None → "" 명시 변환 (#10, #12)

    # 기존 hook 검색 (#11 정리)
    existing_entry = None
    for group in hooks[event]:
        found, entry = _hook_exists_in_group(match_pattern, group)
        if found:
            existing_entry = entry
            break

    if existing_entry is not None:
        # timeout 불일치 업데이트 (#2)
        if existing_entry.get("timeout") != timeout:
            existing_entry["timeout"] = timeout
            updated += 1
        continue

    ext = os.path.splitext(filename)[1]
    prefix = "python3" if ext == ".py" else "bash"
    hook_entry = {"type": "command", "command": f"{prefix} ~/.claude/hooks/{filename}", "timeout": timeout}

    # grouped 포맷으로 등록: 같은 matcher 그룹에 추가
    group_found = False
    for group in hooks[event]:
        if isinstance(group, dict) and group.get("matcher", "") == matcher_key and "hooks" in group:
            group["hooks"].append(hook_entry)
            group_found = True
            break
    if not group_found:
        hooks[event].append({"matcher": matcher_key, "hooks": [hook_entry]})
    added += 1

if added > 0 or updated > 0:
    import tempfile as _tf
    _fd, _tmp = _tf.mkstemp(dir=os.path.dirname(settings_path), suffix=".tmp")
    try:
        with os.fdopen(_fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.rename(_tmp, settings_path)
    except Exception:
        try: os.unlink(_tmp)
        except: pass
        raise
PYEOF
fi

# 오케스트레이션 모드 활성화는 /cmux-start에서만 수행 (cmux-start/SKILL.md:202)
# activation-hook에서 touch하면 스킬 로드만으로 훅이 활성화되는 불변식 위반 (레드팀 Finding 1)

# 설치 완료 플래그
touch "$INSTALL_FLAG"

# 설치 안내 메시지 (첫 설치 시 한 번만)
WELCOME_FLAG="/tmp/cmux-welcome-shown.flag"
if [ ! -f "$WELCOME_FLAG" ]; then
    cat << 'WELCOME'

  ====================================================
   cmux AI 다중 자동 협업 플랫폼 - 설치 완료!
  ====================================================

   시작:
     /cmux-start             오케스트레이션 시작 (이것만!)

   설정:
     /cmux-config            AI 프로파일 확인
     /cmux-config detect     설치된 AI 자동 감지
     /cmux-config add <AI>   AI 추가 (커스텀 가능)
     /cmux-help              명령어 도움말

   제거:
     /cmux-uninstall         완전 제거 + 롤백

   개별 작업:
     /cmux-start 실행 전까지 일반 Claude Code로 사용.
     Hook 간섭 없음.

  ====================================================

WELCOME
    touch "$WELCOME_FLAG"
fi

exit 0
