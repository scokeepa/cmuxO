#!/usr/bin/env python3
"""cmux_utils.py — 공통 유틸리티.

모든 hook과 watcher-scan.py가 공유하는 원자적 JSON 쓰기 + 파일 잠금.

사용법:
    import sys, os
    sys.path.insert(0, os.path.expanduser('~/.claude/skills/cmux-orchestrator/scripts'))
    from cmux_utils import write_json_atomic, locked_json_update
"""
import fcntl
import json
import os
import tempfile
import time
from datetime import datetime, timezone


def write_json_atomic(path, data):
    """원자적 JSON 쓰기: 임시 파일 기록 후 os.rename()으로 교체."""
    path = str(path)
    dir_name = os.path.dirname(path) or "/tmp"
    os.makedirs(dir_name, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=dir_name, delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.rename(tmp_path, path)


def locked_json_update(path, update_fn, default=None):
    """파일 잠금 + JSON 읽기-수정-저장. 파일 미존재 시 default로 생성."""
    path = str(path)
    if default is None:
        default = {}
    # TOCTOU 방지: 파일 열기를 try/except로 감싸고, 없으면 생성 후 재시도
    for attempt in range(2):
        try:
            with open(path, "r+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = default.copy()
                data = update_fn(data)
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2, ensure_ascii=False)
                fcntl.flock(f, fcntl.LOCK_UN)
            return data
        except FileNotFoundError:
            if attempt == 0:
                write_json_atomic(path, default)
            else:
                raise
    return default


def load_json_safe(path, default=None):
    """JSON 파일 안전 로드. 파일 없거나 파싱 실패 시 default 반환."""
    if default is None:
        default = {}
    try:
        with open(str(path)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return default


def utc_now():
    """UTC ISO 8601 타임스탬프."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Task Queue
# ---------------------------------------------------------------------------

QUEUE_FILE = "/tmp/cmux-task-queue.json"


def enqueue_task(task):
    """대기열에 작업 추가. locked_json_update로 race condition 방지."""
    task_copy = dict(task)
    task_copy["id"] = f"task-{int(time.time())}"
    task_copy["queued_at"] = utc_now()
    task_copy["status"] = "pending"

    def _enqueue(queue):
        if not isinstance(queue, list):
            queue = []
        queue.append(task_copy)
        return queue

    locked_json_update(QUEUE_FILE, _enqueue, default=[])
    return task_copy["id"]


def dequeue_next():
    """대기열에서 pending 작업 1개를 running으로 변경하고 반환."""
    result = [None]

    def _dequeue(queue):
        if not isinstance(queue, list):
            return []
        for task in queue:
            if task.get("status") == "pending":
                task["status"] = "running"
                task["started_at"] = utc_now()
                result[0] = dict(task)
                break
        return queue

    locked_json_update(QUEUE_FILE, _dequeue, default=[])
    return result[0]


def is_boss_surface():
    """현재 surface가 오케스트레이션 사장(Boss)인지 판별.
    Boss이면 True -> 워크플로우 규율 적용.
    Boss가 아니면 False → 제한 없이 통과.
    cmux 환경이 아니거나 식별 실패 시 False (안전하게 통과).
    """
    import subprocess
    try:
        result = subprocess.run(
            ["cmux", "identify"],
            capture_output=True, text=True, timeout=3
        )
        caller = json.loads(result.stdout).get("caller", {})
        my_surface = caller.get("surface_ref", "")
    except Exception:
        return False

    if not my_surface:
        return False

    roles = load_json_safe("/tmp/cmux-roles.json")
    boss_surface = roles.get("boss", {}).get("surface", "")
    return my_surface == boss_surface and boss_surface != ""


def complete_task(task_id, status="done"):
    """작업 완료/실패 처리."""
    def _complete(queue):
        if not isinstance(queue, list):
            return []
        for task in queue:
            if task.get("id") == task_id:
                task["status"] = status
                task["completed_at"] = utc_now()
        return queue

    locked_json_update(QUEUE_FILE, _complete, default=[])
