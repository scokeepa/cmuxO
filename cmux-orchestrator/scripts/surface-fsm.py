#!/usr/bin/env python3
"""surface-fsm.py — Surface State Machine
각 surface의 상태를 FSM으로 추적하여 잘못된 전이를 방지.

상태: IDLE → ASSIGNED → WORKING → DONE → VERIFIED → IDLE (재사용)
                                    ↓
                                  ERROR → RECOVERED → IDLE

사용법:
  python3 surface-fsm.py assign surface:5    # IDLE→ASSIGNED
  python3 surface-fsm.py working surface:5   # ASSIGNED→WORKING (자동)
  python3 surface-fsm.py done surface:5      # WORKING→DONE (자동)
  python3 surface-fsm.py verify surface:5    # DONE→VERIFIED
  python3 surface-fsm.py error surface:5     # *→ERROR
  python3 surface-fsm.py recover surface:5   # ERROR→IDLE
  python3 surface-fsm.py reset surface:5     # *→IDLE (강제)
  python3 surface-fsm.py status              # 전체 상태 출력
  python3 surface-fsm.py check-assign surface:5  # IDLE인지 확인 (exit 0/1)
  python3 surface-fsm.py unverified          # DONE이지만 VERIFIED 안 된 목록
"""
import json, sys, os
from datetime import datetime, timezone
from pathlib import Path

FSM_FILE = Path("/tmp/cmux-surface-fsm.json")

# 허용 전이 (from → [to1, to2, ...])
VALID_TRANSITIONS = {
    "IDLE": ["ASSIGNED"],
    "ASSIGNED": ["WORKING", "ERROR", "IDLE"],
    "WORKING": ["DONE", "ERROR"],
    "DONE": ["VERIFIED", "ERROR", "IDLE"],
    "VERIFIED": ["IDLE"],
    "ERROR": ["RECOVERED", "IDLE"],
    "RECOVERED": ["IDLE", "ASSIGNED"],
}

def load():
    if FSM_FILE.exists():
        try:
            return json.loads(FSM_FILE.read_text())
        except Exception:
            pass
    return {"surfaces": {}, "transitions": []}

def save(data):
    from pathlib import Path
    tmp = str(FSM_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.rename(tmp, str(FSM_FILE))

def transition(surface, target_state, force=False):
    data = load()
    surfaces = data.setdefault("surfaces", {})
    transitions = data.setdefault("transitions", [])

    current = surfaces.get(surface, {}).get("state", "IDLE")

    if not force and target_state not in VALID_TRANSITIONS.get(current, []):
        print(f"❌ 잘못된 전이: {surface} {current}→{target_state} (허용: {VALID_TRANSITIONS.get(current, [])})")
        return False

    now = datetime.now(timezone.utc).isoformat()
    surfaces[surface] = {
        "state": target_state,
        "previous": current,
        "updated_at": now,
    }
    transitions.append({
        "surface": surface,
        "from": current,
        "to": target_state,
        "at": now,
        "forced": force,
    })

    # 최근 100개만 유지
    if len(transitions) > 100:
        data["transitions"] = transitions[-100:]

    save(data)
    print(f"✅ {surface}: {current}→{target_state}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: surface-fsm.py <command> [surface]")
        sys.exit(1)

    cmd = sys.argv[1]
    surface = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "status":
        data = load()
        for s, info in sorted(data.get("surfaces", {}).items()):
            print(f"  {s}: {info.get('state', 'IDLE')}")
        sys.exit(0)

    if cmd == "unverified":
        data = load()
        unv = [s for s, i in data.get("surfaces", {}).items() if i.get("state") == "DONE"]
        if unv:
            print(f"미검증 surface {len(unv)}개: {unv}")
            sys.exit(1)
        else:
            print("전부 검증됨")
            sys.exit(0)

    if cmd == "check-assign":
        if not surface:
            print("surface 필요"); sys.exit(1)
        data = load()
        state = data.get("surfaces", {}).get(surface, {}).get("state", "IDLE")
        if state == "IDLE":
            print(f"✅ {surface}: IDLE → 배정 가능")
            sys.exit(0)
        else:
            print(f"❌ {surface}: {state} → 배정 불가 (IDLE이어야 함)")
            sys.exit(1)

    if not surface:
        print("surface 필요"); sys.exit(1)

    cmd_map = {
        "assign": "ASSIGNED",
        "working": "WORKING",
        "done": "DONE",
        "verify": "VERIFIED",
        "error": "ERROR",
        "recover": "RECOVERED",
        "reset": "IDLE",
    }

    target = cmd_map.get(cmd)
    if not target:
        print(f"알 수 없는 명령: {cmd}"); sys.exit(1)

    force = cmd == "reset" or cmd == "error"  # reset/error는 어디서든 강제
    ok = transition(surface, target, force=force)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
