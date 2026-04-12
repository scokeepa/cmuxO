#!/bin/bash
# cmux-jarvis-gate.sh — JARVIS GATE (최소 개입 원칙)
#
# 차단 대상 (이것만!):
#   1. JARVIS surface에서 settings.json 무단 수정 (Iron Law #1)
#   2. JARVIS surface에서 .evolution-lock 직접 위조 (IL1-ATK-3)
#   3. Worker surface에서 evolutions/ 외부 파일 수정
#
# 차단하지 않는 것:
#   - 사용자/Boss/Watcher/팀장/팀원의 모든 작업 → 무조건 allow
#   - JARVIS의 일반 파일 작업 (knowledge, 문서 등) → allow
#   - rm 같은 파괴적 명령 → cmux-orchestrator의 기존 guard가 담당

set -u

ALLOW='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
ROLES_FILE="/tmp/cmux-roles.json"

deny() {
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"$1\"}}"
  exit 0
}

# --- 빠른 탈출 (대부분의 호출은 여기서 종료) ---

# jq 없으면 pass
command -v jq >/dev/null 2>&1 || { echo "$ALLOW"; exit 0; }

# 오케스트레이션 모드 아니면 pass
[ -f /tmp/cmux-orch-enabled ] || { echo "$ALLOW"; exit 0; }

# 현재 surface 식별
MY_SID=""
command -v cmux >/dev/null 2>&1 && MY_SID=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['surface_ref'])" 2>/dev/null || echo "")

JARVIS_SID=$(jq -r '.jarvis.surface // ""' "$ROLES_FILE" 2>/dev/null)

# JARVIS surface가 아니고 Worker 마커도 없으면 → 즉시 allow (전체 통과)
IS_JARVIS=false
[ -n "$MY_SID" ] && [ -n "$JARVIS_SID" ] && [ "$MY_SID" = "$JARVIS_SID" ] && IS_JARVIS=true

IS_WORKER=false
if ls /tmp/cmux-jarvis-worker-* >/dev/null 2>&1; then
  BOSS_SID=$(jq -r '.boss.surface // ""' "$ROLES_FILE" 2>/dev/null)
  WATCHER_SID=$(jq -r '.watcher.surface // ""' "$ROLES_FILE" 2>/dev/null)
  [ -n "$MY_SID" ] && [ "$MY_SID" != "$JARVIS_SID" ] && [ "$MY_SID" != "$BOSS_SID" ] && [ "$MY_SID" != "$WATCHER_SID" ] && IS_WORKER=true
fi

# JARVIS도 Worker도 아님 → 모든 것 허용 (사용자/Boss/Watcher/팀장/팀원)
[ "$IS_JARVIS" = "false" ] && [ "$IS_WORKER" = "false" ] && { echo "$ALLOW"; exit 0; }

# --- 여기부터 JARVIS 또는 Worker surface에서만 실행 ---

INPUT_JSON=$(cat)
TOOL_NAME=$(echo "$INPUT_JSON" | jq -r '.tool_name // ""')

# === JARVIS surface 제한 (settings.json + .evolution-lock만) ===
if [ "$IS_JARVIS" = "true" ]; then
  if [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ]; then
    FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // ""')

    # .evolution-lock 직접 위조 차단
    case "$FILE_PATH" in
      *".evolution-lock"*) deny "GATE: LOCK 파일은 jarvis-evolution.sh만 생성 가능" ;;
    esac

    # settings.json → 진화 반영 단계에서만 허용
    case "$FILE_PATH" in
      *"settings.json"*|*"settings.local.json"*)
        LOCK_FILE="$HOME/.claude/cmux-jarvis/.evolution-lock"
        if [ -f "$LOCK_FILE" ]; then
          PHASE=$(jq -r '.phase // ""' "$LOCK_FILE" 2>/dev/null)
          EVO_ID=$(jq -r '.evo_id // ""' "$LOCK_FILE" 2>/dev/null)
          if [ "$PHASE" = "applying" ] && [ -f "$HOME/.claude/cmux-jarvis/evolutions/$EVO_ID/evidence.json" ]; then
            echo "$ALLOW"; exit 0  # 3조건 충족 → 허용
          fi
        fi
        deny "GATE: settings.json은 진화 반영(phase=applying+evidence) 시에만 수정 가능"
        ;;
    esac

    # 나머지 파일 → 허용 (JARVIS가 knowledge, 문서 등 자유롭게 작업)
    echo "$ALLOW"; exit 0
  fi

  if [ "$TOOL_NAME" = "Bash" ]; then
    COMMAND=$(echo "$INPUT_JSON" | jq -r '.tool_input.command // ""')
    # settings.json 직접 쓰기만 차단
    if echo "$COMMAND" | grep -qE "cp [^ ]+ [^ ]*settings\.json|mv [^ ]+ [^ ]*settings\.json|>[[:space:]]*[^ ]*settings\.json"; then
      deny "GATE: settings.json Bash 쓰기 차단"
    fi
    echo "$ALLOW"; exit 0
  fi
fi

# === Worker surface 제한 (evolutions/ 내부만) ===
if [ "$IS_WORKER" = "true" ]; then
  if [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ]; then
    FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // ""')
    case "$FILE_PATH" in
      *"/cmux-jarvis/evolutions/"*) echo "$ALLOW"; exit 0 ;;
      *) deny "Worker: evolutions/ 내부에만 파일 생성 허용" ;;
    esac
  fi
  # Worker Bash → 허용 (evolutions/ 내 작업)
  echo "$ALLOW"; exit 0
fi

# 기타 → 허용
echo "$ALLOW"
