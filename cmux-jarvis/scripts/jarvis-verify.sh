#!/bin/bash
# jarvis-verify.sh — 독립 검증 스크립트 (사전 정의, AI 미개입)
# Usage: jarvis-verify.sh <evo-id>

set -euo pipefail

EVO_ID="${1:?evo-id 필요}"
JARVIS_DIR="$HOME/.claude/cmux-jarvis"
EVO_DIR="$JARVIS_DIR/evolutions/$EVO_ID"
VERIFY_PLUGINS="$HOME/.claude/skills/cmux-jarvis/scripts/verify-plugins"

[ ! -d "$EVO_DIR" ] && echo "ERROR: $EVO_DIR 없음" >&2 && exit 1

ERRORS=0
CHECKS=0

check() {
  CHECKS=$((CHECKS + 1))
  if eval "$2"; then
    echo "✓ $1"
  else
    echo "✗ $1"
    ERRORS=$((ERRORS + 1))
  fi
}

# === 공통 검증 ===
check "STATUS 파일 존재" "[ -f '$EVO_DIR/STATUS' ]"
check "STATUS JSON 유효" "python3 -c 'import json;json.load(open(\"$EVO_DIR/STATUS\"))' 2>/dev/null"

# STATUS 읽기
EVOLUTION_TYPE=$(jq -r '.evolution_type // "unknown"' "$EVO_DIR/STATUS" 2>/dev/null)
STATUS_PHASE=$(jq -r '.phase // ""' "$EVO_DIR/STATUS" 2>/dev/null)
check "STATUS phase=completed" "[ '$STATUS_PHASE' = 'completed' ]"

# === Iron Law #2: 예상 결과/TDD 물리 체크 ===
case "$EVOLUTION_TYPE" in
  settings_change)
    check "07-expected-outcomes.md 존재" "[ -f '$EVO_DIR/07-expected-outcomes.md' ]"
    check "expected-outcomes 비어있지 않음" "[ -s '$EVO_DIR/07-expected-outcomes.md' ]"
    ;;
  hook_change|skill_change|code_change)
    check "05-tdd.md 존재" "[ -f '$EVO_DIR/05-tdd.md' ]"
    check "05-tdd.md 3줄 이상" "[ \$(wc -l < '$EVO_DIR/05-tdd.md') -ge 3 ]"
    check "05-tdd.md test/assert 키워드" "grep -qiE 'test|assert|expect|검증' '$EVO_DIR/05-tdd.md'"
    ;;
  mixed)
    check "07-expected-outcomes.md 존재" "[ -f '$EVO_DIR/07-expected-outcomes.md' ]"
    check "05-tdd.md 존재" "[ -f '$EVO_DIR/05-tdd.md' ]"
    ;;
esac

# === proposed 검증 ===
check "proposed-settings.json 존재" "[ -f '$EVO_DIR/proposed-settings.json' ]"
check "proposed JSON 유효" "python3 -c 'import json;json.load(open(\"$EVO_DIR/proposed-settings.json\"))' 2>/dev/null"
check "file-mapping.json 존재" "[ -f '$EVO_DIR/file-mapping.json' ]"
check "file-mapping JSON 유효" "python3 -c 'import json;json.load(open(\"$EVO_DIR/file-mapping.json\"))' 2>/dev/null"

# === Outbound Gate: hooks 키 방어 (E4) ===
check "proposed에 hooks 키 없음" "! jq -e '.hooks' '$EVO_DIR/proposed-settings.json' >/dev/null 2>&1"

# === after-metrics 수집 + evidence.json 생성 (Iron Law #3) ===
python3 -c "
import json
eagle = json.load(open('/tmp/cmux-eagle-status.json'))
metrics = {k: eagle.get('stats', {}).get(k, 0) for k in ['stalled','error','idle','working','ended','total']}
metrics['timestamp'] = eagle.get('timestamp', '')
with open('$EVO_DIR/after-metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)

before = json.load(open('$EVO_DIR/before-metrics.json'))
after = metrics
evidence = {
    'evidence_type': 'metric_comparison',
    'before_snapshot': 'before-metrics.json',
    'after_snapshot': 'after-metrics.json',
    'metrics_compared': list(before.keys()),
    'collection_method': 'jarvis-verify.sh',
    'collected_at': after['timestamp'],
}
with open('$EVO_DIR/evidence.json', 'w') as f:
    json.dump(evidence, f, indent=2)
" 2>/dev/null
check "evidence.json 생성" "[ -f '$EVO_DIR/evidence.json' ]"

# === 유형별 플러그인 검증 (있으면 실행) ===
PLUGIN="$VERIFY_PLUGINS/${EVOLUTION_TYPE}.sh"
if [ -f "$PLUGIN" ] && [ -x "$PLUGIN" ]; then
  echo "--- 플러그인: $EVOLUTION_TYPE ---"
  bash "$PLUGIN" "$EVO_ID" || ERRORS=$((ERRORS + 1))
fi

# === 결과 ===
echo ""
echo "검증 결과: $CHECKS 체크, $ERRORS 실패"
if [ "$ERRORS" -gt 0 ]; then
  echo "FAIL"
  exit 1
else
  echo "PASS"
  exit 0
fi
