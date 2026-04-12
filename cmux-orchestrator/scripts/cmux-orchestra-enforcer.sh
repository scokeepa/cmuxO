#!/bin/bash
# cmux-orchestra-enforcer.sh — SessionStart hook (v9)
# 와쳐가 이미 스캔+저장한 결과를 읽기만 함. 없으면 직접 스캔.
# AI 판단 의존 ZERO — 모든 정보가 자동 주입됨.

[ -n "$CMUX_WORKSPACE_ID" ] || exit 0

variable_surface_count=$(cmux tree --all 2>/dev/null | grep -c "surface:" || echo 0)
[ "$variable_surface_count" -ge 2 ] || exit 0

variable_detect_script="$HOME/.claude/skills/cmux-orchestrator/scripts/detect-surface-models.py"
variable_my_surface=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['surface_ref'].split(':')[1])" 2>/dev/null)

python3 -c "
import json, subprocess, sys, os, time
from pathlib import Path
from datetime import datetime, timezone

my_surface = '$variable_my_surface'
count = $variable_surface_count
detect = '$variable_detect_script'
scan_file = '/tmp/cmux-surface-scan.json'
roles_file = '/tmp/cmux-roles.json'

# 1. 와쳐 캐시 확인 (2분 이내)
surfaces = {}
scan_source = 'direct'
try:
    if os.path.exists(scan_file):
        age = time.time() - os.path.getmtime(scan_file)
        if age < 120:
            d = json.load(open(scan_file))
            surfaces = d.get('surfaces', {})
            scan_source = f'watcher-cache ({int(age)}s ago)'
except Exception:
    pass

# 2. 캐시 없으면 직접 스캔 (detect-surface-models.py가 자동 저장)
if not surfaces:
    try:
        r = subprocess.run(['python3', detect, my_surface, '--no-activate'], capture_output=True, text=True, timeout=60)
        if r.stdout.strip():
            surfaces = json.loads(r.stdout)
        scan_source = 'direct-scan'
    except Exception:
        pass

# 3. 역할 확인
roles = {}
try:
    if os.path.exists(roles_file):
        roles = json.load(open(roles_file))
except Exception:
    pass

my_ref = f'surface:{my_surface}'
boss_ref = roles.get('boss', {}).get('surface', '미등록')
watcher_ref = roles.get('watcher', {}).get('surface', '미등록')

# 내 역할 판단
my_role = 'unknown'
if boss_ref == my_ref:
    my_role = 'BOSS'
elif watcher_ref == my_ref:
    my_role = 'WATCHER'
else:
    # boss가 없으면 boss 후보
    my_role = 'BOSS (자동)' if boss_ref == '미등록' else 'WORKER'

# 4. 출력
lines = []
for s, i in sorted(surfaces.items(), key=lambda x: int(x[0].split(':')[1])):
    tag = ''
    if i.get('has_cmux'): tag = ' [/cmux]'
    lines.append(f'  {s} = {i.get(\"model\",\"?\")} ({i.get(\"status\",\"?\")}, {i.get(\"role\",\"?\")}){tag}')
summary = chr(10).join(lines) if lines else '  (스캔 실패)'

ws_counts = {}
for s, i in surfaces.items():
    ws = i.get('workspace', '?')
    ws_counts[ws] = ws_counts.get(ws, 0) + 1
ws_summary = ', '.join(f'{ws}:{n}개' for ws, n in sorted(ws_counts.items()))

orch_dir = os.path.expanduser('~/.claude/skills/cmux-orchestrator')

msg = (
    f'[CMUX-ORCHESTRA v9] {count}개 surface. 소스: {scan_source}\\n\\n'
    f'나: surface:{my_surface} ({my_role})\\n'
    f'와쳐: {watcher_ref}\\n'
    f'사장: {boss_ref}\\n\\n'
    f'{summary}\\n\\n'
    f'워크스페이스: {ws_summary}\\n\\n'
    f'⛔ 강제 규칙 (Hook 차단):\\n'
    f'- cmux read-screen/send → --workspace 자동 주입 (cmux-read-guard.sh)\\n'
    f'- IDLE surface + Agent(Explore 등) → 물리 차단 (cmux-gate6-agent-block.sh)\\n'
    f'- WORKING surface + 세션 종료 → 물리 차단 (cmux-stop-guard.sh)\\n'
    f'- 미검증 DONE + 커밋 → 물리 차단 (gate-blocker.sh + FSM)\\n'
    f'- surface 스캔: python3 {orch_dir}/scripts/detect-surface-models.py {my_surface}\\n'
    f'- 개별 읽기: bash {orch_dir}/scripts/read-surface.sh N --lines 20'
)

print(json.dumps({'additionalContext': msg}, ensure_ascii=False))
" 2>/dev/null
