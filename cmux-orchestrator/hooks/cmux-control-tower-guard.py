#!/usr/bin/env python3
"""cmux-control-tower-guard.py — PreToolUse:Bash Hook

cmux close-workspace 명령이 컨트롤 타워를 대상으로 하면 BLOCK.
컨트롤 타워(Boss/Watcher가 속한 workspace)는 절대 닫을 수 없다.
"""
import json
import os
import re
import shlex
import sys

ROLES_FILE = "/tmp/cmux-roles.json"


def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        print(json.dumps({"decision": "approve"}))
        return

    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "block", "reason": "[HOOK-ERROR] stdin parse failed. Blocked for safety."}))
        print(f"[cmux-control-tower-guard] ERROR: stdin parse failed", file=sys.stderr)
        return
    if inp.get("tool_name") != "Bash":
        print(json.dumps({"decision": "approve"}))
        return

    command = inp.get("tool_input", {}).get("command", "")

    # shlex 토큰화로 실제 cmux close-workspace 명령만 정확히 감지
    # (echo "close-workspace", grep "close-workspace" 등 간접 참조는 통과)
    is_close_cmd = False
    try:
        tokens = shlex.split(command)
        for i, token in enumerate(tokens):
            if token == "cmux" and i + 1 < len(tokens) and tokens[i + 1] == "close-workspace":
                is_close_cmd = True
                break
    except ValueError:
        pass

    if not is_close_cmd:
        print(json.dumps({"decision": "approve"}))
        return

    # 대상 workspace 추출
    m = re.search(r"--workspace\s+(workspace:\d+)", command)
    if not m:
        # --workspace 없는 naked close-workspace → 기본 workspace 닫을 수 있어 위험
        print(json.dumps({
            "decision": "block",
            "reason": "[CONTROL-TOWER-GUARD] close-workspace에 --workspace 플래그가 필요합니다."
        }))
        return

    target_ws = m.group(1)

    # 컨트롤 타워 workspace 확인
    try:
        with open(ROLES_FILE) as f:
            roles = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(json.dumps({"decision": "approve"}))
        return

    boss_ws = roles.get("boss", {}).get("workspace", "")
    watcher_ws = roles.get("watcher", {}).get("workspace", "")

    if target_ws in (boss_ws, watcher_ws) and target_ws:
        print(json.dumps({
            "decision": "block",
            "reason": f"[CONTROL-TOWER-GUARD] {target_ws}는 컨트롤 타워입니다. 닫을 수 없습니다."
        }))
        return

    print(json.dumps({"decision": "approve"}))


if __name__ == "__main__":
    main()
