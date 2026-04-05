#!/usr/bin/env python3
"""cmux-enforcement-escalator.py — PostToolUse Hook (L2 WARNING)

강제력 자동 승격: L3 규칙 위반 추적 → 반복 위반 시 경고 에스컬레이션.

동작:
1. PostToolUse에서 systemMessage 경고를 추적
2. 같은 패턴의 경고가 3회 누적되면 "L0 Hook 생성 필요" 메시지 주입
3. /tmp/cmux-violation-tracker.json에 위반 이력 저장 (72시간 만료)

이 Hook 자체는 L2(경고)이지만, 반복 위반을 감지하여
사용자/AI에게 L0 Hook 생성을 촉구한다.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import write_json_atomic

TRACKER_FILE = "/tmp/cmux-violation-tracker.json"
EXPIRY_HOURS = 72
ESCALATION_THRESHOLD = 3  # 3회 위반 시 에스컬레이션

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"violations": {}, "escalated": []}

def save_tracker(data):
    write_json_atomic(TRACKER_FILE, data)

def cleanup_expired(tracker):
    """Remove violations older than EXPIRY_HOURS."""
    now = time.time()
    cutoff = now - (EXPIRY_HOURS * 3600)
    for pattern, entries in list(tracker["violations"].items()):
        tracker["violations"][pattern] = [e for e in entries if e > cutoff]
        if not tracker["violations"][pattern]:
            del tracker["violations"][pattern]
    return tracker

def classify_violation(tool_result_str):
    """Classify the violation pattern from hook output."""
    patterns = {
        "watcher-msg": ["WATCHER-MSG", "와쳐에 보고성"],
        "init-missing": ["INIT-ENFORCER", "초기화 없이"],
        "verify-missing": ["VERIFY-BLOCK", "검증 미실행"],
        "state-machine": ["STATE-MACHINE", "상태"],
        "notify-missing": ["WATCHER-BLOCK", "와쳐에 알림"],
        "stall": ["NO-STALL", "멈춤 감지"],
        "idle-waste": ["IDLE", "놀고 있음"],
        "gate-block": ["GATE", "WORKING surface"],
    }
    for pattern_name, keywords in patterns.items():
        if any(kw in tool_result_str for kw in keywords):
            return pattern_name
    return None

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        sys.exit(0)
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print("[cmux-enforcement-escalator] ERROR: stdin parse failed", file=sys.stderr)
        sys.exit(0)
    tool_result = inp.get("tool_result", {})

    # Extract text from result
    result_str = ""
    if isinstance(tool_result, dict):
        result_str = json.dumps(tool_result)
    elif isinstance(tool_result, str):
        result_str = tool_result

    # Check if this contains a hook warning/block
    if not any(marker in result_str for marker in ["⛔", "⚠️", "BLOCK", "WARNING", "ENFORCER"]):
        print(json.dumps({}))
        return

    tracker = load_tracker()
    tracker = cleanup_expired(tracker)

    pattern = classify_violation(result_str)
    if not pattern:
        print(json.dumps({}))
        return

    # Record violation
    if pattern not in tracker["violations"]:
        tracker["violations"][pattern] = []
    tracker["violations"][pattern].append(time.time())
    save_tracker(tracker)

    count = len(tracker["violations"][pattern])

    # Check for escalation threshold
    if count >= ESCALATION_THRESHOLD and pattern not in tracker["escalated"]:
        tracker["escalated"].append(pattern)
        save_tracker(tracker)

        print(json.dumps({
            "decision": "approve",
            "reason": f"[ESCALATION] 🔴 '{pattern}' 위반 {count}회 누적. L3 규칙으로는 부족합니다. L0 PreToolUse Hook으로 물리적 차단을 강화하세요. /sdd 자가개선 실행을 권장합니다."
        }))
        return

    if count >= 2:
        print(json.dumps({
            "decision": "approve",
            "reason": f"[ESCALATION-WARN] ⚠️ '{pattern}' 위반 {count}/{ESCALATION_THRESHOLD}회. {ESCALATION_THRESHOLD}회 도달 시 L0 승격 권고."
        }))
        return

    print(json.dumps({}))

if __name__ == "__main__":
    main()
