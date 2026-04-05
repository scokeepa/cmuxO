#!/bin/bash
# cmux-main-context.sh — UserPromptSubmit hook
# /cmux 입력 시 와쳐 캐시 + roles를 AI context에 강제 주입
# enforcer는 세션 시작 시 1회만 → /cmux 시점엔 와쳐 정보 없을 수 있음

PAYLOAD=$(cat)
[ -f /tmp/cmux-orch-enabled ] || exit 0
[ -n "${CMUX_WORKSPACE_ID:-}" ] || exit 0

USER_MSG=$(echo "$PAYLOAD" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('message',''))" 2>/dev/null)

# /cmux만 매칭 (/cmux-watcher 제외)
echo "$USER_MSG" | grep -qE "^/cmux$|^/cmux " || exit 0
echo "$USER_MSG" | grep -qi "watcher" && exit 0

# 캐시 + roles 읽어서 주입
python3 -c "
import json, os, time

scan_file = '/tmp/cmux-surface-scan.json'
roles_file = '/tmp/cmux-roles.json'

surfaces = {}
roles = {}
scan_age = 999

if os.path.exists(scan_file):
    scan_age = time.time() - os.path.getmtime(scan_file)
    if scan_age < 300:
        try: surfaces = json.load(open(scan_file)).get('surfaces', {})
        except: pass

if os.path.exists(roles_file):
    try: roles = json.load(open(roles_file))
    except: pass

watcher = roles.get('watcher', {}).get('surface', '미등록')
main = roles.get('main', {}).get('surface', '미등록')
total = len(surfaces)

lines = []
for s, i in sorted(surfaces.items(), key=lambda x: int(x[0].split(':')[1])):
    lines.append(f'  {s} = {i.get(\"model\",\"?\")} ({i.get(\"status\",\"?\")}, {i.get(\"role\",\"?\")})')
summary = chr(10).join(lines[:20])

# Traits 요약 — dispatch 시 AI별 특성 반영
traits_section = ''
profile_file = os.path.expanduser('~/.claude/skills/cmux-orchestrator/config/ai-profile.json')
if os.path.exists(profile_file):
    try:
        with open(profile_file) as pf:
            profiles = json.load(pf).get('profiles', {})
        trait_lines = []
        for name, p in profiles.items():
            t = p.get('traits', {})
            active = [k for k, v in t.items() if v]
            if active:
                trait_lines.append(f'  {p.get(\"display_name\",name)}: {\" \".join(active)}')
        if trait_lines:
            traits_section = chr(10) + 'AI traits (dispatch 참조):' + chr(10) + chr(10).join(trait_lines)
    except: pass

# 메모리 요약 (최근 10건) — 의사결정 연결
memory_file = os.path.expanduser('~/.claude/memory/cmux/memories.json')
mem_section = ''
if os.path.exists(memory_file):
    try:
        with open(memory_file) as mf:
            mems = json.load(mf)
        if isinstance(mems, list) and mems:
            recent = mems[-10:]
            ml = [f'\\n학습 메모리 ({len(mems)}건 중 최근 {len(recent)}건):']
            for m in recent:
                ml.append(f'  - {m.get(\"summary\", str(m)[:80])}')
            mem_section = chr(10).join(ml)
    except: pass

msg = f'[CMUX-MAIN] 와쳐 캐시 주입 (scan: {int(scan_age)}초 전)\\n와쳐: {watcher}\\n메인: {main}\\nsurface: {total}개\\n{summary}{traits_section}{mem_section}'

print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': msg}}, ensure_ascii=False))
" 2>/dev/null || exit 0
