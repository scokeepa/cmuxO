#!/usr/bin/env python3
"""cmux-idle-reuse-enforcer.py — PostToolUse:Bash Hook (L2 WARNING)

와쳐가 surface 완료를 보고한 후, 해당 surface가 3분 이상 재투입 없이 IDLE이면 경고.

동작:
1. cmux rename-tab "✅" 감지 → /tmp/cmux-idle-tracker.json에 완료 시각 기록
2. 3분 후에도 해당 surface에 새 set-buffer가 없으면 → 경고 주입
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import write_json_atomic

TRACKER_FILE = "/tmp/cmux-idle-tracker.json"
IDLE_THRESHOLD_SECONDS = 180  # 3분

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"completed": {}, "reused": []}

def save_tracker(data):
    write_json_atomic(TRACKER_FILE, data)

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        sys.exit(0)
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print("[cmux-idle-reuse-enforcer] ERROR: stdin parse failed", file=sys.stderr)
        sys.exit(0)
    tool_input = inp.get("tool_input", {})
    command = tool_input.get("command", "")

    tracker = load_tracker()

    # ✅ 탭 이름 = surface 완료 → 완료 시각 기록
    if "rename-tab" in command and "✅" in command:
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = m.group(1)
            tracker["completed"][sid] = time.time()
            if sid in tracker["reused"]:
                tracker["reused"].remove(sid)
            save_tracker(tracker)

    # set-buffer = surface에 새 작업 → 재투입으로 기록
    if "set-buffer" in command and "--surface" in command:
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = m.group(1)
            if sid in tracker["completed"]:
                del tracker["completed"][sid]
            if sid not in tracker["reused"]:
                tracker["reused"].append(sid)
            save_tracker(tracker)

    # IDLE 체크 — 3분+ 방치된 surface 경고
    idle_surfaces = []
    now = time.time()
    for sid, completed_at in list(tracker["completed"].items()):
        if now - completed_at > IDLE_THRESHOLD_SECONDS:
            idle_surfaces.append(f"surface:{sid}")

    if len(idle_surfaces) >= 3:
        surfaces_str = ", ".join(idle_surfaces)
        print(json.dumps({
            "decision": "approve",
            "additionalContext": f"[IDLE-ENFORCER] ⚠️ {surfaces_str} 가 {IDLE_THRESHOLD_SECONDS//60}분+ IDLE. 즉시 새 작업 배정하세요. (규칙 15 위반)"
        }))
        return

    print(json.dumps({"decision": "approve"}))

if __name__ == "__main__":
    main()
