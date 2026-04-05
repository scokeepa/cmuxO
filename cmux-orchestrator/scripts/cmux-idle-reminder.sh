#!/bin/bash
# cmux-idle-reminder.sh — UserPromptSubmit hook
# Enhanced: IDLE count, per-surface idle duration, task queue count, surface→task assignment suggestions
# 부하: eagle_watcher.sh --once (bash only, API 0원, ~1초)

# cmux 아니면 무시
[ -n "$CMUX_WORKSPACE_ID" ] || exit 0
command -v cmux &>/dev/null || exit 0

# SKILL_DIR 동적 해석
variable_script_dir="$(cd "$(dirname "$0")" && pwd)"
variable_skill_dir="${SKILL_DIR:-$(dirname "$variable_script_dir")}"
variable_eagle="${variable_skill_dir}/scripts/eagle_watcher.sh"
[ -f "$variable_eagle" ] || exit 0

# eagle --once 실행
bash "$variable_eagle" --once > /dev/null 2>&1

# 상태 파일 읽기
variable_status_file="/tmp/cmux-eagle-status.json"
variable_activity_file="/tmp/cmux-eagle-activity.json"
variable_task_queue="/tmp/cmux-task-queue.json"

[ -f "$variable_status_file" ] || exit 0

# ──────────────────────────────────────────────
# Python으로 통합 분석
# ──────────────────────────────────────────────
python3 -c "
import json, os, time
from datetime import datetime

status_file = '$variable_status_file'
activity_file = '$variable_activity_file'
queue_file = '$variable_task_queue'

now_ts = time.time()

# ── 1. 상태 로드 ──
with open(status_file) as f:
    d = json.load(f)

idle_sids = (d.get('idle_surfaces') or '').strip().split()
idle_sids = [s for s in idle_sids if s]
surfaces = d.get('surfaces', {})

# ── 2. IDLE duration 계산 ──
# activity 파일이 있으면 last_activity 기반, 없으면 추가된 지 너무 오래된 task 기준 fallback
idle_info = {}
if os.path.exists(activity_file):
    with open(activity_file) as f:
        act = json.load(f)
    for sid in idle_sids:
        act_key = f'surface_{sid}'
        last = act.get(act_key, {}).get('last_cmd_at') or act.get(act_key, {}).get('last_activity')
        if last:
            try:
                dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
                idle_sec = int(now_ts - dt.timestamp())
                idle_info[sid] = idle_sec
            except:
                idle_info[sid] = None
        else:
            idle_info[sid] = None
else:
    # fallback: task queue 추가 시각으로 역산
    if os.path.exists(queue_file):
        with open(queue_file) as f:
            queue = json.load(f)
        if queue:
            oldest = queue[0].get('added_at', '')
            try:
                dt = datetime.fromisoformat(oldest.replace('Z', '+00:00'))
                base_sec = int(now_ts - dt.timestamp())
                for sid in idle_sids:
                    idle_info[sid] = base_sec
            except:
                for sid in idle_sids:
                    idle_info[sid] = None
    else:
        for sid in idle_sids:
            idle_info[sid] = None

# ── 3. Task queue 분석 ──
pending_tasks = []
if os.path.exists(queue_file):
    with open(queue_file) as f:
        pending_tasks = json.load(f)

queue_count = len(pending_tasks)

# difficulty → 순위
difficulty_rank = {'high': 0, 'mid': 1, 'low': 2}
sorted_tasks = sorted(pending_tasks, key=lambda x: difficulty_rank.get(x.get('difficulty', 'low'), 9))

# ── 4. AI capability 매칭 ──
# Codex > Sonnet > Claude Code > GLM > MiniMax
capability_order = ['Codex', 'Sonnet', 'Claude Code', 'GLM', 'MiniMax', 'Gemini']

idle_with_ai = []
for sid in idle_sids:
    ai = surfaces.get(sid, {}).get('ai', '?')
    dur = idle_info.get(sid)
    idle_with_ai.append((sid, ai, dur))

# capability 순으로 정렬 (같은 capability면 오래된 순)
idle_with_ai.sort(key=lambda x: (capability_order.index(x[1]) if x[1] in capability_order else 99, x[2] or 0))

# ── 5. 매칭: IDLE surface → sorted task ──
assignments = []
for i, (sid, ai, dur) in enumerate(idle_with_ai):
    if i < len(sorted_tasks):
        t = sorted_tasks[i]
        diff = t.get('difficulty', 'low')
        assignments.append(f's:{sid}→{t[\"id\"]}({diff})')
    else:
        break

# ── 6. 출력 포맷 ──
# IDLE surfaces 요약
if idle_sids:
    parts = []
    for sid, ai, dur in sorted(idle_with_ai, key=lambda x: x[2] or 0, reverse=True):
        dur_str = f'{dur}s' if dur is not None else '?'
        parts.append(f's:{sid}={dur_str}')
    idle_summary = ', '.join(parts)
    idle_count = len(idle_sids)
else:
    idle_summary = ''
    idle_count = 0

# 제안
suggestion = ', '.join(assignments) if assignments else 'none'

# ── 7. 출력 ──
print(f'IDLE_ALERT: {idle_count} surfaces idle ({idle_summary}). Queue: {queue_count} tasks pending. Suggested: {suggestion}')

" 2>/dev/null

