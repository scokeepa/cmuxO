#!/bin/bash
# cmux-stop-guard.sh — Stop hook (v3)
# 1. WORKING surface 있으면 세션 종료 차단
# 2. 와쳐 엔터 신호 처리 — 와쳐 AI 완전 종료 후 메인에 /cmux 엔터

# 오케스트레이션 모드 아니면 패스
[ -f /tmp/cmux-orch-enabled ] || exit 0
[ -n "${CMUX_WORKSPACE_ID:-}" ] || exit 0
cat > /dev/null 2>&1

python3 -c "
import json, os, time, subprocess, shlex

def run(cmd, timeout=10):
    try:
        r = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ''

scan_file = '/tmp/cmux-surface-scan.json'
eagle_file = '/tmp/cmux-eagle-status.json'
enter_signal = '/tmp/cmux-watcher-enter-signal.json'

# --- 1. WORKING surface 차단 (오케스트레이션이 디스패치한 surface만) ---
working = []

# 오케스트레이션 관리 대상 surface 목록 (dispatched + team members, 자기자신/watcher/jarvis 제외)
managed_surfaces = set()
roles_file = '/tmp/cmux-roles.json'
excluded_roles = {'boss', 'watcher', 'jarvis'}
if os.path.exists(roles_file):
    try:
        roles = json.load(open(roles_file))
        for role_name, role_info in roles.items():
            if role_name in excluded_roles:
                continue
            sf = role_info.get('surface', '')
            if sf:
                sf_id = sf.replace('surface:', '')
                managed_surfaces.add(sf_id)
        # dispatched 목록이 있으면 추가
        for sf in roles.get('dispatched', []):
            sf_id = str(sf).replace('surface:', '')
            managed_surfaces.add(sf_id)
    except: pass

if managed_surfaces:
    if os.path.exists(scan_file) and (time.time() - os.path.getmtime(scan_file)) < 300:
        try:
            d = json.load(open(scan_file))
            working = [s for s, i in d.get('surfaces', {}).items()
                       if i.get('status') == 'WORKING' and s in managed_surfaces]
        except: pass

    if not working and os.path.exists(eagle_file):
        try:
            d = json.load(open(eagle_file))
            working = [s for s, i in d.get('surfaces', {}).items()
                       if i.get('status') == 'WORKING' and s in managed_surfaces]
        except: pass

# --- 2. 와쳐 엔터 신호 처리 (Stop = AI 응답 완료 = 안전하게 엔터 가능) ---
if os.path.exists(enter_signal):
    try:
        sig = json.load(open(enter_signal))
        boss_sf = sig.get('boss_surface', '')
        boss_ws = sig.get('boss_workspace', '')
        needs_send = sig.get('needs_cmux_send', False)

        if boss_sf and boss_ws:
            q_ws = shlex.quote(boss_ws)
            q_sf = shlex.quote(boss_sf)
            # /cmux 전송 필요 시
            if needs_send:
                run(f'cmux send --workspace {q_ws} --surface {q_sf} /cmux')
                time.sleep(1)
            # 엔터 전송
            run(f'cmux send-key --workspace {q_ws} --surface {q_sf} enter')
            import sys
            print(f'[STOP-HOOK] {boss_sf}에 엔터 전송 완료', file=sys.stderr)

        # 신호 파일 삭제 (1회성)
        os.unlink(enter_signal)
    except Exception as e:
        import sys
        print(f'[STOP-HOOK] 엔터 신호 처리 실패: {e}', file=sys.stderr)

# --- 출력 ---
if working:
    print(json.dumps({'continue': False, 'stopReason': f'WORKING surface {len(working)}개. 수집 먼저.'}))
else:
    print(json.dumps({'continue': True}))
" 2>/dev/null || echo '{"continue":true}'
