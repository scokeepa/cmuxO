#!/usr/bin/env python3
"""Phase 2.4 — anti-rationalization pattern detector.

Pure detection + evidence-check module. Callers (hooks, slash commands,
JARVIS reports) use :func:`classify` to decide whether a payload should
trigger an **ask** (not deny) back to the user.

Design decision — *why separate from cmux-leceipts-gate.py*:
    The existing commit gate is L0 BLOCK (hard deny on missing leceipts).
    Broadening that hook to match rationalization over every Bash call
    would increase latency and blast radius. This module stays hook-agnostic
    so it can be wired incrementally (slash command first, then narrow hook
    integration). See plan §3.3 and §0.6 (remaining-risk absorption).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

_SCRIPT_DIR = Path(__file__).parent.resolve()
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    import ledger as _ledger
except ImportError:
    _ledger = None


# Pattern groups. Each (name, compiled_re, category) — category drives which
# counter table to cite.
_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Table A — 보고 합리화
    ("completed_no_evidence",
     re.compile(r"(?:^|[^a-zA-Z0-9_])(완료했습니다|완료[\s]*$|completed\b|done\b)",
                re.IGNORECASE),
     "A"),
    ("env_issue_bare",
     re.compile(r"(환경\s*문제|environment\s*issue)", re.IGNORECASE),
     "A"),
    ("probably_fine",
     re.compile(r"(아마\s*(동작|작동|될\s*것)|probably\s+(fine|work|ok))",
                re.IGNORECASE),
     "A"),
    ("peer_fallback_rationalization",
     re.compile(r"(peer.*(실패|죽|dead).*fallback|fallback.*있으니.*괜찮)",
                re.IGNORECASE),
     "A"),
    # Table B — 작업 회피
    ("out_of_scope",
     re.compile(r"(범위\s*밖|out\s*of\s*scope)", re.IGNORECASE),
     "B"),
    ("refactor_separate_pr",
     re.compile(r"(리팩터링은\s*별도|refactor\s*(is\s*)?separate)",
                re.IGNORECASE),
     "B"),
    ("edge_case_unlikely",
     re.compile(r"(edge\s*case.*(unlikely|무시)|엣지\s*케이스.*(무시|드물))",
                re.IGNORECASE),
     "B"),
]

# Evidence markers that flip a detection from ASK → PASS.
_EVIDENCE_MARKERS = (
    re.compile(r"VERIFY_PASS"),
    re.compile(r"test\s*\d+\s*/\s*\d+", re.IGNORECASE),
    re.compile(r"pass\s*\d+\s*/\s*\d+\s*fail\s*\d+", re.IGNORECASE),
    re.compile(r"ledger\s+query", re.IGNORECASE),
    re.compile(r"override\s*reason\s*[:=]", re.IGNORECASE),
)

# Specific-cause markers that neutralize the "env issue" excuse.
_ENV_SPECIFIC_MARKERS = (
    re.compile(r"(binary|바이너리|PATH)\s*[:=]?\s*\S"),
    re.compile(r"(env\s*var|환경\s*변수|\$[A-Z_]+)"),
    re.compile(r"(permission|권한|chmod|sudo)"),
    re.compile(r"(install|설치)\s+중"),
)

# Quoted code / comment should not trigger.
_QUOTED_RE = re.compile(r"[\"']([^\"']{0,80})[\"']")


def _is_within_quotes(text: str, span: tuple[int, int]) -> bool:
    for m in _QUOTED_RE.finditer(text):
        if m.start() <= span[0] and span[1] <= m.end():
            return True
    return False


def _has_override(text: str) -> bool:
    return bool(_EVIDENCE_MARKERS[-1].search(text))


def _has_any(patterns: Iterable[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def _recent_verify_evidence(worker: str | None, since_sec: int = 600) -> bool:
    """Return True if ledger has a VERIFY_PASS for *worker* within window."""
    if _ledger is None or not worker:
        return False
    import time as _time
    try:
        rows = _ledger.query(worker=worker, event_type="VERIFY_PASS",
                             since_ts=int(_time.time()) - since_sec)
    except Exception:  # noqa: BLE001
        return False
    return len(rows) > 0


def classify(text: str, worker: str | None = None) -> dict:
    """Return a decision dict for *text*.

    Shape:
        {"decision": "pass" | "ask",
         "matches": [{"name","category","snippet"}],
         "evidence": "text" | "ledger" | None,
         "reason": str}
    """
    if not text:
        return {"decision": "pass", "matches": [], "evidence": None,
                "reason": "empty input"}

    matches = []
    for name, pat, cat in _PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        if _is_within_quotes(text, m.span()):
            continue
        matches.append({"name": name, "category": cat,
                        "snippet": text[max(0, m.start() - 15):m.end() + 15]})

    if not matches:
        return {"decision": "pass", "matches": [], "evidence": None,
                "reason": "no pattern matched"}

    # Env issue with a specific cause → PASS.
    if any(m["name"] == "env_issue_bare" for m in matches) and _has_any(
        _ENV_SPECIFIC_MARKERS, text
    ):
        matches = [m for m in matches if m["name"] != "env_issue_bare"]
        if not matches:
            return {"decision": "pass", "matches": [], "evidence": "text",
                    "reason": "environment issue cited with specific cause"}

    # Override reason keyword → PASS (explicit authorial note).
    if _has_override(text):
        return {"decision": "pass", "matches": matches, "evidence": "text",
                "reason": "override reason present"}

    # Evidence markers in-text → PASS for completion/verify claims.
    completion_matched = any(m["name"] == "completed_no_evidence"
                             for m in matches)
    if completion_matched and _has_any(_EVIDENCE_MARKERS[:-1], text):
        return {"decision": "pass", "matches": matches, "evidence": "text",
                "reason": "completion claim backed by in-text evidence"}

    # Ledger evidence → PASS only for completion claims.
    if completion_matched and _recent_verify_evidence(worker):
        return {"decision": "pass", "matches": matches, "evidence": "ledger",
                "reason": f"VERIFY_PASS found for worker={worker}"}

    return {
        "decision": "ask",
        "matches": matches,
        "evidence": None,
        "reason": "rationalization pattern detected — cite anti-rationalization.md",
    }


def render_ask_message(result: dict) -> str:
    """Human-readable ASK text that hooks can surface."""
    if result["decision"] != "ask":
        return ""
    names = ", ".join(m["name"] for m in result["matches"])
    return (
        f"[anti-rationalization] 감지된 패턴: {names}\n"
        "→ `cmux-orchestrator/references/anti-rationalization.md` 참조.\n"
        "계속 진행하려면 override reason 을 명시하거나 evidence"
        " (test N/N, VERIFY_PASS, ledger query 결과)를 포함하세요."
    )


if __name__ == "__main__":
    import json
    if len(sys.argv) < 2:
        print("usage: anti_rationalization.py '<text>' [worker]",
              file=sys.stderr)
        sys.exit(2)
    text = sys.argv[1]
    worker = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(classify(text, worker), ensure_ascii=False, indent=2))
