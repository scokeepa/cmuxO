#!/bin/bash
# install.sh — cmux-orchestrator 스킬 설치 스크립트
# 다른 사람 PC에서도 실행 가능하도록 Hook 심링크 + settings.json 자동 등록
#
# 사용법: bash install.sh
# 제거: bash install.sh --uninstall

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_TARGET="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
SKILLS_DIR="$HOME/.claude/skills"
WATCHER_SKILL_DIR="$SKILLS_DIR/cmux-watcher"

# cmux-watcher가 공유스킬 옆에 있으면 자동 설치
WATCHER_SOURCE="$(dirname "$SKILL_DIR")/cmux-watcher"

echo "=== cmux-orchestrator + cmux-watcher 설치 ==="
echo "스킬 경로: $SKILL_DIR"
echo ""

# --- Uninstall mode ---
if [[ "${1:-}" == "--uninstall" ]]; then
    echo "[제거 모드]"
    for f in "$SKILL_DIR"/hooks/*; do
        fname=$(basename "$f")
        link="$HOOKS_TARGET/$fname"
        if [ -L "$link" ]; then
            rm "$link"
            echo "  🗑 $fname 심링크 제거"
        fi
    done
    # watcher hooks
    if [ -d "$WATCHER_SKILL_DIR/hooks" ]; then
        for f in "$WATCHER_SKILL_DIR"/hooks/*; do
            fname=$(basename "$f")
            link="$HOOKS_TARGET/$fname"
            if [ -L "$link" ]; then
                rm "$link"
                echo "  🗑 $fname 심링크 제거"
            fi
        done
    fi
    echo ""
    echo "✅ 심링크 제거 완료. settings.json에서 수동으로 cmux Hook을 제거하세요."
    exit 0
fi

# --- Install mode ---

# Step 0: cmux-watcher 자동 설치 (공유스킬 옆에 있으면)
mkdir -p "$SKILLS_DIR"
mkdir -p "$HOOKS_TARGET"

if [ -d "$WATCHER_SOURCE" ] && [ ! -d "$WATCHER_SKILL_DIR" ]; then
    echo "[Step 0] cmux-watcher 자동 설치"
    cp -r "$WATCHER_SOURCE" "$WATCHER_SKILL_DIR"
    echo "  ✅ cmux-watcher → $WATCHER_SKILL_DIR"
elif [ -d "$WATCHER_SKILL_DIR" ]; then
    echo "[Step 0] cmux-watcher 이미 설치됨"
else
    echo "[Step 0] ⚠️ cmux-watcher 소스 없음 ($WATCHER_SOURCE)"
    echo "  cmux-watcher 폴더를 $(dirname "$SKILL_DIR")/cmux-watcher 에 넣고 다시 실행하세요."
fi

# Step 0.5: cmux-orchestrator 자체를 skills에 복사 (현재 위치가 skills 밖이면)
ORCH_SKILL_DIR="$SKILLS_DIR/cmux-orchestrator"
if [ "$SKILL_DIR" != "$ORCH_SKILL_DIR" ] && [ ! -d "$ORCH_SKILL_DIR" ]; then
    echo "[Step 0.5] cmux-orchestrator → $ORCH_SKILL_DIR"
    cp -r "$SKILL_DIR" "$ORCH_SKILL_DIR"
    echo "  ✅ 복사 완료"
fi

# Step 2: Hook 심링크 생성
echo "[Step 1] Hook 심링크 생성"
installed=0
skipped=0

for f in "$SKILL_DIR"/hooks/*.sh "$SKILL_DIR"/hooks/*.py; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    link="$HOOKS_TARGET/$fname"

    if [ -L "$link" ] || [ -f "$link" ]; then
        echo "  ⏭ $fname (이미 존재)"
        skipped=$((skipped + 1))
    else
        ln -s "$f" "$link"
        chmod +x "$f"
        echo "  ✅ $fname"
        installed=$((installed + 1))
    fi
done

# Watcher hooks
if [ -d "$WATCHER_SKILL_DIR/hooks" ]; then
    for f in "$WATCHER_SKILL_DIR"/hooks/*.sh "$WATCHER_SKILL_DIR"/hooks/*.py; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        link="$HOOKS_TARGET/$fname"

        if [ -L "$link" ] || [ -f "$link" ]; then
            echo "  ⏭ $fname (이미 존재)"
            skipped=$((skipped + 1))
        else
            ln -s "$f" "$link"
            chmod +x "$f"
            echo "  ✅ $fname"
            installed=$((installed + 1))
        fi
    done
fi

echo "  설치: $installed, 스킵: $skipped"
echo ""

# Step 3: settings.json Hook 등록
echo "[Step 2] settings.json Hook 등록"

if [ ! -f "$SETTINGS" ]; then
    echo "  ⚠️ $SETTINGS 없음 — 건너뜀"
    echo "  수동으로 settings.json에 Hook을 등록하세요."
else
    python3 << 'PYEOF'
import json
import os

settings_path = os.path.expanduser("~/.claude/settings.json")
with open(settings_path) as f:
    data = json.load(f)

if "hooks" not in data:
    data["hooks"] = {}

hooks = data["hooks"]

# Hook 등록 매핑: {파일명: (이벤트, matcher, timeout)}
HOOK_MAP = {
    # PreToolUse
    "cmux-init-enforcer.py": ("PreToolUse", "Bash", 3),
    "cmux-watcher-notify-enforcer.py": ("PreToolUse", "Bash", 3),
    "cmux-no-stall-enforcer.py": ("PreToolUse", "Bash|Agent", 3),
    "cmux-gate6-agent-block.sh": ("PreToolUse", "Agent", 5),
    "cmux-read-guard.sh": ("PreToolUse", "Bash", 5),
    "cmux-watcher-msg-guard.py": ("PreToolUse", "Bash", 3),
    "cmux-completion-verifier.py": ("PreToolUse", "Bash", 3),
    "cmux-workflow-state-machine.py": ("PreToolUse", "Bash|Agent", 3),
    # PostToolUse
    "cmux-dispatch-notify.sh": ("PostToolUse", "Bash", 3),
    "cmux-idle-reuse-enforcer.py": ("PostToolUse", "Bash", 3),
    "cmux-setbuffer-fallback.py": ("PostToolUse", "Bash", 3),
    "cmux-enforcement-escalator.py": ("PostToolUse", "Bash|Agent", 3),
    # UserPromptSubmit
    "cmux-idle-reminder.sh": ("UserPromptSubmit", None, 5),
    "cmux-main-context.sh": ("UserPromptSubmit", None, 10),
    # Stop
    "cmux-stop-guard.sh": ("Stop", None, 5),
    # SessionStart
    "cmux-model-profile-hook.sh": ("SessionStart", None, 5),
    "cmux-hook-audit.sh": ("SessionStart", None, 5),
    "cmux-watcher-session.sh": ("SessionStart", None, 5),
    # Watcher hooks
    "cmux-watcher-activate.sh": ("UserPromptSubmit", None, 5),
    # GATE 7 + LECEIPTS + Memory
    "cmux-control-tower-guard.py": ("PreToolUse", "Bash", 3),
    "cmux-send-guard.py": ("PreToolUse", "Bash", 3),
    "cmux-leceipts-gate.py": ("PreToolUse", "Bash", 3),
    "cmux-memory-recorder.sh": ("PostToolUse", "Bash", 3),
    # Plan Quality Gate
    "cmux-plan-quality-gate.py": ("PreToolUse", "ExitPlanMode", 5),
}

added = 0
already = 0

for filename, (event, matcher, timeout) in HOOK_MAP.items():
    if event not in hooks:
        hooks[event] = []

    # Check if already registered
    exists = any(filename in h.get("command", "") for h in hooks[event])
    if exists:
        already += 1
        continue

    entry = {
        "type": "command",
        "command": f"bash ~/.claude/hooks/{filename}" if filename.endswith(".sh") else f"python3 ~/.claude/hooks/{filename}",
        "timeout": timeout,
    }
    if matcher:
        entry["matcher"] = matcher

    hooks[event].append(entry)
    added += 1

with open(settings_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"  등록: {added}, 이미 존재: {already}")
PYEOF
fi

echo ""

# Step 4: 실행 권한 확인
echo "[Step 3] 실행 권한 확인"
for f in "$SKILL_DIR"/hooks/*.sh "$SKILL_DIR"/hooks/*.py "$SKILL_DIR"/scripts/*.sh "$SKILL_DIR"/scripts/*.py; do
    [ -f "$f" ] || continue
    if [ ! -x "$f" ]; then
        chmod +x "$f"
        echo "  ✅ chmod +x $(basename $f)"
    fi
done
if [ -d "$WATCHER_SKILL_DIR" ]; then
    for f in "$WATCHER_SKILL_DIR"/hooks/*.sh "$WATCHER_SKILL_DIR"/hooks/*.py "$WATCHER_SKILL_DIR"/scripts/*.sh "$WATCHER_SKILL_DIR"/scripts/*.py; do
        [ -f "$f" ] || continue
        if [ ! -x "$f" ]; then
            chmod +x "$f"
            echo "  ✅ chmod +x $(basename $f)"
        fi
    done
fi

echo ""

# Step 5: 네거티브 테스트
echo "[Step 4] 네거티브 테스트 실행"
if [ -f "$SKILL_DIR/hooks/test-hooks-negative.sh" ]; then
    bash "$SKILL_DIR/hooks/test-hooks-negative.sh"
else
    echo "  ⚠️ test-hooks-negative.sh 없음 — 건너뜀"
fi

echo ""
echo "=== 설치 완료 ==="
echo "스킬: cmux-orchestrator + cmux-watcher"
echo "Hook: $HOOKS_TARGET/ (심링크)"
echo "설정: $SETTINGS (자동 등록)"
echo ""
echo "제거: bash $SKILL_DIR/install.sh --uninstall"
