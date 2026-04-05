#!/bin/bash
# cmux-model-profile-hook.sh — SessionStart hook
# 모델 감지 → skills symlink 전환 (sonnet=lean, opus=full)
# Haiku clean mode는 cch() 함수로 별도 실행 (파일 교체 없음)

SETTINGS="$HOME/.claude/settings.json"
SKILLS_LINK="$HOME/.claude/skills"
SKILLS_LEAN="$HOME/.claude/skills-lean"
SKILLS_FULL="$HOME/.claude/skills-full"

# 현재 모델 읽기
CURRENT_MODEL=$(python3 -c "
import json
try:
    d=json.load(open('$SETTINGS'))
    print(d.get('model','').lower())
except:
    print('')
" 2>/dev/null)

# 린 모델 판단
IS_LEAN=false
echo "$CURRENT_MODEL" | grep -qiE "sonnet|haiku" && IS_LEAN=true

# skills symlink 상태 확인
CURRENT_LINK=""
[ -L "$SKILLS_LINK" ] && CURRENT_LINK=$(readlink "$SKILLS_LINK")

if [ "$IS_LEAN" = "true" ]; then
    if [ "$CURRENT_LINK" != "$SKILLS_LEAN" ]; then
        rm -f "$SKILLS_LINK"
        ln -s "$SKILLS_LEAN" "$SKILLS_LINK"
    fi
    SKILL_COUNT=$(ls "$SKILLS_LEAN" 2>/dev/null | wc -l | tr -d ' ')

    cat << JSON
{"additionalContext":"[LEAN MODE] Sonnet/Haiku 감지 → 스킬 ${SKILL_COUNT}개만 활성화됨.\n\n⚠️ LEAN MODE 규칙:\n- Skill() 자동 호출 절대 금지\n- 명시적 요청이 없으면 어떤 스킬도 로드하지 않음\n- cmux 명령어는 Bash로 직접 실행\n- 컨텍스트 절약 최우선"}
JSON
else
    if [ "$CURRENT_LINK" != "$SKILLS_FULL" ] && [ -d "$SKILLS_FULL" ]; then
        rm -f "$SKILLS_LINK"
        ln -s "$SKILLS_FULL" "$SKILLS_LINK"
    fi
    SKILL_COUNT=$(ls "$SKILLS_FULL" 2>/dev/null | wc -l | tr -d ' ')

    cat << JSON
{"additionalContext":"[FULL MODE] Opus 감지 → 모든 스킬 ${SKILL_COUNT}개 활성화됨. 오케스트레이션 모드."}
JSON
fi
