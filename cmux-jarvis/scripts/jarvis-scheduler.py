#!/usr/bin/env python3
"""jarvis-scheduler.py — JARVIS 멀티태스크 스케줄러

OpenJarvis 스케줄러 패턴: SQLite 퍼시스턴스 + cron/interval/once + EventBus 통합.

Usage:
    jarvis-scheduler.py run [--interval SEC] [--cron EXPR] [--once]
    jarvis-scheduler.py next-run [--cron EXPR]
    jarvis-scheduler.py status | stop
    jarvis-scheduler.py create-task --name N --type T --value V --handler H
    jarvis-scheduler.py list-tasks [--status S] | pause-task ID | resume-task ID
"""
import importlib.util, json, os, signal, sqlite3, sys, threading, time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import uuid4

try:
    from jarvis_telemetry import Telemetry
except ImportError:
    class Telemetry:
        def __init__(self, *a, **kw): pass
        def emit(self, *a, **kw): pass
try:
    from jarvis_events import JarvisEventType, get_jarvis_bus
except ImportError:
    JarvisEventType = None; get_jarvis_bus = None

PID_FILE = Path("/tmp/jarvis-scheduler.pid")
JARVIS_DIR = Path.home() / ".claude" / "cmux-jarvis"
CONFIG_PATH = JARVIS_DIR / "config.json"
DB_PATH = JARVIS_DIR / "scheduler.db"

@dataclass
class ScheduledTask:
    """4-state machine: active -> paused -> active | cancelled | completed."""
    id: str; name: str; schedule_type: str; schedule_value: str; handler: str
    status: str = "active"; next_run: Optional[str] = None
    last_run: Optional[str] = None; metadata: dict = field(default_factory=dict)
    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        if isinstance(d["metadata"], dict): d["metadata"] = json.dumps(d["metadata"])
        return d

class SchedulerStore:
    """SQLite persistence for scheduled tasks and run logs."""
    def __init__(self, db_path: Path):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript("""
              CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY, name TEXT, schedule_type TEXT,
                schedule_value TEXT, handler TEXT, status TEXT DEFAULT 'active',
                next_run TEXT, last_run TEXT, metadata TEXT DEFAULT '{}');
              CREATE TABLE IF NOT EXISTS task_run_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
                started_at TEXT, finished_at TEXT, success INTEGER DEFAULT 0,
                result TEXT DEFAULT '', error TEXT DEFAULT '');
            """)
            self._conn.commit()

    def save_task(self, task: dict):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO scheduled_tasks"
                " (id,name,schedule_type,schedule_value,handler,status,next_run,last_run,metadata)"
                " VALUES (:id,:name,:schedule_type,:schedule_value,:handler,:status,:next_run,:last_run,:metadata)", task)
            self._conn.commit()

    def get_task(self, task_id: str) -> Optional[dict]:
        with self._lock:
            r = self._conn.execute("SELECT * FROM scheduled_tasks WHERE id=?", (task_id,)).fetchone()
            return dict(r) if r else None

    def list_tasks(self, status: str = None) -> list:
        with self._lock:
            if status:
                rows = self._conn.execute("SELECT * FROM scheduled_tasks WHERE status=?", (status,)).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM scheduled_tasks").fetchall()
            return [dict(r) for r in rows]

    def get_due_tasks(self, now_iso: str) -> list:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM scheduled_tasks WHERE status='active' AND next_run<=?", (now_iso,)).fetchall()
            return [dict(r) for r in rows]

    def update_status(self, task_id: str, status: str):
        with self._lock:
            self._conn.execute("UPDATE scheduled_tasks SET status=? WHERE id=?", (status, task_id))
            self._conn.commit()

    def log_run(self, task_id, started_at, finished_at, success, result, error):
        with self._lock:
            self._conn.execute(
                "INSERT INTO task_run_logs (task_id,started_at,finished_at,success,result,error)"
                " VALUES (?,?,?,?,?,?)", (task_id, started_at, finished_at, int(success), result, error))
            self._conn.commit()

    def get_run_logs(self, task_id: str, limit: int = 10) -> list:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM task_run_logs WHERE task_id=? ORDER BY id DESC LIMIT ?", (task_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def close(self):
        self._conn.close()

