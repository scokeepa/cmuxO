#!/usr/bin/env python3
"""jarvis_monitor.py — MonitorOperative 4축 전략 시스템

OpenJarvis agents/monitor_operative.py 이식.
cmux-watcher의 관찰→판단→행동 루프를 구조화.
"""
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from jarvis_events import JarvisEventType, get_jarvis_bus


# ─── 4축 전략 설정 ───────────────────────────────────────────

class MemoryExtraction(str, Enum):
    """발견사항 저장 방식."""
    CAUSALITY_GRAPH = "causality_graph"  # 원인→결과 관계 추출
    SCRATCHPAD = "scratchpad"            # 자유 형식 메모
    STRUCTURED_JSON = "structured_json"  # 구조화 JSON
    NONE = "none"

class ObservationCompression(str, Enum):
    """관찰 결과 압축 방식."""
    SUMMARIZE = "summarize"   # 핵심만 요약
    TRUNCATE = "truncate"     # 앞부분만 잘라냄
    NONE = "none"

class RetrievalStrategy(str, Enum):
    """이전 컨텍스트 회수 방식."""
    HYBRID = "hybrid"      # 키워드 + 시맨틱 조합
    KEYWORD = "keyword"    # 키워드 매칭
    RECENT = "recent"      # 최근 N개
    NONE = "none"

class TaskDecomposition(str, Enum):
    """복잡 작업 분해 방식."""
    PHASED = "phased"            # 단계별 분해
    MONOLITHIC = "monolithic"    # 분해 없음
    HIERARCHICAL = "hierarchical"  # 트리 구조


@dataclass
class MonitorConfig:
    """MonitorOperative 4축 설정."""
    memory_extraction: MemoryExtraction = MemoryExtraction.CAUSALITY_GRAPH
    observation_compression: ObservationCompression = ObservationCompression.SUMMARIZE
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.RECENT
    task_decomposition: TaskDecomposition = TaskDecomposition.PHASED
    max_observations: int = 100       # 관찰 히스토리 최대
    compression_threshold: int = 2000  # 이 길이 초과 시 압축
    persist_interval: int = 10        # N 관찰마다 자동 저장
    operator_id: str = "watcher"


# ─── Observation (관찰 결과) ──────────────────────────────────

@dataclass
class Observation:
    """단일 관찰 결과."""
    timestamp: float = field(default_factory=time.time)
    source: str = ""           # 관찰 출처 (surface_id, eagle-status 등)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    compressed: str = ""       # 압축된 요약
    causality: List[Dict[str, str]] = field(default_factory=list)  # [{cause, effect, confidence}]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "raw_data": self.raw_data,
            "compressed": self.compressed,
            "causality": self.causality,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Observation":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


# ─── CausalityGraph (인과관계 그래프) ─────────────────────────

