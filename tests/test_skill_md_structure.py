"""Phase 2.1 — cmux-watcher SKILL.md progressive disclosure guards.

두 가지를 강제한다:

1. **size gate**: `cmux-watcher/SKILL.md` 는 200 라인 이하. 상세는
   `references/` 로 이관해야 한다 (진정한 L1 유지).
2. **link gate**: L1 의 GATE 표가 참조하는 `references/gate-w-*.md`
   파일은 실제로 존재해야 한다.

baseline (Phase 2.1 전): 838 줄. 1 번 가드가 회귀를 즉시 잡는다.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = REPO_ROOT / "cmux-watcher" / "SKILL.md"
REFS_DIR = REPO_ROOT / "cmux-watcher" / "references"

MAX_LINES = 200


def test_skill_md_size_gate():
    """L1 SKILL.md 는 200 라인 이하여야 한다 (progressive disclosure)."""
    assert SKILL_MD.exists(), f"{SKILL_MD} not found"
    lines = SKILL_MD.read_text().splitlines()
    assert len(lines) <= MAX_LINES, (
        f"SKILL.md has {len(lines)} lines (> {MAX_LINES}). "
        f"Move detail to cmux-watcher/references/."
    )


def test_gate_table_links_resolve():
    """L1 의 GATE 표 링크가 실제 파일로 해석되어야 한다."""
    assert SKILL_MD.exists(), f"{SKILL_MD} not found"
    text = SKILL_MD.read_text()

    link_re = re.compile(r"\[([^\]]*gate-w-\d+[^\]]*)\]\(references/(gate-w-\d+\.md)\)")
    matches = link_re.findall(text)
    assert matches, "GATE 표에 references/gate-w-*.md 링크가 하나도 없다"

    missing: list[str] = []
    for _label, target in matches:
        if not (REFS_DIR / target).exists():
            missing.append(target)
    assert not missing, f"missing L2 files: {missing}"


def test_all_gates_w1_through_w10_linked():
    """GATE 표에 W-1 ~ W-10 전부 포함되어야 한다."""
    text = SKILL_MD.read_text()
    for n in range(1, 11):
        needle = f"gate-w-{n}.md"
        assert needle in text, f"{needle} 링크가 SKILL.md 에 없다"


def test_no_detailed_sections_leaked_to_l1():
    """상세 예시/스텝 설명이 L1 에 남아있지 않아야 한다.

    Layer/GATE 개요 언급은 허용하되, 코드 스텝(`Step 1:`)이나 장문의
    판정 테이블/예시 블록은 references/ 로 이관해야 한다.
    """
    text = SKILL_MD.read_text().lower()
    forbidden = [
        "step 1:",
        "step 2:",
        "# step 4",
        "ane_tool ocr /tmp/cmux-vdiff",
    ]
    leaked = [p for p in forbidden if p in text]
    assert not leaked, f"상세 섹션이 L1 에 잔류: {leaked} — references/ 로 옮겨라"
