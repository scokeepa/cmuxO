#!/bin/bash
# cmux-role-exec.sh — Boss/Watcher/Peer 세션을 지정된 logical_name 으로 기동.
#
# Claude Code 는 자식 프로세스로 MCP claude-peers 를 띄우면서
# $CLAUDE_PEERS_NAME_PREFIX 를 읽어 logical_name="<prefix>@<surface_id_8>" 로 등록.
# 이 값은 Claude Code 가 **시작되기 전** 환경변수로 존재해야 한다.
#
# Usage:
#   bash cmux-role-exec.sh boss [--] [claude args...]
#   bash cmux-role-exec.sh watcher
#   bash cmux-role-exec.sh peer [custom claude path]
#
# 동작:
#   1) CLAUDE_PEERS_NAME_PREFIX=<role> 를 export
#   2) claude 실행 파일을 찾아 exec
#   3) 실패 시 어떤 경로 / 어떤 prefix 로 시도했는지 명시
set -euo pipefail

ROLE="${1:-}"
if [ -z "$ROLE" ]; then
  echo "Usage: cmux-role-exec.sh {boss|watcher|peer} [-- claude args...]" >&2
  exit 2
fi
shift

case "$ROLE" in
  boss|watcher|peer) ;;
  *)
    echo "ERROR: unknown role '$ROLE' (expected boss|watcher|peer)" >&2
    exit 2
    ;;
esac

if [ "${1:-}" = "--" ]; then shift; fi

CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || true)}"
if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
  echo "ERROR: claude binary not found (checked \$CLAUDE_BIN and PATH)" >&2
  echo "  힌트: export CLAUDE_BIN=/path/to/claude 또는 npm/brew 설치 확인" >&2
  exit 127
fi

export CLAUDE_PEERS_NAME_PREFIX="$ROLE"
echo "[cmux-role-exec] CLAUDE_PEERS_NAME_PREFIX=$ROLE → exec $CLAUDE_BIN $*" >&2
exec "$CLAUDE_BIN" "$@"
