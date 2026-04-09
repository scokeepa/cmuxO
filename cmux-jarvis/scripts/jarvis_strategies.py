#!/usr/bin/env python3
"""jarvis_strategies.py -- Registry-based Evolution Strategies

OpenJarvis core/registry.py 패턴 이식.
5개 전략: settings_change, hook_change, skill_change, code_change, mixed.
"""
from abc import ABC, abstractmethod

from jarvis_registry import EvolutionStrategyRegistry
from jarvis_eventbus import PipelineError


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursive deep merge -- overlay wins on conflict."""
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class EvolutionStrategy(ABC):
    @abstractmethod
    def validate(self, ctx: dict): ...
    @abstractmethod
    def merge(self, ctx: dict) -> dict: ...


@EvolutionStrategyRegistry.register("settings_change")
class SettingsChangeStrategy(EvolutionStrategy):
    def validate(self, ctx: dict):
        proposed = ctx.get("proposed", {})
        if "hooks" in proposed:
            raise PipelineError("settings_change",
                                "E4 defense: hooks key in proposed -- rejected")

    def merge(self, ctx: dict) -> dict:
        return deep_merge(ctx.get("settings", {}), ctx.get("proposed", {}))


@EvolutionStrategyRegistry.register("hook_change")
class HookChangeStrategy(EvolutionStrategy):
    def validate(self, ctx: dict):
        if not ctx.get("proposed"):
            raise PipelineError("hook_change", "No proposed hook changes")

    def merge(self, ctx: dict) -> dict:
        return deep_merge(ctx.get("settings", {}), ctx.get("proposed", {}))


@EvolutionStrategyRegistry.register("skill_change")
class SkillChangeStrategy(EvolutionStrategy):
    def validate(self, ctx: dict):
        if not ctx.get("proposed"):
            raise PipelineError("skill_change", "No proposed skill changes")

    def merge(self, ctx: dict) -> dict:
        return deep_merge(ctx.get("settings", {}), ctx.get("proposed", {}))


@EvolutionStrategyRegistry.register("code_change")
class CodeChangeStrategy(EvolutionStrategy):
    def validate(self, ctx: dict):
        if not ctx.get("proposed"):
            raise PipelineError("code_change", "No proposed code changes")

    def merge(self, ctx: dict) -> dict:
        return deep_merge(ctx.get("settings", {}), ctx.get("proposed", {}))


@EvolutionStrategyRegistry.register("mixed")
class MixedStrategy(EvolutionStrategy):
    def validate(self, ctx: dict):
        proposed = ctx.get("proposed", {})
        if "hooks" in proposed:
            raise PipelineError("mixed",
                                "E4 defense: hooks key in proposed -- rejected")

    def merge(self, ctx: dict) -> dict:
        return deep_merge(ctx.get("settings", {}), ctx.get("proposed", {}))
