#!/usr/bin/env python3
"""test_cmux_utils.py — cmux_utils.py unit tests."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.expanduser("~/.claude/skills/cmux-orchestrator/scripts"))
from cmux_utils import (
    write_json_atomic,
    locked_json_update,
    load_json_safe,
    utc_now,
    enqueue_task,
    dequeue_next,
    complete_task,
)


def test_write_json_atomic():
    path = tempfile.mktemp(suffix=".json")
    try:
        write_json_atomic(path, {"key": "value"})
        with open(path) as f:
            data = json.load(f)
        assert data == {"key": "value"}, f"Expected key=value, got {data}"
    finally:
        os.remove(path)
    print("  write_json_atomic: PASS")


def test_write_json_atomic_creates_dir():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "subdir", "test.json")
    try:
        write_json_atomic(path, {"nested": True})
        assert os.path.exists(path)
        with open(path) as f:
            assert json.load(f) == {"nested": True}
    finally:
        import shutil
        shutil.rmtree(d)
    print("  write_json_atomic_creates_dir: PASS")


def test_locked_json_update_new_file():
    path = tempfile.mktemp(suffix=".json")
    try:
        result = locked_json_update(path, lambda d: {**d, "x": 1}, default={"x": 0})
        assert result == {"x": 1}, f"Expected x=1, got {result}"
    finally:
        if os.path.exists(path):
            os.remove(path)
    print("  locked_json_update_new_file: PASS")


def test_locked_json_update_increment():
    path = tempfile.mktemp(suffix=".json")
    try:
        locked_json_update(path, lambda d: {**d, "count": 1}, default={"count": 0})
        result = locked_json_update(path, lambda d: {**d, "count": d.get("count", 0) + 1})
        assert result["count"] == 2, f"Expected count=2, got {result}"
    finally:
        if os.path.exists(path):
            os.remove(path)
    print("  locked_json_update_increment: PASS")


def test_load_json_safe_missing():
    result = load_json_safe("/tmp/nonexistent_cmux_test.json", {"default": True})
    assert result == {"default": True}
    print("  load_json_safe_missing: PASS")


def test_load_json_safe_valid():
    path = tempfile.mktemp(suffix=".json")
    try:
        with open(path, "w") as f:
            json.dump({"valid": 42}, f)
        result = load_json_safe(path)
        assert result == {"valid": 42}
    finally:
        os.remove(path)
    print("  load_json_safe_valid: PASS")


def test_utc_now_format():
    ts = utc_now()
    assert ts.endswith("Z"), f"Expected Z suffix, got {ts}"
    assert "T" in ts, f"Expected T separator, got {ts}"
    print("  utc_now_format: PASS")


def test_queue_enqueue_dequeue_complete():
    queue_file = "/tmp/cmux-test-queue.json"
    try:
        # cleanup
        if os.path.exists(queue_file):
            os.remove(queue_file)
        # monkey-patch QUEUE_FILE
        import cmux_utils
        orig = cmux_utils.QUEUE_FILE
        cmux_utils.QUEUE_FILE = queue_file

        # enqueue
        tid = enqueue_task({"task": "test job", "ai": "opus"})
        assert tid is not None, "Expected task id"
        assert tid.startswith("task-"), f"Expected task- prefix, got {tid}"

        # dequeue
        task = dequeue_next()
        assert task is not None, "Expected task"
        assert task["status"] == "running", f"Expected running, got {task['status']}"
        assert task["task"] == "test job"

        # complete
        complete_task(tid, "done")
        queue = load_json_safe(queue_file, [])
        assert queue[0]["status"] == "done", f"Expected done, got {queue[0]['status']}"

        # dequeue empty
        task2 = dequeue_next()
        assert task2 is None, "Expected None for empty queue"

        cmux_utils.QUEUE_FILE = orig
    finally:
        if os.path.exists(queue_file):
            os.remove(queue_file)
    print("  queue_enqueue_dequeue_complete: PASS")


def test_queue_locked_concurrent_safety():
    """Verify queue uses locked_json_update (not load+write)."""
    import inspect
    src = inspect.getsource(enqueue_task)
    assert "locked_json_update" in src, "enqueue_task must use locked_json_update"
    src2 = inspect.getsource(dequeue_next)
    assert "locked_json_update" in src2, "dequeue_next must use locked_json_update"
    src3 = inspect.getsource(complete_task)
    assert "locked_json_update" in src3, "complete_task must use locked_json_update"
    print("  queue_locked_concurrent_safety: PASS")


if __name__ == "__main__":
    print("=== cmux_utils.py tests ===")
    test_write_json_atomic()
    test_write_json_atomic_creates_dir()
    test_locked_json_update_new_file()
    test_locked_json_update_increment()
    test_load_json_safe_missing()
    test_load_json_safe_valid()
    test_utc_now_format()
    test_queue_enqueue_dequeue_complete()
    test_queue_locked_concurrent_safety()
    print("=== ALL PASSED ===")
