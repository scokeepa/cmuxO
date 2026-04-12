#!/usr/bin/env python3
"""cmux-no-stall-enforcer.py — PreToolUse:Bash Hook (L0 BLOCK)

메인 AI의 3가지 멈춤 패턴을 물리적으로 차단:
1. surface 완료 알림 후 Sonnet 검증 미투입
2. IDLE surface 3개+ 방치
3. 와쳐 완료 알림 후 결과 미수집

/tmp/cmux-orchestration-state.json 으로 상태 추적.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import write_json_atomic, is_boss_surface

STATE_FILE = "/tmp/cmux-orchestration-state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "completed_unverified": [],  # surface 완료됐지만 Sonnet 미투입
        "completed_unreassigned": {},  # surface 완료 시각 (재투입 대기)
        "last_watcher_done": 0,  # 마지막 와쳐 DONE 알림 시각
        "last_action": 0,  # 마지막 유의미 액션 시각
    }

def save_state(data):
    write_json_atomic(STATE_FILE, data)

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        print(json.dumps({"decision": "approve"}))
        return
    # Boss surface에서만 stall 방지 강제. 다른 세션은 자유.
    if not is_boss_surface():
        print(json.dumps({"decision": "approve"}))
        return
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "block", "reason": "[HOOK-ERROR] stdin parse failed. Blocked for safety."}))
        print(f"[cmux-no-stall-enforcer] ERROR: stdin parse failed", file=sys.stderr)
        return
    tool_name = inp.get("tool_name", "")
    tool_input = inp.get("tool_input", {})
    command = tool_input.get("command", "") if tool_name == "Bash" else ""

    state = load_state()
    now = time.time()
    violations = []

    # === 상태 업데이트 ===

    # cmux rename-tab ✅ = surface 완료
    if "rename-tab" in command and "✅" in command:
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = m.group(1)
            state["completed_unverified"].append(sid)
            state["completed_unreassigned"][sid] = now
            save_state(state)

    # Agent 호출 = Sonnet 검증 투입 (verify 접두사)
    if tool_name == "Agent":
        desc = inp.get("tool_input", {}).get("description", "")
        if "검증" in desc or "verify" in desc.lower():
            # 가장 오래된 미검증 surface 해소
            if state["completed_unverified"]:
                state["completed_unverified"].pop(0)
                save_state(state)

    # cmux set-buffer = 새 작업 배정 → 재투입 기록
    if "set-buffer" in command and "--surface" in command:
        m = re.search(r'surface:(\d+)', command)
        if m:
            sid = m.group(1)
            if sid in state["completed_unreassigned"]:
                del state["completed_unreassigned"][sid]
            state["last_action"] = now
            save_state(state)

    # === 위반 감지 ===

    # 위반 1: 완료됐지만 Sonnet 미투입 2건+
    if len(state["completed_unverified"]) >= 2:
        sids = ", ".join([f"surface:{s}" for s in state["completed_unverified"][:3]])
        violations.append(f"Sonnet 미투입 {len(state['completed_unverified'])}건 ({sids})")

    # 위반 2: 3개+ surface가 2분+ IDLE
    idle_count = 0
    idle_list = []
    for sid, completed_at in state["completed_unreassigned"].items():
        if now - completed_at > 120:  # 2분
            idle_count += 1
            idle_list.append(f"surface:{sid}")
    if idle_count >= 3:
        violations.append(f"IDLE 방치 {idle_count}개 ({', '.join(idle_list[:4])})")

    # === 판정 ===
    if violations:
        msg = " | ".join(violations)
        print(json.dumps({
            "decision": "block",
            "reason": f"[NO-STALL] ⛔ 멈춤 감지: {msg}. 즉시 (1) Sonnet 검증 투입 (2) IDLE surface 재배정 하세요."
        }))
        return

    print(json.dumps({"decision": "approve"}))

if __name__ == "__main__":
    main()
