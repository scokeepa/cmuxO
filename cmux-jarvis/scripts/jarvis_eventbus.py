#!/usr/bin/env python3
"""jarvis_eventbus.py — Worker 프로토콜 + Pipeline 추상화

EventBus: JSON-RPC 스타일 Worker↔JARVIS 통신 (Step 4)
  - events.jsonl 파일 기록
  - JarvisEventBus 인메모리 pub/sub 듀얼 퍼블리시
Pipeline: 단계별 실행 + 텔레메트리 + 에러 핸들링
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from jarvis_events import JarvisEventType, JarvisEventBus, get_jarvis_bus

try:
    from jarvis_telemetry import Telemetry
except ImportError:
    class Telemetry:
        def __init__(self, *a, **kw): pass
        def emit(self, *a, **kw): pass


# ═══════════════════════════════════════════════════════════════
#  METHOD → JarvisEventType 매핑
# ═══════════════════════════════════════════════════════════════

METHOD_TO_EVENT: dict[str, JarvisEventType] = {
    "worker.started": JarvisEventType.WORKER_START,
    "worker.progress": JarvisEventType.WORKER_PROGRESS,
    "worker.completed": JarvisEventType.WORKER_COMPLETE,
    "worker.failed": JarvisEventType.WORKER_FAIL,
    "jarvis.approved": JarvisEventType.GATE_ALLOW,
    "jarvis.rejected": JarvisEventType.EVOLUTION_REJECT,
    "jarvis.phase_change": JarvisEventType.PIPELINE_STAGE_START,
    "verify.started": JarvisEventType.VERIFY_START,
    "verify.passed": JarvisEventType.VERIFY_PASS,
    "verify.failed": JarvisEventType.VERIFY_FAIL,
}


# ═══════════════════════════════════════════════════════════════
#  EventBus: Worker 프로토콜 구조화 (Step 4)
# ═══════════════════════════════════════════════════════════════

class EventBus:
    """Worker 이벤트 버스 — JSON-RPC 스타일 구조화된 통신.

    듀얼 퍼블리시:
      1) events.jsonl 파일 기록 (영속)
      2) JarvisEventBus 인메모리 pub/sub (실시간)
    레거시 호환: worker.completed 시 done 플래그 파일 생성.
    """

    VALID_METHODS = {
        "worker.started", "worker.progress", "worker.completed", "worker.failed",
        "jarvis.approved", "jarvis.rejected", "jarvis.phase_change",
        "verify.started", "verify.passed", "verify.failed",
    }

    def __init__(self, evo_dir: Path, jarvis_bus: JarvisEventBus | None = None):
        self.evo_dir = evo_dir
        self.events_file = evo_dir / "events.jsonl"
        self.status_file = evo_dir / "STATUS.json"
        self._seq_file = evo_dir / ".seq"
        self._jarvis_bus = jarvis_bus if jarvis_bus is not None else get_jarvis_bus()

    def publish(self, method: str, params: dict = None, source: str = "jarvis") -> dict:
        """이벤트 발행 — 파일 + 인메모리 듀얼 퍼블리시."""
        seq = self._next_seq()
        event = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "meta": {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": source,
                "seq": seq,
            },
        }

        # 1) 파일 기록
        with open(self.events_file, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        # seq 카운터 갱신
        self._seq_file.write_text(str(seq))

        # 2) 인메모리 JarvisEventBus 퍼블리시
        evt_type = METHOD_TO_EVENT.get(method)
        if evt_type is not None:
            self._jarvis_bus.publish(evt_type, params or {})

        # 3) STATUS.json 갱신
        self._update_status(method, params, event["meta"])

        # 레거시 호환: 완료 시 플래그 파일도 생성
        if method == "worker.completed":
            Path(f"/tmp/cmux-jarvis-{self.evo_dir.name}-done").touch()

        return event

    def read_events(self, since_seq: int = 0) -> list[dict]:
        """이벤트 조회 (seq 기반 폴링)."""
        if not self.events_file.exists():
            return []
        events = []
        for line in self.events_file.read_text().strip().split("\n"):
            if not line:
                continue
            try:
                ev = json.loads(line)
                if ev.get("meta", {}).get("seq", 0) > since_seq:
                    events.append(ev)
            except json.JSONDecodeError:
                continue
        return events

    def read_status(self) -> dict | None:
        """현재 STATUS 조회."""
        if not self.status_file.exists():
            return None
        try:
            return json.loads(self.status_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _next_seq(self) -> int:
        """O(1) seq — 카운터 파일 기반."""
        if self._seq_file.exists():
            try:
                val = int(self._seq_file.read_text().strip())
                return val + 1
            except (ValueError, OSError):
                pass
        return 1

    def _update_status(self, method: str, params: dict, meta: dict):
        """STATUS.json 갱신 — fcntl.flock 으로 원자적 쓰기."""
        current = self.read_status() or {
            "evo_id": self.evo_dir.name,
            "phase": "unknown",
            "evolution_type": (params or {}).get("evolution_type", "unknown"),
        }

        phase_map = {
            "worker.started": "implementing",
            "worker.completed": "completed",
            "worker.failed": "failed",
            "jarvis.approved": "approved",
            "jarvis.rejected": "rejected",
            "jarvis.phase_change": (params or {}).get("phase", current.get("phase")),
            "verify.started": "verifying",
            "verify.passed": "verified",
            "verify.failed": "verify_failed",
        }

        if method in phase_map:
            current["phase"] = phase_map[method]

        current["last_event"] = method
        current["last_event_ts"] = meta["ts"]
        current["last_event_params"] = params or {}

        fd, tmp = tempfile.mkstemp(dir=str(self.evo_dir), suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(current, f, indent=2, ensure_ascii=False)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.replace(tmp, str(self.status_file))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


# ═══════════════════════════════════════════════════════════════
#  Pipeline: 진화 파이프라인 추상화
# ═══════════════════════════════════════════════════════════════

class PipelineError(Exception):
    """파이프라인 단계 실패."""
    def __init__(self, step: str, message: str):
        self.step = step
        super().__init__(f"[{step}] {message}")


class Pipeline:
    """진화 파이프라인 추상화.

    실제 진화 흐름: detect → rate_check → backup → (외부: implement) → verify → apply
    각 단계는 context dict를 받아 결과를 반환하는 callable.
    실패 시 PipelineError → 자동 롤백 트리거.
    """

    def __init__(self, name: str, steps: list[tuple[str, callable]],
                 telemetry: Telemetry = None, event_bus: EventBus = None):
        self.name = name
        self.steps = steps
        self.telemetry = telemetry
        self.event_bus = event_bus

    def run(self, context: dict) -> dict:
        """파이프라인 순차 실행."""
        context["_pipeline"] = self.name
        context["_completed_steps"] = []
        context["_started_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if self.event_bus:
            self.event_bus.publish("jarvis.phase_change", {
                "phase": "pipeline_started", "pipeline": self.name,
                "total_steps": len(self.steps),
            })

        for i, (step_name, step_fn) in enumerate(self.steps):
            if self.event_bus:
                self.event_bus.publish("worker.progress", {
                    "step": step_name, "step_index": i,
                    "total_steps": len(self.steps),
                })

            try:
                result = step_fn(context)
                if isinstance(result, dict):
                    context.update(result)
                context["_completed_steps"].append(step_name)
            except PipelineError:
                context["_failed_step"] = step_name
                self._emit_failure(step_name, context)
                raise
            except Exception as e:
                context["_failed_step"] = step_name
                context["_error"] = str(e)
                self._emit_failure(step_name, context, str(e))
                raise PipelineError(step_name, str(e)) from e

        context["_finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if self.telemetry:
            self.telemetry.emit(f"pipeline_{self.name}_done", {
                "steps": context["_completed_steps"],
                "started_at": context["_started_at"],
                "finished_at": context["_finished_at"],
            })
        if self.event_bus:
            self.event_bus.publish("worker.completed", {
                "pipeline": self.name, "steps": context["_completed_steps"],
            })

        return context

    def _emit_failure(self, step_name: str, context: dict, error: str = None):
        payload = {"step": step_name, "completed": context.get("_completed_steps", [])}
        if error:
            payload["error"] = error
        if self.telemetry:
            self.telemetry.emit(f"pipeline_{self.name}_fail", payload)
        if self.event_bus:
            self.event_bus.publish("worker.failed", payload)
