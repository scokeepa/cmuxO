# Crash Recovery

## cmux daemon crash

If cmux process crashes while orchestration is running:

1. Restart cmux application
2. `cmux tree --all` — check surviving surfaces
3. Run `/cmux-start` in a new Claude Code session
4. Watcher will re-scan and rebuild surface map
5. Check each department surface status:
   ```bash
   cmux read-screen --workspace WS --surface SID --lines 10
   ```
6. IDLE surfaces → re-dispatch tasks
7. WORKING surfaces → wait for completion

## Boss session crash

If Claude Code session running Boss (COO) closes unexpectedly:

1. Open new Claude Code in the same surface
2. Run `/cmux-start` — it will re-register Boss
3. Check `/tmp/cmux-surface-map.json` for department status
4. Resume orchestration from last known state

## Watcher crash

Handled automatically:
- Watchdog in `activation-hook.sh` restarts watcher-scan.py
- Error logged to `/tmp/cmux-watcher-alerts.json` as WATCHER_ERROR
- Debounce state persisted in `/tmp/cmux-watcher-debounce.json`

## Orphaned surfaces

Watcher detects surfaces registered in roles.json but missing from cmux tree:
- Alert: "ORPHAN_SURFACE: registered but not found"
- Action: Boss updates roles.json to remove orphaned entries

## Lost uncommitted work

If surface completes (DONE) but Boss crashes before reading:
1. Surface still has changes in working directory
2. Check: `cmux read-screen --workspace WS --surface SID --scrollback --lines 100`
3. Look for file paths in DONE output
4. Manually review and commit: `git diff`, `git add`, `git commit`
