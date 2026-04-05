#!/usr/bin/env python3
"""speckit-tracker.py — Speckit 태스크 추적기

디스패치 시 태스크 등록, 수집 시 완료 마킹.
gate-enforcer.py가 이 파일을 읽어 미완료 태스크를 감지.

Usage:
  python3 speckit-tracker.py --init "Round 12"            # 라운드 초기화
  python3 speckit-tracker.py --add T1 surface:3 "export"  # 태스크 등록
  python3 speckit-tracker.py --done T1                    # 완료 마킹
  python3 speckit-tracker.py --fail T1 "sandbox 제약"     # 실패 마킹
  python3 speckit-tracker.py --reassign T1 surface:1      # 재배정
  python3 speckit-tracker.py --status                     # 상태 출력
  python3 speckit-tracker.py --stats                      # 라운드 통계
  python3 speckit-tracker.py --history                    # 이전 라운드 히스토리
  python3 speckit-tracker.py --gate                       # GATE 5 검증
  python3 speckit-tracker.py --status --json              # JSON 출력
"""

import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TRACKER_FILE = Path(os.environ.get("TRACKER_FILE", "/tmp/cmux-speckit-tracker.json"))
SURFACE_PATTERN = re.compile(r"^surface:\d+$")


def empty_tracker() -> dict:
    return {
        "schema_version": 2,
        "round": "",
        "tasks": {},
        "created_at": "",
        "history": [],
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def duration_seconds(start: str, end: str):
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    if not start_dt or not end_dt:
        return None
    return max(0, int((end_dt - start_dt).total_seconds()))


def format_duration(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def normalize_task(task: dict) -> dict:
    task = dict(task)
    started_at = task.get("started_at") or task.get("assigned_at") or ""
    if started_at:
        task["started_at"] = started_at
        task.setdefault("assigned_at", started_at)
    else:
        task.setdefault("started_at", "")
        task.setdefault("assigned_at", "")

    if task.get("status") == "failed" and task.get("completed_at") and not task.get("failed_at"):
        task["failed_at"] = task["completed_at"]

    task.setdefault("completed_at", "")
    task.setdefault("failed_at", "")
    task.setdefault("reason", task.get("reason", ""))
    task.setdefault("last_failure_reason", task.get("reason", "") if task.get("status") == "failed" else "")
    task.setdefault("last_failure_at", task.get("failed_at", ""))
    task.setdefault("reassignments", [])
    return task


def normalize_round(round_data: dict) -> dict:
    result = {
        "round": round_data.get("round", ""),
        "tasks": {},
        "created_at": round_data.get("created_at", ""),
    }
    if round_data.get("archived_at"):
        result["archived_at"] = round_data["archived_at"]

    for tid, task in round_data.get("tasks", {}).items():
        result["tasks"][tid] = normalize_task(task)
    return result


def normalize_tracker(data: dict) -> dict:
    normalized = empty_tracker()
    normalized.update(
        {
            "schema_version": data.get("schema_version", 2),
            "round": data.get("round", ""),
            "tasks": {},
            "created_at": data.get("created_at", ""),
            "history": [],
        }
    )

    for tid, task in data.get("tasks", {}).items():
        normalized["tasks"][tid] = normalize_task(task)

    for entry in data.get("history", []):
        normalized["history"].append(normalize_round(entry))

    return normalized


def load() -> dict:
    if TRACKER_FILE.exists():
        return normalize_tracker(json.loads(TRACKER_FILE.read_text()))
    return empty_tracker()


def save(data: dict):
    """Atomic write: temp 파일에 쓰고 rename (POSIX atomic)."""
    content = json.dumps(data, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=TRACKER_FILE.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(content)
        tmp_path = handle.name
    shutil.move(tmp_path, str(TRACKER_FILE))


def usage() -> str:
    return (
        "Usage: speckit-tracker.py --init|--add|--done|--fail|--reassign|"
        "--status|--stats|--history|--gate [--json]"
    )


def extract_cli(argv):
    json_mode = False
    args = []
    for item in argv[1:]:
        if item == "--json":
            json_mode = True
        else:
            args.append(item)
    return json_mode, args


def round_snapshot(data: dict, archived_at: str = "") -> dict:
    snapshot = normalize_round(
        {
            "round": data.get("round", ""),
            "tasks": data.get("tasks", {}),
            "created_at": data.get("created_at", ""),
        }
    )
    if archived_at:
        snapshot["archived_at"] = archived_at
    return snapshot


def has_current_round(data: dict) -> bool:
    return bool(data.get("round") or data.get("tasks") or data.get("created_at"))


def task_finished_at(task: dict) -> str:
    return task.get("completed_at") or task.get("failed_at") or ""


def surface_sort_key(surface: str):
    if isinstance(surface, str) and surface.startswith("surface:"):
        suffix = surface.split(":", 1)[1]
        if suffix.isdigit():
            return (0, int(suffix))
    return (1, str(surface))


def task_attempts(tid: str, task: dict):
    attempts = []
    attempt_start = task.get("started_at") or task.get("assigned_at") or ""

    for event in task.get("reassignments", []):
        previous_status = event.get("previous_status", "pending")
        attempt_status = previous_status if previous_status in {"done", "failed"} else "reassigned"
        attempts.append(
            {
                "task_id": tid,
                "surface": event.get("from", "unknown"),
                "status": attempt_status,
                "description": task.get("description", ""),
                "started_at": attempt_start,
                "completed_at": event.get("at", ""),
                "duration_seconds": duration_seconds(attempt_start, event.get("at", "")),
            }
        )
        attempt_start = event.get("at", "") or attempt_start

    attempts.append(
        {
            "task_id": tid,
            "surface": task.get("surface", "unknown"),
            "status": task.get("status", "pending"),
            "description": task.get("description", ""),
            "started_at": attempt_start,
            "completed_at": task_finished_at(task),
            "duration_seconds": duration_seconds(attempt_start, task_finished_at(task)),
        }
    )
    return attempts


def compute_round_stats(round_data: dict) -> dict:
    tasks = round_data.get("tasks", {})
    total = len(tasks)
    done = 0
    failed = 0
    pending = 0
    durations = []
    finished_times = []
    surfaces = {}

    for tid, task in tasks.items():
        status = task.get("status", "pending")
        started_at = task.get("started_at") or task.get("assigned_at") or ""
        finished_at = task_finished_at(task)
        duration = duration_seconds(started_at, finished_at)

        if status == "done":
            done += 1
        elif status == "failed":
            failed += 1
        else:
            pending += 1

        if duration is not None:
            durations.append(duration)

        finished_dt = parse_iso(finished_at)
        if finished_dt:
            finished_times.append(finished_dt)

        for attempt in task_attempts(tid, task):
            surface_bucket = surfaces.setdefault(
                attempt["surface"],
                {
                    "surface": attempt["surface"],
                    "total": 0,
                    "done": 0,
                    "failed": 0,
                    "pending": 0,
                    "reassigned": 0,
                    "durations": [],
                    "tasks": [],
                },
            )
            surface_bucket["total"] += 1
            surface_bucket["tasks"].append(attempt)

            if attempt["status"] == "done":
                surface_bucket["done"] += 1
            elif attempt["status"] == "failed":
                surface_bucket["failed"] += 1
            elif attempt["status"] == "reassigned":
                surface_bucket["reassigned"] += 1
            else:
                surface_bucket["pending"] += 1

            if attempt["duration_seconds"] is not None:
                surface_bucket["durations"].append(attempt["duration_seconds"])

    created_at = round_data.get("created_at", "")
    completed_at = ""
    if total and pending == 0 and finished_times:
        completed_at = max(finished_times).strftime("%Y-%m-%dT%H:%M:%SZ")

    round_duration = duration_seconds(created_at, completed_at)
    avg_duration = int(sum(durations) / len(durations)) if durations else None

    surface_stats = []
    for bucket in sorted(surfaces.values(), key=lambda item: surface_sort_key(item["surface"])):
        duration_values = bucket.pop("durations")
        terminal = bucket["done"] + bucket["failed"]
        bucket["success_rate"] = round((bucket["done"] / terminal) * 100, 1) if terminal else None
        bucket["avg_duration_seconds"] = (
            int(sum(duration_values) / len(duration_values)) if duration_values else None
        )
        surface_stats.append(bucket)

    return {
        "round": round_data.get("round", ""),
        "created_at": created_at,
        "completed_at": completed_at,
        "archived_at": round_data.get("archived_at", ""),
        "total": total,
        "done": done,
        "failed": failed,
        "pending": pending,
        "avg_duration_seconds": avg_duration,
        "round_duration_seconds": round_duration,
        "surfaces": surface_stats,
    }


def collect_rounds(data: dict):
    rounds = [normalize_round(entry) for entry in data.get("history", [])]
    if has_current_round(data):
        rounds.append(round_snapshot(data))
    return rounds


def status_payload(data: dict) -> dict:
    stats = compute_round_stats(round_snapshot(data))
    tasks = []
    for tid, info in sorted(data.get("tasks", {}).items()):
        tasks.append(
            {
                "task_id": tid,
                "surface": info.get("surface", ""),
                "description": info.get("description", ""),
                "status": info.get("status", "pending"),
                "started_at": info.get("started_at") or info.get("assigned_at") or "",
                "completed_at": task_finished_at(info),
                "reason": info.get("reason", ""),
                "last_failure_reason": info.get("last_failure_reason", ""),
                "reassignments": info.get("reassignments", []),
            }
        )

    return {
        "round": data.get("round", ""),
        "created_at": data.get("created_at", ""),
        "summary": {
            "total": stats["total"],
            "done": stats["done"],
            "failed": stats["failed"],
            "pending": stats["pending"],
        },
        "tasks": tasks,
    }


def stats_payload(data: dict) -> dict:
    rounds = [compute_round_stats(entry) for entry in collect_rounds(data)]
    return {"rounds": rounds}


def history_payload(data: dict) -> dict:
    history = []
    for entry in normalize_tracker(data).get("history", []):
        summary = compute_round_stats(entry)
        tasks = []
        for tid, task in sorted(entry.get("tasks", {}).items()):
            tasks.append(
                {
                    "task_id": tid,
                    "surface": task.get("surface", ""),
                    "description": task.get("description", ""),
                    "status": task.get("status", "pending"),
                    "started_at": task.get("started_at") or task.get("assigned_at") or "",
                    "completed_at": task_finished_at(task),
                    "reason": task.get("reason", ""),
                    "last_failure_reason": task.get("last_failure_reason", ""),
                    "reassignments": task.get("reassignments", []),
                }
            )
        history.append({"summary": summary, "tasks": tasks})
    return {"history": history}


def emit(payload: dict, json_mode: bool, lines=None, exit_code: int = 0):
    payload = dict(payload)
    payload.setdefault("ok", exit_code == 0)
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in lines or []:
            print(line)
    return exit_code


def error(message: str, json_mode: bool, exit_code: int = 1, **payload):
    payload.update({"error": message, "ok": False})
    return emit(payload, json_mode=json_mode, lines=[message], exit_code=exit_code)


def validate_surface(surface: str) -> bool:
    return bool(SURFACE_PATTERN.match(surface))


def cmd_init(data: dict, args, json_mode: bool):
    round_name = args[1] if len(args) > 1 else "unknown"
    archived_at = now_iso()
    history = list(data.get("history", []))
    if has_current_round(data):
        history.append(round_snapshot(data, archived_at=archived_at))

    new_data = {
        "schema_version": 2,
        "round": round_name,
        "tasks": {},
        "created_at": archived_at,
        "history": history,
    }
    save(new_data)
    return emit(
        {
            "message": f"Tracker initialized: {round_name}",
            "round": round_name,
            "created_at": new_data["created_at"],
            "history_count": len(history),
        },
        json_mode=json_mode,
        lines=[f"Tracker initialized: {round_name}"],
    )


def cmd_add(data: dict, args, json_mode: bool):
    if len(args) < 4:
        return error("Usage: --add TASK_ID SURFACE_ID DESCRIPTION", json_mode)

    tid, surface, description = args[1], args[2], args[3]
    tasks = data.setdefault("tasks", {})

    if not tid or len(tid) > 30:
        return error(f"❌ Invalid TASK_ID: '{tid}' (1-30 chars)", json_mode)
    if tid in tasks:
        return error(
            f"⚠️ TASK_ID '{tid}' already exists — use --fail + --reassign for rework",
            json_mode,
        )
    if not validate_surface(surface):
        return error(f"❌ Invalid SURFACE_ID: '{surface}' (must be 'surface:N')", json_mode)
    if not description:
        return error("❌ DESCRIPTION cannot be empty", json_mode)

    started_at = now_iso()
    tasks[tid] = {
        "surface": surface,
        "description": description[:200],
        "status": "pending",
        "assigned_at": started_at,
        "started_at": started_at,
        "completed_at": "",
        "failed_at": "",
        "reassignments": [],
    }
    save(data)
    return emit(
        {
            "message": f"Added: {tid} → {surface}: {description[:50]}",
            "task": {
                "task_id": tid,
                "surface": surface,
                "description": description[:200],
                "status": "pending",
                "started_at": started_at,
            },
        },
        json_mode=json_mode,
        lines=[f"Added: {tid} → {surface}: {description[:50]}"],
    )


def cmd_done(data: dict, args, json_mode: bool):
    tid = args[1] if len(args) > 1 else ""
    tasks = data.get("tasks", {})
    if tid not in tasks:
        return error(f"Task not found: {tid}", json_mode)

    completed_at = now_iso()
    task = tasks[tid]
    task["status"] = "done"
    task["completed_at"] = completed_at
    task["failed_at"] = ""
    task["reason"] = ""
    save(data)
    return emit(
        {
            "message": f"Done: {tid}",
            "task": {
                "task_id": tid,
                "status": "done",
                "completed_at": completed_at,
            },
        },
        json_mode=json_mode,
        lines=[f"Done: {tid}"],
    )


def cmd_fail(data: dict, args, json_mode: bool):
    tid = args[1] if len(args) > 1 else ""
    reason = args[2] if len(args) > 2 else "unknown"
    tasks = data.get("tasks", {})
    if tid not in tasks:
        return error(f"Task not found: {tid}", json_mode)

    failed_at = now_iso()
    task = tasks[tid]
    task["status"] = "failed"
    task["reason"] = reason
    task["failed_at"] = failed_at
    task["last_failure_reason"] = reason
    task["last_failure_at"] = failed_at
    task["completed_at"] = failed_at
    save(data)
    return emit(
        {
            "message": f"Failed: {tid} — {reason}",
            "task": {
                "task_id": tid,
                "status": "failed",
                "reason": reason,
                "completed_at": failed_at,
            },
        },
        json_mode=json_mode,
        lines=[f"Failed: {tid} — {reason}"],
    )


def cmd_reassign(data: dict, args, json_mode: bool):
    if len(args) < 3:
        return error("Usage: --reassign TASK_ID NEW_SURFACE", json_mode)

    tid, new_surface = args[1], args[2]
    tasks = data.get("tasks", {})
    if tid not in tasks:
        return error(f"Task not found: {tid}", json_mode)
    if not validate_surface(new_surface):
        return error(
            f"❌ Invalid SURFACE_ID: '{new_surface}' (must be 'surface:N')",
            json_mode,
        )

    task = tasks[tid]
    old_surface = task.get("surface", "")
    reassigned_at = now_iso()
    task.setdefault("reassignments", []).append(
        {
            "from": old_surface,
            "to": new_surface,
            "at": reassigned_at,
            "previous_status": task.get("status", "pending"),
        }
    )
    task["surface"] = new_surface
    task["status"] = "pending"
    task["reassigned_at"] = reassigned_at
    task["completed_at"] = ""
    task["failed_at"] = ""
    task["reason"] = ""
    save(data)
    return emit(
        {
            "message": f"Reassigned: {tid} {old_surface} → {new_surface}",
            "task": {
                "task_id": tid,
                "old_surface": old_surface,
                "new_surface": new_surface,
                "status": "pending",
                "reassigned_at": reassigned_at,
            },
        },
        json_mode=json_mode,
        lines=[f"Reassigned: {tid} {old_surface} → {new_surface}"],
    )


def cmd_status(data: dict, json_mode: bool):
    payload = status_payload(data)
    lines = [
        f"Round: {payload['round'] or '?'}",
        (
            "Tasks: "
            f"{payload['summary']['total']} "
            f"(done:{payload['summary']['done']} "
            f"failed:{payload['summary']['failed']} "
            f"pending:{payload['summary']['pending']})"
        ),
    ]

    for task in payload["tasks"]:
        status = task["status"]
        if status == "done":
            mark = "✅"
        elif status == "failed":
            mark = "❌"
        else:
            mark = "⏳"
        timing = task["completed_at"] or task["started_at"] or "-"
        lines.append(
            f"  {mark} {task['task_id']} [{task['surface']}] "
            f"{task['description'][:40]} @ {timing}"
        )

    return emit(payload, json_mode=json_mode, lines=lines)


def cmd_gate(data: dict, json_mode: bool):
    incomplete = [
        {
            "task_id": tid,
            "surface": info.get("surface", ""),
            "status": info.get("status", "pending"),
            "description": info.get("description", ""),
        }
        for tid, info in sorted(data.get("tasks", {}).items())
        if info.get("status") not in ("done",)
    ]
    if incomplete:
        lines = [f"⛔ GATE 5 BLOCKED: {len(incomplete)} 미완료 태스크"]
        for item in incomplete:
            lines.append(
                f"  → {item['task_id']} [{item['surface']}] "
                f"{item['status']}: {item['description'][:40]}"
            )
        return emit(
            {"blocked_tasks": incomplete},
            json_mode=json_mode,
            lines=lines,
            exit_code=1,
        )

    total = len(data.get("tasks", {}))
    return emit(
        {"message": f"✅ GATE 5 PASSED: {total}/{total} 태스크 완료", "total": total},
        json_mode=json_mode,
        lines=[f"✅ GATE 5 PASSED: {total}/{total} 태스크 완료"],
        exit_code=0,
    )


def cmd_stats(data: dict, json_mode: bool):
    payload = stats_payload(data)
    rounds = payload["rounds"]
    if not rounds:
        return emit(payload, json_mode=json_mode, lines=["No rounds found."])

    lines = []
    for index, item in enumerate(rounds, start=1):
        completed = item["completed_at"] or "in-progress"
        avg = format_duration(item["avg_duration_seconds"])
        round_duration = format_duration(item["round_duration_seconds"])
        lines.append(
            f"[{index}] {item['round'] or 'unknown'} | "
            f"tasks:{item['total']} done:{item['done']} "
            f"failed:{item['failed']} pending:{item['pending']} | "
            f"completed:{completed} | avg:{avg} | round:{round_duration}"
        )
        for surface in item["surfaces"]:
            success = (
                f"{surface['success_rate']}%"
                if surface["success_rate"] is not None
                else "-"
            )
            lines.append(
                f"  - {surface['surface']}: total:{surface['total']} "
                f"done:{surface['done']} failed:{surface['failed']} "
                f"pending:{surface['pending']} reassigned:{surface['reassigned']} success:{success} "
                f"avg:{format_duration(surface['avg_duration_seconds'])}"
            )

    return emit(payload, json_mode=json_mode, lines=lines)


def cmd_history(data: dict, json_mode: bool):
    payload = history_payload(data)
    history = payload["history"]
    if not history:
        return emit(payload, json_mode=json_mode, lines=["No archived rounds found."])

    lines = [f"Archived rounds: {len(history)}"]
    for index, item in enumerate(history, start=1):
        summary = item["summary"]
        completed = summary["completed_at"] or "in-progress"
        archived = summary["archived_at"] or "-"
        lines.append(
            f"[{index}] {summary['round'] or 'unknown'} | archived:{archived} | "
            f"completed:{completed} | tasks:{summary['total']} "
            f"(done:{summary['done']} failed:{summary['failed']} pending:{summary['pending']})"
        )
        for task in item["tasks"]:
            lines.append(
                f"  - {task['task_id']} [{task['surface']}] "
                f"{task['status']}: {task['description'][:40]}"
            )

    return emit(payload, json_mode=json_mode, lines=lines)


def main():
    json_mode, args = extract_cli(sys.argv)
    if not args:
        return emit({"usage": usage()}, json_mode=json_mode, lines=[usage()], exit_code=1)

    cmd = args[0]
    data = load()

    if cmd == "--init":
        return cmd_init(data, args, json_mode)
    if cmd == "--add":
        return cmd_add(data, args, json_mode)
    if cmd == "--done":
        return cmd_done(data, args, json_mode)
    if cmd == "--fail":
        return cmd_fail(data, args, json_mode)
    if cmd == "--reassign":
        return cmd_reassign(data, args, json_mode)
    if cmd == "--status":
        return cmd_status(data, json_mode)
    if cmd == "--stats":
        return cmd_stats(data, json_mode)
    if cmd == "--history":
        return cmd_history(data, json_mode)
    if cmd == "--gate":
        return cmd_gate(data, json_mode)

    return error(usage(), json_mode)


if __name__ == "__main__":
    sys.exit(main())
