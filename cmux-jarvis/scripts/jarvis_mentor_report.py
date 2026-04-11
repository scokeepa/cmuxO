#!/usr/bin/env python3
"""jarvis_mentor_report.py — AI 협업 하네스 개선 리포트 생성기.

SSOT: docs/jarvis/architecture/mentor-lane.md (트리거, 표본 부족 보류)
Schema: docs/jarvis/architecture/mentor-ontology.md (6축, Fit Score, Gate)
Privacy: docs/jarvis/architecture/mentor-privacy-policy.md (raw quote 최소화)

Usage:
    python3 jarvis_mentor_report.py generate [--since YYYY-MM-DD]
    python3 jarvis_mentor_report.py timeline
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MENTOR_DIR = Path.home() / ".claude" / "cmux-jarvis" / "mentor"
SIGNALS_FILE = MENTOR_DIR / "signals.jsonl"
REPORTS_DIR = MENTOR_DIR / "reports"
TIMELINE_FILE = MENTOR_DIR / "TIMELINE.md"

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")
AXIS_NAMES = {"decomp": "DECOMP", "verify": "VERIFY", "orch": "ORCH",
              "fail": "FAIL", "ctx": "CTX", "meta": "META"}
WEIGHTS = {"decomp": 0.20, "verify": 0.22, "orch": 0.20,
           "fail": 0.18, "ctx": 0.10, "meta": 0.10}

MIN_SIGNALS = 3

GATE_CONDITIONS = [
    ("L3", "context_specificity > 0.5", lambda s: s.get("ctx", 0) > 0.5),
    ("L4", "verification > 0.15 AND correction > 0.05", lambda s: s.get("verify", 0) > 0.15),
    ("L5", "tool_diversity + strategic > 0.05", lambda s: s.get("orch", 0) > 0.5),
]

ANTIPATTERN_HINTS = {
    "fix_me_syndrome": "오류 메시지를 먼저 읽고 원인을 분석한 뒤 지시하세요.",
    "context_skip": "파일 경로와 제약 조건을 명시하면 정확도가 올라갑니다.",
    "verification_skip": "완료 조건을 1줄 추가하면 검증 누락이 줄어듭니다.",
    "over_partition": "단일 AI로 충분한 작업인지 먼저 확인하세요.",
    "scope_creep": "작업 범위를 고정하고 추가 요청은 다음 round로 분리하세요.",
}


def utc_now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_signals(since=None):
    if not SIGNALS_FILE.exists():
        return []
    signals = []
    with open(SIGNALS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
                if since and s.get("ts", "") < since:
                    continue
                signals.append(s)
            except json.JSONDecodeError:
                continue
    return signals


def _compute_avg_scores(signals):
    avg = {}
    for axis in AXES:
        values = [s["scores"].get(axis, 0) for s in signals]
        avg[axis] = round(sum(values) / len(values), 2) if values else 0
    return avg


def _compute_trend(signals):
    """Compare first half vs second half fit_scores."""
    if len(signals) < 4:
        return {}
    mid = len(signals) // 2
    first_avg = sum(s["fit_score"] for s in signals[:mid]) / mid
    second_avg = sum(s["fit_score"] for s in signals[mid:]) / (len(signals) - mid)
    trends = {}
    for axis in AXES:
        first = sum(s["scores"].get(axis, 0) for s in signals[:mid]) / mid
        second = sum(s["scores"].get(axis, 0) for s in signals[mid:]) / (len(signals) - mid)
        diff = second - first
        if diff > 0.05:
            trends[axis] = "↑"
        elif diff < -0.05:
            trends[axis] = "↓"
        else:
            trends[axis] = "→"
    return trends


def _collect_antipatterns(signals):
    counts = {}
    for s in signals:
        for p in s.get("antipatterns", []):
            counts[p] = counts.get(p, 0) + 1
    return counts


def _find_previous_report():
    """Find most recent previous report for trend comparison."""
    if not REPORTS_DIR.exists():
        return None
    reports = sorted(REPORTS_DIR.glob("report-*.md"))
    return reports[-1] if reports else None


def generate_report(signals):
    """Generate mentor report markdown from signals."""
    avg_scores = _compute_avg_scores(signals)
    avg_fit = round(sum(s["fit_score"] for s in signals) / len(signals), 2)
    latest_level = signals[-1].get("harness_level", "?")
    avg_conf = round(sum(s["confidence"] for s in signals) / len(signals), 2)
    trends = _compute_trend(signals)
    ap_counts = _collect_antipatterns(signals)

    period_start = signals[0].get("ts", "?")[:10]
    period_end = signals[-1].get("ts", "?")[:10]

    sorted_axes = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
    strong = sorted_axes[:2]
    weak = sorted_axes[-2:]

    lines = [
        f"# AI 협업 하네스 개선 리포트: {period_start} ~ {period_end}",
        "",
        "## 요약",
        f"- 기간: {period_start} ~ {period_end}",
        f"- 분석 신호: {len(signals)}개",
        f"- 현재 Harness Level: L{latest_level}",
        f"- 평균 Fit Score: {avg_fit}",
        f"- 평균 신뢰도: {avg_conf}",
        "",
        "## 6축 분석",
        "| 차원 | 점수 | 가중치 | 가중점수 | 추세 |",
        "|------|------|--------|----------|------|",
    ]

    total_weighted = 0
    for axis in AXES:
        w = WEIGHTS[axis]
        ws = round(avg_scores[axis] * w, 3)
        total_weighted += ws
        trend = trends.get(axis, "→")
        lines.append(f"| {AXIS_NAMES[axis]} | {avg_scores[axis]} | {int(w*100)}% | {ws} | {trend} |")
    lines.append(f"| **종합** | | | **{round(total_weighted, 3)}** | |")

    lines.extend(["", "## 강점"])
    for axis, score in strong:
        lines.append(f"- {AXIS_NAMES[axis]} ({score})")

    lines.extend(["", "## 개선 필요"])
    for axis, score in weak:
        hint = ANTIPATTERN_HINTS.get(f"{axis}_skip", "")
        lines.append(f"- {AXIS_NAMES[axis]} ({score})" + (f": {hint}" if hint else ""))

    if ap_counts:
        lines.extend(["", "## 안티패턴 현황", "| 패턴 | 빈도 |", "|------|------|"])
        for p, c in sorted(ap_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {p} | {c}회 |")

    lines.extend(["", "## Gate 조건 충족 상태", "| Gate | 조건 | 상태 |", "|------|------|------|"])
    for gate_name, condition, check_fn in GATE_CONDITIONS:
        status = "통과" if check_fn(avg_scores) else "미충족"
        lines.append(f"| {gate_name} | {condition} | {status} |")

    lines.extend(["", "## 다음 단계 제안"])
    suggestions = []
    for axis, score in weak[:2]:
        hint = ANTIPATTERN_HINTS.get(f"{axis}_skip", "")
        if hint:
            suggestions.append(hint)
    if not suggestions:
        suggestions.append("현재 균형 잡힌 상태입니다. 기존 습관을 유지하세요.")
    for i, s in enumerate(suggestions[:3], 1):
        lines.append(f"{i}. {s}")

    lines.extend([
        "",
        "---",
        f"생성일: {utc_now_str()}",
        "이 리포트는 사용자를 평가하는 문서가 아니라 AI 협업 하네스 개선을 위한 참고자료입니다.",
    ])

    return "\n".join(lines), avg_scores, avg_fit, latest_level, ap_counts


def _update_timeline(avg_scores, latest_level, ap_counts, note=""):
    """Append a row to TIMELINE.md."""
    MENTOR_DIR.mkdir(parents=True, exist_ok=True)

    header = "| 날짜 | 레벨 | DECOMP | VERIFY | ORCH | FAIL | CTX | META | 안티패턴 | 변화 포인트 |"
    separator = "|------|------|--------|--------|------|------|-----|------|---------|------------|"

    if not TIMELINE_FILE.exists():
        with open(TIMELINE_FILE, "w") as f:
            f.write("# 성장 타임라인\n\n")
            f.write(header + "\n")
            f.write(separator + "\n")

    ap_str = ", ".join(ap_counts.keys()) if ap_counts else "-"
    row = f"| {utc_now_str()} | L{latest_level} | {avg_scores.get('decomp',0)} | {avg_scores.get('verify',0)} | {avg_scores.get('orch',0)} | {avg_scores.get('fail',0)} | {avg_scores.get('ctx',0)} | {avg_scores.get('meta',0)} | {ap_str} | {note or '-'} |"

    with open(TIMELINE_FILE, "a") as f:
        f.write(row + "\n")

    return row


def cmd_generate(since=None):
    """Generate mentor report."""
    signals = _read_signals(since)

    if len(signals) < MIN_SIGNALS:
        print(f"표본 부족으로 리포트를 보류합니다. (현재 {len(signals)}개, 최소 {MIN_SIGNALS}개 필요)")
        return 0

    report_text, avg_scores, avg_fit, latest_level, ap_counts = generate_report(signals)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f"report-{utc_now_str()}.md"
    report_file.write_text(report_text, encoding="utf-8")
    print(f"Report saved: {report_file}")

    # Determine change note
    prev = _find_previous_report()
    note = "첫 리포트" if not prev else "정기 리포트"
    row = _update_timeline(avg_scores, latest_level, ap_counts, note)
    print(f"TIMELINE updated: {row[:60]}...")

    return 0


def cmd_timeline():
    """Show current TIMELINE."""
    if not TIMELINE_FILE.exists():
        print("TIMELINE이 아직 없습니다. report를 먼저 생성하세요.")
        return 0
    print(TIMELINE_FILE.read_text(encoding="utf-8"))
    return 0


def main():
    parser = argparse.ArgumentParser(description="JARVIS Mentor Report Generator")
    sub = parser.add_subparsers(dest="cmd")

    p_gen = sub.add_parser("generate", help="Generate mentor report")
    p_gen.add_argument("--since", default=None, help="ISO date filter")

    sub.add_parser("timeline", help="Show TIMELINE")

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
