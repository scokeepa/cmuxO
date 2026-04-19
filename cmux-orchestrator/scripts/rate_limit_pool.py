#!/usr/bin/env python3
"""rate_limit_pool.py — SSOT for cmux rate-limited surface pool (GATE W-2).

Watcher detects RATE_LIMITED surfaces and upserts entries here; Boss/dispatch
scripts read this pool before assigning tasks so rate-limited surfaces are
skipped. Entries auto-expire via 3-tier GC (lazy on read/write, explicit
watcher scan, dispatch-time check).

Schema (version 1):
  {
    "version": 1,
    "updated_at": <unix_ts>,
    "entries": {
      "<surface_id>": {
        "ai": "claude|gemini|codex|...",
        "detected_at": <unix_ts>,
        "reset_at":    <unix_ts>,
        "reason":      "usage_limit|429|...",
        "message_excerpt": "<<=200 chars>"
      }
    }
  }

File path resolves via cmux_paths.RATE_LIMITED_POOL_FILE; override with
CMUX_RATE_LIMITED_POOL_FILE env var (primarily for tests).
Concurrency: fcntl.flock on a sibling `<pool>.lock` file (flock on the pool
itself breaks because atomic rename replaces the inode).
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from cmux_paths import RATE_LIMITED_POOL_FILE as _DEFAULT_POOL_FILE
except ImportError:
    _DEFAULT_POOL_FILE = Path("/tmp/cmux-rate-limited-pool.json")


def _resolve_pool_file() -> Path:
    override = os.environ.get("CMUX_RATE_LIMITED_POOL_FILE")
    if override:
        return Path(override).expanduser()
    return _DEFAULT_POOL_FILE


POOL_FILE = _resolve_pool_file()
MAX_ENTRIES = 100
DEFAULT_TTL = 3600


def _lock_path() -> Path:
    p = _resolve_pool_file()
    return p.with_suffix(p.suffix + ".lock")


def _now() -> int:
    return int(time.time())


def _empty() -> dict:
    return {"version": 1, "updated_at": _now(), "entries": {}}


def _load_from_disk() -> dict:
    pool = _resolve_pool_file()
    if not pool.exists():
        return _empty()
    try:
        raw = pool.read_text()
    except OSError:
        return _empty()
    if not raw:
        return _empty()
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or "entries" not in data:
            raise ValueError("missing entries key")
        if not isinstance(data["entries"], dict):
            raise ValueError("entries not a dict")
        return data
    except (json.JSONDecodeError, ValueError) as exc:
        try:
            backup = pool.with_suffix(".json.corrupt")
            backup.write_text(raw)
        except OSError:
            pass
        print(
            f"[rate_limit_pool] corrupt pool file {pool}: {exc} — reinitializing",
            file=sys.stderr,
        )
        return _empty()


def _atomic_write(data: dict) -> None:
    pool = _resolve_pool_file()
    pool.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(pool.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, pool)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _gc_inplace(entries: dict, now: int | None = None) -> int:
    now = now if now is not None else _now()
    expired = [k for k, v in entries.items() if v.get("reset_at", 0) <= now]
    for k in expired:
        del entries[k]
    return len(expired)


def _evict_overflow(entries: dict) -> int:
    if len(entries) <= MAX_ENTRIES:
        return 0
    sorted_items = sorted(entries.items(), key=lambda kv: kv[1].get("detected_at", 0))
    drop = len(entries) - MAX_ENTRIES
    for k, _ in sorted_items[:drop]:
        del entries[k]
    return drop


def _with_pool(mutate):
    pool = _resolve_pool_file()
    pool.parent.mkdir(parents=True, exist_ok=True)
    lock = _lock_path()
    with open(lock, "a+") as lockfd:
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        try:
            data = _load_from_disk()
            result = mutate(data)
            data["updated_at"] = _now()
            _atomic_write(data)
            return result
        finally:
            fcntl.flock(lockfd, fcntl.LOCK_UN)


def upsert_entry(
    surface_id: str,
    ai: str,
    reason: str,
    excerpt: str,
    ttl_seconds: int = DEFAULT_TTL,
) -> dict:
    """Insert or overwrite a rate-limited entry. Runs lazy GC + overflow eviction."""

    def _m(data: dict) -> dict:
        now = _now()
        _gc_inplace(data["entries"], now)
        data["entries"][surface_id] = {
            "ai": ai,
            "detected_at": now,
            "reset_at": now + int(ttl_seconds),
            "reason": reason,
            "message_excerpt": (excerpt or "")[:200],
        }
        _evict_overflow(data["entries"])
        return data["entries"][surface_id]

    return _with_pool(_m)


def is_limited(surface_id: str) -> bool:
    """Return True iff `surface_id` has a live (non-expired) entry."""

    def _m(data: dict) -> bool:
        _gc_inplace(data["entries"])
        return surface_id in data["entries"]

    return _with_pool(_m)


def list_limited() -> list[dict]:
    """Return all live entries as a list, each merged with its surface id."""

    def _m(data: dict) -> list[dict]:
        _gc_inplace(data["entries"])
        return [{"surface": k, **v} for k, v in data["entries"].items()]

    return _with_pool(_m)


def gc_expired() -> int:
    """Explicit GC trigger. Returns number of entries removed."""

    def _m(data: dict) -> int:
        return _gc_inplace(data["entries"])

    return _with_pool(_m)


def load() -> dict:
    """Best-effort read without acquiring the lock. Use for read-only inspection."""
    return _load_from_disk()


def _cli(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "Usage: rate_limit_pool.py <command> [args]\n"
            "  check <surface_id>     exit 2 if rate-limited, else exit 0\n"
            "  list                   print JSON array of live entries\n"
            "  gc                     run GC, print removed count\n"
            "  dump                   print raw pool JSON"
        )
        return 0
    cmd = argv[0]
    if cmd == "check":
        if len(argv) < 2:
            print("check requires <surface_id>", file=sys.stderr)
            return 1
        return 2 if is_limited(argv[1]) else 0
    if cmd == "list":
        print(json.dumps(list_limited(), indent=2))
        return 0
    if cmd == "gc":
        print(gc_expired())
        return 0
    if cmd == "dump":
        print(json.dumps(load(), indent=2))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
