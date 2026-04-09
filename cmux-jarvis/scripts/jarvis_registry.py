#!/usr/bin/env python3
"""jarvis_registry.py — 데코레이터 기반 플러그인 레지스트리

OpenJarvis core/registry.py 패턴 이식.
RegistryBase(Generic[T])로 서브클래스별 독립 저장소 제공.
"""
from typing import Any, Callable, Dict, Generic, TypeVar

T = TypeVar("T")

class RegistryBase(Generic[T]):
    """OpenJarvis RegistryBase 이식 — 서브클래스별 격리된 레지스트리.

    핵심 패턴: _entries()가 `_registry_entries_{cls.__name__}` 동적 어트리뷰트로
    서브클래스마다 독립 딕셔너리를 생성. 상속 시 저장소가 공유되지 않음.
    """

    @classmethod
    def _entries(cls) -> Dict[str, T]:
        attr = f"_registry_entries_{cls.__name__}"
        if not hasattr(cls, attr):
            setattr(cls, attr, {})
        return getattr(cls, attr)

    @classmethod
    def register(cls, key: str) -> Callable[[T], T]:
        """데코레이터 — key로 등록. 중복 시 덮어쓰기 (re-import 안전)."""
        def wrapper(value: T) -> T:
            entries = cls._entries()
            entries[key] = value
            return value
        return wrapper

    @classmethod
    def register_value(cls, key: str, value: T) -> T:
        """명령형 등록. 중복 시 덮어쓰기 (re-import 안전)."""
        entries = cls._entries()
        entries[key] = value
        return value

    @classmethod
    def get(cls, key: str) -> T:
        """키로 조회. 없으면 KeyError."""
        entries = cls._entries()
        if key not in entries:
            raise KeyError(f"Registry '{cls.__name__}': key '{key}' not found. Available: {list(entries.keys())}")
        return entries[key]

    @classmethod
    def create(cls, key: str, *args: Any, **kwargs: Any) -> Any:
        """조회 + 인스턴스화."""
        return cls.get(key)(*args, **kwargs)

    @classmethod
    def items(cls):
        return cls._entries().items()

    @classmethod
    def keys(cls):
        return cls._entries().keys()

    @classmethod
    def contains(cls, key: str) -> bool:
        return key in cls._entries()

    @classmethod
    def clear(cls):
        cls._entries().clear()


# ─── cmux-jarvis 전용 레지스트리 서브클래스 ─────────────────────

class EvolutionStrategyRegistry(RegistryBase):
    """진화 전략 레지스트리 — settings_change, hook_change, skill_change, code_change, mixed"""

class VerifyPluginRegistry(RegistryBase):
    """검증 플러그인 레지스트리 — evolution_type별 검증 로직"""

class ScheduledTaskRegistry(RegistryBase):
    """스케줄 태스크 타입 레지스트리"""


# ─── 전략 자동 등록 (import 시 @register 데코레이터 실행) ──────
def _auto_register_strategies():
    try:
        import jarvis_strategies  # noqa: F401
    except ImportError:
        pass

_auto_register_strategies()
