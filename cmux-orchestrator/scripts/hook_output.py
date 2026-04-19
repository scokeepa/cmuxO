"""hook_output.py — Claude Code hook output helpers (SSOT).

Emits JSON payloads that conform to Claude Code's SyncHookJSONOutputSchema
(coreSchemas.ts:907). All cmux hooks should call into this module instead of
hand-writing payloads so the shape stays consistent as the upstream schema
evolves.

Project SSOT for hook shapes: docs/01-architecture/gate-logic.md

Valid top-level keys (coreSchemas.ts:907-913):
  continue, suppressOutput, stopReason, decision ("approve"|"block" legacy),
  reason, hookSpecificOutput, systemMessage.

Valid PreToolUse.hookSpecificOutput (coreSchemas.ts:806-814):
  hookEventName="PreToolUse", permissionDecision ("allow"|"deny"|"ask"),
  permissionDecisionReason, updatedInput, additionalContext.

Valid PostToolUse.hookSpecificOutput:
  hookEventName="PostToolUse", additionalContext.

Pass-through convention: exit 0 + empty stdout. Do NOT emit {"decision":"allow"}
(not in enum) or {"decision":"approve"} (legacy, diverges from SSOT).
"""
from __future__ import annotations

import json as _json
import sys as _sys
from typing import Any, Dict


def _emit(payload: Dict[str, Any]) -> None:
    _sys.stdout.write(_json.dumps(payload, ensure_ascii=False))
    _sys.stdout.write("\n")
    _sys.stdout.flush()


def deny_pretool(reason: str) -> None:
    """Block a PreToolUse tool call with a reason shown to the model."""
    _emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })


def ask_pretool(reason: str) -> None:
    """Request user confirmation before a PreToolUse tool call."""
    _emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    })


def allow_pretool_with_updated_input(updated_input: Dict[str, Any]) -> None:
    """Allow a PreToolUse call after rewriting its tool_input."""
    _emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated_input,
        }
    })


def inject_posttool_context(message: str) -> None:
    """Inject additional context for the model after a PostToolUse call."""
    _emit({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    })


def warn(message: str) -> None:
    """Pass through with a systemMessage banner."""
    _emit({"systemMessage": message})
