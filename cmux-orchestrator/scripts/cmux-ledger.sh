#!/bin/bash
# cmux-ledger.sh — Phase 2.3 Boss ledger viewer / maintenance UI.
#
# Usage:
#   cmux-ledger.sh tail [N]              # last N events (default 20)
#   cmux-ledger.sh worker <surface_ref>  # filter by worker
#   cmux-ledger.sh verify-fail           # only VERIFY_FAIL events
#   cmux-ledger.sh since <seconds>       # events within the last N seconds
#   cmux-ledger.sh integrity             # parse stats for today's file
#   cmux-ledger.sh compact               # gzip/delete old files
#   cmux-ledger.sh context               # compaction-replay block for Boss
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEDGER="${SCRIPT_DIR}/ledger.py"

if [ $# -lt 1 ]; then
  sed -n '2,13p' "$0" | sed 's/^# //'
  exit 0
fi

CMD="$1"
shift || true

case "$CMD" in
  tail)
    N="${1:-20}"
    python3 "$LEDGER" tail --n "$N"
    ;;
  worker)
    if [ $# -lt 1 ]; then
      echo "usage: cmux-ledger.sh worker <surface_ref>" >&2
      exit 2
    fi
    python3 "$LEDGER" query --worker "$1"
    ;;
  verify-fail)
    python3 "$LEDGER" query --type VERIFY_FAIL
    ;;
  since)
    if [ $# -lt 1 ]; then
      echo "usage: cmux-ledger.sh since <seconds>" >&2
      exit 2
    fi
    NOW=$(date -u +%s)
    CUTOFF=$((NOW - $1))
    python3 "$LEDGER" query --since-ts "$CUTOFF"
    ;;
  integrity)
    python3 "$LEDGER" integrity
    ;;
  compact)
    python3 "$LEDGER" compact
    ;;
  context)
    python3 "$LEDGER" context
    ;;
  -h|--help)
    sed -n '2,13p' "$0" | sed 's/^# //'
    ;;
  *)
    echo "unknown command: $CMD" >&2
    sed -n '2,13p' "$0" | sed 's/^# //'
    exit 2
    ;;
esac
