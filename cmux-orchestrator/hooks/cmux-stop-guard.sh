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

# --- 1. WORKING surface 차단 ---
working = []
if os.path.exists(scan_file) and (time.time() - os.path.getmtime(scan_file)) < 300:
    try:
        d = json.load(open(scan_file))
        working = [s for s, i in d.get('surfaces', {}).items() if i.get('status') == 'WORKING']
    except: pass

if not working and os.path.exists(eagle_file):
    try:
        d = json.load(open(eagle_file))
        if d.get('stats', {}).get('working', 0) > 0:
            working = ['eagle-detected']
    except: pass

# --- 2. 와쳐 엔터 신호 처리 (Stop = AI 응답 완료 = 안전하게 엔터 가능) ---
if os.path.exists(enter_signal):
    try:
        sig = json.load(open(enter_signal))
        main_sf = sig.get('main_surface', '')
        main_ws = sig.get('main_workspace', '')
        needs_send = sig.get('needs_cmux_send', False)

        if main_sf and main_ws:
            q_ws = shlex.quote(main_ws)
            q_sf = shlex.quote(main_sf)
            # /cmux 전송 필요 시
            if needs_send:
                run(f'cmux send --workspace {q_ws} --surface {q_sf} /cmux')
                time.sleep(1)
            # 엔터 전송
            run(f'cmux send-key --workspace {q_ws} --surface {q_sf} enter')
            import sys
            print(f'[STOP-HOOK] {main_sf}에 엔터 전송 완료', file=sys.stderr)

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
