#!/usr/bin/env python3
"""jarvis_a2a.py — Agent-to-Agent (A2A) 프로토콜 구현

OpenJarvis a2a/ 패턴 이식.
AgentCard, A2ATask, TaskState, A2ARequest, A2AResponse,
SurfaceRegistry, A2AServer, A2AClient.

cmux surface 간 통신을 위한 경량 A2A 레이어.
"""
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.request import Request, urlopen

from jarvis_events import JarvisEventBus, JarvisEventType, get_jarvis_bus
from jarvis_registry import RegistryBase


# ─── TaskState ────────────────────────────────────────────────

class TaskState(str, Enum):
    """A2A 태스크 상태 — OpenJarvis TaskState 패턴."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ─── AgentCard ────────────────────────────────────────────────

@dataclass
class AgentCard:
    """에이전트 메타데이터 — OpenJarvis AgentCard 패턴.

    각 surface(Claude Code, Cursor 등)가 자신을 기술하는 카드.
    """
    agent_id: str
    name: str
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    endpoint: str = ""
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentCard":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── A2ATask ──────────────────────────────────────────────────

@dataclass
class A2ATask:
    """A2A 태스크 — 에이전트 간 작업 단위."""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""
    target: str = ""
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    state: TaskState = TaskState.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "A2ATask":
        d = dict(d)
        if "state" in d and isinstance(d["state"], str):
            d["state"] = TaskState(d["state"])
        valid = {k for k in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid})

    def complete(self, result: Any = None):
        self.state = TaskState.COMPLETED
        self.result = result
        self.updated_at = time.time()

    def fail(self, error: str):
        self.state = TaskState.FAILED
        self.error = error
        self.updated_at = time.time()


# ─── A2ARequest / A2AResponse ─────────────────────────────────

@dataclass
class A2ARequest:
    """A2A 요청 메시지."""
    method: str
    task: Optional[A2ATask] = None
    agent_card: Optional[AgentCard] = None
    params: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_json(self) -> str:
        d: Dict[str, Any] = {
            "method": self.method,
            "request_id": self.request_id,
            "params": self.params,
        }
        if self.task:
            d["task"] = self.task.to_dict()
        if self.agent_card:
            d["agent_card"] = self.agent_card.to_dict()
        return json.dumps(d)

    @classmethod
    def from_json(cls, raw: str) -> "A2ARequest":
        d = json.loads(raw)
        task = A2ATask.from_dict(d["task"]) if "task" in d and d["task"] else None
        card = AgentCard.from_dict(d["agent_card"]) if "agent_card" in d and d["agent_card"] else None
        return cls(
            method=d["method"],
            task=task,
            agent_card=card,
            params=d.get("params", {}),
            request_id=d.get("request_id", uuid.uuid4().hex[:12]),
        )


@dataclass
class A2AResponse:
    """A2A 응답 메시지."""
    request_id: str = ""
    success: bool = True
    task: Optional[A2ATask] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_json(self) -> str:
        d: Dict[str, Any] = {
            "request_id": self.request_id,
            "success": self.success,
            "data": self.data,
        }
        if self.task:
            d["task"] = self.task.to_dict()
        if self.error:
            d["error"] = self.error
        return json.dumps(d)

    @classmethod
    def from_json(cls, raw: str) -> "A2AResponse":
        d = json.loads(raw)
        task = A2ATask.from_dict(d["task"]) if "task" in d and d["task"] else None
        return cls(
            request_id=d.get("request_id", ""),
            success=d.get("success", True),
            task=task,
            data=d.get("data", {}),
            error=d.get("error"),
        )


# ─── SurfaceRegistry ─────────────────────────────────────────

class SurfaceRegistry(RegistryBase):
    """cmux surface 레지스트리 — AgentCard 기반.

    각 surface가 AgentCard로 자신을 등록하면
    다른 surface가 조회해서 통신할 수 있다.
    """

    @classmethod
    def register_surface(cls, card: AgentCard) -> AgentCard:
        """AgentCard를 키=agent_id로 등록."""
        entries = cls._entries()
        entries[card.agent_id] = card
        bus = get_jarvis_bus()
        bus.publish(JarvisEventType.WORKER_START, {
            "component": "a2a",
            "action": "surface_registered",
            "agent_id": card.agent_id,
        })
        return card

    @classmethod
    def unregister_surface(cls, agent_id: str):
        entries = cls._entries()
        entries.pop(agent_id, None)

    @classmethod
    def list_surfaces(cls) -> List[AgentCard]:
        return list(cls._entries().values())

    @classmethod
    def get_surface(cls, agent_id: str) -> Optional[AgentCard]:
        return cls._entries().get(agent_id)


# ─── A2AServer ────────────────────────────────────────────────

TaskHandler = Callable[[A2ARequest], A2AResponse]


class A2AServer:
    """경량 A2A HTTP 서버 — cmux surface 간 통신 수신부.

    OpenJarvis a2a/server.py 패턴 이식.
    """

    def __init__(self, card: AgentCard, host: str = "127.0.0.1", port: int = 0):
        self.card = card
        self.host = host
        self.port = port
        self._handlers: Dict[str, TaskHandler] = {}
        self._tasks: Dict[str, A2ATask] = {}
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def on(self, method: str, handler: TaskHandler):
        """메서드별 핸들러 등록."""
        self._handlers[method] = handler

    def _handle_request(self, req: A2ARequest) -> A2AResponse:
        handler = self._handlers.get(req.method)
        if not handler:
            return A2AResponse(
                request_id=req.request_id,
                success=False,
                error=f"Unknown method: {req.method}",
            )
        try:
            resp = handler(req)
            resp.request_id = req.request_id
            if req.task:
                self._tasks[req.task.task_id] = req.task
            return resp
        except Exception as exc:
            return A2AResponse(
                request_id=req.request_id,
                success=False,
                error=str(exc),
            )

    def start(self):
        """서버 시작 (백그라운드 스레드)."""
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                req = A2ARequest.from_json(body)
                resp = server_ref._handle_request(req)
                payload = resp.to_json().encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                pass  # suppress logs

        self._server = HTTPServer((self.host, self.port), Handler)
        if self.port == 0:
            self.port = self._server.server_address[1]
        self.card.endpoint = f"http://{self.host}:{self.port}"
        SurfaceRegistry.register_surface(self.card)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            SurfaceRegistry.unregister_surface(self.card.agent_id)
            self._server = None

    @property
    def tasks(self) -> Dict[str, A2ATask]:
        return dict(self._tasks)


# ─── A2AClient ────────────────────────────────────────────────

class A2AClient:
    """A2A HTTP 클라이언트 — surface 간 요청 발송.

    OpenJarvis a2a/client.py 패턴 이식.
    """

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def send(self, endpoint: str, request: A2ARequest) -> A2AResponse:
        """동기 HTTP POST 전송."""
        data = request.to_json().encode()
        req = Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode()
        return A2AResponse.from_json(body)

    def send_task(self, endpoint: str, task: A2ATask) -> A2AResponse:
        """태스크 전송 편의 메서드."""
        request = A2ARequest(method=task.action, task=task)
        return self.send(endpoint, request)

    def discover(self, agent_id: str) -> Optional[AgentCard]:
        """SurfaceRegistry에서 surface 조회."""
        return SurfaceRegistry.get_surface(agent_id)
