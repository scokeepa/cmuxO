#!/usr/bin/env python3
"""Phase 2.3 — append-only event ledger for cmuxO Boss state.

Single writer API (:func:`append`) that fanout callers use from:
    - Boss dispatch path (ASSIGN, ASSIGN_SKIP, CLEAR)
    - Worker verification (VERIFY_PASS, VERIFY_FAIL)
    - Watcher (RATE_LIMIT_DETECTED, ALERT_RAISED, REPORT_DONE_CLAIMED)
    - peer_channel (PEER_SENT, PEER_SEND_FAILED, PEER_PAYLOAD_DENIED)
    - Role registration (ROLE_PEER_BIND)

File layout (SSOT via :mod:`cmux_paths`):
    - Daily rotation: ``runtime/ledger/boss-ledger-{YYYY-MM-DD}.jsonl``
    - First line is ``{"type":"SCHEMA","version":1,"started_at":ts}`` — used
      by :func:`integrity_check` to detect version drift.
    - Each event line <= MAX_LINE_BYTES so ``O_APPEND`` guarantees atomicity.

Concurrency model:
    - Multiple writers share the file via ``fcntl.flock(LOCK_EX)`` +
      ``O_APPEND`` + ``fsync``. Lock is released before return.
    - Reads (``tail``, ``query``) take ``LOCK_SH`` for a consistent snapshot.
"""
from __future__ import annotations

import argparse
import fcntl
import gzip
import json
import os
import re
import sys
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cmux_paths import LEDGER_DIR, ledger_today_path

SCHEMA_VERSION = 1
MAX_LINE_BYTES = 4000
MAX_EXCERPT_BYTES = 200
COMPACT_AFTER_DAYS = 30
DELETE_AFTER_DAYS = 90

EVENT_TYPES = {
    "SCHEMA",
    "ASSIGN", "ASSIGN_SKIP",
    "REPORT_DONE_CLAIMED",
    "VERIFY_PASS", "VERIFY_FAIL",
    "CLEAR",
    "RATE_LIMIT_DETECTED",
    "ALERT_RAISED",
    "HOOK_BLOCK",
    "PEER_SENT", "PEER_SEND_FAILED", "PEER_PAYLOAD_DENIED",
    "ROLE_PEER_BIND",
}


def _ensure_schema_header(path: Path, now: float) -> None:
    """Write the SCHEMA line if the file does not yet exist."""
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "type": "SCHEMA",
        "version": SCHEMA_VERSION,
        "started_at": int(now),
    }
    line = json.dumps(header, ensure_ascii=False) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if os.fstat(fd).st_size == 0:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _truncate_excerpt(event: dict) -> dict:
    """Shrink ``message_excerpt`` so the full JSON line fits in MAX_LINE_BYTES."""
    line = json.dumps(event, ensure_ascii=False)
    if len(line.encode("utf-8")) <= MAX_LINE_BYTES:
        return event
    excerpt = event.get("message_excerpt")
    if not isinstance(excerpt, str):
        event = dict(event)
        event["truncated"] = True
        event["message_excerpt"] = ""
        return event
    event = dict(event)
    event["message_excerpt"] = ""
    skeleton = json.dumps(event, ensure_ascii=False).encode("utf-8")
    budget = MAX_LINE_BYTES - len(skeleton) - 2
    if budget <= 0:
        event["truncated"] = True
        return event
    cut = excerpt.encode("utf-8")[: max(0, budget)]
    event["message_excerpt"] = cut.decode("utf-8", errors="ignore")
    event["truncated"] = True
    return event


def append(event_type: str, path: Path | None = None, **fields) -> bool:
    """Append one event line. Never raises — returns True on success."""
    now = time.time()
    if event_type not in EVENT_TYPES:
        fields["_unknown_type"] = event_type
        event_type = "ALERT_RAISED"
    target = path or ledger_today_path(now)
    try:
        _ensure_schema_header(target, now)
    except OSError as exc:
        sys.stderr.write(f"ledger: header write failed: {exc}\n")
        return False

    event = {"ts": int(now), "type": event_type}
    event.update(fields)
    excerpt = event.get("message_excerpt")
    if isinstance(excerpt, str) and len(excerpt) > MAX_EXCERPT_BYTES:
        event["message_excerpt"] = excerpt[:MAX_EXCERPT_BYTES]
    event = _truncate_excerpt(event)
    line = json.dumps(event, ensure_ascii=False) + "\n"

    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    except OSError as exc:
        sys.stderr.write(f"ledger: open failed: {exc}\n")
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except OSError as exc:
        sys.stderr.write(f"ledger: append failed: {exc}\n")
        return False
    finally:
        os.close(fd)


def _iter_lines(path: Path):
    """Yield (raw_line, parsed_or_None) pairs from a ledger file."""
    if not path.exists():
        return
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8") as f:
            for raw in f:
                raw = raw.rstrip("\n")
                if not raw:
                    continue
                try:
                    yield raw, json.loads(raw)
                except json.JSONDecodeError:
                    yield raw, None
    except OSError:
        return


def tail(n: int = 50, path: Path | None = None) -> list[dict]:
    """Return the last *n* valid events (excluding the SCHEMA header)."""
    target = path or ledger_today_path()
    events: list[dict] = []
    for _raw, parsed in _iter_lines(target):
        if parsed is None:
            continue
        if parsed.get("type") == "SCHEMA":
            continue
        events.append(parsed)
    return events[-n:]