class CausalityGraph:
    """관찰에서 추출한 인과관계 저장소.

    OpenJarvis monitor_operative의 causality_graph 전략 이식.
    cause→effect 관계를 누적하여 패턴 학습.
    """

    def __init__(self, store_path: Path = None):
        self.store_path = store_path
        self._edges: List[Dict[str, Any]] = []
        if store_path and store_path.exists():
            try:
                self._edges = json.loads(store_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    def add(self, cause: str, effect: str, confidence: float = 0.5,
            source: str = ""):
        edge = {
            "cause": cause, "effect": effect,
            "confidence": confidence, "source": source,
            "timestamp": time.time(),
        }
        self._edges.append(edge)

    def query(self, cause: str = None, effect: str = None) -> List[Dict]:
        results = self._edges
        if cause:
            results = [e for e in results if cause.lower() in e["cause"].lower()]
        if effect:
            results = [e for e in results if effect.lower() in e["effect"].lower()]
        return results

    def frequent_causes(self, n: int = 5) -> List[tuple]:
        counts: Dict[str, int] = {}
        for e in self._edges:
            c = e["cause"]
            counts[c] = counts.get(c, 0) + 1
        return sorted(counts.items(), key=lambda x: -x[1])[:n]

    def save(self):
        if self.store_path:
            self.store_path.write_text(
                json.dumps(self._edges, indent=2, ensure_ascii=False))

    def __len__(self):
        return len(self._edges)


# ─── SessionStore (세션 영속화) ───────────────────────────────

class MonitorSessionStore:
    """모니터링 세션 상태 영속화.

    OpenJarvis monitor_operative의 session_store + auto_persist 패턴.
    와쳐 재시작 시에도 상태 복원 가능.
    """

    def __init__(self, store_dir: Path):
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, operator_id: str, state: dict):
        path = self.store_dir / f"{operator_id}_state.json"
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    def load_state(self, operator_id: str) -> Optional[dict]:
        path = self.store_dir / f"{operator_id}_state.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def save_observations(self, operator_id: str, observations: List[Observation]):
        path = self.store_dir / f"{operator_id}_observations.jsonl"
        with open(path, "a") as f:
            for obs in observations:
                f.write(json.dumps(obs.to_dict(), ensure_ascii=False) + "\n")

    def load_recent_observations(self, operator_id: str, n: int = 20) -> List[Observation]:
        path = self.store_dir / f"{operator_id}_observations.jsonl"
        if not path.exists():
            return []
        lines = path.read_text().strip().split("\n")
        recent = lines[-n:] if len(lines) > n else lines
        result = []
        for line in recent:
            if line:
                try:
                    result.append(Observation.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return result


# ─── MonitorOperative (메인 클래스) ───────────────────────────

class MonitorOperative:
    """4축 전략 기반 모니터링 에이전트.

    cmux-watcher의 관찰→판단→행동 루프를 구조화.

    사용 예:
        monitor = MonitorOperative(config, session_store)
        obs = monitor.observe(eagle_status_data, source="eagle")
        action = monitor.decide(obs)
        monitor.act(action)
    """

    def __init__(self, config: MonitorConfig = None,
                 session_store: MonitorSessionStore = None,
                 compressor: Callable[[str], str] = None):
        self.config = config or MonitorConfig()
        self.session = session_store
        self._compressor = compressor or self._default_compress
        self._bus = get_jarvis_bus()

        # 인과관계 그래프
        cg_path = None
        if session_store:
            cg_path = session_store.store_dir / f"{self.config.operator_id}_causality.json"
        self.causality = CausalityGraph(cg_path)

        # 관찰 히스토리 (인메모리)
        self._observations: List[Observation] = []
        self._observe_count = 0

        # 세션 복원
        self._restore_state()

    def observe(self, data: dict, source: str = "") -> Observation:
        """관찰 수행 — 데이터 수집 + 압축 + 인과관계 추출."""
        obs = Observation(source=source, raw_data=data)

        # 압축
        if self.config.observation_compression != ObservationCompression.NONE:
            raw_str = json.dumps(data, ensure_ascii=False)
            if len(raw_str) > self.config.compression_threshold:
                obs.compressed = self._compress(raw_str)
            else:
                obs.compressed = raw_str

        # 인과관계 추출
        if self.config.memory_extraction == MemoryExtraction.CAUSALITY_GRAPH:
            obs.causality = self._extract_causality(data, source)
            for c in obs.causality:
                self.causality.add(c.get("cause", ""), c.get("effect", ""),
                                   c.get("confidence", 0.5), source)

        self._observations.append(obs)
        self._observe_count += 1

        # 자동 영속화
        if (self.config.persist_interval > 0
                and self._observe_count % self.config.persist_interval == 0):
            self._auto_persist()

        self._bus.publish(JarvisEventType.TELEMETRY_EMIT, {
            "monitor": self.config.operator_id,
            "source": source,
            "observation_count": self._observe_count,
        })

        return obs

    def recall(self, n: int = None) -> List[Observation]:
        """최근 관찰 회수 — retrieval_strategy 적용."""
        n = n or 10
        if self.config.retrieval_strategy == RetrievalStrategy.RECENT:
            return self._observations[-n:]
        elif self.config.retrieval_strategy == RetrievalStrategy.KEYWORD:
            return self._observations[-n:]  # simplified
        return self._observations[-n:]

    def get_causality_summary(self) -> dict:
        """인과관계 요약."""
        return {
            "total_edges": len(self.causality),
            "frequent_causes": self.causality.frequent_causes(),
        }

    def persist(self):
        """수동 영속화."""
        self._auto_persist()
        self.causality.save()

    # ─── 내부 메서드 ──────────────────────────────────────────

    def _compress(self, text: str) -> str:
        if self.config.observation_compression == ObservationCompression.TRUNCATE:
            return text[:self.config.compression_threshold]
        return self._compressor(text)

    @staticmethod
    def _default_compress(text: str) -> str:
        # 기본 압축: 앞뒤 500자 + 중간 생략
        if len(text) <= 1000:
            return text
        return text[:500] + "\n...[compressed]...\n" + text[-500:]

    def _extract_causality(self, data: dict, source: str) -> List[Dict[str, str]]:
        """규칙 기반 인과관계 추출 (cmux 메트릭 특화)."""
        causality = []
        stats = data.get("stats", data)

        # cmux 메트릭 기반 인과 규칙
        if stats.get("stalled", 0) > 0 and stats.get("error", 0) > 0:
            causality.append({
                "cause": "stalled_surfaces",
                "effect": "error_propagation",
                "confidence": 0.7,
            })
        if stats.get("idle", 0) > 2 and stats.get("working", 0) == 0:
            causality.append({
                "cause": "all_idle",
                "effect": "orchestration_stall",
                "confidence": 0.8,
            })
        if stats.get("ended", 0) > 0:
            causality.append({
                "cause": "session_ended",
                "effect": "capacity_reduction",
                "confidence": 0.9,
            })
        if stats.get("rate_limited", 0) > 0:
            causality.append({
                "cause": "rate_limit_hit",
                "effect": "session_stall",
                "confidence": 0.95,
            })

        return causality

    def _auto_persist(self):
        """자동 영속화 — OpenJarvis auto_persist_state 패턴."""
        if not self.session:
            return
        # 관찰 저장
        unsaved = self._observations[-(self.config.persist_interval):]
        if unsaved:
            self.session.save_observations(self.config.operator_id, unsaved)
        # 상태 저장
        self.session.save_state(self.config.operator_id, {
            "observe_count": self._observe_count,
            "last_persist": time.time(),
            "causality_edges": len(self.causality),
        })

    def _restore_state(self):
        """세션 복원."""
        if not self.session:
            return
        state = self.session.load_state(self.config.operator_id)
        if state:
            self._observe_count = state.get("observe_count", 0)
        recent = self.session.load_recent_observations(
            self.config.operator_id, self.config.max_observations)
        self._observations.extend(recent)