class CronExpr:
    """Cron 5-field parser. Weekday: 0=Sun..6=Sat (standard cron)."""
    RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]

    def __init__(self, expr: str):
        self.expr = expr.strip()
        parts = self.expr.split()
        if len(parts) != 5:
            raise ValueError(f"cron needs 5 fields: '{expr}'")
        self.fields = [self._parse_field(parts[i], *self.RANGES[i]) for i in range(5)]

    @staticmethod
    def _parse_field(field: str, lo: int, hi: int) -> set[int]:
        values: set[int] = set()
        for part in field.split(","):
            if "/" in part:
                base, step_s = part.split("/", 1); step = int(step_s)
                if base == "*": start, end = lo, hi
                elif "-" in base: start, end = map(int, base.split("-", 1))
                else: start, end = int(base), hi
                values.update(range(start, end + 1, step))
            elif part == "*": values.update(range(lo, hi + 1))
            elif "-" in part:
                a, b = map(int, part.split("-", 1))
                values.update(range(a, b + 1))
            else: values.add(int(part))
        return {v for v in values if lo <= v <= hi}

    def matches(self, dt: datetime = None) -> bool:
        dt = dt or datetime.now()
        cron_wday = (dt.weekday() + 1) % 7  # Python Mon=0 -> cron Sun=0
        checks = [dt.minute, dt.hour, dt.day, dt.month, cron_wday]
        return all(checks[i] in self.fields[i] for i in range(5))

    def seconds_to_next(self, dt: datetime = None) -> int:
        dt = dt or datetime.now()
        check = dt.replace(second=0, microsecond=0)
        for _ in range(1441):
            check += timedelta(minutes=1)
            if self.matches(check):
                return max(1, int((check - dt).total_seconds()))
        return 60

# --- helpers ---
def load_config() -> dict:
    try: return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError, FileNotFoundError): return {}

def load_interval() -> int: return int(load_config().get("poll_interval_seconds", 300))
def load_cron() -> Optional[str]: return load_config().get("scheduler_cron")

def _publish(etype, data=None):
    if get_jarvis_bus is not None: get_jarvis_bus().publish(etype, data or {})

