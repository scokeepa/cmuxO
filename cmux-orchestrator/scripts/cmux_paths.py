#!/usr/bin/env python3
"""Runtime path SSOT for cmux orchestration state."""
from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def runtime_dir(create: bool = True) -> Path:
    """Return the non-/tmp runtime directory shared by cmux hooks/scripts."""
    override = os.environ.get("CMUX_RUNTIME_DIR")
    if override:
        path = Path(override).expanduser()
    elif platform.system() == "Darwin":
        path = Path.home() / "Library" / "Application Support" / "cmux" / "orchestrator-runtime"
    else:
        state_home = os.environ.get("XDG_STATE_HOME")
        base = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
        path = base / "cmux" / "orchestrator-runtime"

    if create:
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except (OSError, NotImplementedError):
            pass
    return path


def runtime_path(name: str, create: bool = True) -> Path:
    path = runtime_dir(create=create) / name
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def runtime_directory(name: str, create: bool = True) -> Path:
    path = runtime_dir(create=create) / name
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


ORCH_FLAG = runtime_path("cmux-orch-enabled")
ROLES_FILE = runtime_path("cmux-roles.json")
SURFACE_MAP_FILE = runtime_path("cmux-surface-map.json")
SURFACE_SCAN_FILE = runtime_path("cmux-surface-scan.json")
EAGLE_STATUS_FILE = runtime_path("cmux-eagle-status.json")
WATCHER_ALERTS_FILE = runtime_path("cmux-watcher-alerts.json")

# Hook-local state
DISPATCH_PENDING_FILE = runtime_path("state/cmux-dispatch-pending.json")
WORKFLOW_STATE_FILE = runtime_path("state/cmux-workflow-state.json")
INIT_STATE_FILE = runtime_path("state/cmux-init-state.json")
VERIFICATION_PASSED_FILE = runtime_path("state/cmux-verification-passed")
IDLE_TRACKER_FILE = runtime_path("state/cmux-idle-tracker.json")
PASTE_PENDING_FILE = runtime_path("state/cmux-paste-pending.json")
VIOLATION_TRACKER_FILE = runtime_path("state/cmux-violation-tracker.json")
ORCHESTRATION_STATE_FILE = runtime_path("state/cmux-orchestration-state.json")
LECEIPTS_REPORT_FILE = runtime_path("state/cmux-leceipts-report.json")
MENTOR_LAST_HINT_FILE = runtime_path("state/cmux-mentor-last-hint.txt")
DISPATCH_SIGNAL_FILE = runtime_path("state/cmux-dispatch-signal.json")
WATCHER_ENTER_SIGNAL_FILE = runtime_path("state/cmux-watcher-enter-signal.json")
DISPATCH_REGISTRY_FILE = runtime_path("state/cmux-dispatch-registry.json")
REVIEW_STATUS_FILE = runtime_path("state/cmux-review-status.json")
SURFACE_FSM_FILE = runtime_path("state/cmux-surface-fsm.json")
WELCOME_FLAG = runtime_path("state/cmux-welcome-shown.flag")
HELP_DISABLED_FLAG = runtime_path("state/cmux-help-disabled")

# Queue and tracker state
TASK_QUEUE_FILE = runtime_path("queue/cmux-task-queue.json")
COMPLETED_TASKS_FILE = runtime_path("queue/cmux-completed-tasks.jsonl")
SPECKIT_TRACKER_FILE = runtime_path("queue/cmux-speckit-tracker.json")
WATCHER_QUEUE_FILE = runtime_path("queue/cmux-queue.json")

# Watcher state
WATCHER_LOG_FILE = runtime_path("watcher/cmux-watcher.log")
WATCHER_STATE_FILE = runtime_path("watcher/cmux-watcher-state.json")
WATCHER_WATCHDOG_PID_FILE = runtime_path("watcher/cmux-watcher-watchdog.pid")
WATCHER_SCAN_PID_FILE = runtime_path("watcher/cmux-watcher-scan.pid")
WATCHER_HISTORY_FILE = runtime_path("watcher/cmux-watcher-history.jsonl")
WATCHER_DEBOUNCE_FILE = runtime_path("watcher/cmux-watcher-debounce.json")
WATCHER_PREV_MANAGED_FILE = runtime_path("watcher/cmux-watcher-prev-managed.json")
WATCHER_BOOT_SCAN_FILE = runtime_path("watcher/cmux-watcher-boot-scan.json")
WATCHER_MUTE_FLAG = runtime_path("watcher/cmux-watcher-muted.flag")
PAUSE_FLAG = runtime_path("watcher/cmux-paused.flag")
RATE_LIMITED_POOL_FILE = runtime_path("watcher/cmux-rate-limited-pool.json")
ERROR_HISTORY_FILE = runtime_path("watcher/cmux-error-history.jsonl")
SURFACE_PROFILES_FILE = runtime_path("watcher/cmux-surface-profiles.json")
PEER_MESSAGES_FILE = runtime_path("watcher/cmux-peer-messages.log")
PIPE_PANE_INITIALIZED_FILE = runtime_path("watcher/cmux-pipe-pane-initialized.flag")
ORPHAN_COUNTER_FILE = runtime_path("watcher/cmux-orphan-counter.json")
VISION_DIFF_PREV_FILE = runtime_path("watcher/cmux-vdiff-prev.json")
VISION_PREV_STATE_FILE = runtime_path("watcher/cmux-vision-prev-state.json")

