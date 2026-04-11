#!/usr/bin/env python3
"""tests/test_mentor_report.py — jarvis_mentor_report.py ChromaDB 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_mentor_report as mr


AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")


def _setup(td):
    mr.PALACE_PATH = os.path.join(td, "palace")
    mr.COLLECTION_NAME = "test_signals"


def _add_signals(td, n=5):
    import chromadb
    os.makedirs(mr.PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=mr.PALACE_PATH)
    try:
        col = client.get_collection(mr.COLLECTION_NAME)
    except Exception:
        col = client.create_collection(mr.COLLECTION_NAME)

    for i in range(n):
        sid = f"sig-{i}"
        meta = {
            "wing": "cmux_mentor", "room": "verify",
            "signal_id": sid, "ts": f"2026-04-{i+1:02d}T12:00:00Z",
            "fit_score": 0.65 + i * 0.01, "harness_level": 3.5,
            "confidence": 0.7, "evidence_count": "5",
            "coaching_hint": "", "calibration_note": "ok",
            "antipatterns": "verification_skip" if i % 2 == 0 else "",
        }
        for a in AXES:
            meta[a] = 0.5 + i * 0.02
        col.add(ids=[sid], documents=[f"signal {i}"], metadatas=[meta])


def test_generate_report():
    """signals → report 생성."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 5)
        signals = mr._read_signals()
        report_text, *_ = mr.generate_report(signals)
        assert "6축 분석" in report_text
        assert "Harness Level" in report_text
    print("  test_generate_report: PASS")


def test_insufficient_signals():
    """signals < 3 → 보류."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 2)
        rc = mr.cmd_generate()
        assert rc == 0  # defers gracefully
    print("  test_insufficient_signals: PASS")


def test_timeline_stored():
    """report → timeline drawer 저장."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 5)
        mr.cmd_generate()

        col = mr._get_collection()
        results = col.get(where={"wing": "cmux_timeline"})
        assert len(results["ids"]) >= 1
    print("  test_timeline_stored: PASS")


def test_report_not_evaluation():
    """disclaimer 포함."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 5)
        signals = mr._read_signals()
        report_text, *_ = mr.generate_report(signals)
        assert "사용자를 평가하는 문서가 아니라" in report_text
    print("  test_report_not_evaluation: PASS")


def test_report_stored_in_palace():
    """report가 cmux_reports wing에 저장."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 5)
        mr.cmd_generate()

        col = mr._get_collection()
        results = col.get(where={"wing": "cmux_reports"})
        assert len(results["ids"]) >= 1
    print("  test_report_stored_in_palace: PASS")


def test_gate_conditions():
    """Gate 조건 표 포함."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_signals(td, 5)
        signals = mr._read_signals()
        report_text, *_ = mr.generate_report(signals)
        assert "Gate" in report_text
    print("  test_gate_conditions: PASS")


def main():
    test_generate_report()
    test_insufficient_signals()
    test_timeline_stored()
    test_report_not_evaluation()
    test_report_stored_in_palace()
    test_gate_conditions()
    print("\nAll mentor report (ChromaDB) tests passed.")


if __name__ == "__main__":
    main()
