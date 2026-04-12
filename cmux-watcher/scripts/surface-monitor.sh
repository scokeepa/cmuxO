#!/bin/bash
# surface-monitor.sh — 지정 surface DONE 감지 + Boss 알림 (v2.0)
# Usage: bash surface-monitor.sh --targets "1 3 4 21 22" --boss surface:28 [--interval 20] [--max-rounds 90]
#
# DONE 판정 기준 (3가지 중 하나):
#   1. 강한 키워드: DONE: / TASK COMPLETE / Brewed / Cooked / Baked / Crunched / Worked
#   2. Codex 프롬프트 복귀: "›" 있고 "Working" 없음
#   3. Claude 프롬프트 복귀: "❯" 있고 "Working/Processing/Choreographing" 없음

set -u

ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"
READ_SURFACE="$ORCH_DIR/scripts/read-surface.sh"

# 파라미터 파싱
TARGETS=""
BOSS_SF=""
INTERVAL=20
MAX_ROUNDS=90

while [[ $# -gt 0 ]]; do
  case "$1" in
    --targets) TARGETS="$2"; shift 2 ;;
    --boss) BOSS_SF="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --max-rounds) MAX_ROUNDS="$2"; shift 2 ;;
    *) shift ;;
  esac
done

[ -z "$TARGETS" ] && echo "ERROR: --targets required" && exit 1
[ -z "$BOSS_SF" ] && echo "ERROR: --boss required" && exit 1

TARGET_COUNT=$(echo $TARGETS | wc -w | tr -d ' ')
DONE_SET=""

is_done() {
  local screen="$1"

  # 0. WORKING 신호 최우선 — 하나라도 있으면 절대 DONE 아님
  # Claude Code 작업 중 표시: Working, Processing, Choreographing, thinking,
  # Honking, Scurrying, Running, Actioning, Compiling, tokens, attempt
  if echo "$screen" | grep -qiE 'Working|Processing|Choreographing|Compiling|thinking|Honking|Scurrying|Running|Actioning|Retrying|attempt|tokens'; then
    return 1
  fi

  # 0.5. WAITING 신호 — 질문 대기 중이면 DONE 아님
  if echo "$screen" | grep -qiE '할까요\?|하시겠습니까\?|선택해|which.*first|proceed\?|y/n|yes/no|\(Y/n\)'; then
    return 1
  fi

  # 1. 강한 DONE 키워드
  if echo "$screen" | grep -qiE 'DONE:|TASK COMPLETE|Brewed|Cooked|Baked|Crunched|Worked'; then
    return 0
  fi

  # 2. Codex 프롬프트 복귀 (›) — Codex는 프롬프트가 › 형태
  # ❯는 Claude Code이므로 별도 처리
  if echo "$screen" | grep -q '›'; then
    return 0
  fi

  # 3. Claude Code 프롬프트 (❯) — Working 신호가 이미 0단계에서 걸렸으므로
  # 여기까지 왔으면 진짜 IDLE
  if echo "$screen" | grep -q '❯'; then
    # 추가 안전: scrollback에 진행 중 표시가 없는지 2중 확인
    # (화면 하단 ❯는 항상 있으므로, 상단에 완료 마커가 있어야 함)
    if echo "$screen" | grep -qiE 'Brewed|Cooked|Baked|Crunched|Worked|✓|완료|success|PASS'; then
      return 0
    fi
    # 완료 마커 없어도 Working 신호 없으면 IDLE = DONE으로 간주
    # 단, ctrl+b to run in background 같은 표시가 있으면 아직 WORKING
    if echo "$screen" | grep -qiE 'ctrl\+b|ctrl\+o|interrupt'; then
      return 1
    fi
    return 0
  fi

  return 1
}

