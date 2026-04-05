#!/bin/bash
# detect-surface-models.sh v2 — 실시간 surface 모델 감지
# 이전 config 무시. 항상 read-screen에서 직접 파싱.
# 아이콘(🤖) 없어도 텍스트 패턴으로 감지.
# workspace 지정하여 다른 workspace surface도 읽기.

variable_self_surface="${1:-}"  # 자기 자신 surface (스킵용)

# cmux tree 파싱: surface 번호 + workspace 매핑
variable_tree=$(cmux tree --all 2>/dev/null)

# workspace:surface 매핑 추출
declare -A variable_ws_map
variable_current_ws=""
while IFS= read -r variable_line; do
    # workspace 감지
    variable_ws=$(echo "$variable_line" | grep -oE 'workspace:[0-9]+' | head -1)
    [ -n "$variable_ws" ] && variable_current_ws="$variable_ws"
    # surface 감지
    variable_sf=$(echo "$variable_line" | grep -oE 'surface:[0-9]+' | head -1)
    [ -n "$variable_sf" ] && [ -n "$variable_current_ws" ] && variable_ws_map["$variable_sf"]="$variable_current_ws"
done <<< "$variable_tree"

echo "{"
variable_first=true

for variable_surf in $(echo "${!variable_ws_map[@]}" | tr ' ' '\n' | sort -t: -k2 -n); do
    variable_num="${variable_surf#surface:}"
    variable_ws="${variable_ws_map[$variable_surf]}"

    # 자기 자신은 스킵
    [ "$variable_num" = "$variable_self_surface" ] && continue

    # workspace 지정하여 화면 읽기
    variable_screen=$(cmux read-screen --workspace "$variable_ws" --surface "$variable_surf" --lines 20 2>/dev/null)
    [ -z "$variable_screen" ] && continue

    # 모델 감지 — 텍스트 패턴 (아이콘 무관)
    variable_model="unknown"

    # 1. Claude Code statusline: "🤖 모델명 |" 또는 그냥 "Opus 4.6", "Sonnet 4.6"
    variable_m=$(echo "$variable_screen" | grep -oiE '(Opus|Sonnet|Haiku) [0-9]+\.[0-9]+( \([^)]+\))?' | head -1)
    [ -n "$variable_m" ] && variable_model="$variable_m"

    # 2. Codex CLI: "gpt-5.4" 또는 "o3-pro" 등
    if [ "$variable_model" = "unknown" ]; then
        variable_m=$(echo "$variable_screen" | grep -oiE 'gpt-[0-9]+\.[0-9]+|o[0-9]+-?(pro|mini)?' | head -1)
        [ -n "$variable_m" ] && variable_model="Codex ($variable_m)"
    fi

    # 3. GLM: "glm-4.7" 등
    if [ "$variable_model" = "unknown" ]; then
        variable_m=$(echo "$variable_screen" | grep -oiE 'glm-[0-9]+\.[0-9]+' | head -1)
        [ -n "$variable_m" ] && variable_model="$variable_m"
    fi

    # 4. MiniMax: "MiniMax-M2.5" "MiniMax-M2.7" 등
    if [ "$variable_model" = "unknown" ]; then
        variable_m=$(echo "$variable_screen" | grep -oiE 'MiniMax-M[0-9]+\.[0-9]+' | head -1)
        [ -n "$variable_m" ] && variable_model="$variable_m"
    fi

    # 5. Gemini: "gemini-3.1-pro" 등
    if [ "$variable_model" = "unknown" ]; then
        variable_m=$(echo "$variable_screen" | grep -oiE 'gemini-[0-9]+\.[0-9]+-?(pro|flash|ultra)?' | head -1)
        [ -n "$variable_m" ] && variable_model="$variable_m"
    fi

    # 6. tree 출력의 탭 제목으로 fallback
    if [ "$variable_model" = "unknown" ]; then
        variable_title=$(echo "$variable_tree" | grep "$variable_surf" | grep -oE '"[^"]+"' | head -1 | tr -d '"')
        [ -n "$variable_title" ] && variable_model="($variable_title)"
    fi

    # 상태 감지
    variable_status="IDLE"
    if echo "$variable_screen" | grep -qE '⏳|Working|running|interrupt|Thinking'; then
        variable_status="WORKING"
    elif echo "$variable_screen" | grep -qE 'Error|error|ERROR|API Error|rate.limit|OVERLOADED'; then
        variable_status="ERROR"
    elif echo "$variable_screen" | grep -qE 'DONE:|완료'; then
        variable_status="DONE"
    fi

    # 역할 감지
    variable_role="worker"
    if echo "$variable_screen" | grep -qE 'W:[0-9].*I:[0-9]|요약 :|watcher|센티넬|eagle'; then
        variable_role="watcher"
    fi

    # JSON 출력
    if [ "$variable_first" = true ]; then
        variable_first=false
    else
        echo ","
    fi
    printf '  "%s": {"model": "%s", "status": "%s", "role": "%s", "workspace": "%s"}' \
        "$variable_surf" "$variable_model" "$variable_status" "$variable_role" "$variable_ws"
done

echo ""
echo "}"
