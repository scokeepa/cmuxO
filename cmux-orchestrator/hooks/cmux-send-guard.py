#!/usr/bin/env python3
"""cmux-send-guard.py — PreToolUse:Bash Hook (GATE W-9 send-keys guard)

Worker/Watcher 역할이 다른 surface를 향해 `tmux send-keys` 또는
`cmux send-keys`로 `/new` 또는 `/clear`를 전송하지 못하게 차단한다.

개입 금지 원칙(GATE W-9): Watcher는 감지·기록·보고만, Worker는 본인 작업만.
동료 surface의 세션을 리셋하거나 새로 여는 행위는 Boss 권한이다.

출력 스키마: Claude Code SyncHookJSONOutputSchema (coreSchemas.ts:907).
pass-through는 exit 0 + 빈 stdout, 차단은 hookSpecificOutput.permissionDecision:"deny".
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from hook_output import deny_pretool as deny  # noqa: E402

ROLES_FILE = "/tmp/cmux-roles.json"
GUARDED_ROLES = {"worker", "watcher"}
FORBIDDEN_TOKENS = ("/new", "/clear")

SEND_KEYS_RE = re.compile(
    r"\b(?:tmux|cmux)\s+send-keys\b(?P<rest>.*)", re.DOTALL
)
TARGET_RE = re.compile(r"-t\s+(?P<target>[A-Za-z0-9:_./@-]+)")
VARIABLE_RE = re.compile(r"\$[A-Za-z_{]")
QUOTED_RE = re.compile(r"""(?:"[^"]*"|'[^']*')""")


def _read_my_surface() -> str:
    try:
        out = subprocess.run(
            ["cmux", "identify"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return ""
        data = json.loads(out.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError,
            json.JSONDecodeError, OSError):
        return ""
    caller = data.get("caller") or data.get("focused") or {}
    return caller.get("surface_ref", "") or ""


def _read_my_role(my_surface: str) -> str:
    if not my_surface:
        return "unknown"
    try:
        with open(ROLES_FILE) as f:
            roles = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "worker"
    for role, info in roles.items():
        if isinstance(info, dict) and info.get("surface") == my_surface:
            return role
    return "worker"


def _strip_quoted_strings(text: str) -> str:
    return QUOTED_RE.sub(" ", text)


def _contains_forbidden_token(rest: str) -> bool:
    stripped = _strip_quoted_strings(rest)
    # The forbidden tokens are free-standing or at command boundaries.
    for tok in FORBIDDEN_TOKENS:
        if tok in rest:
            return True
        if tok in stripped:
            return True
    return False


def _extract_target(rest: str) -> str | None:
    m = TARGET_RE.search(rest)
    if not m:
        return None
    return m.group("target")


def _is_self_target(target: str, my_surface: str) -> bool:
    if target == "self":
        return True
    if my_surface and target == my_surface:
        return True
    return False


def _has_variable(rest: str) -> bool:
    return bool(VARIABLE_RE.search(rest))


def evaluate(command: str, role: str, my_surface: str) -> bool:
    """Return True if the command should be denied."""
    if role not in GUARDED_ROLES:
        return False
    m = SEND_KEYS_RE.search(command)
    if not m:
        return False
    rest = m.group("rest")
    if _has_variable(rest):
        return False
    if not _contains_forbidden_token(rest):
        return False
    target = _extract_target(rest)
    if target is None:
        return False
    if _is_self_target(target, my_surface):
        return False
    return True


def main() -> None:
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        return
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        deny("[cmux-send-guard] stdin parse failed. Blocked for safety.")
        return
    if inp.get("tool_name") != "Bash":
        return

    command = inp.get("tool_input", {}).get("command", "") or ""
    my_surface = _read_my_surface()
    role = _read_my_role(my_surface)

    if not evaluate(command, role, my_surface):
        return

    target = _extract_target(SEND_KEYS_RE.search(command).group("rest"))
    deny(
        f"[GATE W-9] role={role} surface={my_surface or 'unknown'}은 "
        f"다른 surface({target})에 /new·/clear를 보낼 수 없습니다. "
        f"개입은 Boss 권한입니다. See cmux-watcher/references/gate-w-9.md."
    )


if __name__ == "__main__":
    main()