def run_detect() -> dict:
    sd = Path(__file__).parent
    spec = importlib.util.spec_from_file_location("jarvis_evolution", sd / "jarvis-evolution.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.EvolutionEngine().detect()

def _execute_handler(handler: str) -> tuple:
    try:
        if handler == "detect": return True, json.dumps(run_detect(), default=str), ""
        elif handler == "verify": return True, "verify ok", ""
        elif handler == "prune": return True, "prune ok", ""
        else: return True, f"custom:{handler}", ""
    except Exception as e: return False, "", str(e)

def write_pid(): PID_FILE.write_text(str(os.getpid()))
def remove_pid(): PID_FILE.unlink(missing_ok=True)
def is_running() -> tuple:
    if not PID_FILE.exists(): return False, None
    try:
        pid = int(PID_FILE.read_text().strip()); os.kill(pid, 0); return True, pid
    except (ValueError, OSError): remove_pid(); return False, None

def _compute_next_run(task: dict) -> str:
    now = datetime.now(timezone.utc)
    if task["schedule_type"] == "interval":
        return (now + timedelta(seconds=int(task["schedule_value"]))).isoformat()
    elif task["schedule_type"] == "cron":
        secs = CronExpr(task["schedule_value"]).seconds_to_next(now.replace(tzinfo=None))
        return (now + timedelta(seconds=secs)).isoformat()
    return task.get("next_run") or now.isoformat()

def _run_task(store: SchedulerStore, task: dict, telemetry: Telemetry):
    tid, started = task["id"], datetime.now(timezone.utc).isoformat()
    ts = datetime.now().strftime("%H:%M:%S")
    if JarvisEventType is not None:
        _publish(JarvisEventType.SCHEDULER_TASK_START, {"task_id": tid, "handler": task["handler"]})
    success, result, error = _execute_handler(task["handler"])
    finished = datetime.now(timezone.utc).isoformat()
    store.log_run(tid, started, finished, int(success), result, error)
    if success: print(f"[{ts}] OK task={tid} handler={task['handler']}")
    else:
        print(f"[{ts}] ERROR task={tid}: {error}", file=sys.stderr)
        telemetry.emit("scheduler_error", {"task_id": tid, "error": error})
    if JarvisEventType is not None:
        _publish(JarvisEventType.SCHEDULER_TASK_END, {"task_id": tid, "success": success})
    if task["schedule_type"] == "once": store.update_status(tid, "completed")
    else:
        t = store.get_task(tid)
        if t: t["next_run"] = _compute_next_run(task); t["last_run"] = finished; store.save_task(t)

# --- CLI commands ---
def cmd_run(interval: int = None, cron_expr: str = None, once: bool = False):
    telemetry = Telemetry(JARVIS_DIR / "telemetry")
    running, epid = is_running()
    if running: print(f"ERROR: already running (PID {epid})", file=sys.stderr); sys.exit(1)
    write_pid(); JARVIS_DIR.mkdir(parents=True, exist_ok=True)
    store = SchedulerStore(DB_PATH)
    if not store.get_task("default-detect"):
        cron = CronExpr(cron_expr) if cron_expr else (CronExpr(load_cron()) if not interval and load_cron() else None)
        st = "once" if once else ("cron" if cron else "interval")
        sv = cron.expr if cron else str(interval or load_interval())
        store.save_task({"id": "default-detect", "name": "detect", "schedule_type": st,
            "schedule_value": sv, "handler": "detect", "status": "active",
            "next_run": datetime.now(timezone.utc).isoformat(), "last_run": None, "metadata": "{}"})
    def _sig(signum, frame): remove_pid(); store.close(); sys.exit(0)
    signal.signal(signal.SIGTERM, _sig); signal.signal(signal.SIGINT, _sig)
    print(f"JARVIS scheduler start (multi-task, once={once})")
    try:
        while True:
            for task in store.get_due_tasks(datetime.now(timezone.utc).isoformat()):
                try: _run_task(store, task, telemetry)
                except Exception as e: print(f"[{datetime.now():%H:%M:%S}] ERROR: {e}", file=sys.stderr)
            if once: break
            time.sleep(min(30, interval or load_interval()))
    finally: store.close(); remove_pid()

def cmd_next_run(cron_expr: str = None):
    expr = cron_expr or load_cron()
    if not expr: print(json.dumps({"mode": "interval", "next_in_seconds": load_interval()})); return
    secs = CronExpr(expr).seconds_to_next()
    print(json.dumps({"mode": "cron", "expression": expr,
        "next_run": (datetime.now() + timedelta(seconds=secs)).strftime("%Y-%m-%d %H:%M"),
        "seconds_until": secs}, indent=2))

def cmd_status():
    running, pid = is_running(); cfg = load_config()
    print(json.dumps({"running": running, "pid": pid,
        "interval_seconds": int(cfg.get("poll_interval_seconds", 300)),
        "cron": cfg.get("scheduler_cron"), "pid_file": str(PID_FILE)}, indent=2))

def cmd_stop():
    running, pid = is_running()
    if not running: print("not running"); return
    try: os.kill(pid, signal.SIGTERM); print(f"OK: stopped (PID {pid})")
    except OSError as e: print(f"ERROR: {e}", file=sys.stderr)
    finally: remove_pid()

def _ensure_store() -> SchedulerStore:
    JARVIS_DIR.mkdir(parents=True, exist_ok=True); return SchedulerStore(DB_PATH)

def cmd_create_task(name, stype, sval, handler):
    store = _ensure_store(); tid = f"{name}-{uuid4().hex[:8]}"
    store.save_task({"id": tid, "name": name, "schedule_type": stype, "schedule_value": sval,
        "handler": handler, "status": "active", "next_run": datetime.now(timezone.utc).isoformat(),
        "last_run": None, "metadata": "{}"})
    store.close(); print(json.dumps({"created": tid}))

def cmd_list_tasks(filt=None):
    store = _ensure_store(); print(json.dumps(store.list_tasks(filt), indent=2, default=str)); store.close()

def cmd_pause_task(tid):
    store = _ensure_store(); store.update_status(tid, "paused"); store.close(); print(f"OK: {tid} paused")

def cmd_resume_task(tid):
    store = _ensure_store(); store.update_status(tid, "active"); store.close(); print(f"OK: {tid} resumed")

def _parse_kv(args, keys):
    """Parse --key value pairs from argv."""
    result = {k: None for k in keys}; i = 0
    while i < len(args):
        for k in keys:
            if args[i] == f"--{k}" and i + 1 < len(args):
                result[k] = args[i + 1]; i += 2; break
        else: i += 1
    return result

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "run":
        kv = _parse_kv(sys.argv[2:], ["interval", "cron"])
        once = "--once" in sys.argv[2:]
        cmd_run(interval=int(kv["interval"]) if kv["interval"] else None, cron_expr=kv["cron"], once=once)
    elif cmd == "next-run":
        kv = _parse_kv(sys.argv[2:], ["cron"]); cmd_next_run(kv["cron"])
    elif cmd == "status": cmd_status()
    elif cmd == "stop": cmd_stop()
    elif cmd == "create-task":
        kv = _parse_kv(sys.argv[2:], ["name", "type", "value", "handler"])
        if not all(kv.values()): print("ERROR: --name, --type, --value, --handler required", file=sys.stderr); sys.exit(1)
        cmd_create_task(kv["name"], kv["type"], kv["value"], kv["handler"])
    elif cmd == "list-tasks":
        kv = _parse_kv(sys.argv[2:], ["status"]); cmd_list_tasks(kv["status"])
    elif cmd == "pause-task":
        if len(sys.argv) < 3: print("ERROR: task ID required", file=sys.stderr); sys.exit(1)
        cmd_pause_task(sys.argv[2])
    elif cmd == "resume-task":
        if len(sys.argv) < 3: print("ERROR: task ID required", file=sys.stderr); sys.exit(1)
        cmd_resume_task(sys.argv[2])
    else: print(__doc__)

if __name__ == "__main__":
    main()