# Phase 2.2 — token/cache telemetry
TELEMETRY_DIR = runtime_directory("telemetry")
TOKEN_METRICS_FILE = runtime_path("telemetry/token-metrics.json")

# Phase 2.2.5 — claude-peers inter-session channel
PEER_DIR = runtime_directory("peer")
PEER_SENT_LOG_FILE = runtime_path("peer/cmux-peer-sent.log")

# Phase 2.3 — append-only event ledger
LEDGER_DIR = runtime_directory("ledger")


def ledger_today_path(now: float | None = None) -> Path:
    """Return today's ledger file (daily rotation by UTC date)."""
    import time as _time
    ts = now if now is not None else _time.time()
    day = _time.strftime("%Y-%m-%d", _time.gmtime(ts))
    return runtime_path(f"ledger/boss-ledger-{day}.jsonl")

# JARVIS worker markers
JARVIS_FREEZE_MODE_FILE = runtime_path("jarvis/cmux-jarvis-freeze-mode")
JARVIS_BACKUP_LOCK_FILE = runtime_path("jarvis/cmux-jarvis-backup.lock")
JARVIS_FILE_CHANGED_DEBOUNCE_FILE = runtime_path("jarvis/jarvis-file-changed-last")
JARVIS_SCHEDULER_PID_FILE = runtime_path("jarvis/jarvis-scheduler.pid")

# Socket/pid state
COMPAT_SOCK_FILE = runtime_path("sockets/cmux-compat.sock")
COMPAT_PID_FILE = runtime_path("sockets/cmux-compat.pid")

# Scratch paths
SCRATCH_DIR = runtime_directory("scratch")
VISION_DIFF_DIR = runtime_directory("scratch/cmux-vdiff")
VISION_MONITOR_DIR = runtime_directory("scratch/cmux-vision-monitor")
STALL_DETECT_DIR = runtime_directory("scratch/cmux-stall-detect")
DUAL_MONITOR_DIR = runtime_directory("scratch/cmux-dual-monitor")
VISION_MONITOR_PREV_FILE = runtime_path("scratch/cmux-vision-monitor-prev.json")
VISION_SCAN_FILE = runtime_path("scratch/cmux-vision-scan.png")
VISION_FULLSCREEN_FILE = runtime_path("scratch/cmux-vision-fullscreen.png")
EAGLE_ACTIVITY_FILE = runtime_path("scratch/cmux-eagle-activity.json")
EAGLE_CALLER_SID_FILE = runtime_path("scratch/cmux-eagle-caller-sid.txt")
CMUX_SHIM_REGISTRY_FILE = runtime_path("state/cmux-shim-registry.json")


def orch_enabled() -> bool:
    return ORCH_FLAG.exists()


def cwd_to_slug(cwd: str) -> str:
    """Convert an absolute cwd path to Claude Code's project-slug form.

    Claude Code stores transcripts under
    ``~/.claude/projects/<slug>/<uuid>.jsonl`` where ``slug`` is the cwd
    with every ``/`` replaced by ``-``. Examples::

        /Users/csm/projects/x → -Users-csm-projects-x
    """
    return cwd.replace("/", "-")


def claude_projects_dir() -> Path:
    """Resolve Claude Code's per-project transcript root."""
    override = os.environ.get("CLAUDE_PROJECTS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "projects"


def surface_to_slug(cwd: str) -> str:
    """Plan §3.1 helper — alias of :func:`cwd_to_slug` for surface callers."""
    return cwd_to_slug(cwd)


_ANE_DEFAULT = Path.home() / "Ai" / "System" / "11_Modules" / "ane-cli" / "ane_tool"


def ane_tool_path() -> Path | None:
    """Resolve the Apple Neural Engine OCR binary.

    Resolution order: CMUX_ANE_TOOL env → ANE_TOOL env → PATH lookup →
    ~/Ai/System/11_Modules/ane-cli/ane_tool. Returns None when no
    executable candidate is found.
    """
    candidates = [
        os.environ.get("CMUX_ANE_TOOL", ""),
        os.environ.get("ANE_TOOL", ""),
        shutil.which("ane_tool") or "",
        str(_ANE_DEFAULT),
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c).expanduser()
        if p.exists() and os.access(p, os.X_OK):
            return p
    return None
