#!/bin/bash
# gate-checker.sh — GATE 자동 검증 스크립트
# Usage: bash gate-checker.sh
#
# GATE 1: eagle_watcher.sh --once → WORKING surface 0개 확인
# GATE 5: speckit-tracker.py --gate → 미완료 0개 확인
# GATE 7: git worktree list | grep /tmp/wt → 미정리 워크트리 0개 확인

# ── 색상 정의 ──────────────────────────────────────────────────────────
variable_color_red='\033[0;31m'
variable_color_green='\033[0;32m'
variable_color_yellow='\033[0;33m'
variable_color_reset='\033[0m'

function_color_echo() {
  local variable_color="$1"
  local variable_msg="$2"
  echo -e "${variable_color}${variable_msg}${variable_color_reset}"
}

# ── 경로 설정 ─────────────────────────────────────────────────────────
# SKILL_DIR 동적 해석 (이식성: 하드코딩 경로 제거)
variable_script_dir="$(cd "$(dirname "$0")" && pwd)"
variable_skill_dir="${SKILL_DIR:-$(dirname "$variable_script_dir")}"

variable_eagle_watcher="${variable_skill_dir}/scripts/eagle_watcher.sh"
variable_speckit_tracker="${variable_skill_dir}/scripts/speckit-tracker.py"

# ── 결과 추적 ─────────────────────────────────────────────────────────
declare -a variable_failed_gates=()
declare -i variable_all_passed=1

# ── GATE 1: WORKING surface 0개 ───────────────────────────────────────
function_check_gate1() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "GATE 1: eagle_watcher.sh --once"

  if [ ! -f "$variable_eagle_watcher" ]; then
    function_color_echo "$variable_color_red" "  ⛔ GATE 1 FAIL: eagle_watcher.sh not found"
    variable_failed_gates+=("GATE 1")
    variable_all_passed=0
    return
  fi

  local variable_eagle_output
  variable_eagle_output=$(bash "$variable_eagle_watcher" --once 2>/dev/null)

  local variable_working_count
  variable_working_count=$(echo "$variable_eagle_output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('stats',{}).get('working',0))" 2>/dev/null || echo "-1")

  if [ "$variable_working_count" -eq 0 ]; then
    function_color_echo "$variable_color_green" "  ✅ GATE 1 PASS: WORKING surface = 0"
  else
    function_color_echo "$variable_color_red" "  ⛔ GATE 1 FAIL: WORKING surface = ${variable_working_count}"
    variable_failed_gates+=("GATE 1")
    variable_all_passed=0
  fi
}

# ── GATE 5: 미완료 태스크 0개 ──────────────────────────────────────────
function_check_gate5() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "GATE 5: speckit-tracker.py --gate"

  if [ ! -f "$variable_speckit_tracker" ]; then
    function_color_echo "$variable_color_red" "  ⛔ GATE 5 FAIL: speckit-tracker.py not found"
    variable_failed_gates+=("GATE 5")
    variable_all_passed=0
    return
  fi

  local variable_tracker_output
  local variable_tracker_exit

  variable_tracker_output=$(python3 "$variable_speckit_tracker" --gate 2>&1)
  variable_tracker_exit=$?

  if [ "$variable_tracker_exit" -eq 0 ]; then
    function_color_echo "$variable_color_green" "  ✅ GATE 5 PASS: 미완료 태스크 = 0"
  else
    function_color_echo "$variable_color_red" "  ⛔ GATE 5 FAIL: 미완료 태스크 존재"
    echo "$variable_tracker_output" | sed 's/^/    /'
    variable_failed_gates+=("GATE 5")
    variable_all_passed=0
  fi
}

# ── GATE 7: 미정리 워크트리 0개 ───────────────────────────────────────
function_check_gate7() {
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "GATE 7: git worktree list | grep /tmp/wt"

  local variable_worktree_count
  variable_worktree_count=$(git worktree list 2>/dev/null | grep '/tmp/wt' | wc -l | tr -d ' ')

  if [ "$variable_worktree_count" -eq 0 ]; then
    function_color_echo "$variable_color_green" "  ✅ GATE 7 PASS: 미정리 워크트리 = 0"
  else
    function_color_echo "$variable_color_red" "  ⛔ GATE 7 FAIL: 미정리 워크트리 = ${variable_worktree_count}"
    git worktree list 2>/dev/null | grep '/tmp/wt' | sed 's/^/    /'
    variable_failed_gates+=("GATE 7")
    variable_all_passed=0
  fi
}

# ── 메인 실행 ─────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════╗"
echo "║         GATE CHECKER — ALL GATES          ║"
echo "╚══════════════════════════════════════════╝"

function_check_gate1
function_check_gate5
function_check_gate7

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$variable_all_passed" -eq 1 ]; then
  echo ""
  function_color_echo "$variable_color_green" "✅ ALL GATES PASSED"
  echo ""
  exit 0
else
  echo ""
  function_color_echo "$variable_color_red" "⛔ GATE(S) FAILED: ${variable_failed_gates[*]}"
  echo ""
  exit 1
fi
