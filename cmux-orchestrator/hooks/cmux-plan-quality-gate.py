#!/usr/bin/env python3
"""cmux-plan-quality-gate.py — PreToolUse:ExitPlanMode Hook (L0 BLOCK)

플랜 품질 게이트 자동 강제: 5관점 순환검증 + 코드 시뮬레이션 완료 전 ExitPlanMode 차단.

검증 기준:
1. 플랜 파일이 존재해야 함 (없으면 BLOCK)
2. 5관점 순환검증 섹션 헤더(### N. 관점명) + 최소 내용(30자) 필수
3. 시뮬레이션 결과 섹션에 verdict(PASS/FAIL) 포함 필수
"""
import json
import os
import re
import sys
import glob

PLANS_DIR = os.path.expanduser("~/.claude/plans")

# 5관점 순환검증: 섹션 헤더 패턴 + 최소 내용 길이
VERIFICATION_SECTIONS = [
    ("SSOT", re.compile(r"^###\s+\d+\.\s+SSOT\b", re.MULTILINE)),
    ("SRP", re.compile(r"^###\s+\d+\.\s+SRP\b", re.MULTILINE)),
    ("엣지케이스", re.compile(r"^###\s+\d+\.\s+엣지케이스\b", re.MULTILINE)),
    ("아키텍트", re.compile(r"^###\s+\d+\.\s+아키텍트\b", re.MULTILINE)),
    ("Iron Law", re.compile(r"^###\s+\d+\.\s+Iron Law\b", re.MULTILINE)),
]

# 시뮬레이션 결과 섹션 헤더
SIMULATION_HEADER = re.compile(r"^##\s+.*시뮬레이션 결과", re.MULTILINE)
# verdict 패턴: ALL PASS 또는 PASS만 통과. FAIL은 block.
PASS_VERDICT = re.compile(r"\bALL PASS\b")
FAIL_VERDICT = re.compile(r"\bFAIL\b")

MIN_SECTION_LENGTH = 30  # 섹션 헤더 ~ 다음 헤더 사이 최소 문자 수


def _extract_section_content(content, header_match):
    """섹션 헤더 이후 ~ 다음 동급 이상 헤더 전까지의 내용을 추출."""
    start = header_match.end()
    # 다음 ### 또는 ## 헤더 찾기
    next_header = re.search(r"^#{2,3}\s+", content[start:], re.MULTILINE)
    if next_header:
        return content[start:start + next_header.start()].strip()
    return content[start:].strip()


def main():
    if not os.path.exists("/tmp/cmux-orch-enabled"):
        print(json.dumps({"decision": "approve"}))
        return

    # 가장 최근 플랜 파일 찾기
    plans = glob.glob(os.path.join(PLANS_DIR, "*.md"))
    if not plans:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "[PLAN-QUALITY-GATE] 플랜 파일이 없습니다.\n"
                "~/.claude/plans/에 플랜 파일을 작성한 후 다시 시도하세요."
            )
        }))
        return

    latest = max(plans, key=os.path.getmtime)
    with open(latest) as f:
        content = f.read()

    issues = []

    # 1. 5관점 순환검증 섹션 검사
    for name, pattern in VERIFICATION_SECTIONS:
        match = pattern.search(content)
        if not match:
            issues.append(f"순환검증 섹션 누락: {name} (### N. {name} 형식 필요)")
            continue
        section_content = _extract_section_content(content, match)
        if len(section_content) < MIN_SECTION_LENGTH:
            issues.append(
                f"순환검증 내용 부족: {name} ({len(section_content)}자 < {MIN_SECTION_LENGTH}자)"
            )

    # 2. 시뮬레이션 결과 섹션 검사
    sim_match = SIMULATION_HEADER.search(content)
    if not sim_match:
        issues.append("시뮬레이션 결과 섹션 누락 (## ... 시뮬레이션 결과 형식 필요)")
    else:
        sim_content = _extract_section_content(content, sim_match)
        if FAIL_VERDICT.search(sim_content):
            issues.append(
                "시뮬레이션 결과에 FAIL 존재 — blocking issue를 수정한 후 다시 시도하세요"
            )
        elif not PASS_VERDICT.search(sim_content):
            issues.append(
                "시뮬레이션 결과에 verdict 누락 (ALL PASS 필요)"
            )

    if issues:
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"[PLAN-QUALITY-GATE] 플랜 품질 게이트 미통과.\n"
                + "\n".join(f"  - {i}" for i in issues)
                + f"\n플랜 파일({os.path.basename(latest)})을 수정한 후 다시 시도하세요."
            )
        }))
    else:
        print(json.dumps({"decision": "approve"}))


if __name__ == "__main__":
    main()
