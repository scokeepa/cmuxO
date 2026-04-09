#!/usr/bin/env python3
"""jarvis_guardrails.py — Security guardrails engine

프롬프트/응답 내 민감정보(시크릿, PII) 스캔 + 모드별 처리.
RedactionMode(WARN/REDACT/BLOCK), SecretScanner, PIIScanner, GuardrailsEngine.
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from jarvis_events import JarvisEventType, get_jarvis_bus


# ─── Enums & Errors ──────────────────────────────────────────

class RedactionMode(str, Enum):
    """가드레일 처리 모드."""
    WARN = "warn"
    REDACT = "redact"
    BLOCK = "block"


class SecurityBlockError(Exception):
    """BLOCK 모드에서 민감정보 발견 시 raise."""

    def __init__(self, findings: "List[ScanFinding]"):
        self.findings = findings
        labels = [f.label for f in findings]
        super().__init__(f"Blocked: sensitive content detected — {labels}")


# ─── Data Models ──────────────────────────────────────────────

@dataclass
class ScanFinding:
    """단일 스캔 결과."""
    scanner: str
    label: str
    matched: str
    start: int
    end: int


@dataclass
class ScanResult:
    """스캐너 집계 결과."""
    findings: List[ScanFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.findings) == 0


# ─── Base Scanner ─────────────────────────────────────────────

class BaseScanner(ABC):
    """스캐너 인터페이스."""
    name: str = "base"

    @abstractmethod
    def scan(self, text: str) -> List[ScanFinding]:
        ...


# ─── Secret Scanner ──────────────────────────────────────────

class SecretScanner(BaseScanner):
    """시크릿/API키 패턴 스캐너."""
    name = "secret"

    PATTERNS: List[tuple] = [
        ("api_key", r"(?:sk|pk)[-_][a-zA-Z0-9]{20,}"),
        ("github_token", r"ghp_[a-zA-Z0-9]{36,}"),
        ("slack_token", r"xoxb-[a-zA-Z0-9\-]{20,}"),
        ("aws_key", r"AKIA[A-Z0-9]{16}"),
        ("password", r"(?i)(?:password|passwd|pwd)\s*[:=]\s*\S{4,}"),
        ("bearer_token", r"(?i)bearer\s+[a-zA-Z0-9_.~+/\-]{20,}"),
    ]

    def scan(self, text: str) -> List[ScanFinding]:
        findings: List[ScanFinding] = []
        for label, pattern in self.PATTERNS:
            for m in re.finditer(pattern, text):
                findings.append(ScanFinding(
                    scanner=self.name,
                    label=label,
                    matched=m.group(),
                    start=m.start(),
                    end=m.end(),
                ))
        return findings


# ─── PII Scanner ─────────────────────────────────────────────

class PIIScanner(BaseScanner):
    """개인정보 패턴 스캐너."""
    name = "pii"

    PATTERNS: List[tuple] = [
        ("email", r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}"),
        ("phone", r"\d{2,3}-\d{3,4}-\d{4}"),
        ("resident_id", r"\d{6}-[1-4]\d{6}"),
    ]

    def scan(self, text: str) -> List[ScanFinding]:
        findings: List[ScanFinding] = []
        for label, pattern in self.PATTERNS:
            for m in re.finditer(pattern, text):
                findings.append(ScanFinding(
                    scanner=self.name,
                    label=label,
                    matched=m.group(),
                    start=m.start(),
                    end=m.end(),
                ))
        return findings


# ─── Guardrails Engine ───────────────────────────────────────

class GuardrailsEngine:
    """가드레일 엔진 — scan / redact / process / wrap."""

    def __init__(
        self,
        mode: RedactionMode = RedactionMode.WARN,
        scanners: Optional[List[BaseScanner]] = None,
    ):
        self.mode = mode
        self.scanners: List[BaseScanner] = scanners or [
            SecretScanner(),
            PIIScanner(),
        ]
        self._bus = get_jarvis_bus()

    # ── scan ──────────────────────────────────────────────────

    def scan_text(self, text: str) -> ScanResult:
        """모든 스캐너로 텍스트 스캔."""
        all_findings: List[ScanFinding] = []
        for scanner in self.scanners:
            all_findings.extend(scanner.scan(text))
        return ScanResult(findings=all_findings)

    # ── redact ────────────────────────────────────────────────

    @staticmethod
    def redact_text(text: str, findings: List[ScanFinding]) -> str:
        """발견된 매치를 [REDACTED] 로 치환 (역순 처리)."""
        # 역순 정렬하여 인덱스 유지
        sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)
        result = text
        for f in sorted_findings:
            result = result[:f.start] + "[REDACTED]" + result[f.end:]
        return result

    # ── process (core) ────────────────────────────────────────

    def process(self, text: str, direction: str = "inbound") -> str:
        """텍스트 처리: WARN → 경고만, REDACT → 치환, BLOCK → 예외.

        Args:
            text: 스캔 대상 텍스트
            direction: "inbound" (프롬프트) 또는 "outbound" (응답)
        """
        scan = self.scan_text(text)
        if scan.clean:
            self._bus.publish(JarvisEventType.GATE_ALLOW, {
                "direction": direction,
                "mode": self.mode.value,
            })
            return text

        # 발견 사항 이벤트 발행
        finding_dicts = [
            {"scanner": f.scanner, "label": f.label, "matched": f.matched}
            for f in scan.findings
        ]

        if self.mode == RedactionMode.BLOCK:
            self._bus.publish(JarvisEventType.GATE_BLOCK, {
                "direction": direction,
                "findings": finding_dicts,
            })
            raise SecurityBlockError(scan.findings)

        if self.mode == RedactionMode.REDACT:
            self._bus.publish(JarvisEventType.GATE_WARN, {
                "direction": direction,
                "findings": finding_dicts,
                "action": "redacted",
            })
            return self.redact_text(text, scan.findings)

        # WARN: 경고 이벤트만 발행, 텍스트 그대로 반환
        self._bus.publish(JarvisEventType.GATE_WARN, {
            "direction": direction,
            "findings": finding_dicts,
            "action": "warn_only",
        })
        return text

    # ── convenience wrappers ──────────────────────────────────

    def wrap_prompt(self, prompt: str) -> str:
        """프롬프트(인바운드) 래핑."""
        return self.process(prompt, direction="inbound")

    def wrap_response(self, response: str) -> str:
        """응답(아웃바운드) 래핑."""
        return self.process(response, direction="outbound")
