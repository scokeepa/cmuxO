#!/usr/bin/env python3
"""jarvis_mentor_signal.py — Mentor Lane 6축 signal engine (ChromaDB).

SSOT: docs/02-jarvis/palace-memory.md
Schema: docs/02-jarvis/mentor-ontology.md

Usage:
    python3 jarvis_mentor_signal.py emit --event '{"type":"...","data":{...}}'
    python3 jarvis_mentor_signal.py query [--since 2026-04-01] [--summary]
    python3 jarvis_mentor_signal.py prune --keep-days 90
    python3 jarvis_mentor_signal.py tail [--n 5]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import chromadb

PALACE_PATH = os.path.expanduser("~/.cmux-jarvis-palace")
COLLECTION_NAME = "cmux_mentor_signals"

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")

DEFAULT_WEIGHTS = {
    "decomp": 0.20, "verify": 0.22, "orch": 0.20,
    "fail": 0.18, "ctx": 0.10, "meta": 0.10,
}


def _get_collection():
    os.makedirs(PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=PALACE_PATH)
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return client.create_collection(COLLECTION_NAME)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_fit_score(scores, weights=None):
    w = weights or DEFAULT_WEIGHTS
    return round(sum(w.get(a, 0) * scores.get(a, 0) for a in AXES), 2)


def compute_harness_level(fit_score):
    if fit_score < 0.25:
        return 0.0
    level = 1.0 + fit_score * 6.0
    return round(round(level * 2) / 2, 1)


def compute_calibration(evidence_count, confidence):
    if evidence_count < 3 or confidence < 0.5:
        return "insufficient_evidence"
    return "ok"


def detect_antipatterns(scores):
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


def generate_coaching_hint(antipatterns):
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


def _store_signal(signal):
    """Store signal as a drawer in ChromaDB palace."""
    col = _get_collection()
    scores = signal["scores"]
    weakest = min(AXES, key=lambda a: scores.get(a, 1))

    doc = json.dumps(scores) + " " + " ".join(signal.get("antipatterns", []))
    if signal.get("coaching_hint"):
        doc += " " + signal["coaching_hint"]

    meta = {
        "wing": "cmux_mentor",
        "room": weakest,
        "signal_id": signal["signal_id"],
        "ts": signal["ts"],
        "fit_score": signal["fit_score"],
        "harness_level": signal["harness_level"],
        "confidence": signal["confidence"],
        "evidence_count": str(signal.get("evidence_count", 0)),
        "coaching_hint": signal.get("coaching_hint", ""),
        "calibration_note": signal.get("calibration_note", ""),
        "antipatterns": ",".join(signal.get("antipatterns", [])),
    }
    # 축별 score를 metadata에 개별 저장 (L1 생성, report, 검색에 필요)
    for axis in AXES:
        meta[axis] = scores.get(axis, 0.0)

    col.add(ids=[signal["signal_id"]], documents=[doc], metadatas=[meta])


def _read_signals(since=None):
    """Read signals from ChromaDB palace."""
    col = _get_collection()
    try:
        results = col.get(
            where={"wing": "cmux_mentor"},
            include=["metadatas", "documents"],
            limit=10000,
        )
    except Exception:
        return []

    signals = []
    for did, meta in zip(results.get("ids", []), results.get("metadatas", [])):
        ts = meta.get("ts", "")
        if since and ts < since:
            continue
        signals.append({
            "signal_id": did,
            "ts": ts,
            "scores": {a: float(meta.get(a, meta.get(f"score_{a}", 0))) for a in AXES},
            "fit_score": float(meta.get("fit_score", 0)),
            "harness_level": float(meta.get("harness_level", 0)),
            "confidence": float(meta.get("confidence", 0)),
            "evidence_count": int(meta.get("evidence_count", 0)),
            "coaching_hint": meta.get("coaching_hint", ""),
            "calibration_note": meta.get("calibration_note", ""),
            "antipatterns": [p for p in meta.get("antipatterns", "").split(",") if p],
        })

    return sorted(signals, key=lambda s: s["ts"])


def cmd_emit(event_json, round_id=None, window_size=5):
    try:
        event = json.loads(event_json) if isinstance(event_json, str) else event_json
    except json.JSONDecodeError:
        print("Error: invalid JSON event", file=sys.stderr)
        return 1

    data = event.get("data", {})
    scores = data.get("scores", {})
    for axis in AXES:
        scores.setdefault(axis, 0.5)

    evidence_count = data.get("evidence_count", 1)
    confidence = data.get("confidence", 0.5)

    fit_score = compute_fit_score(scores)
    harness_level = compute_harness_level(fit_score)
    calibration = compute_calibration(evidence_count, confidence)
    antipatterns = detect_antipatterns(scores)
    hint = generate_coaching_hint(antipatterns)

    signal = {
        "ts": utc_now(),
        "signal_id": f"sig-{int(time.time())}",
        "round_id": round_id or data.get("round_id", "unknown"),
        "window_size": window_size,
        "scores": {a: round(scores[a], 2) for a in AXES},
        "fit_score": fit_score,
        "harness_level": harness_level,
        "antipatterns": antipatterns,
        "coaching_hint": hint,
        "confidence": round(confidence, 2),
        "evidence_count": evidence_count,
        "calibration_note": calibration,
    }

    _store_signal(signal)
    print(json.dumps(signal, ensure_ascii=False, indent=2))
    return 0


def cmd_query(since=None, summary=False):
    signals = _read_signals(since)

    if summary:
        if not signals:
            print(json.dumps({"count": 0, "message": "no signals found"}))
            return 0

        avg_scores = {}
        for axis in AXES:
            vals = [s["scores"].get(axis, 0) for s in signals]
            avg_scores[axis] = round(sum(vals) / len(vals), 2)

        all_ap = []
        for s in signals:
            all_ap.extend(s.get("antipatterns", []))
        ap_counts = {}
        for p in all_ap:
            ap_counts[p] = ap_counts.get(p, 0) + 1

        result = {
            "count": len(signals),
            "period": {"from": signals[0]["ts"], "to": signals[-1]["ts"]},
            "avg_scores": avg_scores,
            "avg_fit_score": round(sum(s["fit_score"] for s in signals) / len(signals), 2),
            "latest_harness_level": signals[-1].get("harness_level"),
            "antipattern_counts": ap_counts,
            "avg_confidence": round(sum(s["confidence"] for s in signals) / len(signals), 2),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for s in signals:
            print(json.dumps(s, ensure_ascii=False))
    return 0


def cmd_tail(n=5):
    signals = _read_signals()
    for s in signals[-n:]:
        print(json.dumps(s, ensure_ascii=False))
    return 0


def cmd_prune(keep_days=90):
    col = _get_collection()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    results = col.get(where={"wing": "cmux_mentor"}, include=["metadatas"], limit=10000)
    to_delete = [did for did, meta in zip(results.get("ids", []), results.get("metadatas", []))
                 if meta.get("ts", "9999") < cutoff]

    if to_delete:
        col.delete(ids=to_delete)

    print(f"Pruned {len(to_delete)} signals (cutoff {cutoff})")
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Mentor Signal Engine (ChromaDB)")
    sub = parser.add_subparsers(dest="cmd")

    p_emit = sub.add_parser("emit", help="Emit a mentor signal")
    p_emit.add_argument("--event", required=True)
    p_emit.add_argument("--round-id", default=None)
    p_emit.add_argument("--window-size", type=int, default=5)

    p_query = sub.add_parser("query", help="Query signals")
    p_query.add_argument("--since", default=None)
    p_query.add_argument("--summary", action="store_true")

    p_tail = sub.add_parser("tail", help="Recent signals")
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
