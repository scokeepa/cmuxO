#!/bin/bash
# jarvis-verify.sh — 독립 검증 스크립트 (Python 래퍼)
# Usage: jarvis-verify.sh <evo-id>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/jarvis_verify.py" "$@"
