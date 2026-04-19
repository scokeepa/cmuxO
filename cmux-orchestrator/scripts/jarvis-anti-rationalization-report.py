#!/usr/bin/env python3
"""jarvis-anti-rationalization-report.py — Phase 2.4 monthly aggregator.

Scans ledger JSONL (last 30 days default) and rewrites the
`<!-- BEGIN AUTO -->` ... `<!-- END AUTO -->` block of
`cmux-orchestrator/references/anti-rationalization.md` with a frequency
table of rationalization-adjacent events.

Counted event types:
    - PEER_SEND_FAILED / PEER_PAYLOAD_DENIED → peer fallback 합리화 징후
    - VERIFY_FAIL → 미검증 commit 시도 횟수
    - ALERT_RAISED → 환경/작업 회피 합리화 알림
    - RATE_LIMIT_DETECTED → 외부 원인 합리화 정당화 건

Usage:
    jarvis-anti-rationalization-report.py              # rewrite AUTO block
    jarvis-anti-rationalization-report.py --print      # dry-run, stdout only
    jarvis-anti-rationalization-report.py --days 30    # window
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cmux_paths import LEDGER_DIR  # noqa: E402

REF_PATH = _SCRIPT_DIR.parent / "references" / "anti-rationalization.md"
BEGIN_MARKER = "<!-- BEGIN AUTO"
END_MARKER = "<!-- END AUTO -->"

TRACKED_TYPES = {
    "PEER_SEND_FAILED",
    "PEER_PAYLOAD_DENIED",
    "VERIFY_FAIL",
    "ALERT_RAISED",
    "RATE_LIMIT_DETECTED",
}

_LEDGER_NAME_RE = re.compile(r"^boss-ledger-(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?$")


def _ledger_files(directory: Path, days: int, now: float) -> list[Path]:
    if not directory.exists():
        return []
    cutoff = now - days * 86400
    hits: list[Path] = []
    for entry in sorted(directory.iterdir()):
        m = _LEDGER_NAME_RE.match(entry.name)
        if not m:
            continue
        try:
            day_ts = time.mktime(time.strptime(m.group(1), "%Y-%m-%d"))
        except ValueError:
            continue
        if day_ts >= cutoff:
            hits.append(entry)
    return hits


def _iter_events(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8") as f:
            for raw in f:
                raw = raw.rstrip("\n")
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def aggregate(days: int = 30, now: float | None = None) -> dict:
    now = now or time.time()
    files = _ledger_files(LEDGER_DIR, days, now)
    by_type: Counter = Counter()
    worker_by_type: dict[str, Counter] = defaultdict(Counter)
    reason_by_type: dict[str, Counter] = defaultdict(Counter)
    for f in files:
        for ev in _iter_events(f):
            t = ev.get("type")
            if t not in TRACKED_TYPES:
                continue
            by_type[t] += 1
            w = ev.get("worker") or ev.get("surface") or "unknown"
            worker_by_type[t][w] += 1
            reason = ev.get("reason") or ev.get("evidence") or ""
            if reason:
                reason_by_type[t][reason[:60]] += 1
    return {
        "days": days,
        "scanned_files": len(files),
        "now": int(now),
        "totals": dict(by_type),
        "per_worker": {k: dict(v) for k, v in worker_by_type.items()},
        "top_reasons": {
            k: v.most_common(3) for k, v in reason_by_type.items()
        },
    }


def render_block(stats: dict) -> str:
    lines = []
    lines.append(
        f"{BEGIN_MARKER} — jarvis-anti-rationalization-report.py 가 주기적으로 갱신 -->"
    )
    lines.append("")
    total = sum(stats["totals"].values())
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(stats["now"]))
    lines.append(
        f"_최종 갱신: {ts} · 윈도: 최근 {stats['days']}일 · 스캔 파일: {stats['scanned_files']} · 이벤트: {total}_"
    )
    lines.append("")
    if total == 0:
        lines.append(
            "_데이터 없음. Phase 2.3 ledger 가 채워지면 월 1회 집계 갱신._"
        )
    else:
        lines.append("### 이벤트 빈도 (최근 30일)")
        lines.append("")
        lines.append("| 이벤트 타입 | 건수 | 상위 worker |")
        lines.append("|-------------|------|--------------|")
        for t in sorted(stats["totals"], key=lambda k: -stats["totals"][k]):
            count = stats["totals"][t]
            workers = stats["per_worker"].get(t, {})
            top = ", ".join(
                f"{w}({c})"
                for w, c in sorted(workers.items(), key=lambda x: -x[1])[:3]
            ) or "-"
            lines.append(f"| `{t}` | {count} | {top} |")
        has_reasons = any(stats["top_reasons"].get(t) for t in stats["totals"])
        if has_reasons:
            lines.append("")
            lines.append("### 상위 원인 (reason/evidence 필드)")
            lines.append("")
            for t in sorted(stats["totals"], key=lambda k: -stats["totals"][k]):
                rs = stats["top_reasons"].get(t) or []
                if not rs:
                    continue
                lines.append(f"- **{t}**")
                for reason, cnt in rs:
                    lines.append(f"  - `{reason}` ×{cnt}")
    lines.append("")
    lines.append(END_MARKER)
    return "\n".join(lines)


def rewrite(ref_path: Path, block: str) -> bool:
    if not ref_path.exists():
        sys.stderr.write(f"missing reference: {ref_path}\n")
        return False
    content = ref_path.read_text(encoding="utf-8")
    pat = re.compile(
        r"<!--\s*BEGIN AUTO.*?<!--\s*END AUTO\s*-->",
        re.DOTALL,
    )
    if not pat.search(content):
        sys.stderr.write(
            f"markers not found in {ref_path} — "
            "expected '<!-- BEGIN AUTO ... --> ... <!-- END AUTO -->'\n"
        )
        return False
    new = pat.sub(lambda _m: block, content)
    if new == content:
        return True
    tmp = ref_path.with_suffix(ref_path.suffix + ".tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, ref_path)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--print", dest="dry", action="store_true",
                    help="print block without rewriting the reference file")
    ap.add_argument("--ref", default=str(REF_PATH))
    args = ap.parse_args(argv)

    stats = aggregate(days=args.days)
    block = render_block(stats)
    if args.dry:
        print(block)
        return 0
    ok = rewrite(Path(args.ref), block)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