for i in $(seq 1 $MAX_ROUNDS); do
  NEW_DONE=""

  for sf in $TARGETS; do
    # 이미 DONE된 surface 스킵
    echo "$DONE_SET" | grep -qw "$sf" && continue

    SCREEN=$(bash "$READ_SURFACE" $sf --lines 8 2>/dev/null)

    if is_done "$SCREEN"; then
      NEW_DONE="$NEW_DONE $sf"
      DONE_SET="$DONE_SET $sf"
      echo "[$(date +%H:%M:%S)] surface:$sf DONE ✅"
    else
      echo "[$(date +%H:%M:%S)] surface:$sf WORKING..."
    fi
  done

  # 새로 DONE된 게 있으면 Boss에 중간 알림
  if [ -n "$NEW_DONE" ]; then
    DONE_COUNT=$(echo "$DONE_SET" | wc -w | tr -d ' ')
    cmux send --surface "$BOSS_SF" "[WATCHER→BOSS] DONE: s:${NEW_DONE// / s:} 완료 (${DONE_COUNT}/${TARGET_COUNT})" 2>/dev/null
    sleep 0.5
    cmux send-key --surface "$BOSS_SF" enter 2>/dev/null
  fi

  # Vision Diff 재검증: DONE 판정된 surface를 60초 후 재확인
  # (오판 방지 — 화면이 실제로 변하지 않는지 확인)
  if [ -n "$NEW_DONE" ]; then
    sleep 30
    for sf in $NEW_DONE; do
      RECHECK=$(bash "$READ_SURFACE" $sf --lines 12 2>/dev/null)
      # 재확인에서 WORKING 신호 발견 시 DONE 취소
      if echo "$RECHECK" | grep -qiE 'Working|Processing|Choreographing|thinking|Honking|Scurrying|Running|Actioning|tokens|ctrl\+b'; then
        echo "[$(date +%H:%M:%S)] surface:$sf ❌ DONE 취소 — 재확인 시 WORKING 감지"
        DONE_SET=$(echo "$DONE_SET" | sed "s/\b$sf\b//g" | tr -s ' ')
      elif echo "$RECHECK" | grep -qiE '할까요\?|하시겠습니까\?|proceed\?|y/n'; then
        echo "[$(date +%H:%M:%S)] surface:$sf ❌ DONE 취소 — WAITING (질문 대기)"
        DONE_SET=$(echo "$DONE_SET" | sed "s/\b$sf\b//g" | tr -s ' ')
        cmux send --surface "$BOSS_SF" "[WATCHER→BOSS] WAITING: surface:$sf 사용자 입력 대기 중" 2>/dev/null
        sleep 0.5
        cmux send-key --surface "$BOSS_SF" enter 2>/dev/null
      fi
    done
  fi

  # 전부 DONE이면 최종 알림 + 종료
  DONE_COUNT=$(echo "$DONE_SET" | wc -w | tr -d ' ')
  if [ "$DONE_COUNT" -ge "$TARGET_COUNT" ]; then
    echo "[$(date +%H:%M:%S)] ALL $TARGET_COUNT DONE ✅✅✅"
    cmux send --surface "$BOSS_SF" "[WATCHER→BOSS] ⚠️ ALL ${TARGET_COUNT} DONE: 전부 완료! 즉시 결과 수집." 2>/dev/null
    sleep 0.5
    cmux send-key --surface "$BOSS_SF" enter 2>/dev/null
    exit 0
  fi

  sleep "$INTERVAL"
done

echo "[$(date +%H:%M:%S)] 타임아웃. DONE: $DONE_SET ($(echo $DONE_SET | wc -w | tr -d ' ')/${TARGET_COUNT})"
# 타임아웃이어도 부분 결과 알림
DONE_COUNT=$(echo "$DONE_SET" | wc -w | tr -d ' ')
if [ "$DONE_COUNT" -gt 0 ]; then
  cmux send --surface "$BOSS_SF" "[WATCHER→BOSS] TIMEOUT: ${DONE_COUNT}/${TARGET_COUNT} 완료. 나머지 확인 필요." 2>/dev/null
  sleep 0.5
  cmux send-key --surface "$BOSS_SF" enter 2>/dev/null
fi
