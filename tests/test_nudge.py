#!/usr/bin/env python3
"""tests/test_nudge.py — jarvis_nudge.py ChromaDB 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_nudge as nudge


def _setup(td):
    nudge.PALACE_PATH = os.path.join(td, "palace")
    nudge.COLLECTION_NAME = "test_signals"


def test_l1_send():
    """L1 재촉 → palace drawer 기록."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        rc = nudge.cmd_send("surface:7", "team_lead", "STALLED", "8분간 진행 없음")
        assert rc == 0

        col = nudge._get_collection()
        results = col.get(where={"wing": "cmux_nudge"})
        assert len(results["ids"]) == 1
    print("  test_l1_send: PASS")


def test_watcher_blocked():
    """issuer=watcher → 거부."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        rc = nudge.cmd_send("surface:7", "watcher", "STALLED", "test")
        assert rc == 1
    print("  test_watcher_blocked: PASS")


def test_cooldown_enforced():
    """5분 내 재전송 → rate_limited."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        rc1 = nudge.cmd_send("surface:7", "team_lead", "STALLED", "stuck")
        assert rc1 == 0
        rc2 = nudge.cmd_send("surface:7", "team_lead", "STALLED", "still stuck")
        assert rc2 == 2
    print("  test_cooldown_enforced: PASS")


def test_l2_blocked():
    """level=L2 → 거부."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        rc = nudge.cmd_send("surface:7", "boss", "STALLED", "test", level="L2")
        assert rc == 1
    print("  test_l2_blocked: PASS")


def test_invalid_issuer():
    """유효하지 않은 issuer → 거부."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        rc = nudge.cmd_send("surface:7", "worker", "STALLED", "test")
        assert rc == 1
    print("  test_invalid_issuer: PASS")


def test_different_targets_no_cooldown():
    """다른 target은 cooldown 독립."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        rc1 = nudge.cmd_send("surface:7", "team_lead", "STALLED", "stuck")
        rc2 = nudge.cmd_send("surface:8", "team_lead", "IDLE", "idle")
        assert rc1 == 0
        assert rc2 == 0
    print("  test_different_targets_no_cooldown: PASS")


def test_check_cooldown():
    """cooldown 상태 확인."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        in_cd, _ = nudge._check_cooldown("surface:99")
        assert not in_cd

        nudge.cmd_send("surface:99", "boss", "IDLE", "5분")
        in_cd2, _ = nudge._check_cooldown("surface:99")
        assert in_cd2
    print("  test_check_cooldown: PASS")


def main():
    test_l1_send()
    test_watcher_blocked()
    test_cooldown_enforced()
    test_l2_blocked()
    test_invalid_issuer()
    test_different_targets_no_cooldown()
    test_check_cooldown()
    print("\nAll nudge (ChromaDB) tests passed.")


if __name__ == "__main__":
    main()
