#!/usr/bin/env python3
"""cmux-watcher-notify-enforcer.py — PreToolUse:Bash Hook (L0 BLOCK)

워커 surface에 작업 배정 후 와쳐에 알리지 않으면 다음 Bash 명령을 BLOCK.

동작:
1. cmux set-buffer --surface (워커) 감지 → pending에 surface 기록
2. cmux set-buffer --surface (와쳐) 감지 → pending 해소
3. pending이 남은 상태에서 다른 Bash 실행 시 → BLOCK (approve가 아닌 block)
4. 와쳐에 알림 보내는 명령만 통과 허용
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import write_json_atomic, is_boss_surface

PENDING_FILE = "/tmp/cmux-dispatch-pending.json"
SURFACE_MAP_FILE = "/tmp/cmux-surface-map.json"

def load_surface_map():
    if not os.path.exists(SURFACE_MAP_FILE):
        return None
    try:
        with open(SURFACE_MAP_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def load_pending():
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"surfaces": [], "timestamp": 0}

def save_pending(data):
    write_json_atomic(PENDING_FILE, data)

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        print(json.dumps({"decision": "approve"}))
        return
    # Boss surface에서만 와쳐 알림 강제. 다른 세션은 자유.
    if not is_boss_surface():
        print(json.dumps({"decision": "approve"}))
        return
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "approve"}))
        print("[cmux-watcher-notify-enforcer] ERROR: stdin parse failed", file=sys.stderr)
        return
    tool_name = inp.get("tool_name", "")
    tool_input = inp.get("tool_input", {})
    command = tool_input.get("command", "")

    if tool_name != "Bash":
        print(json.dumps({"decision": "approve"}))
        return

    # 동적 watcher surface 확인 (fail-open)
    smap = load_surface_map()
    if smap is None:
        print(json.dumps({"decision": "approve"}))
        return
    watcher_id = smap.get("watcher_surface", "")
    if not watcher_id:
        print(json.dumps({"decision": "approve"}))
        return

    # cmux set-buffer 감지
    if "cmux set-buffer" in command and "--surface" in command:
        pending = load_pending()

        # 와쳐에 보내는 건 → pending 전부 해소
        if re.search(rf'surface:{watcher_id}\b', command):
            pending["surfaces"] = []
            pending["timestamp"] = 0
            save_pending(pending)
            print(json.dumps({"decision": "approve"}))
            return

        # 워커에 보내는 건 → pending 추가
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = f"surface:{m.group(1)}"
            if sid not in pending["surfaces"]:
                pending["surfaces"].append(sid)
            pending["timestamp"] = time.time()
            save_pending(pending)

        print(json.dumps({"decision": "approve"}))
        return

    # cmux 관련 명령 → 항상 허용 (set-buffer 제외, 위에서 이미 처리)
    if re.search(r'cmux (paste-buffer|send-key|rename-tab|display-message|read-screen|capture-pane|tree|identify|notify|new-|close-|rename-|reorder-)', command):
        print(json.dumps({"decision": "approve"}))
        return

    # sleep, touch, echo, test, git 등 비-dispatch 명령 → 허용
    if re.search(r'^(sleep|touch|echo|test |git |diff |grep |cat |ls |cd |python3 -c|bash -n|\[)', command.strip()):
        print(json.dumps({"decision": "approve"}))
        return

    # pending 확인 — 와쳐 미알림 상태에서 다른 작업 시도 시 BLOCK
    pending = load_pending()
    if pending["surfaces"] and pending["timestamp"] > 0:
        elapsed = time.time() - pending["timestamp"]
        # Deadlock 방지: 5분(300초) 이상 pending이면 자동 해소
        # (Watcher crash 등으로 Boss가 영구 차단되는 것 방지)
        if elapsed > 300:
            pending["surfaces"] = []
            pending["timestamp"] = 0
            save_pending(pending)
            print(json.dumps({
                "decision": "approve",
                "reason": f"[WATCHER-TIMEOUT] ⚠️ pending이 {int(elapsed)}초 경과 — 자동 해소 (Watcher 상태 확인 권장)"
            }))
            return
        if elapsed > 3:
            surfaces_str = ", ".join(pending["surfaces"])
            print(json.dumps({
                "decision": "block",
                "reason": f"[WATCHER-BLOCK] ⛔ {surfaces_str}에 작업 배정했지만 와쳐(surface:{watcher_id})에 알림을 보내지 않았습니다. 먼저 cmux set-buffer --surface surface:{watcher_id} 로 와쳐에 모니터링 요청을 보내세요."
            }))
            return

    print(json.dumps({"decision": "approve"}))

if __name__ == "__main__":
    main()
