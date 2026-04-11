#!/usr/bin/env python3
"""tests/test_nudge.py — jarvis_nudge.py 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_nudge as nudge


def test_l1_send():
    """L1 재촉 → audit event 1행 기록."""
    with tempfile.TemporaryDirectory() as td:
        nudge.AUDIT_DIR = type(nudge.AUDIT_DIR)(td)
        nudge.AUDIT_FILE = nudge.AUDIT_DIR / "nudge-audit.jsonl"

        rc = nudge.cmd_send("surface:7", "team_lead", "STALLED", "8분간 진행 없음")
        assert rc == 0, f"Expected rc=0, got {rc}"

        entries = nudge._read_audit()
        assert len(entries) == 1, f"Expected 1 audit entry, got {len(entries)}"
        e = entries[0]
        assert e["target_surface_id"] == "surface:7"
        assert e["issuer_role"] == "team_lead"
        assert e["reason_code"] == "STALLED"
        assert e["level"] == "L1"
        assert e["outcome"] == "pending"
        assert "cooldown_until" in e
    print("  test_l1_send: PASS")


def test_watcher_blocked():
    """issuer=watcher → 거부 (code 1)."""
    with tempfile.TemporaryDirectory() as td:
        nudge.AUDIT_DIR = type(nudge.AUDIT_DIR)(td)
        nudge.AUDIT_FILE = nudge.AUDIT_DIR / "nudge-audit.jsonl"

        rc = nudge.cmd_send("surface:7", "watcher", "STALLED", "test")
        assert rc == 1, f"Watcher should be blocked, got rc={rc}"

        entries = nudge._read_audit()
        assert len(entries) == 0, "No audit entry for blocked watcher"
    print("  test_watcher_blocked: PASS")


def test_cooldown_enforced():
    """5분 내 재전송 → rate_limited (code 2)."""
    with tempfile.TemporaryDirectory() as td:
        nudge.AUDIT_DIR = type(nudge.AUDIT_DIR)(td)
        nudge.AUDIT_FILE = nudge.AUDIT_DIR / "nudge-audit.jsonl"

        # First send: OK
        rc1 = nudge.cmd_send("surface:7", "team_lead", "STALLED", "8분간 진행 없음")
        assert rc1 == 0

        # Second send: cooldown
        rc2 = nudge.cmd_send("surface:7", "team_lead", "STALLED", "still stuck")
        assert rc2 == 2, f"Cooldown should block, got rc={rc2}"

        entries = nudge._read_audit()
        # 1 normal + 1 rate_limited
        assert len(entries) == 2
        assert entries[1]["outcome"] == "rate_limited"
    print("  test_cooldown_enforced: PASS")


def test_l2_blocked():
    """level=L2 → 거부 (code 1)."""
    with tempfile.TemporaryDirectory() as td:
        nudge.AUDIT_DIR = type(nudge.AUDIT_DIR)(td)
        nudge.AUDIT_FILE = nudge.AUDIT_DIR / "nudge-audit.jsonl"

        rc = nudge.cmd_send("surface:7", "boss", "STALLED", "test", level="L2")
        assert rc == 1, f"L2 should be blocked, got rc={rc}"
    print("  test_l2_blocked: PASS")


def test_invalid_issuer():
    """유효하지 않은 issuer → 거부."""
    with tempfile.TemporaryDirectory() as td:
        nudge.AUDIT_DIR = type(nudge.AUDIT_DIR)(td)
        nudge.AUDIT_FILE = nudge.AUDIT_DIR / "nudge-audit.jsonl"

        rc = nudge.cmd_send("surface:7", "worker", "STALLED", "test")
        assert rc == 1
    print("  test_invalid_issuer: PASS")


def test_different_targets_no_cooldown():
    """서로 다른 target은 cooldown 독립."""
    with tempfile.TemporaryDirectory() as td:
        nudge.AUDIT_DIR = type(nudge.AUDIT_DIR)(td)
        nudge.AUDIT_FILE = nudge.AUDIT_DIR / "nudge-audit.jsonl"

        rc1 = nudge.cmd_send("surface:7", "team_lead", "STALLED", "stuck")
        rc2 = nudge.cmd_send("surface:8", "team_lead", "IDLE", "idle")
        assert rc1 == 0
        assert rc2 == 0, f"Different target should not be in cooldown, got rc={rc2}"
    print("  test_different_targets_no_cooldown: PASS")


def test_check_cooldown():
    """check-cooldown 명령 동작 확인."""
    with tempfile.TemporaryDirectory() as td:
        nudge.AUDIT_DIR = type(nudge.AUDIT_DIR)(td)
        nudge.AUDIT_FILE = nudge.AUDIT_DIR / "nudge-audit.jsonl"

        # No entries → not in cooldown
        in_cd, _ = nudge._check_cooldown("surface:99")
        assert not in_cd

        # After send → in cooldown
        nudge.cmd_send("surface:99", "boss", "IDLE", "5분 경과")
        in_cd2, until = nudge._check_cooldown("surface:99")
        assert in_cd2
        assert until != ""
    print("  test_check_cooldown: PASS")


def main():
    test_l1_send()
    test_watcher_blocked()
    test_cooldown_enforced()
    test_l2_blocked()
    test_invalid_issuer()
    test_different_targets_no_cooldown()
    test_check_cooldown()
    print("\nAll nudge tests passed.")


if __name__ == "__main__":
    main()
