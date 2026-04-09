#!/usr/bin/env python3
"""jarvis_dag.py — DAG-based pipeline (Kahn algorithm)

OpenJarvis workflow/engine.py 패턴 이식.
NodeType + DAGNode + EvolutionDAG.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from jarvis_events import JarvisEventType
from jarvis_eventbus import PipelineError


class NodeType(str, Enum):
    CHECK = "check"
    ACTION = "action"
    CONDITION = "condition"


class DAGNode:
    __slots__ = ("id", "node_type", "fn", "depends_on")

    def __init__(self, id: str, node_type: NodeType, fn: Callable,
                 depends_on: list[str] | None = None):
        self.id = id
        self.node_type = node_type
        self.fn = fn
        self.depends_on = depends_on or []


class EvolutionDAG:
    """DAG-based pipeline with Kahn algorithm stage computation."""

    def __init__(self):
        self._nodes: dict[str, DAGNode] = {}

    def add_node(self, node: DAGNode):
        self._nodes[node.id] = node

    def validate(self):
        """Cycle detection via DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self._nodes}

        def dfs(nid: str):
            color[nid] = GRAY
            for dep in self._nodes[nid].depends_on:
                if dep not in self._nodes:
                    raise ValueError(f"Unknown dependency '{dep}' in node '{nid}'")
                if color[dep] == GRAY:
                    raise ValueError(f"Cycle detected involving '{dep}'")
                if color[dep] == WHITE:
                    dfs(dep)
            color[nid] = BLACK

        for nid in self._nodes:
            if color[nid] == WHITE:
                dfs(nid)

    def execution_stages(self) -> list[list[DAGNode]]:
        """Kahn algorithm BFS leveling -- returns stages of parallel-ready nodes."""
        in_degree = {nid: len(self._nodes[nid].depends_on) for nid in self._nodes}
        queue: deque[str] = deque(nid for nid, d in in_degree.items() if d == 0)
        stages: list[list[DAGNode]] = []

        while queue:
            stage_ids = list(queue)
            queue.clear()
            stages.append([self._nodes[nid] for nid in stage_ids])
            for nid in stage_ids:
                for candidate in self._nodes.values():
                    if nid in candidate.depends_on:
                        in_degree[candidate.id] -= 1
                        if in_degree[candidate.id] == 0:
                            queue.append(candidate.id)

        if sum(len(s) for s in stages) != len(self._nodes):
            raise ValueError("Cycle detected -- not all nodes scheduled")
        return stages

    def run(self, context: dict, bus=None) -> dict:
        """Execute stages sequentially; within each stage, run nodes."""
        self.validate()
        stages = self.execution_stages()
        context["_completed_steps"] = []
        context["_started_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

        if bus:
            bus.publish(JarvisEventType.PIPELINE_STAGE_START,
                        {"total_stages": len(stages)})

        for i, stage in enumerate(stages):
            if bus:
                bus.publish(JarvisEventType.PIPELINE_STAGE_START,
                            {"stage": i, "nodes": [n.id for n in stage]})
            for node in stage:
                try:
                    result = node.fn(context)
                    if isinstance(result, dict):
                        context.update(result)
                    context["_completed_steps"].append(node.id)
                except PipelineError:
                    context["_failed_step"] = node.id
                    if bus:
                        bus.publish(JarvisEventType.PIPELINE_FAIL,
                                    {"node": node.id})
                    raise
                except Exception as e:
                    context["_failed_step"] = node.id
                    if bus:
                        bus.publish(JarvisEventType.PIPELINE_FAIL,
                                    {"node": node.id, "error": str(e)})
                    raise PipelineError(node.id, str(e)) from e

        context["_finished_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        if bus:
            bus.publish(JarvisEventType.PIPELINE_DONE,
                        {"steps": context["_completed_steps"]})
        return context
