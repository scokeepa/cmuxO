# GATE Enforcement Matrix

| GATE | Rule | Hook | Event | Level |
|------|------|------|-------|-------|
| 0 | No proceed before collection complete | cmux-completion-verifier.py | PreToolUse:Bash | L0 BLOCK |
| 2 | Code review requires Sonnet | (SKILL.md policy) | - | L3 Policy |
| 6 | IDLE surface exists -> Agent forbidden | cmux-gate6-agent-block.sh | PreToolUse:Agent | L0 BLOCK |
| 7 | IDLE worker exists -> Boss direct work forbidden | cmux-gate7-main-delegate.py | PreToolUse:Read\|Edit\|Grep\|Glob\|Write | L0 BLOCK |
| CT | Control tower close forbidden | cmux-control-tower-guard.py | PreToolUse:Bash | L0 BLOCK |
| INIT | /new init required before dispatch | cmux-init-enforcer.py | PreToolUse:Bash | L0 BLOCK |
| NOTIFY | Watcher must be notified after dispatch | cmux-watcher-notify-enforcer.py | PreToolUse:Bash | L0 BLOCK |
| MSG | Watcher receives monitoring directives only | cmux-watcher-msg-guard.py | PreToolUse:Bash | L0 BLOCK |
| STALL | No stalling (3+ IDLE surfaces) | cmux-no-stall-enforcer.py | PreToolUse:Bash | L0 BLOCK |
| WF | Workflow state machine (DISPATCH->COLLECT->VERIFY->COMMIT) | cmux-workflow-state-machine.py | PreToolUse:Bash\|Agent | L0/L2 |
| W-8 | Watcher scan cycle mandatory | watcher-scan.py | (automatic) | Auto |
| W-9 | Watcher never intervenes on workers | (SKILL.md policy) | - | L3 Policy |
| W-10 | IDLE surface -> remind Boss to assign | watcher-scan.py | (automatic) | Auto |
| LECEIPTS | 5-section report before commit | cmux-leceipts-gate.py | PreToolUse:Bash | L0 BLOCK |
| PLAN-QG | 5관점 순환검증 + 시뮬레이션 before ExitPlanMode | cmux-plan-quality-gate.py | PreToolUse:ExitPlanMode | L0 BLOCK |

## Level Legend

| Level | Meaning | Implementation |
|-------|---------|---------------|
| L0 BLOCK | Physical block via PreToolUse hook | Hook returns `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}` |
| L2 WARNING | Warning via PostToolUse additionalContext | Hook returns `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"..."}}` |
| L3 Policy | SKILL.md instruction only, no hook | AI follows written rule |
| Auto | Runs automatically in scan cycle | watcher-scan.py logic |
