#!/usr/bin/env python3
"""tests/test_mentor_signal.py — jarvis_mentor_signal.py 단위 테스트."""

import json
import os
import sys
import tempfile

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_mentor_signal as ms


def test_emit_signal():
    """Signal emit → signals.jsonl에 1행 append."""
    with tempfile.TemporaryDirectory() as td:
        ms.SIGNALS_DIR = type(ms.SIGNALS_DIR)(td)
        ms.SIGNALS_FILE = ms.SIGNALS_DIR / "signals.jsonl"

        event = {
            "type": "user_instruction_submitted",
            "data": {
                "scores": {"decomp": 0.8, "verify": 0.6, "orch": 0.7, "fail": 0.5, "ctx": 0.9, "meta": 0.4},
                "evidence_count": 5,
                "confidence": 0.7,
                "round_id": "round-1",
            },
        }
        ms.cmd_emit(json.dumps(event), round_id="round-1")

        signals = ms._read_signals()
        assert len(signals) == 1, f"Expected 1 signal, got {len(signals)}"
        s = signals[0]
        assert s["scores"]["decomp"] == 0.8
        assert s["round_id"] == "round-1"
        assert s["confidence"] == 0.7
        assert s["calibration_note"] == "ok"
    print("  test_emit_signal: PASS")


def test_insufficient_evidence():
    """evidence_count < 3 → calibration_note = insufficient_evidence."""
    with tempfile.TemporaryDirectory() as td:
        ms.SIGNALS_DIR = type(ms.SIGNALS_DIR)(td)
        ms.SIGNALS_FILE = ms.SIGNALS_DIR / "signals.jsonl"

        # Low evidence
        event = {"type": "test", "data": {"evidence_count": 2, "confidence": 0.8}}
        ms.cmd_emit(json.dumps(event))
        s = ms._read_signals()[0]
        assert s["calibration_note"] == "insufficient_evidence", f"Got: {s['calibration_note']}"

        # Low confidence
        ms.SIGNALS_FILE.unlink()
        event2 = {"type": "test", "data": {"evidence_count": 5, "confidence": 0.3}}
        ms.cmd_emit(json.dumps(event2))
        s2 = ms._read_signals()[0]
        assert s2["calibration_note"] == "insufficient_evidence"
    print("  test_insufficient_evidence: PASS")


def test_fit_score_and_level():
    """Fit score 계산 + harness level 반올림."""
    scores = {"decomp": 0.8, "verify": 0.6, "orch": 0.7, "fail": 0.5, "ctx": 0.9, "meta": 0.4}
    fit = ms.compute_fit_score(scores)
    assert 0.0 <= fit <= 1.0, f"Fit score out of range: {fit}"

    level = ms.compute_harness_level(fit)
    # Level should be 0.5-multiple
    assert level == round(level * 2) / 2, f"Level not 0.5-aligned: {level}"
    assert 1.0 <= level <= 7.0, f"Level out of range: {level}"
    print("  test_fit_score_and_level: PASS")


def test_detect_antipatterns():
    """Low axis scores → antipattern detection."""
    scores = {"decomp": 0.8, "verify": 0.3, "orch": 0.7, "fail": 0.2, "ctx": 0.9, "meta": 0.4}
    patterns = ms.detect_antipatterns(scores)
    assert "verification_skip" in patterns
    assert "fix_me_syndrome" in patterns
    assert "context_skip" not in patterns  # ctx is high
    print("  test_detect_antipatterns: PASS")


def test_prune():
    """Prune removes old signals."""
    with tempfile.TemporaryDirectory() as td:
        ms.SIGNALS_DIR = type(ms.SIGNALS_DIR)(td)
        ms.SIGNALS_FILE = ms.SIGNALS_DIR / "signals.jsonl"

        # Write old signal
        old = {"ts": "2025-01-01T00:00:00Z", "signal_id": "sig-old", "scores": {},
               "fit_score": 0, "harness_level": 1.0, "antipatterns": [],
               "coaching_hint": "", "confidence": 0.5, "evidence_count": 1,
               "calibration_note": "ok", "round_id": "r-1", "window_size": 5}
        # Write recent signal
        recent = dict(old, ts="2026-04-10T00:00:00Z", signal_id="sig-recent")

        with open(ms.SIGNALS_FILE, "w") as f:
            f.write(json.dumps(old) + "\n")
            f.write(json.dumps(recent) + "\n")

        ms.cmd_prune(keep_days=90)
        remaining = ms._read_signals()
        assert len(remaining) == 1, f"Expected 1, got {len(remaining)}"
        assert remaining[0]["signal_id"] == "sig-recent"
    print("  test_prune: PASS")


def main():
    test_emit_signal()
    test_insufficient_evidence()
    test_fit_score_and_level()
    test_detect_antipatterns()
    test_prune()
    print("\nAll mentor signal tests passed.")


if __name__ == "__main__":
    main()
