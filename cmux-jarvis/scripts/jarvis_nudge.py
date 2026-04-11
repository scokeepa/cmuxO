#!/usr/bin/env python3
"""jarvis_nudge.py — L1 텍스트 재촉 + audit → ChromaDB palace.

SSOT: docs/02-jarvis/nudge-escalation.md
badclaude는 채찍질 전용. 메모리 시스템이 아님.

Usage:
    python3 jarvis_nudge.py send --target surface:7 --issuer team_lead --reason STALLED --evidence "8분간 진행 없음"
    python3 jarvis_nudge.py check-cooldown --target surface:7
    python3 jarvis_nudge.py audit [--since 2026-04-01]
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
import chromadb

PALACE_PATH = os.path.expanduser("~/.cmux-jarvis-palace")
COLLECTION_NAME = "cmux_mentor_signals"
COOLDOWN_SECONDS = 300
ALLOWED_ISSUERS = {"team_lead", "boss", "jarvis"}


def _get_collection():
    os.makedirs(PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=PALACE_PATH)
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return client.create_collection(COLLECTION_NAME)


def utc_now():
    return datetime.now(timezone.utc)


def utc_str(dt=None):
    return (dt or utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _store_nudge_audit(event):
    """Store nudge audit event as a drawer in palace."""
    col = _get_collection()
    doc = f"NUDGE {event['level']} → {event['target_surface_id']}: {event['evidence_span']}"
    meta = {
        "wing": "cmux_nudge",
        "room": event["reason_code"].lower(),
        "target_surface_id": event["target_surface_id"],
        "issuer_role": event["issuer_role"],
        "reason_code": event["reason_code"],
        "level": event["level"],
        "cooldown_until": event["cooldown_until"],
        "outcome": event["outcome"],
        "ts": event["timestamp"],
    }
    col.add(ids=[f"nudge-{event['timestamp']}"], documents=[doc], metadatas=[meta])


def _check_cooldown(target):
    """Check if target is in cooldown."""
    col = _get_collection()
    try:
        results = col.get(
            where={"$and": [{"wing": "cmux_nudge"}, {"target_surface_id": target}]},
            include=["metadatas"],
            limit=100,
        )
    except Exception:
        return False, ""

    now = utc_now()
    for meta in sorted(results.get("metadatas", []), key=lambda m: m.get("ts", ""), reverse=True):
        cooldown_until = meta.get("cooldown_until", "")
        if cooldown_until:
            try:
                cutoff = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
                if now < cutoff:
                    return True, cooldown_until
            except (ValueError, TypeError):
                pass
        break
    return False, ""


def _cmux_send(target, message):
    try:
        subprocess.run(["cmux", "send", "--surface", target, message], capture_output=True, text=True, timeout=5)
        subprocess.run(["cmux", "send-key", "--surface", target, "enter"], capture_output=True, text=True, timeout=5)
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def cmd_send(target, issuer, reason, evidence, level="L1"):
    if level != "L1":
        print(json.dumps({"error": f"only L1 allowed, got {level}", "code": 1}))
        return 1
    if issuer == "watcher":
        print(json.dumps({"error": "watcher cannot execute nudge (evidence producer only)", "code": 1}))
        return 1
    if issuer not in ALLOWED_ISSUERS:
        print(json.dumps({"error": f"invalid issuer: {issuer}", "code": 1}))
        return 1

    in_cooldown, until = _check_cooldown(target)
    if in_cooldown:
        rate_event = {
            "timestamp": utc_str(), "target_surface_id": target, "issuer_role": issuer,
            "reason_code": "nudge_rate_limited", "evidence_span": f"cooldown until {until}",
            "level": level, "cooldown_until": until, "outcome": "rate_limited",
        }
        _store_nudge_audit(rate_event)
        print(json.dumps({"error": "cooldown active", "cooldown_until": until, "code": 2}))
        return 2

    message = f"현재 {evidence}. 60초 안에 DONE, BLOCKED, NEEDS_INFO 중 하나로 보고하세요."
    sent = _cmux_send(target, message)

    now = utc_now()
    event = {
        "timestamp": utc_str(now), "target_surface_id": target, "issuer_role": issuer,
        "reason_code": reason, "evidence_span": evidence, "level": level,
        "cooldown_until": utc_str(now + timedelta(seconds=COOLDOWN_SECONDS)), "outcome": "pending",
    }
    _store_nudge_audit(event)

    print(json.dumps({"ok": True, "message": message, "sent_via_cmux": sent, "audit": event}, ensure_ascii=False, indent=2))
    return 0


def cmd_check_cooldown(target):
    in_cooldown, until = _check_cooldown(target)
    print(json.dumps({"target": target, "in_cooldown": in_cooldown, "cooldown_until": until if in_cooldown else None}))
    return 0


def cmd_audit(since=None):
    col = _get_collection()
    try:
        results = col.get(where={"wing": "cmux_nudge"}, include=["metadatas", "documents"], limit=1000)
    except Exception:
        print("No audit entries.")
        return 0

    entries = []
    for did, meta, doc in zip(results.get("ids", []), results.get("metadatas", []), results.get("documents", [])):
        if since and meta.get("ts", "") < since:
            continue
        entries.append({"id": did, **meta, "document": doc})

    for e in sorted(entries, key=lambda x: x.get("ts", "")):
        print(json.dumps(e, ensure_ascii=False))
    if not entries:
        print("No audit entries found.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Nudge L1 (ChromaDB)")
    sub = parser.add_subparsers(dest="cmd")

    p_send = sub.add_parser("send")
    p_send.add_argument("--target", required=True)
    p_send.add_argument("--issuer", required=True)
    p_send.add_argument("--reason", required=True)
    p_send.add_argument("--evidence", required=True)

    p_cool = sub.add_parser("check-cooldown")
    p_cool.add_argument("--target", required=True)

    p_audit = sub.add_parser("audit")
    p_audit.add_argument("--since", default=None)

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
