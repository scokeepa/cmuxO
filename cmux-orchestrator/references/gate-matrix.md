# GATE Enforcement Matrix

| GATE | Rule | Hook | Event | Level |
|------|------|------|-------|-------|
| 0 | No proceed before collection complete | cmux-completion-verifier.py | PreToolUse:Bash | L0 BLOCK |
| 2 | Code review requires Sonnet | (SKILL.md policy) | - | L3 Policy |
| 6 | IDLE surface exists -> Agent forbidden | cmux-gate6-agent-block.sh | PreToolUse:Agent | L0 BLOCK |
| CT | Control tower close forbidden | cmux-control-tower-guard.py | PreToolUse:Bash | L0 BLOCK |
| INIT | /new init required before dispatch | cmux-init-enforcer.py | PreToolUse:Bash | L0 BLOCK |
| NOTIFY | Watcher must be notified after dispatch | cmux-watcher-notify-enforcer.py | PreToolUse:Bash | L0 BLOCK |
| MSG | Watcher receives monitoring directives only | cmux-watcher-msg-guard.py | PreToolUse:Bash | L0 BLOCK |
| STALL | No stalling (3+ IDLE surfaces) | cmux-no-stall-enforcer.py | PreToolUse:Bash | L0 BLOCK |
| WF | Workflow state machine (DISPATCH->COLLECT->VERIFY->COMMIT) | cmux-workflow-state-machine.py | PreToolUse:Bash\|Agent | L0/L2 |
| W-8 | Watcher scan cycle mandatory | watcher-scan.py | (automatic) | Auto |
| W-9 | Watcher never intervenes on workers | (SKILL.md policy) | - | L3 Policy |
| W-10 | IDLE surface -> remind Main to assign | watcher-scan.py | (automatic) | Auto |

## Level Legend

| Level | Meaning | Implementation |
|-------|---------|---------------|
| L0 BLOCK | Physical block via PreToolUse hook | Hook returns `{"decision":"block"}` |
| L2 WARNING | Warning via PostToolUse systemMessage | Hook returns `{"systemMessage":"..."}` |
| L3 Policy | SKILL.md instruction only, no hook | AI follows written rule |
| Auto | Runs automatically in scan cycle | watcher-scan.py logic |
