#!/bin/bash
# cmux-hook-audit.sh — SessionStart Hook
# Hook 등록 감사: 파일 존재 vs settings.json 등록 교차 검증
# 누락된 Hook을 자동 감지하여 additionalContext로 경고 주입

SETTINGS="$HOME/.claude/settings.json"
HOOKS_DIR="$HOME/.claude/hooks"

if [[ ! -f "$SETTINGS" ]] || [[ ! -d "$HOOKS_DIR" ]]; then
    exit 0
fi

# Get all hook files
hook_files=$(ls "$HOOKS_DIR"/*.{sh,py} 2>/dev/null | xargs -I{} basename {})
settings_content=$(cat "$SETTINGS")

unregistered=""
count=0

for hf in $hook_files; do
    if ! echo "$settings_content" | grep -q "$hf"; then
        unregistered="$unregistered $hf"
        count=$((count + 1))
    fi
done

if [[ $count -gt 0 ]]; then
    # Output warning as additionalContext
    cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[HOOK-AUDIT] ⚠️ ${count}개 Hook 파일이 settings.json에 미등록: ${unregistered}. /sdd 자가개선으로 등록하거나 불필요하면 삭제하세요."
  }
}
EOF
fi

exit 0
