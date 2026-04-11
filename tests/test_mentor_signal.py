#!/usr/bin/env python3
"""tests/test_mentor_signal.py — jarvis_mentor_signal.py ChromaDB 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_mentor_signal as ms


def _setup(td):
    ms.PALACE_PATH = os.path.join(td, "palace")
    ms.COLLECTION_NAME = "test_signals"


def test_emit_signal():
    """Signal emit → ChromaDB에 drawer 생성."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        event = {
            "type": "user_instruction_submitted",
            "data": {
                "scores": {"decomp": 0.8, "verify": 0.6, "orch": 0.7, "fail": 0.5, "ctx": 0.9, "meta": 0.4},
                "evidence_count": 5, "confidence": 0.7, "round_id": "round-1",
            },
        }
        ms.cmd_emit(json.dumps(event), round_id="round-1")

        signals = ms._read_signals()
        assert len(signals) == 1, f"Expected 1, got {len(signals)}"
        assert signals[0]["scores"]["decomp"] == 0.8
        assert signals[0]["calibration_note"] == "ok"
    print("  test_emit_signal: PASS")


def test_insufficient_evidence():
    """evidence < 3 → insufficient_evidence."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        event = {"type": "test", "data": {"evidence_count": 2, "confidence": 0.8}}
        ms.cmd_emit(json.dumps(event))

        signals = ms._read_signals()
        assert signals[0]["calibration_note"] == "insufficient_evidence"
    print("  test_insufficient_evidence: PASS")


def test_fit_score_and_level():
    """Fit score + harness level 계산."""
    scores = {"decomp": 0.8, "verify": 0.6, "orch": 0.7, "fail": 0.5, "ctx": 0.9, "meta": 0.4}
    fit = ms.compute_fit_score(scores)
    assert 0.0 <= fit <= 1.0
    level = ms.compute_harness_level(fit)
    assert level == round(level * 2) / 2
    assert 1.0 <= level <= 7.0
    print("  test_fit_score_and_level: PASS")


def test_detect_antipatterns():
    """Low scores → antipattern 감지."""
    scores = {"decomp": 0.8, "verify": 0.3, "orch": 0.7, "fail": 0.2, "ctx": 0.9, "meta": 0.4}
    patterns = ms.detect_antipatterns(scores)
    assert "verification_skip" in patterns
    assert "fix_me_syndrome" in patterns
    print("  test_detect_antipatterns: PASS")


def test_prune():
    """Prune으로 오래된 signal 삭제."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        col = ms._get_collection()

        # Old signal
        col.add(ids=["sig-old"], documents=["old"], metadatas=[{
            "wing": "cmux_mentor", "room": "verify", "ts": "2025-01-01T00:00:00Z",
            "signal_id": "sig-old", "fit_score": 0, "harness_level": 1.0,
            "confidence": 0.5, "evidence_count": "1", "calibration_note": "ok",
            "coaching_hint": "", "antipatterns": "",
        }])
        # Recent signal
        col.add(ids=["sig-recent"], documents=["recent"], metadatas=[{
            "wing": "cmux_mentor", "room": "verify", "ts": "2026-04-10T00:00:00Z",
            "signal_id": "sig-recent", "fit_score": 0.5, "harness_level": 3.0,
            "confidence": 0.7, "evidence_count": "3", "calibration_note": "ok",
            "coaching_hint": "", "antipatterns": "",
        }])

        ms.cmd_prune(keep_days=90)
        remaining = ms._read_signals()
        assert len(remaining) == 1
        assert remaining[0]["signal_id"] == "sig-recent"
    print("  test_prune: PASS")


def test_semantic_query():
    """시맨틱 검색으로 signal 조회."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        col = ms._get_collection()
        col.add(ids=["s1"], documents=["testing validation review"], metadatas=[{
            "wing": "cmux_mentor", "room": "verify", "ts": "2026-04-01T00:00:00Z",
            "signal_id": "s1", "fit_score": 0.5, "harness_level": 3.0,
            "confidence": 0.7, "evidence_count": "3", "calibration_note": "ok",
            "coaching_hint": "", "antipatterns": "verification_skip",
        }])
        col.add(ids=["s2"], documents=["task decomposition planning"], metadatas=[{
            "wing": "cmux_mentor", "room": "decomp", "ts": "2026-04-02T00:00:00Z",
            "signal_id": "s2", "fit_score": 0.6, "harness_level": 3.5,
            "confidence": 0.8, "evidence_count": "4", "calibration_note": "ok",
            "coaching_hint": "", "antipatterns": "",
        }])

        results = col.query(query_texts=["testing"], n_results=1)
        assert results["ids"][0][0] == "s1"
    print("  test_semantic_query: PASS")


def main():
    test_emit_signal()
    test_insufficient_evidence()
    test_fit_score_and_level()
    test_detect_antipatterns()
    test_prune()
    test_semantic_query()
    print("\nAll mentor signal (ChromaDB) tests passed.")


if __name__ == "__main__":
    main()
