#!/bin/bash
# cmux-watcher-activate.sh — UserPromptSubmit hook
# 사용자가 /cmux-watcher 타이핑하면 자동으로 detect --as-watcher 실행
# AI 판단 의존 ZERO — hook이 강제 실행

PAYLOAD=$(cat)

# 오케스트레이션 모드 아니면 패스
[ -f /tmp/cmux-orch-enabled ] || exit 0
# cmux 환경 아니면 패스
[ -n "${CMUX_WORKSPACE_ID:-}" ] || exit 0

# 사용자 입력에서 /cmux-watcher 감지
USER_MSG=$(echo "$PAYLOAD" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('message',''))" 2>/dev/null)

echo "$USER_MSG" | grep -qi "cmux-watcher\|cmux_watcher" || exit 0

# 감지됨 → detect --as-watcher 실행
ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"
DETECT="$ORCH_DIR/scripts/detect-surface-models.py"
MY_NUM=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['surface_ref'].split(':')[1])" 2>/dev/null)

[ -z "$MY_NUM" ] && exit 0

# --as-watcher: 와쳐 등록 + 스캔 + 결과 저장 + /cmux 엔터 (맨 마지막)
STDERR_LOG=$(python3 "$DETECT" "$MY_NUM" --as-watcher 2>&1 1>/dev/null)

# 역할 확인
BOSS_SF=$(python3 -c "import json; print(json.load(open('/tmp/cmux-roles.json')).get('boss',{}).get('surface','미등록'))" 2>/dev/null || echo "미등록")
WATCHER_SF=$(python3 -c "import json; print(json.load(open('/tmp/cmux-roles.json')).get('watcher',{}).get('surface','미등록'))" 2>/dev/null || echo "미등록")
SCAN_COUNT=$(python3 -c "import json; print(len(json.load(open('/tmp/cmux-surface-scan.json')).get('surfaces',{})))" 2>/dev/null || echo "0")

# context 주입
CONTEXT="[WATCHER-ACTIVATE] hook 자동 실행 완료. watcher=${WATCHER_SF}, boss=${BOSS_SF}, surfaces=${SCAN_COUNT}개. ${STDERR_LOG}. AI는 추가 스캔/등록 불필요. /tmp/cmux-surface-scan.json 결과만 읽고 보고. 질문 금지."

python3 -c "
import json
ctx = '''$CONTEXT'''
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': ctx}}, ensure_ascii=False))
" 2>/dev/null || exit 0
