#!/bin/bash
# surface-dispatcher.sh v8 — workspace auto-resolve + 글리프 필터링 + 2단계 DONE 탐지 + thought 패턴 + 에러 핸들링
VERSION=8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/workspace-resolver.sh" 2>/dev/null

# --workspace 파싱
WORKSPACE_ARG=""
POSITIONAL_ARGS=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)
            WORKSPACE_ARG="$2"
            shift 2
            ;;
        *)
            POSITIONAL_ARGS="${POSITIONAL_ARGS} $1"
            shift
            ;;
    esac
done
SURFACES="${POSITIONAL_ARGS# }"
SURFACES="${SURFACES:-39 32 41 42 43 44 27 38}"

REPORT=""
CMUX_ERROR=false

# cmux 실행 여부 사전 확인
if ! command -v cmux >/dev/null 2>&1; then
    echo "ERROR: cmux not found"
    exit 1
fi

for S in $SURFACES; do
    # surface 유효성 사전 검사 (cmux가 존재하지 않는 surface에 대해 다른 surface 내용을 반환하는 문제 방지)
    if type function_surface_exists &>/dev/null; then
        if ! function_surface_exists "$S" 2>/dev/null; then
            REPORT="${REPORT}S:${S}=NOT_FOUND "
            CMUX_ERROR=true
            continue
        fi
    fi

    # Resolve workspace for this surface (GATE 8: --workspace mandatory)
    if [ -n "$WORKSPACE_ARG" ]; then
        WS="$WORKSPACE_ARG"
    elif type function_resolve_workspace &>/dev/null; then
        WS=$(function_resolve_workspace "$S" 2>/dev/null)
    else
        WS=""
    fi

    # workspace 해석 실패 = surface가 존재하지 않음
    if [ -z "$WS" ]; then
        REPORT="${REPORT}S:${S}=NO_WS "
        CMUX_ERROR=true
        continue
    fi

    SCREEN=$(cmux read-screen --workspace "$WS" --surface surface:${S} --lines 25 2>&1)

    # cmux 에러 감지 (surface가 존재하지 않거나 cmux가 응답하지 않음)
    if echo "$SCREEN" | grep -qE "error:|surface does not exist|failed to connect|cannot find"; then
        REPORT="${REPORT}S:${S}=INVALID "
        CMUX_ERROR=true
        continue
    fi

    # 빈 응답 = cmux 다운 또는 surface 접근 불가
    if [ -z "$SCREEN" ]; then
        REPORT="${REPORT}S:${S}=NO_REPLY "
        CMUX_ERROR=true
        continue
    fi

    # 글리프 필터링 — 특수 문자를 공백으로 치환
    SCREEN_CLEAN=$(echo "$SCREEN" | sed 's/✻/ /g; s/✶/ /g; s/✽/ /g; s/✢/ /g; s/✳/ /g; s/⏺/ /g; s/·/ /g')

    # === DONE 2단계 탐지 ===
    # Step 1: 최근 10줄 우선 탐지
    LAST10=$(echo "$SCREEN" | tail -10)
    REAL_DONE=$(echo "$LAST10" | grep -cE "^\s*DONE\s*$")
    if [ "$REAL_DONE" -eq 0 ]; then
        # Step 2: 전체 fallback
        REAL_DONE=$(echo "$SCREEN" | grep -cE "^\s*DONE\s*$")
    fi

    QUEUED=$(echo "$SCREEN" | grep -c "Press up to edit queued")
    COMPACT=$(echo "$SCREEN" | grep -c "until auto-compact\|until auto-co")
    RATE=$(echo "$SCREEN" | grep -c "429\|Usage limit")

    # "글자(시간)" 패턴 = 활성 작업 중 (SCREEN_CLEAN 사용)
    HAS_ACTIVITY=$(echo "$SCREEN_CLEAN" | grep -cE "for [0-9]+m|Churning|Cooking|Baking|Sautéing|Cogitating|Crunching|Brewing|Working|esc to interrupt")
    HAS_TIME=$(echo "$SCREEN" | grep -cE "[0-9]+m [0-9]+s|[0-9]+m\b|\([0-9]+s")

    # 시간 추출
    T=$(echo "$SCREEN" | grep -oE "[0-9]+m" | head -1 | tr -d 'm')
    T=${T:-0}

    # "for Xm" = 완료 상태 동사 (thought 패턴 확장)
    FINISHED=$(echo "$SCREEN" | grep -cE "(Churned|Cooked|Baked|Sautéed|Cogitated|Crunched|Brewed|Worked|Ionizing|Gallivanting|Architecting|Planning|Reasoning|Analyzing|Synthesizing) for")
    # "Xm · thinking|tokens" = 실시간 작업 중
    LIVE=$(echo "$SCREEN" | grep -cE "thinking|tokens|esc to interrupt")

    # 판정
    if [ "$REAL_DONE" -ge 1 ]; then
        STATUS="DONE"
    elif [ "$QUEUED" -ge 1 ]; then
        STATUS="QUEUED"
    elif [ "$COMPACT" -ge 1 ]; then
        STATUS="COMPACT!"
    elif [ "$LIVE" -ge 1 ]; then
        STATUS="WORK(${T}m)"
    elif [ "$FINISHED" -ge 1 ] && [ "$T" -ge 1 ]; then
        # "Churned for 3m" = 작업 끝남 → DONE 없으면 멈춤
        STATUS="ENDED(${T}m)"
    elif [ "$RATE" -ge 1 ]; then
        STATUS="RATE_LIM"
    elif [ "$HAS_ACTIVITY" -ge 1 ]; then
        STATUS="ACTIVE"
    else
        STATUS="IDLE"
    fi

    REPORT="${REPORT}S:${S}=${STATUS} "
done

echo "$REPORT"
