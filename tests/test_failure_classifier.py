#!/usr/bin/env python3
"""tests/test_failure_classifier.py — jarvis_failure_classifier.py ChromaDB 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_failure_classifier as fc
from chromadb_test_utils import create_collection, get_collection

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")


def _setup(td):
    fc.PALACE_PATH = os.path.join(td, "palace")
    fc.COLLECTION_NAME = "test_signals"
    fc.TELEMETRY_DIR = type(fc.TELEMETRY_DIR)(os.path.join(td, "telemetry"))


def _add_signals(td, antipattern_count=0):
    import chromadb
    os.makedirs(fc.PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=fc.PALACE_PATH)
    try:
        col = get_collection(client, fc.COLLECTION_NAME)
    except Exception:
        col = create_collection(client, fc.COLLECTION_NAME)

    for i in range(5):
        ap = "verification_skip" if i < antipattern_count else ""
        meta = {
            "wing": "cmux_mentor", "room": "verify",
            "ts": f"2026-04-{i+1:02d}T12:00:00Z",
            "signal_id": f"sig-{i}",
            "antipatterns": ap, "confidence": 0.7,
            "fit_score": 0.5, "harness_level": 3.0,
            "evidence_count": "3", "calibration_note": "ok",
            "coaching_hint": "",
        }
        for a in AXES:
            meta[a] = 0.5
        col.add(ids=[f"sig-{i}"], documents=[f"signal {i}"], metadatas=[meta])


def _add_telemetry(td, applies=5, rollbacks=0):
    fc.TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    events = []
    for i in range(applies):
        events.append({"ts": f"2026-04-{i+1:02d}T12:00:00Z", "type": "apply", "data": {}})
    for i in range(rollbacks):
        events.append({"ts": f"2026-04-{i+1:02d}T13:00:00Z", "type": "rollback", "data": {}})
    with open(fc.TELEMETRY_DIR / "events-2026-04-11.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def test_system_failure():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 0)
        _add_telemetry(td, applies=2, rollbacks=4)
        result = fc.classify(window=5)
        assert result["classification"] == "system"
    print("  test_system_failure: PASS")


def test_user_instruction_failure():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 4)
        _add_telemetry(td, applies=5, rollbacks=0)
        result = fc.classify(window=5)
        assert result["classification"] == "user_instruction"
    print("  test_user_instruction_failure: PASS")


def test_mixed_failure():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 4)
        _add_telemetry(td, applies=1, rollbacks=5)
        result = fc.classify(window=5)
        assert result["classification"] == "mixed"
    print("  test_mixed_failure: PASS")


def test_no_failure():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 1)
        _add_telemetry(td, applies=8, rollbacks=1)
        result = fc.classify(window=5)
        assert result["classification"] == "none"
    print("  test_no_failure: PASS")


def test_iron_law_reminder():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 0)
        _add_telemetry(td, applies=1, rollbacks=5)
        result = fc.classify(window=5)
        assert "Iron Law #1" in result["iron_law_reminder"]
    print("  test_iron_law_reminder: PASS")


def test_empty_data():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        result = fc.classify(window=5)
        assert result["classification"] == "none"
    print("  test_empty_data: PASS")


def test_evidence_fields():
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 2)
        _add_telemetry(td, applies=3, rollbacks=1)
        result = fc.classify(window=5)
        ev = result["evidence"]
        assert "evolution_success_rate" in ev
        assert "mentor_antipattern_count" in ev
    print("  test_evidence_fields: PASS")


def main():
    test_system_failure()
    test_user_instruction_failure()
    test_mixed_failure()
    test_no_failure()
    test_iron_law_reminder()
    test_empty_data()
    test_evidence_fields()
    print("\nAll failure classifier (ChromaDB) tests passed.")


if __name__ == "__main__":
    main()
