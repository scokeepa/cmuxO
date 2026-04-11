#!/usr/bin/env python3
"""jarvis_palace_memory.py — L0/L1 context 생성 + 저장소 현황.

SSOT: docs/jarvis/architecture/palace-memory-ssot.md
Token budget: L0+L1 합산 600-900 token (mentor-lane.md)

Usage:
    python3 jarvis_palace_memory.py generate-context
    python3 jarvis_palace_memory.py status
"""

import argparse
import json
import os
import sys
from pathlib import Path

MENTOR_DIR = Path.home() / ".claude" / "cmux-jarvis" / "mentor"
CONTEXT_DIR = MENTOR_DIR / "context"
SIGNALS_FILE = MENTOR_DIR / "signals.jsonl"
L0_FILE = CONTEXT_DIR / "L0.md"
L1_FILE = CONTEXT_DIR / "L1.md"

MAX_L1_CHARS = 3200  # ~800 tokens (mempalace L1 기준)
MAX_TOTAL_TOKENS = 900  # L0+L1 합산 제한
MAX_SIGNALS_FOR_L1 = 15  # L1 생성에 사용할 최대 signal 수

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")

AXIS_NAMES = {
    "decomp": "DECOMP", "verify": "VERIFY", "orch": "ORCH",
    "fail": "FAIL", "ctx": "CTX", "meta": "META",
}

L0_DEFAULT = """## L0 — IDENTITY
cmux 오케스트레이션 시스템의 CEO 사용자.
Boss(Main), Watcher, JARVIS로 구성된 컨트롤 타워를 운영.
부서별 팀장-팀원 구조로 멀티 AI 작업을 조율."""


def _ensure_dirs():
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)


def _estimate_tokens(text):
    """Rough token estimate: chars // 4."""
    return len(text) // 4


def _read_signals(limit=None):
    """Read signals from signals.jsonl, optionally last N."""
    if not SIGNALS_FILE.exists():
        return []
    signals = []
    with open(SIGNALS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    signals.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if limit:
        signals = signals[-limit:]
    return signals


def generate_l0():
    """Generate L0 identity context."""
    _ensure_dirs()
    if L0_FILE.exists():
        return L0_FILE.read_text(encoding="utf-8")
    # Create default
    L0_FILE.write_text(L0_DEFAULT, encoding="utf-8")
    return L0_DEFAULT


def generate_l1(signals=None):
    """Generate L1 essential story from recent signals."""
    if signals is None:
        signals = _read_signals(limit=MAX_SIGNALS_FOR_L1)

    if not signals:
        return "## L1 — ESSENTIAL STORY\n아직 충분한 관찰이 없습니다."

    latest = signals[-1]
    scores = latest.get("scores", {})

    # Sort axes by score
    sorted_axes = sorted(
        [(axis, scores.get(axis, 0)) for axis in AXES],
        key=lambda x: x[1], reverse=True,
    )
    strong = [f"{AXIS_NAMES[a]} ({v:.2f})" for a, v in sorted_axes[:2]]
    weak = [f"{AXIS_NAMES[a]} ({v:.2f})" for a, v in sorted_axes[-2:]]

    lines = [
        "## L1 — ESSENTIAL STORY",
        "최근 하네스 상태:",
        f"- Harness Level: L{latest.get('harness_level', '?')}",
        f"- 강한 축: {', '.join(strong)}",
        f"- 약한 축: {', '.join(weak)}",
    ]

    # Antipatterns from recent signals
    recent_patterns = []
    for s in signals[-5:]:
        recent_patterns.extend(s.get("antipatterns", []))
    if recent_patterns:
        unique_patterns = list(dict.fromkeys(recent_patterns))[:3]
        lines.append(f"- 최근 안티패턴: {', '.join(unique_patterns)}")

    # Latest coaching hint
    hint = latest.get("coaching_hint", "")
    if hint:
        lines.append(f'- 코칭 힌트: "{hint}"')

    # Calibration warning
    if latest.get("calibration_note") == "insufficient_evidence":
        lines.append("- 주의: 표본 부족으로 신뢰도가 낮습니다.")

    # Trend (if enough signals)
    if len(signals) >= 3:
        first_fit = signals[0].get("fit_score", 0)
        last_fit = signals[-1].get("fit_score", 0)
        diff = last_fit - first_fit
        if abs(diff) > 0.1:
            direction = "상승" if diff > 0 else "하락"
            lines.append(f"- 추세: fit score {direction} ({first_fit:.1f} → {last_fit:.1f})")

    text = "\n".join(lines)
    return text[:MAX_L1_CHARS]


def cmd_generate_context():
    """Generate L0 + L1 and write to files."""
    _ensure_dirs()

    l0_text = generate_l0()
    l1_text = generate_l1()

    L1_FILE.write_text(l1_text, encoding="utf-8")

    l0_tokens = _estimate_tokens(l0_text)
    l1_tokens = _estimate_tokens(l1_text)
    total = l0_tokens + l1_tokens

    # Truncate L1 if over budget
    if total > MAX_TOTAL_TOKENS:
        budget = MAX_TOTAL_TOKENS - l0_tokens
        max_chars = budget * 4
        l1_text = l1_text[:max_chars]
        L1_FILE.write_text(l1_text, encoding="utf-8")
        l1_tokens = _estimate_tokens(l1_text)
        total = l0_tokens + l1_tokens

    print(f"L0: {L0_FILE} ({l0_tokens} tokens)")
    print(f"L1: {L1_FILE} ({l1_tokens} tokens)")
    print(f"Total: {total}/{MAX_TOTAL_TOKENS} tokens")
    return 0


def cmd_status():
    """Show mentor storage status."""
    signals = _read_signals()

    status = {
        "signals_file": str(SIGNALS_FILE),
        "signals_count": len(signals),
        "signals_file_exists": SIGNALS_FILE.exists(),
        "l0_exists": L0_FILE.exists(),
        "l1_exists": L1_FILE.exists(),
        "palace_dir_exists": (MENTOR_DIR / "palace").exists(),
        "drawers_dir_exists": (MENTOR_DIR / "palace" / "drawers").exists(),
    }

    if signals:
        status["latest_signal_ts"] = signals[-1].get("ts", "unknown")
        status["latest_harness_level"] = signals[-1].get("harness_level")
        status["latest_calibration"] = signals[-1].get("calibration_note")

    if SIGNALS_FILE.exists():
        status["signals_file_size_bytes"] = SIGNALS_FILE.stat().st_size

    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Palace Memory Context Generator")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("generate-context", help="Generate L0 + L1 context files")
    sub.add_parser("status", help="Show mentor storage status")

    args = parser.parse_args()

    if args.cmd == "generate-context":
        return cmd_generate_context()
    elif args.cmd == "status":
        return cmd_status()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
