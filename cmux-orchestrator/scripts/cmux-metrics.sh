#!/bin/bash
# cmux-metrics.sh — Phase 2.2 token/cache telemetry viewer.
#
# Usage:
#   cmux-metrics.sh             # table view
#   cmux-metrics.sh --json      # raw metrics JSON
#   cmux-metrics.sh --alerts    # alerts only
#   cmux-metrics.sh --refresh   # force collect_all() before printing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OBS="${SCRIPT_DIR}/token_observer.py"

MODE="table"
for a in "$@"; do
  case "$a" in
    --json) MODE="json" ;;
    --alerts) MODE="alerts" ;;
    --refresh) MODE="refresh" ;;
    -h|--help)
      sed -n '2,8p' "$0" | sed 's/^# //'
      exit 0 ;;
  esac
done

if [ "$MODE" = "refresh" ]; then
  python3 "$OBS" collect >/dev/null
  MODE="table"
fi

if [ "$MODE" = "json" ]; then
  python3 "$OBS" dump
  exit 0
fi

if [ "$MODE" = "alerts" ]; then
  python3 "$OBS" alerts
  exit 0
fi

# Table mode — delegate formatting to Python for layout/commafication.
python3 - "$OBS" <<'PY'
import json
import subprocess
import sys
import time

obs = sys.argv[1]
data = json.loads(subprocess.check_output(["python3", obs, "dump"]))
surfaces = data.get("surfaces", {}) or {}
updated = data.get("updated_at") or 0
now = int(time.time())

def human_ago(ts):
    if not ts:
        return "—"
    try:
        if isinstance(ts, str):
            # ISO format → int seconds if possible, else passthrough
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts = int(dt.timestamp())
        diff = now - int(ts)
    except Exception:
        return str(ts)[:16]
    if diff < 60:
        return f"{diff}s"
    if diff < 3600:
        return f"{diff // 60}m"
    if diff < 86400:
        return f"{diff // 3600}h"
    return f"{diff // 86400}d"

def pct(r):
    return "N/A" if r is None else f"{r * 100:.1f}%"

rows = []
for sid, m in sorted(surfaces.items()):
    rows.append([
        sid[:28],
        (m.get("ai") or "?")[:8],
        str(m.get("turns") or 0),
        f"{m.get('input_tokens_total') or 0:,}",
        f"{m.get('output_tokens_total') or 0:,}",
        pct(m.get("cache_hit_ratio")),
        human_ago(m.get("last_turn_ts")),
    ])

header = ["surface", "ai", "turns", "input", "output", "cache_hit", "last_turn"]
widths = [
    max(len(header[i]), *(len(r[i]) for r in rows)) if rows else len(header[i])
    for i in range(len(header))
]

def fmt_row(row):
    return "  ".join(col.ljust(widths[i]) for i, col in enumerate(row))

print(f"# token-metrics  updated={human_ago(updated)} ago  surfaces={len(surfaces)}")
print(fmt_row(header))
print(fmt_row(["-" * w for w in widths]))
for r in rows:
    print(fmt_row(r))

if not rows:
    print("(no metrics yet — run `cmux-metrics.sh --refresh` or wait for watcher cycle)")
PY
