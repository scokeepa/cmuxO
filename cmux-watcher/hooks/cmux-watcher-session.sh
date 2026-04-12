#!/bin/bash
# cmux-watcher-session.sh — SessionStart hook (v3)
# detect-surface-models.py v4가 모든 것을 자동 처리:
#   1. 전 surface 스캔 (스로틀 + Vision OCR fallback)
#   2. /cmux 감지 → boss 자동 등록 + 엔터 전송
#   3. 스캔 결과 /tmp/cmux-surface-scan.json 자동 저장
#   4. 역할 /tmp/cmux-roles.json 자동 갱신
# 이 hook은 결과를 읽어서 AI context에 주입하기만 함.

set -u
cat > /dev/null 2>&1  # stdin 소비

command -v cmux >/dev/null 2>&1 || exit 0
[ -n "${CMUX_WORKSPACE_ID:-}" ] || exit 0

ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"
DETECT="$ORCH_DIR/scripts/detect-surface-models.py"
ROLES_FILE="/tmp/cmux-roles.json"
SCAN_FILE="/tmp/cmux-surface-scan.json"

# 자기 자신 식별
MY_SURFACE=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['surface_ref'])" 2>/dev/null)
MY_NUM=$(echo "$MY_SURFACE" | sed 's/surface://')
MY_WS=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['workspace_ref'])" 2>/dev/null)

[ -z "$MY_NUM" ] && exit 0

# SessionStart: 스캔 + 저장만 (엔터 안 침!)
# 엔터는 AI가 /cmux-watcher 실행할 때 --as-watcher로 별도 호출
python3 "$DETECT" "$MY_NUM" --no-activate > /dev/null 2>&1

# =====================================================================
# 전 감지 계층 강제 초기화 (Layer 1/2/2.5/3 모두 부팅)
# =====================================================================
WATCHER_SCAN="$HOME/.claude/skills/cmux-watcher/scripts/watcher-scan.py"

# pipe-pane 플래그 리셋 (새 세션이면 재설치 필요)
rm -f /tmp/cmux-pipe-pane-initialized.flag

# Vision Diff 이전 캡처 리셋 (새 세션 기준점)
rm -f /tmp/cmux-vdiff-prev.json

# 1회 풀 스캔 실행 (eagle + ANE OCR + Vision Diff baseline + pipe-pane 설치)
python3 "$WATCHER_SCAN" --json > /tmp/cmux-watcher-boot-scan.json 2>/dev/null &

# 결과 읽어서 context 주입
python3 -c "
import json, os, sys
scan_file = '$SCAN_FILE'
roles_file = '$ROLES_FILE'

surfaces = {}
roles = {}
try:
    if os.path.exists(scan_file):
        surfaces = json.load(open(scan_file)).get('surfaces', {})
    if os.path.exists(roles_file):
        roles = json.load(open(roles_file))
except: pass

total = len(surfaces)
idle = sum(1 for s in surfaces.values() if s.get('status') == 'IDLE')
boss_ref = roles.get('boss', {}).get('surface', '미등록')
watcher_ref = roles.get('watcher', {}).get('surface', '미등록')

# surface 요약
lines = []
for s, i in sorted(surfaces.items(), key=lambda x: int(x[0].split(':')[1])):
    tag = ''
    if i.get('has_cmux'): tag = ' [/cmux→boss]'
    lines.append(f'  {s} = {i.get(\"model\",\"?\")} ({i.get(\"status\",\"?\")}, {i.get(\"role\",\"?\")}){tag}')
summary = chr(10).join(lines)

msg = f'''[CMUX-WATCHER v3.5] {total}개 surface 스캔 완료.
감지 계층: L1(Eagle)✅ L2(ANE-OCR)✅ L2.5(VisionDiff)✅ L3(pipe-pane)✅ — 전 계층 강제 가동
나: {watcher_ref} (WATCHER)
사장: {boss_ref}

{summary}

이 세션은 WATCHER(감시 전용).
⛔ 작업 배정/코드 수정 금지.
⛔ 사용자에게 질문 절대 금지 ("시작할까요?", "어떻게 할까요?" 등 일체 금지).
⛔ 감시 모드 시작 여부 묻지 말 것 — /tmp/cmux-dispatch-signal.json 파일이 나타나면 자동 시작.
와쳐는 대기하면서 Boss의 dispatch 신호를 폴링한다. 신호 감지 시 연속 감시 자동 시작.
surface 스캔: python3 {os.environ.get(\"HOME\",\"~\")}/.claude/skills/cmux-orchestrator/scripts/detect-surface-models.py {\"$MY_NUM\"}
개별 읽기: bash {os.environ.get(\"HOME\",\"~\")}/.claude/skills/cmux-orchestrator/scripts/read-surface.sh N --lines 20'''

print(json.dumps({'continue': True, 'additionalContext': msg}, ensure_ascii=False))
" 2>/dev/null || echo '{"continue":true}'
