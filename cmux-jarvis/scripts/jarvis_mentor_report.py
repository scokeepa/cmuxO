#!/usr/bin/env python3
"""jarvis_mentor_report.py — AI 협업 하네스 개선 리포트 (ChromaDB).

SSOT: docs/02-jarvis/mentor-lane.md
Schema: docs/02-jarvis/mentor-ontology.md
vibe-sunsang growth-analyst 패턴 적용, 결과를 mempalace palace에 저장.

Usage:
    python3 jarvis_mentor_report.py generate [--since YYYY-MM-DD]
    python3 jarvis_mentor_report.py timeline
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import chromadb

PALACE_PATH = os.path.expanduser("~/.cmux-jarvis-palace")
COLLECTION_NAME = "cmux_mentor_signals"

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")
WEIGHTS = {"decomp": 0.20, "verify": 0.22, "orch": 0.20, "fail": 0.18, "ctx": 0.10, "meta": 0.10}
MIN_SIGNALS = 3

ANTIPATTERN_HINTS = {
    "fix_me_syndrome": "오류 메시지를 먼저 읽고 원인을 분석한 뒤 지시하세요.",
    "context_skip": "파일 경로와 제약 조건을 명시하면 정확도가 올라갑니다.",
    "verification_skip": "완료 조건을 1줄 추가하면 검증 누락이 줄어듭니다.",
    "over_partition": "단일 AI로 충분한 작업인지 먼저 확인하세요.",
    "scope_creep": "작업 범위를 고정하고 추가 요청은 다음 round로 분리하세요.",
}

GATE_CONDITIONS = [
    ("L3", "context_specificity > 0.5", lambda s: s.get("ctx", 0) > 0.5),
    ("L4", "verification > 0.15", lambda s: s.get("verify", 0) > 0.15),
    ("L5", "orchestration > 0.5", lambda s: s.get("orch", 0) > 0.5),
]


def _get_collection():
    os.makedirs(PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=PALACE_PATH)
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return client.create_collection(COLLECTION_NAME)


def _read_signals(since=None):
    col = _get_collection()
    try:
        results = col.get(where={"wing": "cmux_mentor"}, include=["metadatas"], limit=10000)
    except Exception:
        return []

    signals = []
    for meta in results.get("metadatas", []):
        ts = meta.get("ts", "")
        if since and ts < since:
            continue
        scores = {}
        for a in AXES:
            v = meta.get(a, meta.get(f"score_{a}", 0))
            scores[a] = float(v) if v else 0.0
        signals.append({
            "ts": ts,
            "scores": scores,
            "fit_score": float(meta.get("fit_score", 0)),
            "harness_level": float(meta.get("harness_level", 0)),
            "confidence": float(meta.get("confidence", 0)),
            "antipatterns": [p for p in meta.get("antipatterns", "").split(",") if p],
            "calibration_note": meta.get("calibration_note", ""),
        })
    return sorted(signals, key=lambda s: s["ts"])


def _compute_trend(signals):
    if len(signals) < 4:
        return {}
    mid = len(signals) // 2
    trends = {}
    for axis in AXES:
        first = sum(s["scores"].get(axis, 0) for s in signals[:mid]) / mid
        second = sum(s["scores"].get(axis, 0) for s in signals[mid:]) / (len(signals) - mid)
        diff = second - first
        trends[axis] = "↑" if diff > 0.05 else ("↓" if diff < -0.05 else "→")
    return trends


def _store_report(report_text):
    """Store report as a drawer in cmux_reports wing."""
    col = _get_collection()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_id = f"report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    meta = {"wing": "cmux_reports", "room": "weekly", "ts": ts}
    try:
        col.add(ids=[doc_id], documents=[report_text[:10000]], metadatas=[meta])
    except Exception:
        pass  # duplicate ID = report already generated today


def _store_timeline_row(row_text):
    """Store TIMELINE row as a drawer in cmux_timeline wing."""
    col = _get_collection()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_id = f"timeline-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    meta = {"wing": "cmux_timeline", "room": "entries", "ts": ts}
    try:
        col.add(ids=[doc_id], documents=[row_text], metadatas=[meta])
    except Exception:
        pass


def generate_report(signals):
    avg_scores = {}
    for axis in AXES:
        vals = [s["scores"].get(axis, 0) for s in signals]
        avg_scores[axis] = round(sum(vals) / len(vals), 2) if vals else 0

    avg_fit = round(sum(s["fit_score"] for s in signals) / len(signals), 2)
    latest_level = signals[-1].get("harness_level", "?")
    avg_conf = round(sum(s["confidence"] for s in signals) / len(signals), 2)
    trends = _compute_trend(signals)

    ap_counts = {}
    for s in signals:
        for p in s.get("antipatterns", []):
            ap_counts[p] = ap_counts.get(p, 0) + 1

    period_start = signals[0].get("ts", "?")[:10]
    period_end = signals[-1].get("ts", "?")[:10]
    sorted_axes = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)

    lines = [
        f"# AI 협업 하네스 개선 리포트: {period_start} ~ {period_end}",
        "", "## 요약",
        f"- 기간: {period_start} ~ {period_end}",
        f"- 분석 신호: {len(signals)}개",
        f"- 현재 Harness Level: L{latest_level}",
        f"- 평균 Fit Score: {avg_fit}",
        f"- 평균 신뢰도: {avg_conf}",
        "", "## 6축 분석",
        "| 차원 | 점수 | 가중치 | 가중점수 | 추세 |",
        "|------|------|--------|----------|------|",
    ]

    total_w = 0
    for axis in AXES:
        w = WEIGHTS[axis]
        ws = round(avg_scores[axis] * w, 3)
        total_w += ws
        lines.append(f"| {axis.upper()} | {avg_scores[axis]} | {int(w*100)}% | {ws} | {trends.get(axis, '→')} |")
    lines.append(f"| **종합** | | | **{round(total_w, 3)}** | |")

    lines.extend(["", "## 강점"])
    for a, v in sorted_axes[:2]:
        lines.append(f"- {a.upper()} ({v})")

    lines.extend(["", "## 개선 필요"])
    for a, v in sorted_axes[-2:]:
        hint = ANTIPATTERN_HINTS.get(f"{a}_skip", "")
        lines.append(f"- {a.upper()} ({v})" + (f": {hint}" if hint else ""))

    if ap_counts:
        lines.extend(["", "## 안티패턴", "| 패턴 | 빈도 |", "|------|------|"])
        for p, c in sorted(ap_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {p} | {c}회 |")

    lines.extend(["", "## Gate 조건", "| Gate | 조건 | 상태 |", "|------|------|------|"])
    for gn, cond, fn in GATE_CONDITIONS:
        st = "통과" if fn(avg_scores) else "미충족"
        lines.append(f"| {gn} | {cond} | {st} |")

    lines.extend(["", "## 다음 단계"])
    suggestions = [ANTIPATTERN_HINTS.get(f"{a}_skip", "") for a, _ in sorted_axes[-2:] if ANTIPATTERN_HINTS.get(f"{a}_skip")]
    if not suggestions:
        suggestions = ["현재 균형 잡힌 상태입니다."]
    for i, s in enumerate(suggestions[:3], 1):
        lines.append(f"{i}. {s}")

    lines.extend(["", "---",
        f"생성일: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "이 리포트는 사용자를 평가하는 문서가 아니라 AI 협업 하네스 개선을 위한 참고자료입니다."])

    return "\n".join(lines), avg_scores, avg_fit, latest_level, ap_counts


def cmd_generate(since=None):
    signals = _read_signals(since)
    if len(signals) < MIN_SIGNALS:
        print(f"표본 부족으로 리포트를 보류합니다. (현재 {len(signals)}개, 최소 {MIN_SIGNALS}개 필요)")
        return 0

    report_text, avg_scores, avg_fit, level, ap_counts = generate_report(signals)
    _store_report(report_text)

    ap_str = ", ".join(ap_counts.keys()) if ap_counts else "-"
    timeline_row = f"| {datetime.now(timezone.utc).strftime('%Y-%m-%d')} | L{level} | {' | '.join(str(avg_scores.get(a, 0)) for a in AXES)} | {ap_str} | report |"
    _store_timeline_row(timeline_row)

    print(report_text)
    print(f"\n[TIMELINE row stored in palace]")
    return 0


def cmd_timeline():
    col = _get_collection()
    try:
        results = col.get(where={"wing": "cmux_timeline"}, include=["documents", "metadatas"], limit=100)
    except Exception:
        print("No timeline entries.")
        return 0

    entries = list(zip(results.get("metadatas", []), results.get("documents", [])))
    entries.sort(key=lambda x: x[0].get("ts", ""))

    print("# 성장 타임라인\n")
    print(f"| 날짜 | 레벨 | {'|'.join(a.upper() for a in AXES)} | 안티패턴 | 비고 |")
    print(f"|------|------| {'|'.join('------' for _ in AXES)} |---------|------|")
    for _, doc in entries:
        print(doc)
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Mentor Report (ChromaDB)")
    sub = parser.add_subparsers(dest="cmd")
    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--since", default=None)
    sub.add_parser("timeline")

    args = parser.parse_args()
    if args.cmd == "generate":
        return cmd_generate(args.since)
    elif args.cmd == "timeline":
        return cmd_timeline()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
