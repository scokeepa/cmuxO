#!/usr/bin/env python3
"""jarvis_claude_bridge.py — Claude Code subprocess bridge

Claude CLI를 subprocess로 실행하여 JARVIS 오케스트레이션과 연결.
SessionConfig / SessionResult / SessionRegistry / ClaudeCodeBridge.
"""
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from jarvis_events import JarvisEventType, get_jarvis_bus
from jarvis_registry import RegistryBase


# ─── Data Models ─────────────────────────────────────────────

@dataclass
class SessionConfig:
    """Claude Code 세션 설정."""
    prompt: str
    working_dir: str = "."
    session_id: Optional[str] = None
    resume: bool = False
    allowed_tools: List[str] = field(default_factory=list)
    system_prompt: Optional[str] = None
    max_turns: Optional[int] = None
    output_format: str = "json"
    print_output: bool = False
    extra_args: List[str] = field(default_factory=list)


@dataclass
class SessionResult:
    """Claude Code 세션 실행 결과."""
    success: bool
    output: str
    parsed: Optional[Dict[str, Any]] = None
    exit_code: int = 0
    duration: float = 0.0
    session_id: Optional[str] = None


class SessionRegistry(RegistryBase):
    """활성 세션 레지스트리 — session_id → SessionConfig 매핑."""


# ─── Sentinel Markers ────────────────────────────────────────

OUTPUT_START = "---JARVIS_OUTPUT_START---"
OUTPUT_END = "---JARVIS_OUTPUT_END---"


# ─── Bridge ──────────────────────────────────────────────────

class ClaudeCodeBridge:
    """Claude CLI subprocess wrapper.

    _build_command: CLI 인자 구성
    _parse_output: JSON → sentinel → plain text 순 파싱
    run: subprocess 실행 + 결과 반환
    is_available: claude CLI 존재 여부 확인
    """

    def __init__(self, claude_bin: str = "claude"):
        self._claude_bin = claude_bin
        self._bus = get_jarvis_bus()

    # ── CLI availability ──────────────────────────────────────

    @staticmethod
    def is_available(claude_bin: str = "claude") -> bool:
        """claude CLI가 PATH에 존재하는지 확인."""
        return shutil.which(claude_bin) is not None

    # ── Command builder ───────────────────────────────────────

    def _build_command(self, config: SessionConfig) -> List[str]:
        """SessionConfig → claude CLI args."""
        cmd: List[str] = [self._claude_bin]

        if config.output_format:
            cmd.extend(["--output-format", config.output_format])

        if config.resume and config.session_id:
            cmd.extend(["--resume", config.session_id])

        if config.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(config.allowed_tools)])

        if config.system_prompt:
            cmd.extend(["--system-prompt", config.system_prompt])

        if config.max_turns is not None:
            cmd.extend(["--max-turns", str(config.max_turns)])

        if config.print_output:
            cmd.append("--print")

        cmd.extend(config.extra_args)

        # prompt은 stdin으로 전달하므로 여기 포함하지 않음
        return cmd

    # ── Output parser ─────────────────────────────────────────

    @staticmethod
    def _parse_output(raw: str) -> Dict[str, Any]:
        """출력 파싱: JSON → sentinel markers → plain text fallback."""
        text = raw.strip()

        # 1) JSON 시도
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # 2) Sentinel markers
        start_idx = text.find(OUTPUT_START)
        end_idx = text.find(OUTPUT_END)
        if start_idx != -1 and end_idx != -1:
            inner = text[start_idx + len(OUTPUT_START):end_idx].strip()
            try:
                return json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                return {"text": inner, "format": "sentinel"}

        # 3) Plain text fallback
        return {"text": text, "format": "plain"}

    # ── Run ───────────────────────────────────────────────────

    def run(self, config: SessionConfig, timeout: float = 300) -> SessionResult:
        """Claude CLI subprocess 실행."""
        if not self.is_available(self._claude_bin):
            return SessionResult(
                success=False, output="claude CLI not found", exit_code=-1
            )

        cmd = self._build_command(config)
        self._bus.publish(JarvisEventType.WORKER_START, {
            "bridge": "claude_code",
            "prompt_length": len(config.prompt),
            "session_id": config.session_id,
        })

        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                input=config.prompt,
                capture_output=True,
                text=True,
                cwd=config.working_dir,
                timeout=timeout,
            )
            duration = time.time() - t0
            parsed = self._parse_output(proc.stdout)

            result = SessionResult(
                success=proc.returncode == 0,
                output=proc.stdout,
                parsed=parsed,
                exit_code=proc.returncode,
                duration=duration,
                session_id=config.session_id,
            )
            evt = JarvisEventType.WORKER_COMPLETE if result.success else JarvisEventType.WORKER_FAIL
            self._bus.publish(evt, {
                "bridge": "claude_code",
                "exit_code": proc.returncode,
                "duration": duration,
            })
            return result

        except subprocess.TimeoutExpired:
            duration = time.time() - t0
            self._bus.publish(JarvisEventType.WORKER_FAIL, {
                "bridge": "claude_code",
                "reason": "timeout",
                "duration": duration,
            })
            return SessionResult(
                success=False, output="timeout", exit_code=-2, duration=duration
            )
        except OSError as exc:
            duration = time.time() - t0
            self._bus.publish(JarvisEventType.WORKER_FAIL, {
                "bridge": "claude_code",
                "reason": str(exc),
                "duration": duration,
            })
            return SessionResult(
                success=False, output=str(exc), exit_code=-3, duration=duration
            )
