#!/bin/bash
# jarvis-evolution.sh — JARVIS 진화 CLI (Python 래퍼)
# Usage: jarvis-evolution.sh <detect|backup|apply|rollback|status|cleanup|lock-phase> [evo-id] [args]
#
# Python 클래스 기반 jarvis-evolution.py로 위임.
# 하위 호환성을 위해 기존 인터페이스 유지.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/jarvis-evolution.py" "$@"
