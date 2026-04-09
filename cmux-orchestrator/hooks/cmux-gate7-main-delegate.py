#!/usr/bin/env python3
"""cmux-gate7-main-delegate.py — PreToolUse Hook (GATE 7 L0)

사장(Main)이 IDLE worker surface가 있을 때 직접 작업 도구를 사용하는 것을 차단.
GATE 6이 Agent 도구만 차단하는 것을 보완하여, Read/Edit/Grep/Glob/Write도 차단.

허용 예외:
- /tmp/cmux-* 상태 파일 읽기 (오케스트레이션 관리)
- cmux 명령어 실행 (Bash)
- 오케스트레이션 비활성 상태
- Main이 아닌 surface
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import load_json_safe, is_main_surface

# 차단 대상 도구
BLOCKED_TOOLS = {"Read", "Edit", "Grep", "Glob", "Write"}

# 상태 파일 읽기는 허용 (오케스트레이션 관리용)
ALLOWED_READ_PREFIXES = (
    "/tmp/cmux-",
    "/tmp/cmux_",
)


def get_idle_worker_surfaces():
    """IDLE worker surface 목록 반환 (컨트롤 타워 제외)."""
    roles = load_json_safe("/tmp/cmux-roles.json")
    # 컨트롤 타워 surface 제외
    excluded = set()
    for role_data in roles.values():
        s = role_data.get("surface", "").replace("surface:", "")
        if s:
            excluded.add(s)

    # Eagle 상태에서 IDLE surface 확인
    eagle = load_json_safe("/tmp/cmux-eagle-status.json")
    idle_raw = eagle.get("idle_surfaces", "")
    if not idle_raw:
        return []

    idle_sids = [sid.strip() for sid in idle_raw.split() if sid.strip()]
    # 컨트롤 타워 제외한 IDLE worker만
    return [sid for sid in idle_sids if sid not in excluded]


def is_allowed_exception(tool_name, tool_input):
    """허용 예외 여부 판단."""
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        for prefix in ALLOWED_READ_PREFIXES:
            if file_path.startswith(prefix):
                return True
        return False

    if tool_name == "Grep":
        path = tool_input.get("path", "")
        for prefix in ALLOWED_READ_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    if tool_name == "Glob":
        path = tool_input.get("path", "")
        pattern = tool_input.get("pattern", "")
        for prefix in ALLOWED_READ_PREFIXES:
            if path.startswith(prefix) or pattern.startswith(prefix):
                return True
        return False

    return False


def main():
    # 오케스트레이션 모드 아니면 패스
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        print(json.dumps({"decision": "approve"}))
        return

    # Main surface가 아니면 패스
    if not is_main_surface():
        print(json.dumps({"decision": "approve"}))
        return

    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({"decision": "approve"}))
        return

    tool_name = inp.get("tool_name", "")
    tool_input = inp.get("tool_input", {})

    # 차단 대상 도구가 아니면 패스
    if tool_name not in BLOCKED_TOOLS:
        print(json.dumps({"decision": "approve"}))
        return

    # 허용 예외 확인
    if is_allowed_exception(tool_name, tool_input):
        print(json.dumps({"decision": "approve"}))
        return

    # IDLE worker surface 확인
    idle_workers = get_idle_worker_surfaces()
    if not idle_workers:
        # IDLE worker가 없으면 직접 작업 허용
        print(json.dumps({"decision": "approve"}))
        return

    # 차단
    idle_list = ", ".join([f"surface:{s}" for s in idle_workers])
    msg = (
        f"GATE 7 (L0): IDLE worker {len(idle_workers)}개 존재 ({idle_list}). "
        f"{tool_name} 차단. 사장은 직접 작업 금지 — "
        f"cmux send로 IDLE surface에 위임하세요."
    )
    print(json.dumps({"decision": "block", "reason": msg}, ensure_ascii=False))


if __name__ == "__main__":
    main()
