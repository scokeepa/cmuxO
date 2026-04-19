#!/bin/bash
# Runtime path SSOT for cmux orchestration state.

cmux_runtime_dir() {
  if [ -n "${CMUX_RUNTIME_DIR:-}" ]; then
    printf '%s\n' "$CMUX_RUNTIME_DIR"
    return 0
  fi

  if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
    printf '%s\n' "$HOME/Library/Application Support/cmux/orchestrator-runtime"
  else
    local variable_state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
    printf '%s\n' "$variable_state_home/cmux/orchestrator-runtime"
  fi
}

cmux_ensure_runtime_dir() {
  local variable_dir
  variable_dir="$(cmux_runtime_dir)"
  mkdir -p "$variable_dir"
  chmod 700 "$variable_dir" 2>/dev/null || true
  printf '%s\n' "$variable_dir"
}

cmux_runtime_path() {
  local variable_name="$1"
  local variable_dir
  local variable_path
  variable_dir="$(cmux_ensure_runtime_dir)"
  variable_path="$variable_dir/$variable_name"
  mkdir -p "$(dirname "$variable_path")"
  printf '%s\n' "$variable_path"
}

cmux_runtime_directory() {
  local variable_path
  variable_path="$(cmux_runtime_path "$1")"
  mkdir -p "$variable_path"
  printf '%s\n' "$variable_path"
}

cmux_ane_tool() {
  # Resolve the Apple Neural Engine OCR binary.
  # Order: CMUX_ANE_TOOL → ANE_TOOL → PATH → $HOME/Ai/System/11_Modules/ane-cli/ane_tool.
  # Prints empty string and returns 1 when none is executable.
  local variable_candidate
  for variable_candidate in \
      "${CMUX_ANE_TOOL:-}" \
      "${ANE_TOOL:-}" \
      "$(command -v ane_tool 2>/dev/null)" \
      "$HOME/Ai/System/11_Modules/ane-cli/ane_tool"; do
    if [ -n "$variable_candidate" ] && [ -x "$variable_candidate" ]; then
      printf '%s\n' "$variable_candidate"
      return 0
    fi
  done
  printf '%s\n' ""
  return 1
}

cmux_worktree_root() {
  local variable_project="${1:-${CMUX_PROJECT_ROOT:-}}"
  if [ -n "${CMUX_WORKTREE_ROOT:-}" ]; then
    printf '%s\n' "$CMUX_WORKTREE_ROOT"
    return 0
  fi

  if [ -n "$variable_project" ]; then
    printf '%s\n' "$variable_project/.cmux-worktrees"
    return 0
  fi

  local variable_git_root
  variable_git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$variable_git_root" ]; then
    printf '%s\n' "$variable_git_root/.cmux-worktrees"
  else
    printf '%s\n' "$PWD/.cmux-worktrees"
  fi
}

