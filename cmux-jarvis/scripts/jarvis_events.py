#!/usr/bin/env python3
"""jarvis_events.py — 인메모리 EventBus (스레드 안전 pub/sub)

OpenJarvis core/events.py 패턴 이식.
JarvisEventType enum + JarvisEvent dataclass + JarvisEventBus 싱글톤.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List


class JarvisEventType(str, Enum):
    """cmux-jarvis 이벤트 타입 — OpenJarvis EventType 패턴."""
    # 진화
    EVOLUTION_DETECT = "evolution.detect"
    EVOLUTION_BACKUP = "evolution.backup"
    EVOLUTION_APPLY = "evolution.apply"
    EVOLUTION_ROLLBACK = "evolution.rollback"
    EVOLUTION_REJECT = "evolution.reject"
    # 검증
    VERIFY_START = "verify.start"
    VERIFY_PASS = "verify.pass"
    VERIFY_FAIL = "verify.fail"
    # 워커
    WORKER_START = "worker.start"
    WORKER_PROGRESS = "worker.progress"
    WORKER_COMPLETE = "worker.complete"
    WORKER_FAIL = "worker.fail"
    # 보안/게이트
    GATE_ALLOW = "gate.allow"
    GATE_WARN = "gate.warn"
    GATE_BLOCK = "gate.block"
    GATE_ESCALATE = "gate.escalate"
    # 스케줄러
    SCHEDULER_TASK_START = "scheduler.task_start"
    SCHEDULER_TASK_END = "scheduler.task_end"
    SCHEDULER_ERROR = "scheduler.error"
    # 루프가드
    LOOP_GUARD_WARN = "loop_guard.warn"
    LOOP_GUARD_BLOCK = "loop_guard.block"
    # 파이프라인
    PIPELINE_STAGE_START = "pipeline.stage_start"
    PIPELINE_STAGE_END = "pipeline.stage_end"
    PIPELINE_FAIL = "pipeline.fail"
    PIPELINE_DONE = "pipeline.done"
    # 텔레메트리
    TELEMETRY_EMIT = "telemetry.emit"


Subscriber = Callable[["JarvisEvent"], None]


@dataclass
class JarvisEvent:
    """단일 이벤트 — OpenJarvis Event 패턴."""
    event_type: JarvisEventType
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)


class JarvisEventBus:
    """인메모리 pub/sub — OpenJarvis EventBus 이식.

    핵심 패턴: publish() 내에서 lock을 잡고 리스너 목록을 복사한 후
    lock을 해제하고 콜백을 호출. 콜백 실행 중 다른 스레드에서
    subscribe/unsubscribe 가능 (데드락 방지).
    """

    def __init__(self, record_history: bool = False):
        self._subscribers: Dict[JarvisEventType, List[Subscriber]] = {}
        self._record_history = record_history
        self._history: List[JarvisEvent] = []
        self._lock = threading.Lock()

    def subscribe(self, event_type: JarvisEventType, callback: Subscriber):
        """콜백 등록."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: JarvisEventType, callback: Subscriber):
        """콜백 제거 (멱등)."""
        with self._lock:
            listeners = self._subscribers.get(event_type, [])
            try:
                listeners.remove(callback)
            except ValueError:
                pass

    def publish(self, event_type: JarvisEventType, data: Dict[str, Any] = None) -> JarvisEvent:
        """이벤트 발행 + 동기 디스패치.

        OpenJarvis 핵심 패턴: lock 잡고 리스너 복사 → lock 해제 → 콜백 호출.
        """
        event = JarvisEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data or {},
        )
        with self._lock:
            if self._record_history:
                self._history.append(event)
            listeners = list(self._subscribers.get(event_type, []))
        for callback in listeners:
            callback(event)
        return event

    @property
    def history(self) -> List[JarvisEvent]:
        """이벤트 히스토리 복사본."""
        with self._lock:
            return list(self._history)

    def clear_history(self):
        with self._lock:
            self._history.clear()


# ─── 모듈 싱글톤 ─────────────────────────────────────────────

_bus: JarvisEventBus | None = None
_bus_lock = threading.Lock()


def get_jarvis_bus(record_history: bool = False) -> JarvisEventBus:
    """모듈 레벨 싱글톤 EventBus."""
    global _bus
    with _bus_lock:
        if _bus is None:
            _bus = JarvisEventBus(record_history=record_history)
        return _bus


def reset_jarvis_bus():
    """테스트용 싱글톤 리셋."""
    global _bus
    with _bus_lock:
        _bus = None
