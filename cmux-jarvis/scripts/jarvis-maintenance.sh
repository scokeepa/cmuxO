#!/bin/bash
# jarvis-maintenance.sh — JARVIS 유지보수 CLI
# Usage: jarvis-maintenance.sh <rebuild-fts|migrate-vault|prune|gc>

set -euo pipefail

JARVIS_DIR="$HOME/.claude/cmux-jarvis"
CONFIG="$JARVIS_DIR/config.json"

case "${1:-help}" in

rebuild-fts)
  echo "FTS5 인덱스 재구축은 Phase 2에서 구현됩니다."
  echo "현재는 grep 폴백으로 검색 가능합니다."
  ;;

migrate-vault)
  NEW_PATH="${2:?새 볼트 경로 필요}"
  OLD_PATH=$(jq -r '.obsidian_vault_path // ""' "$CONFIG" 2>/dev/null)

  if [ -z "$OLD_PATH" ]; then
    # 모드 B → A: 로컬에서 Obsidian으로
    echo "모드 B → A: 로컬 → $NEW_PATH"
    mkdir -p "$NEW_PATH/JARVIS"
    if [ -d "$JARVIS_DIR/evolutions" ]; then
      cp -r "$JARVIS_DIR/evolutions" "$NEW_PATH/JARVIS/Evolutions" 2>/dev/null || true
    fi
    if [ -d "$JARVIS_DIR/knowledge" ]; then
      cp -r "$JARVIS_DIR/knowledge" "$NEW_PATH/JARVIS/Knowledge" 2>/dev/null || true
    fi
  else
    # 모드 A → B 또는 A → A: 이전 볼트에서 새 볼트로
    echo "볼트 이동: $OLD_PATH → $NEW_PATH"
    mkdir -p "$NEW_PATH/JARVIS"
    cp -r "$OLD_PATH/JARVIS/"* "$NEW_PATH/JARVIS/" 2>/dev/null || true
  fi

  # config 업데이트
  jq --arg p "$NEW_PATH" '.obsidian_vault_path = $p' "$CONFIG" > "/tmp/config-$$.json"
  mv "/tmp/config-$$.json" "$CONFIG"
  echo "OK: config.json 업데이트. obsidian_vault_path=$NEW_PATH"
  ;;

prune)
  echo "=== 오래된 진화 정리 ==="
  KEEP=${2:-5}
  EVOS=$(ls -d "$JARVIS_DIR/evolutions"/evo-* 2>/dev/null | sort -V)
  TOTAL=$(echo "$EVOS" | grep -c "evo-" || echo 0)
  if [ "$TOTAL" -le "$KEEP" ]; then
    echo "진화 ${TOTAL}건 (유지 ${KEEP}건). 정리 불필요."
  else
    REMOVE=$((TOTAL - KEEP))
    echo "진화 ${TOTAL}건 중 ${REMOVE}건 정리 (최신 ${KEEP}건 유지)"
    echo "$EVOS" | head -n "$REMOVE" | while read -r d; do
      echo "  삭제: $(basename "$d")"
      rm -rf "$d"
    done
  fi
  ;;

gc)
  echo "3계층 메모리 GC는 Phase 2에서 구현됩니다."
  echo "현재는 jarvis-maintenance.sh prune으로 오래된 진화만 정리 가능합니다."
  ;;

help|*)
  echo "Usage: jarvis-maintenance.sh <rebuild-fts|migrate-vault|prune|gc> [args]"
  echo ""
  echo "  rebuild-fts           FTS5 인덱스 재구축 (Phase 2)"
  echo "  migrate-vault <path>  볼트 경로 이동 (모드 A↔B)"
  echo "  prune [keep=5]        오래된 진화 정리"
  echo "  gc                    3계층 메모리 GC (Phase 2)"
  ;;
esac
