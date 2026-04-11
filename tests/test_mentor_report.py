#!/usr/bin/env python3
"""tests/test_mentor_report.py — jarvis_mentor_report.py 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_mentor_report as mr


def _make_signals(n=5):
    return [
        {"ts": f"2026-04-{i+1:02d}T12:00:00Z",
         "scores": {"decomp": 0.7+i*0.02, "verify": 0.5, "orch": 0.8, "fail": 0.6, "ctx": 0.75, "meta": 0.45},
         "fit_score": 0.65+i*0.01, "harness_level": 3.5, "confidence": 0.7, "evidence_count": 5,
         "antipatterns": ["verification_skip"] if i % 2 == 0 else [], "calibration_note": "ok"}
        for i in range(n)
    ]


def test_generate_report():
    """fixture signals → report 생성 + 6축 표 포함."""
    signals = _make_signals(5)
    report_text, avg, fit, level, ap = mr.generate_report(signals)
    assert "6축 분석" in report_text
    assert "DECOMP" in report_text
    assert "VERIFY" in report_text
    assert "종합" in report_text
    assert "Harness Level" in report_text
    print("  test_generate_report: PASS")


def test_insufficient_signals():
    """signals < 3 → 보류."""
    with tempfile.TemporaryDirectory() as td:
        mr.SIGNALS_FILE = type(mr.SIGNALS_FILE)(td) / "signals.jsonl"
        mr.REPORTS_DIR = type(mr.REPORTS_DIR)(td) / "reports"
        mr.TIMELINE_FILE = type(mr.TIMELINE_FILE)(td) / "TIMELINE.md"
        mr.MENTOR_DIR = type(mr.MENTOR_DIR)(td)

        # Write only 2 signals
        mr.SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(mr.SIGNALS_FILE, "w") as f:
            for s in _make_signals(2):
                f.write(json.dumps(s) + "\n")

        rc = mr.cmd_generate()
        assert rc == 0
        assert not mr.REPORTS_DIR.exists() or len(list(mr.REPORTS_DIR.glob("*.md"))) == 0
    print("  test_insufficient_signals: PASS")


def test_timeline_append():
    """report 생성 → TIMELINE.md에 1행 추가."""
    with tempfile.TemporaryDirectory() as td:
        mr.MENTOR_DIR = type(mr.MENTOR_DIR)(td)
        mr.SIGNALS_FILE = mr.MENTOR_DIR / "signals.jsonl"
        mr.REPORTS_DIR = mr.MENTOR_DIR / "reports"
        mr.TIMELINE_FILE = mr.MENTOR_DIR / "TIMELINE.md"

        mr.MENTOR_DIR.mkdir(parents=True, exist_ok=True)
        with open(mr.SIGNALS_FILE, "w") as f:
            for s in _make_signals(5):
                f.write(json.dumps(s) + "\n")

        mr.cmd_generate()

        assert mr.TIMELINE_FILE.exists(), "TIMELINE.md not created"
        content = mr.TIMELINE_FILE.read_text()
        lines = [l for l in content.strip().split("\n") if l.startswith("|") and "날짜" not in l and "---" not in l]
        assert len(lines) >= 1, f"Expected >= 1 data row, got {len(lines)}"
    print("  test_timeline_append: PASS")


def test_report_not_evaluation():
    """disclaimer 문구 포함 확인."""
    signals = _make_signals(5)
    report_text, *_ = mr.generate_report(signals)
    assert "사용자를 평가하는 문서가 아니라" in report_text
    print("  test_report_not_evaluation: PASS")


def test_trend_comparison():
    """signals >= 4 → 추세 ↑/↓/→ 표시."""
    signals = _make_signals(6)
    # Make later signals have higher decomp
    for i, s in enumerate(signals):
        s["scores"]["decomp"] = 0.5 + i * 0.08
    report_text, *_ = mr.generate_report(signals)
    assert "↑" in report_text or "↓" in report_text or "→" in report_text
    print("  test_trend_comparison: PASS")


def test_gate_conditions():
    """Gate 조건 표 포함."""
    signals = _make_signals(5)
    report_text, *_ = mr.generate_report(signals)
    assert "Gate" in report_text
    assert "통과" in report_text or "미충족" in report_text
    print("  test_gate_conditions: PASS")


def main():
    test_generate_report()
    test_insufficient_signals()
    test_timeline_append()
    test_report_not_evaluation()
    test_trend_comparison()
    test_gate_conditions()
    print("\nAll mentor report tests passed.")


if __name__ == "__main__":
    main()
