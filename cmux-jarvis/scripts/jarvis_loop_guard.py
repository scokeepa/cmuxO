import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class LoopGuardConfig:
    enabled: bool = True
    max_identical_calls: int = 3
    ping_pong_window: int = 6
    poll_tool_budget: int = 5
    max_context_messages: int = 100
    warn_before_block: bool = True


@dataclass
class LoopVerdict:
    blocked: bool = False
    reason: str = ""
    warned: bool = False


class LoopGuard:
    def __init__(self, config: LoopGuardConfig = None):
        self.config = config or LoopGuardConfig()
        self._call_counts: Dict[str, int] = {}
        self._per_tool_counts: Dict[str, int] = {}
        self._call_sequence: deque[str] = deque(
            maxlen=self.config.ping_pong_window * 2
        )
        self._warned_cycles: Set[str] = set()

    def check_call(self, tool_name: str, arguments: str = "") -> LoopVerdict:
        if not self.config.enabled:
            return LoopVerdict()

        h = hashlib.sha256(f"{tool_name}:{arguments}".encode()).hexdigest()[:16]

        self._call_counts[h] = self._call_counts.get(h, 0) + 1
        self._per_tool_counts[tool_name] = self._per_tool_counts.get(tool_name, 0) + 1
        self._call_sequence.append(tool_name)

        # Check 1: identical calls overflow
        if self._call_counts[h] > self.config.max_identical_calls:
            return self._apply_warn_or_block("identical_call_overflow")

        # Check 2: per-tool budget exceeded
        if self._per_tool_counts[tool_name] > self.config.poll_tool_budget:
            return self._apply_warn_or_block("tool_budget_exceeded")

        # Check 3: ping-pong
        if self._detect_ping_pong():
            return self._apply_warn_or_block("ping_pong_detected")

        return LoopVerdict()

    def _apply_warn_or_block(self, reason: str) -> LoopVerdict:
        if not self.config.warn_before_block:
            return LoopVerdict(blocked=True, reason=reason)

        if reason not in self._warned_cycles:
            self._warned_cycles.add(reason)
            return LoopVerdict(warned=True, reason=reason)
        else:
            return LoopVerdict(blocked=True, reason=reason)

    def _detect_ping_pong(self) -> bool:
        seq = list(self._call_sequence)
        for period in [2, 3]:
            length = period * 2
            if len(seq) < length:
                continue
            tail = seq[-length:]
            pattern = tail[:period]
            is_repeat = True
            for i in range(period, length):
                if tail[i] != pattern[i % period]:
                    is_repeat = False
                    break
            if is_repeat and len(set(pattern)) > 1:
                return True
        return False

    def compress_context(self, messages: List[dict]) -> List[dict]:
        limit = self.config.max_context_messages

        if len(messages) <= limit:
            return messages

        # Stage 1: Replace first-half tool messages with truncated
        mid = len(messages) // 2
        stage1 = []
        for i, msg in enumerate(messages):
            if i < mid and msg.get("role") == "tool":
                stage1.append({"role": "tool", "content": "[truncated]"})
            else:
                stage1.append(msg)
        if len(stage1) <= limit:
            return stage1

        # Stage 2: Keep system messages + last N non-system messages (sliding window)
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        remaining_budget = limit - len(system_msgs)
        if remaining_budget < 1:
            remaining_budget = 1
        stage2 = system_msgs + non_system[-remaining_budget:]
        if len(stage2) <= limit:
            return stage2

        # Stage 3: Remove middle tool call/result pairs (keep first 10% + last 50%)
        first_n = max(1, int(len(non_system) * 0.10))
        last_n = max(1, int(len(non_system) * 0.50))
        stage3 = system_msgs + non_system[:first_n] + non_system[-last_n:]
        if len(stage3) <= limit:
            return stage3

        # Stage 4: Extreme — system messages + last 4 messages only
        stage4 = system_msgs + non_system[-4:]
        return stage4

    def reset(self):
        self._call_counts.clear()
        self._per_tool_counts.clear()
        self._call_sequence.clear()
        self._warned_cycles.clear()