CMUX_ORCH_FLAG="$(cmux_runtime_path cmux-orch-enabled)"
CMUX_ROLES_FILE="$(cmux_runtime_path cmux-roles.json)"
CMUX_SURFACE_MAP_FILE="$(cmux_runtime_path cmux-surface-map.json)"
CMUX_SURFACE_SCAN_FILE="$(cmux_runtime_path cmux-surface-scan.json)"
CMUX_EAGLE_STATUS_FILE="$(cmux_runtime_path cmux-eagle-status.json)"
CMUX_WATCHER_ALERTS_FILE="$(cmux_runtime_path cmux-watcher-alerts.json)"
CMUX_DISPATCH_PENDING_FILE="$(cmux_runtime_path state/cmux-dispatch-pending.json)"
CMUX_WORKFLOW_STATE_FILE="$(cmux_runtime_path state/cmux-workflow-state.json)"
CMUX_INIT_STATE_FILE="$(cmux_runtime_path state/cmux-init-state.json)"
CMUX_VERIFICATION_PASSED_FILE="$(cmux_runtime_path state/cmux-verification-passed)"
CMUX_IDLE_TRACKER_FILE="$(cmux_runtime_path state/cmux-idle-tracker.json)"
CMUX_PASTE_PENDING_FILE="$(cmux_runtime_path state/cmux-paste-pending.json)"
CMUX_VIOLATION_TRACKER_FILE="$(cmux_runtime_path state/cmux-violation-tracker.json)"
CMUX_ORCHESTRATION_STATE_FILE="$(cmux_runtime_path state/cmux-orchestration-state.json)"
CMUX_LECEIPTS_REPORT_FILE="$(cmux_runtime_path state/cmux-leceipts-report.json)"
CMUX_MENTOR_LAST_HINT_FILE="$(cmux_runtime_path state/cmux-mentor-last-hint.txt)"
CMUX_DISPATCH_SIGNAL_FILE="$(cmux_runtime_path state/cmux-dispatch-signal.json)"
CMUX_WATCHER_ENTER_SIGNAL_FILE="$(cmux_runtime_path state/cmux-watcher-enter-signal.json)"
CMUX_DISPATCH_REGISTRY_FILE="$(cmux_runtime_path state/cmux-dispatch-registry.json)"
CMUX_REVIEW_STATUS_FILE="$(cmux_runtime_path state/cmux-review-status.json)"
CMUX_SURFACE_FSM_FILE="$(cmux_runtime_path state/cmux-surface-fsm.json)"
CMUX_WELCOME_FLAG="$(cmux_runtime_path state/cmux-welcome-shown.flag)"
CMUX_HELP_DISABLED_FLAG="$(cmux_runtime_path state/cmux-help-disabled)"
CMUX_TASK_QUEUE_FILE="$(cmux_runtime_path queue/cmux-task-queue.json)"
CMUX_COMPLETED_TASKS_FILE="$(cmux_runtime_path queue/cmux-completed-tasks.jsonl)"
CMUX_SPECKIT_TRACKER_FILE="$(cmux_runtime_path queue/cmux-speckit-tracker.json)"
CMUX_WATCHER_QUEUE_FILE="$(cmux_runtime_path queue/cmux-queue.json)"
CMUX_WATCHER_LOG_FILE="$(cmux_runtime_path watcher/cmux-watcher.log)"
CMUX_WATCHER_STATE_FILE="$(cmux_runtime_path watcher/cmux-watcher-state.json)"
CMUX_WATCHER_WATCHDOG_PID_FILE="$(cmux_runtime_path watcher/cmux-watcher-watchdog.pid)"
CMUX_WATCHER_SCAN_PID_FILE="$(cmux_runtime_path watcher/cmux-watcher-scan.pid)"
CMUX_WATCHER_HISTORY_FILE="$(cmux_runtime_path watcher/cmux-watcher-history.jsonl)"
CMUX_WATCHER_DEBOUNCE_FILE="$(cmux_runtime_path watcher/cmux-watcher-debounce.json)"
CMUX_WATCHER_PREV_MANAGED_FILE="$(cmux_runtime_path watcher/cmux-watcher-prev-managed.json)"
CMUX_WATCHER_BOOT_SCAN_FILE="$(cmux_runtime_path watcher/cmux-watcher-boot-scan.json)"
CMUX_WATCHER_MUTE_FLAG="$(cmux_runtime_path watcher/cmux-watcher-muted.flag)"
CMUX_PAUSE_FLAG="$(cmux_runtime_path watcher/cmux-paused.flag)"
CMUX_RATE_LIMITED_POOL_FILE="$(cmux_runtime_path watcher/cmux-rate-limited-pool.json)"
CMUX_ERROR_HISTORY_FILE="$(cmux_runtime_path watcher/cmux-error-history.jsonl)"
CMUX_SURFACE_PROFILES_FILE="$(cmux_runtime_path watcher/cmux-surface-profiles.json)"
CMUX_PEER_MESSAGES_FILE="$(cmux_runtime_path watcher/cmux-peer-messages.log)"
CMUX_PIPE_PANE_INITIALIZED_FILE="$(cmux_runtime_path watcher/cmux-pipe-pane-initialized.flag)"
CMUX_ORPHAN_COUNTER_FILE="$(cmux_runtime_path watcher/cmux-orphan-counter.json)"
CMUX_VISION_DIFF_PREV_FILE="$(cmux_runtime_path watcher/cmux-vdiff-prev.json)"
CMUX_VISION_PREV_STATE_FILE="$(cmux_runtime_path watcher/cmux-vision-prev-state.json)"
CMUX_JARVIS_FREEZE_MODE_FILE="$(cmux_runtime_path jarvis/cmux-jarvis-freeze-mode)"
CMUX_JARVIS_BACKUP_LOCK_FILE="$(cmux_runtime_path jarvis/cmux-jarvis-backup.lock)"
CMUX_JARVIS_FILE_CHANGED_DEBOUNCE_FILE="$(cmux_runtime_path jarvis/jarvis-file-changed-last)"
CMUX_JARVIS_SCHEDULER_PID_FILE="$(cmux_runtime_path jarvis/jarvis-scheduler.pid)"
CMUX_COMPAT_SOCK_FILE="$(cmux_runtime_path sockets/cmux-compat.sock)"
CMUX_COMPAT_PID_FILE="$(cmux_runtime_path sockets/cmux-compat.pid)"
CMUX_SCRATCH_DIR="$(cmux_runtime_directory scratch)"
CMUX_VISION_DIFF_DIR="$(cmux_runtime_directory scratch/cmux-vdiff)"
CMUX_VISION_MONITOR_DIR="$(cmux_runtime_directory scratch/cmux-vision-monitor)"
CMUX_STALL_DETECT_DIR="$(cmux_runtime_directory scratch/cmux-stall-detect)"
CMUX_DUAL_MONITOR_DIR="$(cmux_runtime_directory scratch/cmux-dual-monitor)"
CMUX_VISION_MONITOR_PREV_FILE="$(cmux_runtime_path scratch/cmux-vision-monitor-prev.json)"
CMUX_VISION_SCAN_FILE="$(cmux_runtime_path scratch/cmux-vision-scan.png)"
CMUX_VISION_FULLSCREEN_FILE="$(cmux_runtime_path scratch/cmux-vision-fullscreen.png)"
CMUX_EAGLE_ACTIVITY_FILE="$(cmux_runtime_path scratch/cmux-eagle-activity.json)"
CMUX_EAGLE_CALLER_SID_FILE="$(cmux_runtime_path scratch/cmux-eagle-caller-sid.txt)"
CMUX_SHIM_REGISTRY_FILE="$(cmux_runtime_path state/cmux-shim-registry.json)"

