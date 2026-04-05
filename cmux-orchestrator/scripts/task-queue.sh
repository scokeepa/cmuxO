#!/bin/bash
# Task Queue System for cmux orchestration
# JSON file: /tmp/cmux-task-queue.json
# Completed log: /tmp/cmux-completed-tasks.jsonl

set -euo pipefail

QUEUE_FILE="/tmp/cmux-task-queue.json"
COMPLETED_FILE="/tmp/cmux-completed-tasks.jsonl"
COMMAND="${1:-}"
shift || true

function init_queue() {
    if [[ ! -f "$QUEUE_FILE" ]]; then
        echo "[]" > "$QUEUE_FILE"
    fi
}

function init_completed() {
    if [[ ! -f "$COMPLETED_FILE" ]]; then
        echo "" > "$COMPLETED_FILE"
    fi
}

function add_task() {
    local desc="$1"
    local diff="${2:-medium}"
    local priority="${3:-medium}"
    init_queue

    # Validate priority
    case "$priority" in
        critical|high|medium|low) ;;
        *)
        echo "Error: Invalid priority '$priority'. Use: low|medium|high|critical" >&2
        exit 1
        ;;
    esac

    # Validate difficulty
    case "$diff" in
        low|mid|high) ;;
        *) diff="medium" ;;
    esac

    local id
    id=$(python3 -c "
import json
with open('$QUEUE_FILE', 'r') as f:
    tasks = json.load(f)
existing = [int(t['id'][1:]) for t in tasks if t['id'].startswith('t') and t['id'][1:].isdigit()]
next_num = max(existing) + 1 if existing else 1
print(f't{next_num}')
")

    export TASK_DESC="$desc"
    export TASK_DIFF="$diff"
    export TASK_PRIORITY="$priority"
    export TASK_ID="$id"
    export QUEUE_FILE="$QUEUE_FILE"

    python3 <<'PYEOF'
import json
import os
from datetime import datetime, timezone

desc_raw = os.environ.get('TASK_DESC', '')
diff_val = os.environ.get('TASK_DIFF', 'medium')
priority_val = os.environ.get('TASK_PRIORITY', 'medium')
task_id = os.environ.get('TASK_ID', 't1')
queue_path = os.environ.get('QUEUE_FILE', '/tmp/cmux-task-queue.json')

with open(queue_path, 'r') as f:
    tasks = json.load(f)

task = {
    'id': task_id,
    'task': desc_raw,
    'difficulty': diff_val,
    'priority': priority_val,
    'added_at': datetime.now(timezone.utc).isoformat()
}
tasks.append(task)

with open(queue_path, 'w') as f:
    json.dump(tasks, f, indent=2)

print(f"Added task {task_id} [{priority_val}/{diff_val}]: {desc_raw[:60]}")
PYEOF
}

function next_task() {
    local filter_diff="${1:-}"
    local filter_priority="${2:-}"
    init_queue
    init_completed

    python3 <<'PYEOF'
import json
import sys
from datetime import datetime, timezone

queue_path = '/tmp/cmux-task-queue.json'
completed_path = '/tmp/cmux-completed-tasks.jsonl'
filter_diff = sys.argv[1] if len(sys.argv) > 1 else ''
filter_priority = sys.argv[2] if len(sys.argv) > 2 else ''

with open(queue_path, 'r') as f:
    tasks = json.load(f)

if not tasks:
    print('No tasks in queue')
    sys.exit(0)

# Priority order mapping
priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

# Sort by priority (lower = higher priority), then by insertion order
def task_sort_key(t):
    priority_val = priority_order.get(t.get('priority', 'medium'), 2)
    return (priority_val, t['added_at'])

# Filter by difficulty and/or priority if specified
filtered = tasks
if filter_diff and filter_priority:
    filtered = [t for t in tasks if t['difficulty'] == filter_diff and t.get('priority', 'medium') == filter_priority]
elif filter_diff:
    filtered = [t for t in tasks if t['difficulty'] == filter_diff]
elif filter_priority:
    filtered = [t for t in tasks if t.get('priority', 'medium') == filter_priority]

if not filtered:
    if filter_diff and filter_priority:
        print(f"No [{filter_priority}/{filter_diff}] tasks in queue")
    elif filter_diff:
        print(f"No {filter_diff} tasks in queue")
    elif filter_priority:
        print(f"No {filter_priority} priority tasks in queue")
    sys.exit(0)

# Pick highest priority task
filtered.sort(key=task_sort_key)
task = filtered[0]
tasks.remove(task)

with open(queue_path, 'w') as f:
    json.dump(tasks, f, indent=2)

# Log completed task
completed = {
    'id': task['id'],
    'task': task['task'],
    'difficulty': task['difficulty'],
    'priority': task.get('priority', 'medium'),
    'added_at': task['added_at'],
    'completed_at': datetime.now(timezone.utc).isoformat()
}
with open(completed_path, 'a') as f:
    f.write(json.dumps(completed) + '\n')

print(f"ID: {task['id']}")
print(f"Priority: {task.get('priority', 'medium')}")
print(f"Task: {task['task']}")
print(f"Difficulty: {task['difficulty']}")
print(f"Added: {task['added_at']}")
PYEOF
}

function list_tasks() {
    init_queue
    python3 -c "
import json

with open('$QUEUE_FILE', 'r') as f:
    tasks = json.load(f)

if not tasks:
    print('No tasks in queue')
    exit(0)

# Sort by priority
priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
def sort_key(t):
    return (priority_order.get(t.get('priority', 'medium'), 2), t['added_at'])

tasks.sort(key=sort_key)

for i, task in enumerate(tasks, 1):
    p = task.get('priority', 'medium')
    d = task['difficulty']
    print(f\"{i}. [{p}/{d}] {task['id']}: {task['task']}\")
"
}

function count_tasks() {
    init_queue
    python3 -c "
import json

with open('$QUEUE_FILE', 'r') as f:
    tasks = json.load(f)

print(len(tasks))
"
}

function list_completed() {
    init_completed
    if [[ ! -s "$COMPLETED_FILE" ]]; then
        echo "No completed tasks"
        return
    fi
    python3 -c "
import json

with open('$COMPLETED_FILE', 'r') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            task = json.loads(line)
            print(f\"[{task['priority']}/{task['difficulty']}] {task['id']}: {task['task'][:60]} (done: {task['completed_at']})\")
        except:
            pass
"
}

case "$COMMAND" in
    add)
        if [[ $# -lt 1 ]]; then
            echo "Usage: $0 add 'task description' [difficulty:low|mid|high] [priority:low|medium|high|critical]"
            exit 1
        fi
        add_task "$1" "${2:-medium}" "${3:-medium}"
        ;;
    next)
        next_task "${1:-}" "${2:-}"
        ;;
    list)
        list_tasks
        ;;
    count)
        count_tasks
        ;;
    completed)
        list_completed
        ;;
    *)
        echo "Usage: $0 {add|next|list|count|completed} [args]"
        echo "  add 'description' [difficulty] [priority]  - Add task to queue"
        echo "  next [difficulty] [priority]               - Get next task (optional: filter)"
        echo "  list                                      - Show all pending tasks (sorted by priority)"
        echo "  count                                     - Count pending tasks"
        echo "  completed                                 - Show recently completed tasks"
        echo ""
        echo "Priority levels: critical > high > medium > low"
        echo "Difficulty levels: low, mid, high"
        exit 1
        ;;
esac
