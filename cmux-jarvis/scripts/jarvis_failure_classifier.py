#!/usr/bin/env python3
"""jarvis_failure_classifier.py — 반복 실패 원인 분류기 (ChromaDB).

SSOT: docs/02-jarvis/mentor-lane.md
분류만 수행. config 변경은 Evolution Lane + Iron Law #1 승인 필수.

Usage:
    python3 jarvis_failure_classifier.py classify [--window 5]
"""

import argparse
import json
import os
import sys
from pathlib import Path

import chromadb

PALACE_PATH = os.path.expanduser("~/.cmux-jarvis-palace")
COLLECTION_NAME = "cmux_mentor_signals"
TELEMETRY_DIR = Path.home() / ".claude" / "cmux-jarvis" / "telemetry"

SYSTEM_THRESHOLD_SUCCESS_RATE = 70.0
SYSTEM_THRESHOLD_ROLLBACKS = 3
USER_THRESHOLD_ANTIPATTERNS = 3

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")

RECOMMENDATIONS = {
    "system": {"recommendation": "Evolution Lane에서 config 검토를 권장합니다.", "iron_law_reminder": "system evolution은 Iron Law #1 승인 필수"},
    "user_instruction": {"recommendation": "Mentor Lane에서 coaching hint를 강화합니다.", "iron_law_reminder": ""},
    "mixed": {"recommendation": "시스템 변경 vs 지시 방식 변경을 사용자에게 비교 제안합니다.", "iron_law_reminder": "system 변경 시 Iron Law #1 승인 필수"},
    "none": {"recommendation": "현재 특별한 조치가 필요하지 않습니다.", "iron_law_reminder": ""},
}


def _get_collection():
    os.makedirs(PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=PALACE_PATH)
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return client.create_collection(COLLECTION_NAME)


def _read_signals(limit=None):
    col = _get_collection()
    try:
        results = col.get(where={"wing": "cmux_mentor"}, include=["metadatas"], limit=10000)
    except Exception:
        return []

    signals = []
    for meta in results.get("metadatas", []):
        signals.append({
            "ts": meta.get("ts", ""),
            "antipatterns": [p for p in meta.get("antipatterns", "").split(",") if p],
            "confidence": float(meta.get("confidence", 0)),
        })
    signals.sort(key=lambda s: s["ts"])
    if limit:
        signals = signals[-limit:]
    return signals


def _read_telemetry_summary():
    if not TELEMETRY_DIR.exists():
        return {"total_events": 0, "type_counts": {}, "success_rate_pct": 100.0, "rollback_count": 0}

    events = []
    for f in sorted(TELEMETRY_DIR.glob("events-*.jsonl")):
        try:
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            continue

    if not events:
        return {"total_events": 0, "type_counts": {}, "success_rate_pct": 100.0, "rollback_count": 0}

    type_counts = {}
    for e in events:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    applies = type_counts.get("apply", 0)
    rollbacks = type_counts.get("rollback", 0)
    total_outcomes = applies + rollbacks
    success_rate = (applies / total_outcomes * 100) if total_outcomes > 0 else 100.0

    return {"total_events": len(events), "type_counts": type_counts, "success_rate_pct": round(success_rate, 1), "rollback_count": rollbacks}


def classify(window=5):
    signals = _read_signals(limit=window)
    telem = _read_telemetry_summary()

    all_ap = []
    for s in signals:
        all_ap.extend(s.get("antipatterns", []))
    ap_count = len(all_ap)
    unique_ap = list(dict.fromkeys(all_ap))
    avg_conf = round(sum(s.get("confidence", 0) for s in signals) / len(signals), 2) if signals else 0

    success_rate = telem.get("success_rate_pct", 100.0)
    rollbacks = telem.get("rollback_count", 0)

    system_flag = success_rate < SYSTEM_THRESHOLD_SUCCESS_RATE or rollbacks >= SYSTEM_THRESHOLD_ROLLBACKS
    user_flag = ap_count >= USER_THRESHOLD_ANTIPATTERNS

    if system_flag and user_flag:
        classification = "mixed"
    elif system_flag:
        classification = "system"
    elif user_flag:
        classification = "user_instruction"
    else:
        classification = "none"

    rec = RECOMMENDATIONS[classification]
    return {
        "classification": classification,
        "evidence": {
            "evolution_success_rate": success_rate, "evolution_rollbacks": rollbacks,
            "evolution_total_events": telem.get("total_events", 0),
            "mentor_antipattern_count": ap_count, "mentor_antipatterns": unique_ap,
            "mentor_avg_confidence": avg_conf, "mentor_signals_analyzed": len(signals),
        },
        "recommendation": rec["recommendation"],
        "iron_law_reminder": rec["iron_law_reminder"],
    }


def cmd_classify(window=5):
    result = classify(window)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Failure Classifier (ChromaDB)")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("classify")
    p.add_argument("--window", type=int, default=5)
    args = parser.parse_args()
    if args.cmd == "classify":
        return cmd_classify(args.window)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
