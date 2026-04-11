#!/usr/bin/env python3
"""jarvis_failure_classifier.py — 반복 실패 원인 분류기.

SSOT: docs/CMUX-AGI-MENTOR-INTEGRATED-PLAN.md P6
정책: docs/jarvis/architecture/mentor-lane.md (Evolution vs Mentor 경계)

분류만 수행. config 변경은 Evolution Lane + Iron Law #1 승인을 통과해야 한다.

Usage:
    python3 jarvis_failure_classifier.py classify [--window 5]
"""

import argparse
import json
import sys
from pathlib import Path

MENTOR_DIR = Path.home() / ".claude" / "cmux-jarvis" / "mentor"
SIGNALS_FILE = MENTOR_DIR / "signals.jsonl"
TELEMETRY_DIR = Path.home() / ".claude" / "cmux-jarvis" / "telemetry"

SYSTEM_THRESHOLD_SUCCESS_RATE = 70.0  # % below = system problem
SYSTEM_THRESHOLD_ROLLBACKS = 3
USER_THRESHOLD_ANTIPATTERNS = 3  # occurrences in window

RECOMMENDATIONS = {
    "system": {
        "recommendation": "Evolution Lane에서 config 검토를 권장합니다.",
        "iron_law_reminder": "system evolution은 Iron Law #1 승인 필수",
    },
    "user_instruction": {
        "recommendation": "Mentor Lane에서 coaching hint를 강화합니다.",
        "iron_law_reminder": "",
    },
    "mixed": {
        "recommendation": "시스템 변경 vs 지시 방식 변경을 사용자에게 비교 제안합니다.",
        "iron_law_reminder": "system 변경 시 Iron Law #1 승인 필수",
    },
    "none": {
        "recommendation": "현재 특별한 조치가 필요하지 않습니다.",
        "iron_law_reminder": "",
    },
}


def _read_signals(limit=None):
    if not SIGNALS_FILE.exists():
        return []
    signals = []
    with open(SIGNALS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    signals.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if limit:
        signals = signals[-limit:]
    return signals


def _read_telemetry_summary():
    """Read recent telemetry events and compute summary."""
    if not TELEMETRY_DIR.exists():
        return {"total_events": 0, "type_counts": {}, "success_rate_pct": 100.0}

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
        return {"total_events": 0, "type_counts": {}, "success_rate_pct": 100.0}

    type_counts = {}
    for e in events:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    applies = type_counts.get("apply", 0)
    rollbacks = type_counts.get("rollback", 0)
    total_outcomes = applies + rollbacks
    success_rate = (applies / total_outcomes * 100) if total_outcomes > 0 else 100.0

    return {
        "total_events": len(events),
        "type_counts": type_counts,
        "success_rate_pct": round(success_rate, 1),
        "rollback_count": rollbacks,
    }


def classify(window=5):
    """Classify failure root cause."""
    signals = _read_signals(limit=window)
    telem = _read_telemetry_summary()

    # Mentor signal analysis
    all_antipatterns = []
    for s in signals:
        all_antipatterns.extend(s.get("antipatterns", []))
    ap_count = len(all_antipatterns)
    unique_ap = list(dict.fromkeys(all_antipatterns))
    avg_conf = round(sum(s.get("confidence", 0) for s in signals) / len(signals), 2) if signals else 0

    # Evolution telemetry analysis
    success_rate = telem.get("success_rate_pct", 100.0)
    rollbacks = telem.get("rollback_count", 0)

    # Classification
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

    result = {
        "classification": classification,
        "evidence": {
            "evolution_success_rate": success_rate,
            "evolution_rollbacks": rollbacks,
            "evolution_total_events": telem.get("total_events", 0),
            "mentor_antipattern_count": ap_count,
            "mentor_antipatterns": unique_ap,
            "mentor_avg_confidence": avg_conf,
            "mentor_signals_analyzed": len(signals),
        },
        "recommendation": rec["recommendation"],
        "iron_law_reminder": rec["iron_law_reminder"],
    }

    return result


def cmd_classify(window=5):
    """Run classification and print result."""
    result = classify(window)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Failure Classifier")
    sub = parser.add_subparsers(dest="cmd")

    p_cls = sub.add_parser("classify", help="Classify failure root cause")
    p_cls.add_argument("--window", type=int, default=5, help="Signal window size")

    args = parser.parse_args()

    if args.cmd == "classify":
        return cmd_classify(args.window)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
