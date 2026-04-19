#!/usr/bin/env python3
"""cmux-leceipts-gate.py — PreToolUse:Bash Hook (L0 BLOCK)

git commit 전 leceipts 5-섹션 보고서 존재를 검증.
보고서가 없거나 불완전하면 커밋을 물리적으로 차단한다.

5-섹션 키 정본: CLAUDE.md (leceipts Working Rules)
패턴 기준: cmux-completion-verifier.py + cmux-control-tower-guard.py

출력 스키마: Claude Code SyncHookJSONOutputSchema (coreSchemas.ts:907).
pass-through는 exit 0 + 빈 stdout, 차단은 hookSpecificOutput.permissionDecision:"deny".
"""
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from hook_output import deny_pretool as deny
from leceipts_validator import is_git_commit


def _get_staged_diff_hash():
    """현재 staged 변경의 hash (증거 바인딩용)."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--diff-algorithm=minimal"],
            capture_output=True, text=True, timeout=3,
        )
        return hashlib.sha256(r.stdout.encode()).hexdigest()[:16]
    except Exception:
        return None


def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        return

    try:
        from cmux_utils import is_boss_surface
        if not is_boss_surface():
            return
    except ImportError:
        pass

    # stdin 파싱 — fail-closed (cmux-control-tower-guard.py:21~26 패턴)
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        deny("[LECEIPTS] stdin JSON 파싱 실패. 안전을 위해 차단.")
        print("[cmux-leceipts-gate] ERROR: stdin parse failed", file=sys.stderr)
        return

    if inp.get("tool_name") != "Bash":
        return

    command = inp.get("tool_input", {}).get("command", "")

    if not is_git_commit(command):
        return

    # --- 공통 validator로 보고서 검증 ---
    try:
        from leceipts_validator import validate_report
    except ImportError:
        deny("[LECEIPTS] leceipts_validator.py를 찾을 수 없습니다.")
        return

    diff_hash = _get_staged_diff_hash()
    ok, result = validate_report(check_ttl=True, check_diff_hash=diff_hash)

    if ok:
        return
    deny(
        f"[LECEIPTS] ⛔ {result}. "
        "git commit 전 leceipts 보고서를 /tmp/cmux-leceipts-report.json에 작성하세요."
    )


if __name__ == "__main__":
    main()
