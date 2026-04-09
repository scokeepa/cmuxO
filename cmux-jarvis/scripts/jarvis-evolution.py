#!/usr/bin/env python3
"""jarvis-evolution.py — JARVIS 진화 엔진 (DAG + Registry + LoopGuard)

Usage: jarvis-evolution.py <command> [evo-id] [args]

Commands:
    detect                          메트릭 임계값 감지
    backup <evo-id>                 안전 백업 + LOCK 생성
    apply <evo-id>                  검증된 변경사항 적용
    rollback <evo-id>               백업 복원
    status                          현재 상태 조회
    cleanup <evo-id>                임시 파일 정리
    lock-phase <evo-id> <phase>     LOCK phase 업데이트
    run-pipeline <evo-id>           풀 파이프라인 실행
    event <evo-id> <type> [json]    Worker 이벤트 발행
    events <evo-id>                 Worker 이벤트 로그 조회
"""

from __future__ import annotations

import glob as glob_mod
import json
import os
import sys
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from jarvis_registry import EvolutionStrategyRegistry
from jarvis_events import JarvisEventType, get_jarvis_bus
from jarvis_loop_guard import LoopGuard, LoopGuardConfig
from jarvis_models import EvolutionConfig, LockManager, RateCounter
from jarvis_eventbus import EventBus, PipelineError
from jarvis_dag import EvolutionDAG, DAGNode, NodeType
from jarvis_strategies import deep_merge  # noqa: F401 — registers 5 strategies

try:
    from jarvis_telemetry import Telemetry
except ImportError:
    class Telemetry:
        def __init__(self, *a, **kw): pass
        def emit(self, *a, **kw): pass
        def query(self, *a, **kw): return {}


# Re-export for importlib-based tests
__all__ = ["EvolutionDAG", "DAGNode", "NodeType", "EvolutionEngine"]


