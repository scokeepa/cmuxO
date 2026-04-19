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
boss = roles.get('boss', {}).get('surface', '미등록')
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

msg = f'[CMUX-BOSS] 와쳐 캐시 주입 (scan: {int(scan_age)}초 전)\\n와쳐: {watcher}\\n사장: {boss}\\nsurface: {total}개\\n{summary}{traits_section}{mem_section}'

# Mentor context (L0/L1) 주입 — mempalace ChromaDB 기반
mentor_section = ''
hint_section = ''
try:
    palace_path = os.path.expanduser('~/.cmux-jarvis-palace')
    identity_file = os.path.join(palace_path, 'identity.txt')
    if os.path.exists(palace_path):
        l0 = ''
        if os.path.exists(identity_file):
            l0 = open(identity_file).read().strip()

        import logging as _lg
        _lg.getLogger('chromadb.telemetry.product.posthog').setLevel(_lg.CRITICAL)
        import platform as _pf
        if _pf.machine() == 'arm64' and _pf.system() == 'Darwin':
            os.environ.setdefault('ORT_DISABLE_COREML', '1')
        import chromadb as _cdb
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2 as _EF
        _ef = _EF(preferred_providers=['CPUExecutionProvider'])
        _client = _cdb.PersistentClient(path=palace_path)
        try:
            _col = _client.get_collection('cmux_mentor_signals', embedding_function=_ef)
        except Exception:
            _col = None

        if _col and _col.count() > 0:
            _res = _col.get(where={'wing': 'cmux_mentor'}, include=['metadatas'], limit=10)
            _metas = sorted(_res.get('metadatas', []), key=lambda m: m.get('ts', ''), reverse=True)
            if _metas:
                _latest = _metas[0]
                l1_lines = ['[MENTOR L1] Harness Level: L' + str(_latest.get('harness_level', '?'))]
                _hint = _latest.get('coaching_hint', '')
                if _hint:
                    l1_lines.append('Hint: ' + _hint)
                l1 = chr(10).join(l1_lines)
                combined = l0 + chr(10) + l1 if l0 else l1
                if len(combined) <= 3600:
                    mentor_section = chr(10) + chr(10) + '[MENTOR CONTEXT]' + chr(10) + combined

                # Coaching hint spam 방지
                if _hint:
                    hint_cache = '/tmp/cmux-mentor-last-hint.txt'
                    prev_hint = ''
                    if os.path.exists(hint_cache):
                        prev_hint = open(hint_cache).read().strip()
                    if _hint != prev_hint:
                        hint_section = chr(10) + '[MENTOR HINT] ' + _hint
                        with open(hint_cache, 'w') as hf:
                            hf.write(_hint)
except Exception:
    pass

ledger_section = ''
try:
    import subprocess
    _here = os.path.dirname(os.path.abspath(__file__))
    _ledger_py = os.path.join(_here, '..', 'scripts', 'ledger.py')
    if os.path.exists(_ledger_py):
        _out = subprocess.run(
            ['python3', _ledger_py, 'context'],
            capture_output=True, text=True, timeout=2,
        )
        if _out.returncode == 0 and _out.stdout.strip():
            _stdout = _out.stdout.strip()
            if len(_stdout) <= 6000:
                ledger_section = chr(10) + chr(10) + _stdout
except Exception:
    pass

msg = msg + mentor_section + hint_section + ledger_section

print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': msg}}, ensure_ascii=False))
" 2>/dev/null || exit 0
