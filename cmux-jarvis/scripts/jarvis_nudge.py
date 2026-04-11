#!/usr/bin/env python3
"""jarvis_nudge.py — L1 텍스트 재촉 + audit event 기록.

SSOT: docs/jarvis/architecture/nudge-escalation-policy.md
현재 구현: L1만. L2/L3는 보류.

Usage:
    python3 jarvis_nudge.py send --target surface:7 --issuer team_lead --reason STALLED --evidence "8분간 진행 없음"
    python3 jarvis_nudge.py check-cooldown --target surface:7
    python3 jarvis_nudge.py audit [--since 2026-04-01]
"""

import argparse
import fcntl
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

AUDIT_DIR = Path.home() / ".claude" / "cmux-jarvis" / "mentor"
AUDIT_FILE = AUDIT_DIR / "nudge-audit.jsonl"

COOLDOWN_SECONDS = 300  # 5 minutes for L1
ALLOWED_ISSUERS = {"team_lead", "boss", "jarvis"}
ALLOWED_REASONS = {"STALLED", "IDLE", "instruction_drift", "no_done_report", "rate_limited"}


def utc_now():
    return datetime.now(timezone.utc)


def utc_str(dt=None):
    return (dt or utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _read_audit():
    if not AUDIT_FILE.exists():
        return []
    entries = []
    with open(AUDIT_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def _append_audit(event):
    _ensure_dir()
    with open(AUDIT_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _check_cooldown(target):
    """Check if target is in cooldown. Returns (in_cooldown, cooldown_until)."""
    entries = _read_audit()
    now = utc_now()
    for entry in reversed(entries):
        if entry.get("target_surface_id") == target:
            cooldown_until = entry.get("cooldown_until", "")
            if cooldown_until:
                try:
                    cutoff = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
                    if now < cutoff:
                        return True, cooldown_until
                except (ValueError, TypeError):
                    pass
            break
    return False, ""


def _format_l1_message(evidence_span):
    return f"현재 {evidence_span}. 60초 안에 DONE, BLOCKED, NEEDS_INFO 중 하나로 보고하세요."


def _cmux_send(target, message):
    """Send message via cmux send + enter."""
    try:
        subprocess.run(
            ["cmux", "send", "--surface", target, message],
            capture_output=True, text=True, timeout=5,
        )
        subprocess.run(
            ["cmux", "send-key", "--surface", target, "enter"],
            capture_output=True, text=True, timeout=5,
        )
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def cmd_send(target, issuer, reason, evidence, level="L1"):
    """Send L1 nudge to target surface."""
    # Permission: only L1 allowed
    if level != "L1":
        print(json.dumps({"error": f"only L1 allowed, got {level}", "code": 1}))
        return 1

    # Permission: watcher cannot execute
    if issuer == "watcher":
        print(json.dumps({"error": "watcher cannot execute nudge (evidence producer only)", "code": 1}))
        return 1

    # Permission: issuer must be valid role
    if issuer not in ALLOWED_ISSUERS:
        print(json.dumps({"error": f"invalid issuer: {issuer}. allowed: {', '.join(ALLOWED_ISSUERS)}", "code": 1}))
        return 1

    # Cooldown check
    in_cooldown, until = _check_cooldown(target)
    if in_cooldown:
        rate_event = {
            "timestamp": utc_str(),
            "target_surface_id": target,
            "issuer_role": issuer,
            "reason_code": "nudge_rate_limited",
            "evidence_span": f"cooldown active until {until}",
            "level": level,
            "cooldown_until": until,
            "outcome": "rate_limited",
        }
        _append_audit(rate_event)
        print(json.dumps({"error": "cooldown active", "cooldown_until": until, "code": 2}))
        return 2

    # Build message
    message = _format_l1_message(evidence)

    # Send via cmux
    sent = _cmux_send(target, message)

    # Record audit
    now = utc_now()
    event = {
        "timestamp": utc_str(now),
        "target_surface_id": target,
        "issuer_role": issuer,
        "reason_code": reason,
        "evidence_span": evidence,
        "level": level,
        "cooldown_until": utc_str(now + timedelta(seconds=COOLDOWN_SECONDS)),
        "outcome": "pending",
    }
    _append_audit(event)

    result = {"ok": True, "message": message, "sent_via_cmux": sent, "audit": event}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_check_cooldown(target):
    """Check cooldown status for a target."""
    in_cooldown, until = _check_cooldown(target)
    print(json.dumps({
        "target": target,
        "in_cooldown": in_cooldown,
        "cooldown_until": until if in_cooldown else None,
    }))
    return 0


def cmd_audit(since=None):
    """Show audit log, optionally filtered by date."""
    entries = _read_audit()
    if since:
        entries = [e for e in entries if e.get("timestamp", "") >= since]
    for e in entries:
        print(json.dumps(e, ensure_ascii=False))
    if not entries:
        print("No audit entries found.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Nudge L1")
    sub = parser.add_subparsers(dest="cmd")

    p_send = sub.add_parser("send", help="Send L1 nudge")
    p_send.add_argument("--target", required=True, help="Target surface (e.g. surface:7)")
    p_send.add_argument("--issuer", required=True, help="Issuer role (team_lead|boss|jarvis)")
    p_send.add_argument("--reason", required=True, help="Reason code (STALLED|IDLE|...)")
    p_send.add_argument("--evidence", required=True, help="Evidence description")

    p_cool = sub.add_parser("check-cooldown", help="Check cooldown for target")
    p_cool.add_argument("--target", required=True)

    p_audit = sub.add_parser("audit", help="Show audit log")
    p_audit.add_argument("--since", default=None, help="ISO date filter")

    args = parser.parse_args()

    if args.cmd == "send":
        return cmd_send(args.target, args.issuer, args.reason, args.evidence)
    elif args.cmd == "check-cooldown":
        return cmd_check_cooldown(args.target)
    elif args.cmd == "audit":
        return cmd_audit(args.since)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