export CMUX_ORCH_FLAG
export CMUX_ROLES_FILE
export CMUX_SURFACE_MAP_FILE
export CMUX_SURFACE_SCAN_FILE
export CMUX_EAGLE_STATUS_FILE
export CMUX_WATCHER_ALERTS_FILE
export CMUX_DISPATCH_PENDING_FILE
export CMUX_WORKFLOW_STATE_FILE
export CMUX_INIT_STATE_FILE
export CMUX_VERIFICATION_PASSED_FILE
export CMUX_IDLE_TRACKER_FILE
export CMUX_PASTE_PENDING_FILE
export CMUX_VIOLATION_TRACKER_FILE
export CMUX_ORCHESTRATION_STATE_FILE
export CMUX_LECEIPTS_REPORT_FILE
export CMUX_MENTOR_LAST_HINT_FILE
export CMUX_DISPATCH_SIGNAL_FILE
export CMUX_WATCHER_ENTER_SIGNAL_FILE
export CMUX_DISPATCH_REGISTRY_FILE
export CMUX_REVIEW_STATUS_FILE
export CMUX_SURFACE_FSM_FILE
export CMUX_WELCOME_FLAG
export CMUX_HELP_DISABLED_FLAG
export CMUX_TASK_QUEUE_FILE
export CMUX_COMPLETED_TASKS_FILE
export CMUX_SPECKIT_TRACKER_FILE
export CMUX_WATCHER_QUEUE_FILE
export CMUX_WATCHER_LOG_FILE
export CMUX_WATCHER_STATE_FILE
export CMUX_WATCHER_WATCHDOG_PID_FILE
export CMUX_WATCHER_SCAN_PID_FILE
export CMUX_WATCHER_HISTORY_FILE
export CMUX_WATCHER_DEBOUNCE_FILE
export CMUX_WATCHER_PREV_MANAGED_FILE
export CMUX_WATCHER_BOOT_SCAN_FILE
export CMUX_WATCHER_MUTE_FLAG
export CMUX_PAUSE_FLAG
export CMUX_RATE_LIMITED_POOL_FILE
export CMUX_ERROR_HISTORY_FILE
export CMUX_SURFACE_PROFILES_FILE
export CMUX_PEER_MESSAGES_FILE
export CMUX_PIPE_PANE_INITIALIZED_FILE
export CMUX_ORPHAN_COUNTER_FILE
export CMUX_VISION_DIFF_PREV_FILE
export CMUX_VISION_PREV_STATE_FILE
export CMUX_JARVIS_FREEZE_MODE_FILE
export CMUX_JARVIS_BACKUP_LOCK_FILE
export CMUX_JARVIS_FILE_CHANGED_DEBOUNCE_FILE
export CMUX_JARVIS_SCHEDULER_PID_FILE
export CMUX_COMPAT_SOCK_FILE
export CMUX_COMPAT_PID_FILE
export CMUX_SCRATCH_DIR
export CMUX_VISION_DIFF_DIR
export CMUX_VISION_MONITOR_DIR
export CMUX_STALL_DETECT_DIR
export CMUX_DUAL_MONITOR_DIR
export CMUX_VISION_MONITOR_PREV_FILE
export CMUX_VISION_SCAN_FILE
export CMUX_VISION_FULLSCREEN_FILE
export CMUX_EAGLE_ACTIVITY_FILE
export CMUX_EAGLE_CALLER_SID_FILE
export CMUX_SHIM_REGISTRY_FILE
