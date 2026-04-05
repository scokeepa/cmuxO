#!/bin/bash
# test-hooks-negative.sh — Hook 네거티브(음성) 테스트 프레임워크
# "차단되어야 할 입력이 실제로 차단되는지" 검증
# 용도: SessionStart에서 자동 실행 또는 /sdd health에서 호출

HOOKS_DIR="$HOME/.claude/hooks"
PASS=0
FAIL=0
TOTAL=0

# Helper: test a hook with input and expect block/approve
test_hook() {
    local hook_path="$1"
    local test_input="$2"
    local expected="$3"  # "block" or "approve"
    local test_name="$4"

    TOTAL=$((TOTAL + 1))

    if [[ ! -f "$hook_path" ]]; then
        echo "  SKIP $test_name — hook file missing"
        return
    fi

    local result
    result=$(echo "$test_input" | python3 "$hook_path" 2>/dev/null)
    local decision
    decision=$(echo "$result" | python3 -c "import json,sys; print(json.load(sys.stdin).get('decision','approve'))" 2>/dev/null)

    if [[ "$decision" == "$expected" ]]; then
        PASS=$((PASS + 1))
        echo "  PASS $test_name"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL $test_name (expected=$expected, got=$decision)"
    fi
}

echo "=== Hook Negative Test Suite ==="
echo ""

# --- cmux-completion-verifier.py ---
echo "[cmux-completion-verifier.py]"

# Remove verification flag to ensure block
rm -f /tmp/cmux-verification-passed

test_hook "$HOOKS_DIR/cmux-completion-verifier.py" \
    '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
    "block" \
    "git commit without verification → should BLOCK"

# Create flag and test approve
touch /tmp/cmux-verification-passed
test_hook "$HOOKS_DIR/cmux-completion-verifier.py" \
    '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
    "approve" \
    "git commit with verification → should APPROVE"
rm -f /tmp/cmux-verification-passed

# Non-commit command should always pass
test_hook "$HOOKS_DIR/cmux-completion-verifier.py" \
    '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' \
    "approve" \
    "ls command → should APPROVE"

echo ""

# --- cmux-watcher-msg-guard.py ---
echo "[cmux-watcher-msg-guard.py]"

test_hook "$HOOKS_DIR/cmux-watcher-msg-guard.py" \
    '{"tool_name":"Bash","tool_input":{"command":"cmux set-buffer --surface surface:29 \"핵심성과 보고\""}}' \
    "block" \
    "watcher + 핵심성과 → should BLOCK"

test_hook "$HOOKS_DIR/cmux-watcher-msg-guard.py" \
    '{"tool_name":"Bash","tool_input":{"command":"cmux set-buffer --surface surface:29 \"모니터링 모드: 4중 방어체계. 감시 대상: s:1,s:2\""}}' \
    "approve" \
    "watcher + 4중 방어체계 → should APPROVE"

test_hook "$HOOKS_DIR/cmux-watcher-msg-guard.py" \
    '{"tool_name":"Bash","tool_input":{"command":"cmux set-buffer --surface surface:5 \"작업해줘\""}}' \
    "approve" \
    "worker surface → should APPROVE (not watcher)"

echo ""

# --- cmux-init-enforcer.py ---
echo "[cmux-init-enforcer.py]"

# Clear init state
rm -f /tmp/cmux-init-state.json

test_hook "$HOOKS_DIR/cmux-init-enforcer.py" \
    '{"tool_name":"Bash","tool_input":{"command":"cmux set-buffer --surface surface:5 \"task\""}}' \
    "block" \
    "Claude Code surface without /new → should BLOCK"

test_hook "$HOOKS_DIR/cmux-init-enforcer.py" \
    '{"tool_name":"Bash","tool_input":{"command":"cmux set-buffer --surface surface:1 \"task\""}}' \
    "approve" \
    "Codex surface without /new → should APPROVE (no init needed)"

test_hook "$HOOKS_DIR/cmux-init-enforcer.py" \
    '{"tool_name":"Bash","tool_input":{"command":"cmux set-buffer --surface surface:29 \"msg\""}}' \
    "approve" \
    "Watcher surface → should APPROVE (no init needed)"

echo ""

# --- cmux-workflow-state-machine.py ---
echo "[cmux-workflow-state-machine.py]"

# Reset state to IDLE
echo '{"state":"IDLE","timestamp":'$(date +%s)',"dispatch_count":0}' > /tmp/cmux-workflow-state.json

test_hook "$HOOKS_DIR/cmux-workflow-state-machine.py" \
    '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
    "block" \
    "commit from IDLE → should BLOCK"

# Set state to DISPATCHED
echo '{"state":"DISPATCHED","timestamp":'$(date +%s)',"dispatch_count":1}' > /tmp/cmux-workflow-state.json

test_hook "$HOOKS_DIR/cmux-workflow-state-machine.py" \
    '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
    "block" \
    "commit from DISPATCHED → should BLOCK"

# Set state to VERIFIED
echo '{"state":"VERIFIED","timestamp":'$(date +%s)',"dispatch_count":1}' > /tmp/cmux-workflow-state.json

test_hook "$HOOKS_DIR/cmux-workflow-state-machine.py" \
    '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
    "approve" \
    "commit from VERIFIED → should APPROVE"

echo ""

# --- Summary ---
echo "=== RESULTS ==="
echo "  Total: $TOTAL"
echo "  Pass:  $PASS"
echo "  Fail:  $FAIL"

if [[ $FAIL -eq 0 ]]; then
    echo "  STATUS: ALL PASS ✅"
else
    echo "  STATUS: $FAIL FAILURES ❌"
fi

# Clean up test artifacts
rm -f /tmp/cmux-workflow-state.json /tmp/cmux-init-state.json /tmp/cmux-verification-passed