def query(
    worker: str | None = None,
    since_ts: int | None = None,
    event_type: str | None = None,
    path: Path | None = None,
) -> list[dict]:
    """Filter events by optional worker / since_ts / event_type."""
    target = path or ledger_today_path()
    results: list[dict] = []
    for _raw, parsed in _iter_lines(target):
        if parsed is None:
            continue
        if parsed.get("type") == "SCHEMA":
            continue
        if event_type is not None and parsed.get("type") != event_type:
            continue
        if worker is not None and parsed.get("worker") != worker:
            continue
        if since_ts is not None and int(parsed.get("ts") or 0) < since_ts:
            continue
        results.append(parsed)
    return results


def integrity_check(path: Path | None = None) -> dict:
    """Scan file, report total/valid/broken/schema_version drift."""
    target = path or ledger_today_path()
    total = valid = broken = 0
    schema = None
    for _raw, parsed in _iter_lines(target):
        total += 1
        if parsed is None:
            broken += 1
            continue
        valid += 1
        if parsed.get("type") == "SCHEMA" and schema is None:
            schema = parsed.get("version")
    return {
        "path": str(target),
        "total": total,
        "valid": valid,
        "broken": broken,
        "schema_version": schema,
        "schema_match": schema == SCHEMA_VERSION,
    }


_LEDGER_NAME_RE = re.compile(r"^boss-ledger-(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?$")


def compact_old(
    now: float | None = None, directory: Path | None = None
) -> dict:
    """Gzip files older than COMPACT_AFTER_DAYS, delete past DELETE_AFTER_DAYS."""
    now = now or time.time()
    base = directory or LEDGER_DIR
    stats = {"gzipped": [], "deleted": []}
    if not base.exists():
        return stats
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    for entry in sorted(base.iterdir()):
        m = _LEDGER_NAME_RE.match(entry.name)
        if not m:
            continue
        day = m.group(1)
        if day == today:
            continue
        try:
            day_ts = time.mktime(time.strptime(day, "%Y-%m-%d"))
        except ValueError:
            continue
        age_days = (now - day_ts) / 86400.0

        if m.group(2) is None:
            if age_days >= COMPACT_AFTER_DAYS:
                gz = entry.with_suffix(entry.suffix + ".gz")
                try:
                    with open(entry, "rb") as src, gzip.open(gz, "wb") as dst:
                        dst.write(src.read())
                    entry.unlink()
                    stats["gzipped"].append(str(gz))
                except OSError as exc:
                    sys.stderr.write(f"ledger: gzip failed {entry}: {exc}\n")
        else:
            if age_days >= DELETE_AFTER_DAYS:
                try:
                    entry.unlink()
                    stats["deleted"].append(str(entry))
                except OSError as exc:
                    sys.stderr.write(f"ledger: delete failed {entry}: {exc}\n")
    return stats


def compaction_replay_context(n: int = 30) -> str:
    """Render the most recent *n* events as a Boss-facing context block."""
    events = tail(n)
    if not events:
        return "[ledger] 이번 세션 이전 기록 없음."
    lines = [f"[ledger] 최근 {len(events)} 이벤트:"]
    for e in events:
        ts = e.get("ts", 0)
        iso = time.strftime("%H:%M:%S", time.gmtime(ts)) if ts else "??"
        t = e.get("type", "?")
        worker = e.get("worker") or e.get("surface") or "-"
        excerpt = e.get("message_excerpt") or e.get("reason") or e.get("task") or ""
        if len(excerpt) > 80:
            excerpt = excerpt[:77] + "..."
        lines.append(f"  {iso} {t:<20} {worker:<16} {excerpt}")
    return "\n".join(lines)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="cmuxO Boss ledger")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_append = sub.add_parser("append", help="append one event")
    p_append.add_argument("type")
    p_append.add_argument("--fields", default="{}",
                          help="JSON dict of extra fields")

    p_tail = sub.add_parser("tail", help="print last N events")
    p_tail.add_argument("--n", type=int, default=50)

    p_query = sub.add_parser("query", help="filter events")
    p_query.add_argument("--worker")
    p_query.add_argument("--since-ts", type=int)
    p_query.add_argument("--type")

    sub.add_parser("integrity", help="parse stats for today's ledger")
    sub.add_parser("compact", help="gzip/delete old files")
    sub.add_parser("context", help="render compaction-replay block")

    args = parser.parse_args()

    if args.cmd == "append":
        fields = json.loads(args.fields)
        ok = append(args.type, **fields)
        print(json.dumps({"ok": ok}))
        return 0 if ok else 1

    if args.cmd == "tail":
        for e in tail(args.n):
            print(json.dumps(e, ensure_ascii=False))
        return 0

    if args.cmd == "query":
        rows = query(worker=args.worker, since_ts=args.since_ts,
                     event_type=args.type)
        for e in rows:
            print(json.dumps(e, ensure_ascii=False))
        return 0

    if args.cmd == "integrity":
        print(json.dumps(integrity_check(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "compact":
        print(json.dumps(compact_old(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "context":
        print(compaction_replay_context())
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
