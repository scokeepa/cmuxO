#!/bin/bash
# hook_output.sh — Claude Code hook output helpers (SSOT).
#
# Source from a hook script:
#   . "$HOME/.claude/skills/cmux-orchestrator/scripts/hook_output.sh"
#   hook_deny_pretool "reason here"
#
# Schema reference: SyncHookJSONOutputSchema (coreSchemas.ts:907).
# Project SSOT for hook shapes: docs/01-architecture/gate-logic.md
#
# Pass-through convention: exit 0 + empty stdout. Do NOT echo
# {"decision":"allow"} (not in enum) or {"decision":"approve"} (legacy).

# PreToolUse deny — block tool call with reason to the model.
hook_deny_pretool() {
    HOOK_OUT_REASON="$1" python3 - <<'PY'
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": os.environ.get("HOOK_OUT_REASON", ""),
    }
}, ensure_ascii=False))
PY
}

# PreToolUse ask — user must confirm before tool call.
hook_ask_pretool() {
    HOOK_OUT_REASON="$1" python3 - <<'PY'
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": os.environ.get("HOOK_OUT_REASON", ""),
    }
}, ensure_ascii=False))
PY
}

# PreToolUse allow with rewritten Bash command.
hook_allow_pretool_cmd() {
    HOOK_OUT_CMD="$1" python3 - <<'PY'
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "updatedInput": {"command": os.environ.get("HOOK_OUT_CMD", "")},
    }
}, ensure_ascii=False))
PY
}

# PostToolUse — inject additional context for the model.
hook_inject_posttool() {
    HOOK_OUT_MSG="$1" python3 - <<'PY'
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": os.environ.get("HOOK_OUT_MSG", ""),
    }
}, ensure_ascii=False))
PY
}

# Top-level systemMessage — pass through with a banner.
hook_warn() {
    HOOK_OUT_MSG="$1" python3 - <<'PY'
import json, os
print(json.dumps({"systemMessage": os.environ.get("HOOK_OUT_MSG", "")}, ensure_ascii=False))
PY
}
