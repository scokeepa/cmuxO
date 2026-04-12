#!/usr/bin/env python3
"""cmux-watcher-msg-guard.py — PreToolUse:Bash Hook (L0 BLOCK)

와쳐(동적 surface)에 보내는 메시지에서 금지 패턴을 차단.

교훈: 와쳐는 CCTV — 감시 지시만 받아야 한다. 성과 보고, 요약, 결론을 보내면
컨텍스트 낭비 + 역할 혼동.

차단 대상:
- 핵심성과, 요약, 결론, 결과 종합 등 보고성 메시지
- "DONE: 키워드 감시" — 4중 방어체계 지시가 올바름
- 라운드 결과 보고

허용 대상:
- 모니터링 대상 surface 목록
- 4중 방어체계 감시 지시
- 세션 종료 통보
- 재배정 완료 통보 (간결)
"""
import json
import os
import re
import sys

SURFACE_MAP_FILE = "/tmp/cmux-surface-map.json"

def load_surface_map():
    if not os.path.exists(SURFACE_MAP_FILE):
        return None
    try:
        with open(SURFACE_MAP_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

# 와쳐에 보내면 안 되는 패턴
BANNED_PATTERNS = [
    r"핵심\s*성과",
    r"결과\s*종합",
    r"Round\s*\d+\s*(성과|결과|요약)",
    r"라우트\s*\d+/\d+",
    r"PASS\s*유지",
    r"\d+\s*테스트\s*regression",
    r"SSE.*완료",
    r"WebSocket.*발견",
    r"DONE:\s*키워드\s*감시",  # 올바른 지시는 "4중 방어체계"
]

# 와쳐에 보내야 하는 올바른 패턴 (허용 우선)
ALLOWED_PATTERNS = [
    r"4중\s*방어체계",
    r"모니터링\s*모드",
    r"감시\s*대상",
    r"세션\s*종료",
    r"재배정\s*완료",
    r"DONE\s*감지\s*시",
    r"IDLE.*재촉",
    r"ERROR.*보고",
]

def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        print(json.dumps({"decision": "approve"}))
        return
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "approve"}))
        print("[cmux-watcher-msg-guard] ERROR: stdin parse failed", file=sys.stderr)
        return
    if inp.get("tool_name") != "Bash":
        print(json.dumps({"decision": "approve"}))
        return

    command = inp.get("tool_input", {}).get("command", "")

    # 동적 watcher surface 확인 (fail-open)
    smap = load_surface_map()
    if smap is None:
        print(json.dumps({"decision": "approve"}))
        return
    watcher_id = smap.get("watcher_surface", "")
    if not watcher_id or "set-buffer" not in command or not re.search(rf'surface:{watcher_id}\b', command):
        print(json.dumps({"decision": "approve"}))
        return

    # 허용 패턴 먼저 체크 — 있으면 통과
    for pat in ALLOWED_PATTERNS:
        if re.search(pat, command):
            print(json.dumps({"decision": "approve"}))
            return

    # 금지 패턴 체크
    for pat in BANNED_PATTERNS:
        if re.search(pat, command):
            print(json.dumps({
                "decision": "block",
                "reason": f"[WATCHER-MSG] ⛔ 와쳐에 보고성 메시지 금지. 와쳐는 CCTV — 감시 지시만 전달하세요. 올바른 형식: '[BOSS→WATCHER] 모니터링 모드: 4중 방어체계. 대상: s:N,... DONE 감지 시 보고. IDLE 3분+ 재촉. ERROR 즉시 보고.'"
            }))
            return

    print(json.dumps({"decision": "approve"}))

if __name__ == "__main__":
    main()
