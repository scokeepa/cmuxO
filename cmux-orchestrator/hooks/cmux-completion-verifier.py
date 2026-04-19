#!/usr/bin/env python3
"""cmux-completion-verifier.py — PreToolUse:Bash Hook (L0 BLOCK)

"완료", "커밋", "종료" 등 완료성 Bash 명령 전에 검증 스크립트 실행 강제.

교훈: 이번 세션에서 "docs 2개 존재"라고 보고했지만 pwd 오류로 실제 미존재.
AI의 자기 보고를 믿지 말고 기계적 검증 필수.

동작:
1. git commit / git add 감지 → 미검증 상태면 BLOCK
2. /tmp/cmux-verification-passed 파일이 있으면 통과
3. 검증 스크립트를 먼저 실행해야 함

출력 스키마: Claude Code SyncHookJSONOutputSchema (coreSchemas.ts:907).
pass-through는 exit 0 + 빈 stdout, 차단은 hookSpecificOutput.permissionDecision:"deny".
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import is_boss_surface
from hook_output import deny_pretool as deny
from leceipts_validator import is_git_commit

VERIFY_FLAG = "/tmp/cmux-verification-passed"
MAX_AGE = 300  # 5분 이내 검증만 유효


def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        return
    # Boss surface에서만 검증 강제. JARVIS/Watcher/팀장 등 다른 세션은 자유.
    if not is_boss_surface():
        # JARVIS, Watcher, 팀장 surface는 면제
        return
    try:
        inp = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        deny("[HOOK-ERROR] stdin parse failed. Blocked for safety.")
        print("[cmux-completion-verifier] ERROR: stdin parse failed", file=sys.stderr)
        return
    if inp.get("tool_name") != "Bash":
        return

    command = inp.get("tool_input", {}).get("command", "")

    # git commit 감지 — shlex 토큰 분석
    if not is_git_commit(command):
        return

    # 검증 플래그 확인
    if os.path.exists(VERIFY_FLAG):
        try:
            mtime = os.path.getmtime(VERIFY_FLAG)
            if time.time() - mtime < MAX_AGE:
                # 검증 통과 (TTL 기반 자연 만료, 삭제하지 않음)
                return
        except OSError:
            pass

    # 검증 미실행
    deny("[VERIFY-BLOCK] ⛔ git commit 전 검증 미실행. 먼저 pytest + 파일 존재 확인 등 기계적 검증을 실행하고 touch /tmp/cmux-verification-passed 하세요. AI 자기 보고를 믿지 마세요.")

if __name__ == "__main__":
    main()
