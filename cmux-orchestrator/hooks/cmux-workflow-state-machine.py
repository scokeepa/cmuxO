#!/usr/bin/env python3
"""cmux-workflow-state-machine.py — PreToolUse:Bash Hook (L0 BLOCK)

상태 기계 기반 워크플로우 강제.
dispatch → verify → commit 순서를 물리적으로 강제한다.

교훈: AI는 검증 없이 커밋하거나, 디스패치 없이 결과 수집하거나,
결과 수집 없이 완료 선언한다. 상태 전이 규칙으로 차단.

상태 전이:
  IDLE → DISPATCHED (cmux set-buffer/send로 작업 전송)
  DISPATCHED → COLLECTING (cmux read-screen/capture-pane으로 결과 수집)
  COLLECTING → VERIFIED (Agent로 Sonnet 검증 투입)
  VERIFIED → COMMITTED (git commit)
  COMMITTED → IDLE (다음 라운드)

금지 전이:
  IDLE → COMMITTED (디스패치 없이 커밋 금지)
  DISPATCHED → COMMITTED (검증 없이 커밋 금지)
  IDLE → COLLECTING (디스패치 없이 수집 금지)
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import write_json_atomic, is_main_surface

STATE_FILE = "/tmp/cmux-workflow-state.json"
SURFACE_MAP_FILE = "/tmp/cmux-surface-map.json"

def load_surface_map():
    if not os.path.exists(SURFACE_MAP_FILE):
        return None
    try:
        with open(SURFACE_MAP_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

VALID_TRANSITIONS = {
    "IDLE": ["DISPATCHED", "IDLE"],
    "DISPATCHED": ["COLLECTING", "DISPATCHED", "IDLE"],  # IDLE = reset
    "COLLECTING": ["VERIFIED", "COLLECTING", "DISPATCHED"],  # can re-dispatch
    "VERIFIED": ["COMMITTED", "VERIFIED", "DISPATCHED"],  # can re-dispatch
    "COMMITTED": ["IDLE", "DISPATCHED"],  # next round
}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                d = json.load(f)
                # Auto-expire after 30 minutes of inactivity
                if time.time() - d.get("timestamp", 0) > 1800:
                    return {"state": "IDLE", "timestamp": time.time(), "dispatch_count": 0}
                return d
        except (json.JSONDecodeError, IOError):
            pass
    return {"state": "IDLE", "timestamp": time.time(), "dispatch_count": 0}

def save_state(data):
    data["timestamp"] = time.time()
    write_json_atomic(STATE_FILE, data)

def detect_action(command, tool_name, tool_input):
    """Detect what action the command represents."""
    if tool_name == "Agent":
        desc = tool_input.get("description", "").lower()
        if any(kw in desc for kw in ["검증", "verify", "review", "확인"]):
            return "VERIFY"
        return None

    if tool_name != "Bash":
        return None

    # 동적 watcher surface 제외 (watcher에 보내는 건 DISPATCH가 아님)
    smap = load_surface_map()
    watcher_id = smap.get("watcher_surface", "") if smap else ""
    watcher_pat = rf'surface:{watcher_id}\b' if watcher_id else r'surface:$^'

    # Dispatch: sending work to surfaces
    if "set-buffer" in command and "surface:" in command and not re.search(watcher_pat, command):
        return "DISPATCH"
    if "cmux send" in command and "surface:" in command and not re.search(watcher_pat, command):
        return "DISPATCH"

    # Collect: reading results
    if "read-screen" in command and "--scrollback" in command:
        return "COLLECT"
    if "capture-pane" in command:
        return "COLLECT"

    # Commit
    if "git commit" in command:
        return "COMMIT"

    # Reset: session init
    if "/new" in command or "cmux tree" in command or "cmux identify" in command:
        return None  # neutral

    return None

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        print(json.dumps({"decision": "approve"}))
        return
    # Main surface에서만 워크플로우 규율 적용. 다른 세션은 자유.
    if not is_main_surface():
        print(json.dumps({"decision": "approve"}))
        return
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "block", "reason": "[HOOK-ERROR] stdin parse failed. Blocked for safety."}))
        print(f"[cmux-workflow-state-machine] ERROR: stdin parse failed", file=sys.stderr)
        return
    tool_name = inp.get("tool_name", "")
    tool_input = inp.get("tool_input", {})
    command = tool_input.get("command", "") if tool_name == "Bash" else ""

    state_data = load_state()
    current = state_data.get("state", "IDLE")

    action = detect_action(command, tool_name, tool_input)

    if action is None:
        # Neutral action — always allow
        print(json.dumps({"decision": "approve"}))
        return

    # Map action to target state
    action_to_state = {
        "DISPATCH": "DISPATCHED",
        "COLLECT": "COLLECTING",
        "VERIFY": "VERIFIED",
        "COMMIT": "COMMITTED",
    }

    target = action_to_state.get(action)
    if not target:
        print(json.dumps({"decision": "approve"}))
        return

    # Check if transition is valid
    valid_targets = VALID_TRANSITIONS.get(current, [])
    if target in valid_targets:
        state_data["state"] = target
        if action == "DISPATCH":
            state_data["dispatch_count"] = state_data.get("dispatch_count", 0) + 1
        save_state(state_data)
        print(json.dumps({"decision": "approve"}))
    else:
        # Invalid transition — but only BLOCK for commit violations
        if action == "COMMIT" and current not in ("VERIFIED", "COMMITTED"):
            print(json.dumps({
                "decision": "block",
                "reason": f"[STATE-MACHINE] ⛔ 현재 상태 {current}에서 COMMIT 불가. 검증(VERIFIED) 상태에서만 커밋 가능. 먼저 결과 수집(read-screen) → Sonnet 검증(Agent) 실행하세요."
            }))
            return
        # For other transitions, allow but warn (soft enforcement)
        state_data["state"] = target
        save_state(state_data)
        print(json.dumps({
            "decision": "approve",
            "systemMessage": f"[STATE-MACHINE] ⚠️ {current}→{target} 전이는 권장 순서가 아닙니다. 올바른 순서: {' → '.join(valid_targets)}"
        }))

if __name__ == "__main__":
    main()
