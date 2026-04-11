#!/usr/bin/env python3
"""tests/test_failure_classifier.py — jarvis_failure_classifier.py 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_failure_classifier as fc


def _write_signals(td, signals):
    fc.SIGNALS_FILE = type(fc.SIGNALS_FILE)(td) / "signals.jsonl"
    fc.SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(fc.SIGNALS_FILE, "w") as f:
        for s in signals:
            f.write(json.dumps(s) + "\n")


def _write_telemetry(td, events):
    fc.TELEMETRY_DIR = type(fc.TELEMETRY_DIR)(td) / "telemetry"
    fc.TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    with open(fc.TELEMETRY_DIR / "events-2026-04-11.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def _make_signals(antipattern_count=0):
    signals = []
    for i in range(5):
        ap = ["verification_skip"] if i < antipattern_count else []
        signals.append({
            "ts": f"2026-04-{i+1:02d}T12:00:00Z",
            "scores": {"decomp": 0.7, "verify": 0.5, "orch": 0.8, "fail": 0.6, "ctx": 0.7, "meta": 0.5},
            "antipatterns": ap, "confidence": 0.7,
        })
    return signals


def _make_telemetry(applies=5, rollbacks=0):
    events = []
    for i in range(applies):
        events.append({"ts": f"2026-04-{i+1:02d}T12:00:00Z", "type": "apply", "data": {}})
    for i in range(rollbacks):
        events.append({"ts": f"2026-04-{i+1:02d}T13:00:00Z", "type": "rollback", "data": {}})
    return events


def test_system_failure():
    """evolution rollback 많음 + mentor 정상 → system."""
    with tempfile.TemporaryDirectory() as td:
        _write_signals(td, _make_signals(antipattern_count=0))
        _write_telemetry(td, _make_telemetry(applies=2, rollbacks=4))

        result = fc.classify(window=5)
        assert result["classification"] == "system", f"Got: {result['classification']}"
        assert result["iron_law_reminder"], "Iron Law reminder expected"
    print("  test_system_failure: PASS")


def test_user_instruction_failure():
    """mentor antipattern 반복 + evolution 정상 → user_instruction."""
    with tempfile.TemporaryDirectory() as td:
        _write_signals(td, _make_signals(antipattern_count=4))
        _write_telemetry(td, _make_telemetry(applies=5, rollbacks=0))

        result = fc.classify(window=5)
        assert result["classification"] == "user_instruction", f"Got: {result['classification']}"
        assert not result["iron_law_reminder"], "No Iron Law for user instruction"
    print("  test_user_instruction_failure: PASS")


def test_mixed_failure():
    """둘 다 이상 → mixed."""
    with tempfile.TemporaryDirectory() as td:
        _write_signals(td, _make_signals(antipattern_count=4))
        _write_telemetry(td, _make_telemetry(applies=1, rollbacks=5))

        result = fc.classify(window=5)
        assert result["classification"] == "mixed", f"Got: {result['classification']}"
        assert "Iron Law" in result["iron_law_reminder"]
    print("  test_mixed_failure: PASS")


def test_no_failure():
    """둘 다 정상 → none."""
    with tempfile.TemporaryDirectory() as td:
        _write_signals(td, _make_signals(antipattern_count=1))
        _write_telemetry(td, _make_telemetry(applies=8, rollbacks=1))

        result = fc.classify(window=5)
        assert result["classification"] == "none", f"Got: {result['classification']}"
    print("  test_no_failure: PASS")


def test_iron_law_reminder():
    """system 분류 시 Iron Law 리마인더 포함."""
    with tempfile.TemporaryDirectory() as td:
        _write_signals(td, _make_signals(antipattern_count=0))
        _write_telemetry(td, _make_telemetry(applies=1, rollbacks=5))

        result = fc.classify(window=5)
        assert "Iron Law #1" in result["iron_law_reminder"]
        assert "승인" in result["iron_law_reminder"]
    print("  test_iron_law_reminder: PASS")


def test_empty_data():
    """signals와 telemetry 둘 다 없을 때 → none."""
    with tempfile.TemporaryDirectory() as td:
        fc.SIGNALS_FILE = type(fc.SIGNALS_FILE)(td) / "nonexistent" / "signals.jsonl"
        fc.TELEMETRY_DIR = type(fc.TELEMETRY_DIR)(td) / "nonexistent" / "telemetry"

        result = fc.classify(window=5)
        assert result["classification"] == "none", f"Got: {result['classification']}"
    print("  test_empty_data: PASS")


def test_evidence_fields():
    """결과에 evidence 필드가 모두 포함."""
    with tempfile.TemporaryDirectory() as td:
        _write_signals(td, _make_signals(antipattern_count=2))
        _write_telemetry(td, _make_telemetry(applies=3, rollbacks=1))

        result = fc.classify(window=5)
        ev = result["evidence"]
        assert "evolution_success_rate" in ev
        assert "evolution_rollbacks" in ev
        assert "mentor_antipattern_count" in ev
        assert "mentor_antipatterns" in ev
        assert "mentor_avg_confidence" in ev
        assert "mentor_signals_analyzed" in ev
    print("  test_evidence_fields: PASS")


def main():
    test_system_failure()
    test_user_instruction_failure()
    test_mixed_failure()
    test_no_failure()
    test_iron_law_reminder()
    test_empty_data()
    test_evidence_fields()
    print("\nAll failure classifier tests passed.")


if __name__ == "__main__":
    main()