class EvolutionEngine:
    """JARVIS 진화 파이프라인 엔진 — DAG + LoopGuard + Registry."""

    def __init__(self):
        self.jarvis_dir = Path.home() / ".claude" / "cmux-jarvis"
        self.jarvis_dir.mkdir(parents=True, exist_ok=True)
        (self.jarvis_dir / "evolutions").mkdir(exist_ok=True)

        self.config = EvolutionConfig(self.jarvis_dir / "config.json")
        self.lock = LockManager(
            self.jarvis_dir / ".evolution-lock", self.config.lock_ttl)
        self.counter = RateCounter(self.jarvis_dir / ".evolution-counter")

        self.settings_path = Path.home() / ".claude" / "settings.json"
        self.metric_dict_path = (
            Path.home() / ".claude" / "skills" / "cmux-jarvis"
            / "references" / "metric-dictionary.json"
        )
        self.eagle_path = Path("/tmp/cmux-eagle-status.json")
        self.freeze_path = Path("/tmp/cmux-jarvis-freeze-mode")
        self.telemetry = Telemetry(self.jarvis_dir / "telemetry")

        self.loop_guard = LoopGuard(LoopGuardConfig(
            max_identical_calls=3, poll_tool_budget=10))
        self._bus = get_jarvis_bus()

    def _guarded_call(self, cmd: str, evo_id: str = ""):
        """Every command passes through LoopGuard."""
        verdict = self.loop_guard.check_call(cmd, evo_id)
        if verdict.blocked:
            self._bus.publish(JarvisEventType.LOOP_GUARD_BLOCK,
                              {"cmd": cmd, "evo_id": evo_id,
                               "reason": verdict.reason})
            raise PipelineError(cmd, f"LoopGuard blocked: {verdict.reason}")
        if verdict.warned:
            self._bus.publish(JarvisEventType.LOOP_GUARD_WARN,
                              {"cmd": cmd, "evo_id": evo_id,
                               "reason": verdict.reason})

    def get_event_bus(self, evo_id: str) -> EventBus:
        evo_dir = self.jarvis_dir / "evolutions" / evo_id
        evo_dir.mkdir(parents=True, exist_ok=True)
        return EventBus(evo_dir)

    # ─── DAG Pipeline ────────────────────────────────────────

    def build_pipeline(self, evo_id: str) -> EvolutionDAG:
        engine = self

        def step_detect(ctx):
            result = engine.detect()
            ctx["detect_result"] = result
            if not result.get("threshold_exceeded"):
                raise PipelineError(
                    "detect", f"임계값 미초과: {result.get('reason', '정상')}")
            return {"exceeded": result["exceeded"]}

        def step_rate_check(ctx):
            today = datetime.now().strftime("%Y-%m-%d")
            if engine.counter.consecutive >= engine.config.max_consecutive:
                raise PipelineError(
                    "rate_check",
                    f"연속 {engine.counter.consecutive}회 — "
                    f"상한 {engine.config.max_consecutive}")
            if engine.counter.daily_count(today) >= engine.config.max_daily:
                raise PipelineError(
                    "rate_check",
                    f"일일 {engine.counter.daily_count(today)}회 — "
                    f"상한 {engine.config.max_daily}")
            return {"rate_ok": True}

        def step_stale_lock(ctx):
            if engine.lock.exists():
                if engine.lock.is_stale():
                    data = engine.lock.read()
                    engine.lock.remove()
                    return {"stale_lock_removed": data}
                data = engine.lock.read()
                raise PipelineError(
                    "stale_lock",
                    f"진화 진행 중: {(data or {}).get('evo_id', '?')}")
            return {}

        def step_backup(ctx):
            evo_dir = engine.jarvis_dir / "evolutions" / evo_id
            backup_dir = evo_dir / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            bk = backup_dir / "settings.json"
            if bk.exists():
                shutil.move(str(bk), str(backup_dir / "settings.json.prev"))
            fd, tmp = tempfile.mkstemp(dir=str(backup_dir), suffix=".json")
            os.close(fd)
            shutil.copy2(str(engine.settings_path), tmp)
            os.replace(tmp, str(bk))
            engine.lock.create(evo_id, "planning")
            engine.freeze_path.write_text("warn")
            engine._collect_metrics(evo_dir / "before-metrics.json")
            engine.telemetry.emit("backup", {"evo_id": evo_id})
            engine._bus.publish(JarvisEventType.EVOLUTION_BACKUP,
                                {"evo_id": evo_id})
            return {"backup_done": True}

        def step_pre_apply(ctx):
            evo_dir = engine.jarvis_dir / "evolutions" / evo_id
            proposed = evo_dir / "proposed-settings.json"
            evidence = evo_dir / "evidence.json"
            if not proposed.exists():
                raise PipelineError("pre_apply", "proposed-settings.json 없음")
            if not evidence.exists():
                raise PipelineError("pre_apply", "evidence.json 없음")
            data = json.loads(proposed.read_text())
            if "hooks" in data:
                raise PipelineError(
                    "pre_apply", "proposed에 hooks 키 포함 — E4 방어 거부")
            return {"proposed_data": data}

        def step_apply(ctx):
            proposed_data = ctx.get("proposed_data")
            if not proposed_data:
                p = (engine.jarvis_dir / "evolutions" / evo_id
                     / "proposed-settings.json")
                proposed_data = json.loads(p.read_text())
            engine.lock.update_phase("applying")
            settings = json.loads(engine.settings_path.read_text())
            merged = deep_merge(settings, proposed_data)
            fd, tmp = tempfile.mkstemp(
                dir=str(engine.settings_path.parent), suffix=".json")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(merged, f, indent=2)
                os.replace(tmp, str(engine.settings_path))
            except Exception:
                os.unlink(tmp)
                raise
            engine.freeze_path.unlink(missing_ok=True)
            engine.lock.remove()
            engine.counter.increment()
            engine.telemetry.emit("apply", {"evo_id": evo_id})
            engine._bus.publish(JarvisEventType.EVOLUTION_APPLY,
                                {"evo_id": evo_id})
            return {"apply_done": True}

        dag = EvolutionDAG()
        dag.add_node(DAGNode("detect", NodeType.CHECK, step_detect, []))
        dag.add_node(DAGNode("rate_check", NodeType.CHECK,
                             step_rate_check, ["detect"]))
        dag.add_node(DAGNode("stale_lock", NodeType.CHECK,
                             step_stale_lock, ["detect"]))
        dag.add_node(DAGNode("backup", NodeType.ACTION,
                             step_backup, ["rate_check", "stale_lock"]))
        dag.add_node(DAGNode("pre_apply", NodeType.CHECK,
                             step_pre_apply, ["backup"]))
        dag.add_node(DAGNode("apply", NodeType.ACTION,
                             step_apply, ["pre_apply"]))
        return dag

    def run_pipeline(self, evo_id: str) -> dict:
        self._guarded_call("run-pipeline", evo_id)
        dag = self.build_pipeline(evo_id)
        try:
            result = dag.run({"evo_id": evo_id}, bus=self._bus)
            return {
                "success": True,
                "steps": result.get("_completed_steps", []),
                "started_at": result.get("_started_at"),
                "finished_at": result.get("_finished_at"),
            }
        except PipelineError as e:
            evo_dir = self.jarvis_dir / "evolutions" / evo_id
            backup = evo_dir / "backup" / "settings.json"
            if backup.exists() and self.lock.exists():
                self.rollback(evo_id)
                return {"success": False, "error": str(e),
                        "auto_rollback": True}
            return {"success": False, "error": str(e), "auto_rollback": False}

    # ─── Individual Commands (backward compatible) ───────────

    def detect(self) -> dict:
        self._guarded_call("detect")
        if not self.eagle_path.exists():
            return {"threshold_exceeded": False, "reason": "eagle-status 없음"}
        try:
            eagle = json.loads(self.eagle_path.read_text())
            metrics = json.loads(self.metric_dict_path.read_text())
        except (json.JSONDecodeError, OSError, FileNotFoundError) as e:
            return {"threshold_exceeded": False, "reason": f"파싱 오류: {e}"}
        stats = eagle.get("stats", {})
        exceeded = []
        for name, cfg in metrics.get("metrics", {}).items():
            key = name.replace("_count", "")
            val = stats.get(key, 0)
            warn = cfg.get("threshold", {}).get("warning", 0)
            if warn > 0 and val >= warn:
                exceeded.append(
                    {"metric": name, "value": val, "warning": warn})
        result = {"threshold_exceeded": len(exceeded) > 0,
                  "exceeded": exceeded, "stats": stats}
        if exceeded:
            self._bus.publish(JarvisEventType.EVOLUTION_DETECT,
                              {"exceeded_count": len(exceeded)})
            self.telemetry.emit("detect", {
                "exceeded_count": len(exceeded),
                "metrics": [e["metric"] for e in exceeded]})
        return result

    def backup(self, evo_id: str) -> str:
        self._guarded_call("backup", evo_id)
        evo_dir = self.jarvis_dir / "evolutions" / evo_id
        backup_dir = evo_dir / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        bus = self.get_event_bus(evo_id)
        today = datetime.now().strftime("%Y-%m-%d")
        if self.counter.consecutive >= self.config.max_consecutive:
            self.telemetry.emit("backup_rejected",
                                {"evo_id": evo_id,
                                 "reason": "consecutive_limit"})
            bus.publish("jarvis.rejected", {"reason": "consecutive_limit"})
            print(f"WARNING: 연속 {self.counter.consecutive}회. "
                  "사용자 확인 필요.", file=sys.stderr)
            sys.exit(1)
        if self.counter.daily_count(today) >= self.config.max_daily:
            self.telemetry.emit("backup_rejected",
                                {"evo_id": evo_id, "reason": "daily_limit"})
            bus.publish("jarvis.rejected", {"reason": "daily_limit"})
            print(f"ERROR: 일일 상한 {self.config.max_daily} 도달.",
                  file=sys.stderr)
            sys.exit(2)
        if self.lock.exists():
            if self.lock.is_stale():
                ld = self.lock.read()
                age = "?"
                if ld and "created_at" in ld:
                    c = datetime.fromisoformat(
                        ld["created_at"].replace("Z", "+00:00"))
                    age = int(
                        (datetime.now(timezone.utc) - c).total_seconds() / 60)
                print(f"WARNING: stale lock ({age}분). 해제.",
                      file=sys.stderr)
                self.lock.remove()
            else:
                ld = self.lock.read()
                eid = (ld or {}).get("evo_id", "?")
                print(f"ERROR: 진화 진행 중 ({eid}). 큐에 추가하세요.",
                      file=sys.stderr)
                sys.exit(3)
        bk = backup_dir / "settings.json"
        if bk.exists():
            shutil.move(str(bk), str(backup_dir / "settings.json.prev"))
        fd, tmp = tempfile.mkstemp(dir=str(backup_dir), suffix=".json")
        os.close(fd)
        shutil.copy2(str(self.settings_path), tmp)
        os.replace(tmp, str(bk))
        self.lock.create(evo_id, "planning")
        self.freeze_path.write_text("warn")
        self._collect_metrics(evo_dir / "before-metrics.json")
        self.telemetry.emit("backup", {"evo_id": evo_id})
        self._bus.publish(JarvisEventType.EVOLUTION_BACKUP,
                          {"evo_id": evo_id})
        bus.publish("jarvis.phase_change", {"phase": "planning"})
        return f"OK: {evo_id} 백업 완료. LOCK 생성."

    def apply(self, evo_id: str) -> str:
        self._guarded_call("apply", evo_id)
        evo_dir = self.jarvis_dir / "evolutions" / evo_id
        proposed = evo_dir / "proposed-settings.json"
        evidence = evo_dir / "evidence.json"
        bus = self.get_event_bus(evo_id)
        for p, l in [(proposed, "proposed-settings.json"),
                     (evidence, "evidence.json")]:
            if not p.exists():
                print(f"ERROR: {l} 없음", file=sys.stderr)
                sys.exit(1)
        if not self.lock.exists():
            print("ERROR: CURRENT_LOCK 없음", file=sys.stderr)
            sys.exit(1)
        data = json.loads(proposed.read_text())
        if "hooks" in data:
            self.telemetry.emit("apply_rejected",
                                {"evo_id": evo_id,
                                 "reason": "hooks_key_present"})
            bus.publish("jarvis.rejected", {"reason": "hooks_key_present"})
            print("ERROR: proposed에 hooks 키 포함. 거부.", file=sys.stderr)
            sys.exit(1)
        self.lock.update_phase("applying")
        bus.publish("jarvis.phase_change", {"phase": "applying"})
        settings = json.loads(self.settings_path.read_text())
        merged = deep_merge(settings, data)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.settings_path.parent), suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(merged, f, indent=2)
            os.replace(tmp, str(self.settings_path))
        except Exception:
            os.unlink(tmp)
            raise
        self.freeze_path.unlink(missing_ok=True)
        self.lock.remove()
        self.counter.increment()
        self.telemetry.emit("apply", {"evo_id": evo_id})
        self._bus.publish(JarvisEventType.EVOLUTION_APPLY,
                          {"evo_id": evo_id})
        bus.publish("worker.completed", {"action": "apply"})
        return f"OK: {evo_id} 반영 완료."

    def rollback(self, evo_id: str) -> str:
        self._guarded_call("rollback", evo_id)
        evo_dir = self.jarvis_dir / "evolutions" / evo_id
        backup = evo_dir / "backup" / "settings.json"
        bus = self.get_event_bus(evo_id)
        if not backup.exists():
            print("ERROR: 백업 없음", file=sys.stderr)
            sys.exit(1)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.settings_path.parent), suffix=".json")
        os.close(fd)
        shutil.copy2(str(backup), tmp)
        os.replace(tmp, str(self.settings_path))
        self.lock.remove()
        self.freeze_path.unlink(missing_ok=True)
        self.counter.reset_consecutive()
        self.telemetry.emit("rollback", {"evo_id": evo_id})
        self._bus.publish(JarvisEventType.EVOLUTION_ROLLBACK,
                          {"evo_id": evo_id})
        bus.publish("worker.failed",
                    {"action": "rollback", "reason": "user_or_auto"})
        return f"OK: {evo_id} 롤백 완료."

    def status(self) -> dict:
        self._guarded_call("status")
        lock_data = self.lock.read()
        counter_data = {"consecutive": 0, "daily": {}}
        if self.counter.path.exists():
            try:
                counter_data = json.loads(self.counter.path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        queue_path = self.jarvis_dir / "evolution-queue.json"
        queue_data = []
        if queue_path.exists():
            try:
                queue_data = json.loads(queue_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"lock": lock_data, "counter": counter_data,
                "queue": queue_data}

    def cleanup(self, evo_id: str) -> str:
        self._guarded_call("cleanup", evo_id)
        for f in glob_mod.glob("/tmp/cmux-jarvis-worker-*"):
            os.unlink(f)
        Path(f"/tmp/cmux-jarvis-{evo_id}-done").unlink(missing_ok=True)
        self.telemetry.emit("cleanup", {"evo_id": evo_id})
        return f"OK: {evo_id} 정리 완료."

    def lock_phase(self, evo_id: str, phase: str) -> str:
        self._guarded_call("lock-phase", evo_id)
        if not self.lock.exists():
            print("ERROR: LOCK 없음", file=sys.stderr)
            sys.exit(1)
        self.lock.update_phase(phase)
        bus = self.get_event_bus(evo_id)
        bus.publish("jarvis.phase_change", {"phase": phase})
        return f"OK: phase={phase}"

    # ─── Internal utilities ──────────────────────────────────

    def _collect_metrics(self, output_path: Path):
        try:
            eagle = json.loads(self.eagle_path.read_text())
            keys = ["stalled", "error", "idle", "working", "ended", "total"]
            m = {k: eagle.get("stats", {}).get(k, 0) for k in keys}
            m["timestamp"] = eagle.get("timestamp", "")
            m["stalled_surfaces"] = eagle.get("stalled_surfaces", "")
            m["error_surfaces"] = eagle.get("error_surfaces", "")
            output_path.write_text(json.dumps(m, indent=2))
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            pass


# ─── CLI ──────────────────────────────────────────────────────

def main():
    engine = EvolutionEngine()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "detect":
        print(json.dumps(engine.detect(), indent=2))
    elif cmd == "backup":
        if len(sys.argv) < 3:
            print("ERROR: evo-id 필요", file=sys.stderr); sys.exit(1)
        print(engine.backup(sys.argv[2]))
    elif cmd == "apply":
        if len(sys.argv) < 3:
            print("ERROR: evo-id 필요", file=sys.stderr); sys.exit(1)
        print(engine.apply(sys.argv[2]))
    elif cmd == "rollback":
        if len(sys.argv) < 3:
            print("ERROR: evo-id 필요", file=sys.stderr); sys.exit(1)
        print(engine.rollback(sys.argv[2]))
    elif cmd == "status":
        print(json.dumps(engine.status(), indent=2))
    elif cmd == "cleanup":
        if len(sys.argv) < 3:
            print("ERROR: evo-id 필요", file=sys.stderr); sys.exit(1)
        print(engine.cleanup(sys.argv[2]))
    elif cmd == "lock-phase":
        if len(sys.argv) < 4:
            print("ERROR: evo-id, phase 필요", file=sys.stderr); sys.exit(1)
        print(engine.lock_phase(sys.argv[2], sys.argv[3]))
    elif cmd == "run-pipeline":
        if len(sys.argv) < 3:
            print("ERROR: evo-id 필요", file=sys.stderr); sys.exit(1)
        r = engine.run_pipeline(sys.argv[2])
        print(json.dumps(r, indent=2, ensure_ascii=False))
    elif cmd == "event":
        if len(sys.argv) < 4:
            print("ERROR: evo-id, event-type 필요", file=sys.stderr)
            sys.exit(1)
        params = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        bus = engine.get_event_bus(sys.argv[2])
        ev = bus.publish(sys.argv[3], params)
        print(json.dumps(ev, indent=2, ensure_ascii=False))
    elif cmd == "events":
        if len(sys.argv) < 3:
            print("ERROR: evo-id 필요", file=sys.stderr); sys.exit(1)
        bus = engine.get_event_bus(sys.argv[2])
        for ev in bus.read_events():
            print(json.dumps(ev, ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
