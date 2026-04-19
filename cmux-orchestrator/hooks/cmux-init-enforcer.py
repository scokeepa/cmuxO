#!/usr/bin/env python3
"""cmux-init-enforcer.py — PreToolUse:Bash Hook (L0 BLOCK)

Claude Code surface(GLM/MiniMax)에 작업 전송 전 /new 초기화 여부 강제.
Codex CLI surface는 초기화 불필요.

동작:
1. cmux send "/new" 감지 → 초기화 완료 기록
2. cmux set-buffer --surface (워커) 감지 → 해당 surface가 초기화됐는지 확인
3. 미초기화 시 BLOCK (Codex surface 제외)

출력 스키마: Claude Code SyncHookJSONOutputSchema (coreSchemas.ts:907).
pass-through는 exit 0 + 빈 stdout, 차단은 hookSpecificOutput.permissionDecision:"deny".
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import write_json_atomic
from hook_output import deny_pretool as deny

STATE_FILE = "/tmp/cmux-init-state.json"
SURFACE_MAP_FILE = "/tmp/cmux-surface-map.json"


def load_surface_map():
    if not os.path.exists(SURFACE_MAP_FILE):
        return None
    try:
        with open(SURFACE_MAP_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"initialized": {}}

def save_state(data):
    write_json_atomic(STATE_FILE, data)

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        return
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print("[cmux-init-enforcer] ERROR: stdin parse failed", file=sys.stderr)
        return
    if inp.get("tool_name") != "Bash":
        return

    command = inp.get("tool_input", {}).get("command", "")

    # 알림성 메시지 면제 (/btw, notify, send-key, paste-buffer, read-screen 등)
    if re.search(r'cmux (send-key|paste-buffer|read-screen|capture-pane|notify|rename-tab|tree|identify)', command):
        return
    # /btw 전송은 알림이므로 면제
    if '/btw' in command:
        return

    state = load_state()

    # /new 전송 감지 → 초기화 기록
    if '"/new"' in command or "'/new'" in command or ' /new' in command:
        m = re.search(r'surface[: ]+(\d+)', command)
        if m:
            state["initialized"][m.group(1)] = time.time()
            save_state(state)

    # set-buffer 감지 → 초기화 여부 확인
    if "set-buffer" in command and "--surface" in command:
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = m.group(1)
            # 동적 surface map에서 Codex/와쳐 확인 (fail-open)
            smap = load_surface_map()
            if smap is None:
                return
            no_init_surfaces = set(smap.get("no_init_surfaces", smap.get("codex_surfaces", [])))
            watcher_surface = smap.get("watcher_surface", "")
            if sid in no_init_surfaces or sid == watcher_surface:
                return
            # Claude Code surface — 초기화 확인
            init_time = state.get("initialized", {}).get(sid, 0)
            if time.time() - init_time > 600:  # 10분 이내 초기화 필요
                deny(f"[INIT-ENFORCER] ⛔ surface:{sid}(Claude Code)에 /new 초기화 없이 작업 전송 시도. 먼저 Esc → /new → enter → sleep 3 실행하세요.")
                return

if __name__ == "__main__":
    main()
