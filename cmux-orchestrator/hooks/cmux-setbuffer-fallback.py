#!/usr/bin/env python3
"""cmux-setbuffer-fallback.py — PostToolUse:Bash Hook (L2 WARNING)

set-buffer + paste-buffer 후 surface가 IDLE 상태면 경고.
교훈: Claude Code surface가 set-buffer를 수신하지 못하는 경우가 빈번.
cmux send 로 fallback 필요.

동작:
1. cmux paste-buffer 감지 → 대상 surface 기록
2. 10초 후 다음 Bash에서 해당 surface의 read-screen 결과 확인
3. 여전히 IDLE이면 WARNING: "cmux send 로 재전송하세요"
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import write_json_atomic

STATE_FILE = "/tmp/cmux-paste-pending.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"dispatched": {}}

def save_state(data):
    write_json_atomic(STATE_FILE, data)

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        sys.exit(0)
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print("[cmux-setbuffer-fallback] ERROR: stdin parse failed", file=sys.stderr)
        sys.exit(0)
    tool_name = inp.get("tool_name", "")

    if tool_name != "Bash":
        print(json.dumps({}))
        return

    result = inp.get("tool_result", {})
    stdout = result.get("stdout", "") if isinstance(result, dict) else str(result)
    command = inp.get("tool_input", {}).get("command", "")

    state = load_state()

    # paste-buffer 감지 → dispatch 기록
    if "paste-buffer" in command:
        import re
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = m.group(1)
            state["dispatched"][sid] = time.time()
            save_state(state)

    # read-screen 결과에서 IDLE 감지 → 최근 dispatch한 surface인지 확인
    if "read-screen" in command:
        import re
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = m.group(1)
            dispatch_time = state.get("dispatched", {}).get(sid, 0)
            # 10초~120초 이내에 dispatch했고 IDLE 패턴 발견
            elapsed = time.time() - dispatch_time
            if 10 < elapsed < 120:
                idle_markers = ["bypass permissions", "❯", "gpt-5.4"]
                if any(marker in stdout for marker in idle_markers):
                    # 이미 "Working" 등이 있으면 무시
                    working_markers = ["Working", "thinking", "tokens", "Mulling", "Forging"]
                    if not any(wm in stdout for wm in working_markers):
                        print(json.dumps({
                            "decision": "approve",
                            "reason": f"[FALLBACK-WARN] ⚠️ surface:{sid}가 dispatch 후 {int(elapsed)}초 경과했지만 IDLE. set-buffer 미수신 가능성. cmux send --surface surface:{sid} 로 재전송하세요."
                        }))
                        # 경고 1회만
                        if sid in state["dispatched"]:
                            del state["dispatched"][sid]
                            save_state(state)
                        return

    print(json.dumps({}))

if __name__ == "__main__":
    main()
