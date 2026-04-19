#!/usr/bin/env python3
"""Phase 2.2 — token/cache observability for cmux orchestration.

Parses Claude Code JSONL transcripts at ``~/.claude/projects/<slug>/<uuid>.jsonl``
and aggregates per-cwd usage totals (input/output/cache tokens, turns, session
count) into ``runtime/telemetry/token-metrics.json``.

Public API:
    - collect_surface_metrics(surface_id, cwd, ai='claude') -> dict
    - collect_all(surfaces=None) -> dict (writes TOKEN_METRICS_FILE)
    - load() -> dict (read the latest written metrics)
    - generate_alerts(metrics) -> list[dict]

CLI:
    token_observer.py collect [--surfaces <json>]
    token_observer.py dump
    token_observer.py alerts
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable

_SCRIPT_DIR = Path(__file__).parent.resolve()
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cmux_paths import (
    TELEMETRY_DIR,
    TOKEN_METRICS_FILE,
    claude_projects_dir,
    cwd_to_slug,
)

SCHEMA_VERSION = 1
MAX_TAIL_BYTES = 10 * 1024 * 1024  # 10 MiB — plan §3.4 / §5.1 case 8
MAX_TRANSCRIPTS_PER_SLUG = 3        # most recent N .jsonl files per project

CACHE_HIT_LOW_THRESHOLD = 0.50      # plan §3.5
CACHE_HIT_LOW_MIN_TURNS = 10
CONTEXT_LARGE_THRESHOLD = 200_000


def _now() -> int:
    return int(time.time())


def _iter_jsonl_tail(path: Path, max_bytes: int = MAX_TAIL_BYTES) -> Iterable[dict]:
    """Yield records from the tail of a JSONL file. Skips malformed lines."""
    try:
        size = path.stat().st_size
    except OSError:
        return
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
            f.readline()  # drop partial first line after seek
        for raw in f:
            try:
                yield json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue


def _find_transcripts(projects_dir: Path, cwd: str) -> list[Path]:
    slug = cwd_to_slug(cwd)
    d = projects_dir / slug
    if not d.exists():
        return []
    return sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def _empty_metrics(surface_id: str, ai: str) -> dict:
    return {
        "surface": surface_id,
        "ai": ai,
        "input_tokens_total": 0,
        "output_tokens_total": 0,
        "cache_read_total": 0,
        "cache_creation_total": 0,
        "cache_hit_ratio": None,
        "turns": 0,
        "last_turn_ts": None,
        "sessions": 0,
    }


def collect_surface_metrics(
    surface_id: str,
    cwd: str,
    ai: str = "claude",
    projects_dir: Path | None = None,
) -> dict:
    """Aggregate token metrics for one surface's recent transcripts.

    Only Claude Code produces JSONL transcripts today; other AIs return an
    empty metric dict with ``cache_hit_ratio=None``.
    """
    out = _empty_metrics(surface_id, ai)
    if ai != "claude":
        return out

    projects_dir = projects_dir or claude_projects_dir()
    transcripts = _find_transcripts(projects_dir, cwd)
    if not transcripts:
        out["error"] = "no transcript found"
        return out

    seen_sessions: set[str] = set()
    for path in transcripts[:MAX_TRANSCRIPTS_PER_SLUG]:
        for rec in _iter_jsonl_tail(path):
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            if not usage:
                continue
            out["input_tokens_total"] += int(usage.get("input_tokens") or 0)
            out["output_tokens_total"] += int(usage.get("output_tokens") or 0)
            out["cache_read_total"] += int(usage.get("cache_read_input_tokens") or 0)
            out["cache_creation_total"] += int(usage.get("cache_creation_input_tokens") or 0)
            out["turns"] += 1
            ts = rec.get("timestamp") or rec.get("ts")
            if ts is not None:
                out["last_turn_ts"] = ts
            sid = rec.get("sessionId") or rec.get("session_id")
            if sid:
                seen_sessions.add(sid)

    denom = (
        out["input_tokens_total"]
        + out["cache_creation_total"]
        + out["cache_read_total"]
    )
    if denom > 0:
        out["cache_hit_ratio"] = round(out["cache_read_total"] / denom, 4)
    out["sessions"] = len(seen_sessions)
    return out


def _discover_project_slugs(projects_dir: Path) -> list[tuple[str, str]]:
    """Fall back to scanning ``~/.claude/projects/`` when no surface list is
    provided. Returns ``[(slug, cwd_guess)]`` sorted by most-recent activity.
    """
    if not projects_dir.exists():
        return []
    out: list[tuple[str, str, float]] = []
    for child in projects_dir.iterdir():
        if not child.is_dir():
            continue
        jsonl = sorted(child.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not jsonl:
            continue
        cwd = "/" + child.name.lstrip("-").replace("-", "/")
        out.append((child.name, cwd, jsonl[0].stat().st_mtime))
    out.sort(key=lambda t: t[2], reverse=True)
    return [(slug, cwd) for slug, cwd, _ in out]


def collect_all(
    surfaces: list[dict] | None = None,
    projects_dir: Path | None = None,
    metrics_file: Path | None = None,
) -> dict:
    """Gather metrics for every known surface (or all projects) and persist.

    ``surfaces`` is a list of ``{"surface_id": ..., "cwd": ..., "ai": ...}``
    dicts. When ``None``, scan ``~/.claude/projects/`` and key by slug.
    """
    projects_dir = projects_dir or claude_projects_dir()
    metrics_file = metrics_file or TOKEN_METRICS_FILE

    entries: dict[str, dict] = {}
    if surfaces is None:
        for slug, cwd in _discover_project_slugs(projects_dir):
            sid = f"slug:{slug}"
            m = collect_surface_metrics(sid, cwd, ai="claude", projects_dir=projects_dir)
            m["cwd"] = cwd
            m["slug"] = slug
            entries[sid] = m
    else:
        for s in surfaces:
            sid = s.get("surface_id") or s.get("surface") or "unknown"
            cwd = s.get("cwd") or ""
            ai = s.get("ai") or "claude"
            if not cwd:
                continue
            m = collect_surface_metrics(sid, cwd, ai=ai, projects_dir=projects_dir)
            m["cwd"] = cwd
            m["slug"] = cwd_to_slug(cwd)
            entries[sid] = m

    payload = {
        "version": SCHEMA_VERSION,
        "updated_at": _now(),
        "surfaces": entries,
    }
    _atomic_write(metrics_file, payload)
    return payload


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    with open(lock, "a+") as lockfd:
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        try:
            fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
                os.replace(tmp, path)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        finally:
            fcntl.flock(lockfd, fcntl.LOCK_UN)


def load(metrics_file: Path | None = None) -> dict:
    metrics_file = metrics_file or TOKEN_METRICS_FILE
    if not metrics_file.exists():
        return {"version": SCHEMA_VERSION, "updated_at": 0, "surfaces": {}}
    try:
        with open(metrics_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"version": SCHEMA_VERSION, "updated_at": 0, "surfaces": {}}


def generate_alerts(metrics: dict) -> list[dict]:
    """Plan §3.5 — flag surfaces with low cache hit or oversized context."""
    alerts: list[dict] = []
    for sid, m in (metrics.get("surfaces") or {}).items():
        ratio = m.get("cache_hit_ratio")
        turns = m.get("turns") or 0
        input_total = m.get("input_tokens_total") or 0
        if (
            ratio is not None
            and ratio < CACHE_HIT_LOW_THRESHOLD
            and turns >= CACHE_HIT_LOW_MIN_TURNS
        ):
            alerts.append({
                "surface": sid,
                "severity": "MEDIUM",
                "kind": "CACHE_INEFFICIENT",
                "message": f"cache_hit={ratio:.1%} turns={turns} — Claude 캐시 히트 낮음",
            })
        if input_total > CONTEXT_LARGE_THRESHOLD:
            alerts.append({
                "surface": sid,
                "severity": "MEDIUM",
                "kind": "CONTEXT_LARGE",
                "message": f"input_total={input_total:,} — 컨텍스트 비대",
            })
    return alerts


def _cli() -> int:
    parser = argparse.ArgumentParser(description="cmux token/cache observer")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_collect = sub.add_parser("collect", help="gather + write metrics")
    p_collect.add_argument("--surfaces", type=str, default=None,
                           help="JSON array of {surface_id,cwd,ai} dicts")
    sub.add_parser("dump", help="print last written metrics")
    sub.add_parser("alerts", help="print alerts from last metrics")
    args = parser.parse_args()

    if args.cmd == "collect":
        surfaces = None
        if args.surfaces:
            try:
                surfaces = json.loads(args.surfaces)
                if not isinstance(surfaces, list):
                    print("--surfaces must be a JSON array", file=sys.stderr)
                    return 2
            except json.JSONDecodeError as exc:
                print(f"invalid --surfaces JSON: {exc}", file=sys.stderr)
                return 2
        payload = collect_all(surfaces=surfaces)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "dump":
        print(json.dumps(load(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "alerts":
        print(json.dumps(generate_alerts(load()), ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
