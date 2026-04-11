#!/usr/bin/env python3
"""jarvis_mentor_signal.py — Mentor Lane 6축 signal engine.

SSOT: docs/jarvis/architecture/palace-memory-ssot.md
Schema: docs/jarvis/architecture/mentor-ontology.md

Usage:
    python3 jarvis_mentor_signal.py emit --event '{"type":"...","data":{...}}'
    python3 jarvis_mentor_signal.py query --since 2026-04-01 [--summary]
    python3 jarvis_mentor_signal.py prune --keep-days 90
    python3 jarvis_mentor_signal.py tail [--n 5]
"""

import argparse
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

SIGNALS_DIR = Path.home() / ".claude" / "cmux-jarvis" / "mentor"
SIGNALS_FILE = SIGNALS_DIR / "signals.jsonl"

# 6축 기본 가중치 (cmux orchestration = Builder + Operator 혼합)
DEFAULT_WEIGHTS = {
    "decomp": 0.20, "verify": 0.22, "orch": 0.20,
    "fail": 0.18, "ctx": 0.10, "meta": 0.10,
}

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir():
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)


def _append_signal(signal):
    """Append a signal to signals.jsonl with fcntl locking."""
    _ensure_dir()
    with open(SIGNALS_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(json.dumps(signal, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _read_signals():
    """Read all signals from signals.jsonl."""
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
    return signals


def compute_fit_score(scores, weights=None):
    """Compute weighted fit score from 6-axis scores."""
    w = weights or DEFAULT_WEIGHTS
    return round(sum(w.get(axis, 0) * scores.get(axis, 0) for axis in AXES), 2)


def compute_harness_level(fit_score):
    """Convert fit score to harness level (0.5 increments)."""
    raw = fit_score
    if raw < 0.25:
        return 0.0
    # Map 0-1 score to L1-L7 range (rough heuristic)
    level = 1.0 + raw * 6.0
    # Round to 0.5
    return round(round(level * 2) / 2, 1)


def compute_calibration(evidence_count, confidence):
    """Determine calibration note based on evidence sufficiency."""
    if evidence_count < 3 or confidence < 0.5:
        return "insufficient_evidence"
    return "ok"


def detect_antipatterns(scores):
    """Detect antipatterns from low axis scores."""
    patterns = []
    if scores.get("fail", 1) < 0.4:
        patterns.append("fix_me_syndrome")
    if scores.get("ctx", 1) < 0.4:
        patterns.append("context_skip")
    if scores.get("verify", 1) < 0.4:
        patterns.append("verification_skip")
    if scores.get("orch", 1) < 0.4:
        patterns.append("over_partition")
    if scores.get("meta", 1) < 0.4:
        patterns.append("scope_creep")
    return patterns


def generate_coaching_hint(scores, antipatterns):
    """Generate a single coaching hint based on weakest axis."""
    if not antipatterns:
        return ""
    hints = {
        "fix_me_syndrome": "오류 메시지를 먼저 읽고 원인을 분석한 뒤 지시하면 재작업률이 줄어듭니다.",
        "context_skip": "파일 경로와 제약 조건을 명시하면 팀장이 정확히 분배할 수 있습니다.",
        "verification_skip": "완료 조건을 1줄 추가하면 검증 누락이 줄어듭니다.",
        "over_partition": "이 작업은 단일 AI로 충분할 수 있습니다. 부서 분할이 필요한지 확인하세요.",
        "scope_creep": "작업 범위를 고정한 뒤 추가 요청은 다음 round로 분리하세요.",
    }
    return hints.get(antipatterns[0], "")


def cmd_emit(event_json, round_id=None, window_size=5):
    """Process an event and emit a mentor signal."""
    try:
        event = json.loads(event_json) if isinstance(event_json, str) else event_json
    except json.JSONDecodeError:
        print("Error: invalid JSON event", file=sys.stderr)
        return 1

    data = event.get("data", {})
    scores = data.get("scores", {})

    # Fill missing axes with default 0.5
    for axis in AXES:
        scores.setdefault(axis, 0.5)

    evidence_count = data.get("evidence_count", 1)
    confidence = data.get("confidence", 0.5)

    fit_score = compute_fit_score(scores)
    harness_level = compute_harness_level(fit_score)
    calibration = compute_calibration(evidence_count, confidence)
    antipatterns = detect_antipatterns(scores)
    hint = generate_coaching_hint(scores, antipatterns)

    signal = {
        "ts": utc_now(),
        "signal_id": f"sig-{int(time.time())}",
        "round_id": round_id or data.get("round_id", "unknown"),
        "window_size": window_size,
        "scores": {axis: round(scores[axis], 2) for axis in AXES},
        "fit_score": fit_score,
        "harness_level": harness_level,
        "antipatterns": antipatterns,
        "coaching_hint": hint,
        "confidence": round(confidence, 2),
        "evidence_count": evidence_count,
        "calibration_note": calibration,
    }

    _append_signal(signal)
    print(json.dumps(signal, ensure_ascii=False, indent=2))
    return 0


def cmd_query(since=None, summary=False):
    """Query signals, optionally filtered by date."""
    signals = _read_signals()

    if since:
        signals = [s for s in signals if s.get("ts", "") >= since]

    if summary:
        if not signals:
            print(json.dumps({"count": 0, "message": "no signals found"}))
            return 0

        avg_scores = {}
        for axis in AXES:
            values = [s["scores"].get(axis, 0) for s in signals]
            avg_scores[axis] = round(sum(values) / len(values), 2)

        all_patterns = []
        for s in signals:
            all_patterns.extend(s.get("antipatterns", []))
        pattern_counts = {}
        for p in all_patterns:
            pattern_counts[p] = pattern_counts.get(p, 0) + 1

        result = {
            "count": len(signals),
            "period": {"from": signals[0]["ts"], "to": signals[-1]["ts"]},
            "avg_scores": avg_scores,
            "avg_fit_score": round(sum(s["fit_score"] for s in signals) / len(signals), 2),
            "latest_harness_level": signals[-1].get("harness_level"),
            "antipattern_counts": pattern_counts,
            "avg_confidence": round(sum(s["confidence"] for s in signals) / len(signals), 2),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for s in signals:
            print(json.dumps(s, ensure_ascii=False))

    return 0


def cmd_tail(n=5):
    """Show recent N signals."""
    signals = _read_signals()
    for s in signals[-n:]:
        print(json.dumps(s, ensure_ascii=False))
    return 0


def cmd_prune(keep_days=90):
    """Remove signals older than keep_days."""
    if not SIGNALS_FILE.exists():
        print("No signals file to prune.")
        return 0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    signals = _read_signals()
    kept = [s for s in signals if s.get("ts", "") >= cutoff]
    pruned = len(signals) - len(kept)

    if pruned > 0:
        import tempfile
        tmp_path = str(SIGNALS_FILE) + ".tmp"
        with open(tmp_path, "w") as f:
            for s in kept:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        os.rename(tmp_path, str(SIGNALS_FILE))

    print(f"Pruned {pruned} signals (kept {len(kept)}, cutoff {cutoff})")
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Mentor Signal Engine")
    sub = parser.add_subparsers(dest="cmd")

    p_emit = sub.add_parser("emit", help="Emit a mentor signal from event")
    p_emit.add_argument("--event", required=True, help="Event JSON string")
    p_emit.add_argument("--round-id", default=None)
    p_emit.add_argument("--window-size", type=int, default=5)

    p_query = sub.add_parser("query", help="Query signals")
    p_query.add_argument("--since", default=None, help="ISO date filter")
    p_query.add_argument("--summary", action="store_true")

    p_tail = sub.add_parser("tail", help="Show recent signals")
    p_tail.add_argument("--n", type=int, default=5)

    p_prune = sub.add_parser("prune", help="Prune old signals")
    p_prune.add_argument("--keep-days", type=int, default=90)

    args = parser.parse_args()

    if args.cmd == "emit":
        return cmd_emit(args.event, args.round_id, args.window_size)
    elif args.cmd == "query":
        return cmd_query(args.since, args.summary)
    elif args.cmd == "tail":
        return cmd_tail(args.n)
    elif args.cmd == "prune":
        return cmd_prune(args.keep_days)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
