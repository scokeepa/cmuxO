#!/usr/bin/env python3
"""cmux-plan-quality-gate.py — PreToolUse:ExitPlanMode Hook (L0 BLOCK)

플랜 품질 게이트 자동 강제.
전역 설정(CLAUDE.md)의 플랜 수립 절차를 강제:
  검증(5관점 순환검증) → 고도화(판정 기록) → 시뮬레이션(실행 결과 + verdict)

검증 기준:
1. 플랜 파일 존재 (없으면 BLOCK)
2. 5관점 순환검증 — 각 섹션 헤더(### N. 관점명) + 최소 내용(30자) + 판정: 키워드
3. 시뮬레이션 결과 — 섹션 존재 + TC 테이블/결과 + ALL PASS verdict (FAIL 시 BLOCK)

출력 스키마: Claude Code SyncHookJSONOutputSchema (coreSchemas.ts:907).
pass-through는 exit 0 + 빈 stdout, 차단은 hookSpecificOutput.permissionDecision:"deny".
"""
import json
import os
import re
import sys
import glob

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from hook_output import deny_pretool as deny

PLANS_DIR = os.path.expanduser("~/.claude/plans")

# ── 5관점 순환검증: 섹션 헤더 패턴 ──
VERIFICATION_SECTIONS = [
    ("SSOT", re.compile(r"^###\s+\d+\.\s+SSOT\b", re.MULTILINE)),
    ("SRP", re.compile(r"^###\s+\d+\.\s+SRP\b", re.MULTILINE)),
    ("엣지케이스", re.compile(r"^###\s+\d+\.\s+엣지케이스\b", re.MULTILINE)),
    ("아키텍트", re.compile(r"^###\s+\d+\.\s+아키텍트\b", re.MULTILINE)),
    ("Iron Law", re.compile(r"^###\s+\d+\.\s+Iron Law\b", re.MULTILINE)),
]

# ── 판정 키워드 (각 순환검증 섹션에 필수) ──
VERDICT_KEYWORD = re.compile(r"\*\*판정:\*\*\s*(조건부\s+)?PASS|판정:\s*(조건부\s+)?PASS")

# ── 시뮬레이션 결과 ──
SIMULATION_HEADER = re.compile(r"^##\s+.*시뮬레이션 결과", re.MULTILINE)
PASS_VERDICT = re.compile(r"\bALL PASS\b")
FAIL_VERDICT = re.compile(r"\bFAIL\b")
# TC 테이블 또는 실행 결과 패턴
TC_PATTERN = re.compile(r"\bTC\d+|테스트케이스|\| TC \||\| 시나리오 \|")

MIN_SECTION_LENGTH = 30


def _extract_section_content(content, header_match):
    """섹션 헤더 이후 ~ 다음 동급 이상 헤더 전까지의 내용을 추출."""
    start = header_match.end()
    next_header = re.search(r"^#{2,3}\s+", content[start:], re.MULTILINE)
    if next_header:
        return content[start:start + next_header.start()].strip()
    return content[start:].strip()


def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        return

    plans = glob.glob(os.path.join(PLANS_DIR, "*.md"))
    if not plans:
        deny(
            "[PLAN-QUALITY-GATE] 플랜 파일이 없습니다.\n"
            "~/.claude/plans/에 플랜 파일을 작성한 후 다시 시도하세요."
        )
        return

    latest = max(plans, key=os.path.getmtime)
    with open(latest) as f:
        content = f.read()

    issues = []

    # ── Phase 1: 검증 — 5관점 순환검증 ──
    for name, pattern in VERIFICATION_SECTIONS:
        match = pattern.search(content)
        if not match:
            issues.append(f"[검증] 순환검증 섹션 누락: {name} (### N. {name} 형식 필요)")
            continue
        section_content = _extract_section_content(content, match)
        if len(section_content) < MIN_SECTION_LENGTH:
            issues.append(
                f"[검증] 순환검증 내용 부족: {name} ({len(section_content)}자 < {MIN_SECTION_LENGTH}자)"
            )
            continue
        # Phase 2: 고도화 — 각 섹션에 판정 기록 필수
        if not VERDICT_KEYWORD.search(section_content):
            issues.append(
                f"[고도화] {name} 섹션에 판정 누락 (**판정:** PASS 또는 **판정:** 조건부 PASS 필요)"
            )

    # ── Phase 3: 시뮬레이션 — 실행 결과 + verdict ──
    sim_match = SIMULATION_HEADER.search(content)
    if not sim_match:
        issues.append("[시뮬레이션] 시뮬레이션 결과 섹션 누락 (## ... 시뮬레이션 결과 형식 필요)")
    else:
        sim_content = _extract_section_content(content, sim_match)
        # TC 테이블 또는 실행 결과 존재 확인
        if not TC_PATTERN.search(sim_content):
            issues.append(
                "[시뮬레이션] 테스트케이스(TC) 결과 누락 — 실제 실행 결과를 기록하세요"
            )
        if FAIL_VERDICT.search(sim_content):
            issues.append(
                "[시뮬레이션] FAIL 존재 — blocking issue를 수정한 후 다시 시도하세요"
            )
        elif not PASS_VERDICT.search(sim_content):
            issues.append(
                "[시뮬레이션] verdict 누락 (ALL PASS 필요)"
            )

    if issues:
        phase_summary = []
        if any("[검증]" in i for i in issues):
            phase_summary.append("검증 미완료")
        if any("[고도화]" in i for i in issues):
            phase_summary.append("고도화 미완료")
        if any("[시뮬레이션]" in i for i in issues):
            phase_summary.append("시뮬레이션 미완료")

        deny(
            f"[PLAN-QUALITY-GATE] 플랜 수립 절차 미준수: {' + '.join(phase_summary)}\n"
            f"필수 절차: 검증(5관점) → 고도화(판정 기록) → 시뮬레이션(TC 실행 + ALL PASS)\n"
            + "\n".join(f"  - {i}" for i in issues)
            + f"\n\n플랜 파일({os.path.basename(latest)})을 수정한 후 다시 시도하세요."
        )


if __name__ == "__main__":
    main()
