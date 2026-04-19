#!/bin/bash
# cmux-check.sh — Phase 2.4 anti-rationalization on-demand checker.
#
# Usage:
#   cmux-check.sh "<text>" [worker]      # classify text
#   cmux-check.sh --stdin [worker]        # read text from stdin
#   cmux-check.sh --table                 # open references/anti-rationalization.md
#   cmux-check.sh --last N [worker]       # check last N ledger message_excerpts
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AR="${SCRIPT_DIR}/anti_rationalization.py"
LEDGER="${SCRIPT_DIR}/ledger.py"
TABLE="${SCRIPT_DIR}/../references/anti-rationalization.md"

if [ $# -lt 1 ]; then
  sed -n '2,9p' "$0" | sed 's/^# //'
  exit 0
fi

case "$1" in
  --table)
    if [ -f "$TABLE" ]; then
      cat "$TABLE"
    else
      echo "anti-rationalization.md not found at $TABLE" >&2
      exit 2
    fi
    ;;
  --stdin)
    WORKER="${2:-}"
    TEXT="$(cat)"
    if [ -n "$WORKER" ]; then
      python3 "$AR" "$TEXT" "$WORKER"
    else
      python3 "$AR" "$TEXT"
    fi
    ;;
  --last)
    N="${2:-10}"
    WORKER="${3:-}"
    python3 - "$AR" "$LEDGER" "$N" "$WORKER" <<'PY'
import json, subprocess, sys
ar, ledger, n, worker = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
out = subprocess.run(["python3", ledger, "tail", "--n", str(n)],
                     capture_output=True, text=True, timeout=3)
rows = [json.loads(ln) for ln in out.stdout.splitlines() if ln.strip()]
results = []
for r in rows:
    excerpt = r.get("message_excerpt") or r.get("reason") or ""
    if not excerpt:
        continue
    args = ["python3", ar, excerpt]
    if worker:
        args.append(worker)
    elif r.get("worker"):
        args.append(r["worker"])
    c = subprocess.run(args, capture_output=True, text=True, timeout=3)
    try:
        decision = json.loads(c.stdout)
    except json.JSONDecodeError:
        continue
    if decision["decision"] == "ask":
        results.append({
            "ts": r.get("ts"), "type": r.get("type"),
            "worker": r.get("worker"),
            "excerpt": excerpt[:120],
            "matches": [m["name"] for m in decision["matches"]],
        })
print(json.dumps({"flagged": len(results), "events": results},
                 ensure_ascii=False, indent=2))
PY
    ;;
  -h|--help)
    sed -n '2,9p' "$0" | sed 's/^# //'
    ;;
  *)
    TEXT="$1"
    WORKER="${2:-}"
    if [ -n "$WORKER" ]; then
      python3 "$AR" "$TEXT" "$WORKER"
    else
      python3 "$AR" "$TEXT"
    fi
    ;;
esac
