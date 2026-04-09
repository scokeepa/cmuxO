#!/usr/bin/env python3
"""jarvis_models.py — JARVIS 진화 엔진 기반 클래스

EvolutionConfig, LockManager, RateCounter — 상태 관리 모듈.
fcntl.flock() 기반 동시 접근 안전성 보장.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class EvolutionConfig:
    """진화 엔진 설정 로더."""

    def __init__(self, config_path: Path):
        self._data = {}
        if config_path.exists():
            try:
                self._data = json.loads(config_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    @property
    def max_consecutive(self) -> int:
        return int(self.get("max_consecutive_evolutions", 3))

    @property
    def max_daily(self) -> int:
        return int(self.get("max_daily_evolutions", 10))

    @property
    def lock_ttl(self) -> int:
        return int(self.get("lock_ttl_minutes", 60))


class LockManager:
    """진화 LOCK 파일 관리. 원자적 쓰기 + flock 보장."""

    def __init__(self, lock_path: Path, ttl_minutes: int):
        self.path = lock_path
        self.ttl = ttl_minutes

    def exists(self) -> bool:
        return self.path.exists()

    def read(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def create(self, evo_id: str, phase: str = "planning") -> dict:
        lock_data = {
            "evo_id": evo_id,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ttl_minutes": self.ttl,
            "phase": phase,
            "surface_id": "jarvis",
        }
        self._atomic_write(lock_data)
        return lock_data

    def update_phase(self, phase: str):
        data = self.read()
        if not data:
            raise FileNotFoundError("LOCK 없음")
        data["phase"] = phase
        self._atomic_write(data)

    def remove(self):
        self.path.unlink(missing_ok=True)

    def is_stale(self) -> bool:
        data = self.read()
        if not data or "created_at" not in data:
            return False
        try:
            created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - created).total_seconds() / 60
            return age_min > self.ttl
        except (ValueError, TypeError):
            return False

    def _atomic_write(self, data: dict):
        lock_path = Path(str(self.path) + ".lock")
        with open(lock_path, "w") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            try:
                fd, tmp = tempfile.mkstemp(
                    dir=str(self.path.parent), suffix=".json"
                )
                try:
                    with os.fdopen(fd, "w") as f:
                        json.dump(data, f, indent=2)
                    os.replace(tmp, str(self.path))
                except Exception:
                    os.unlink(tmp)
                    raise
            finally:
                fcntl.flock(lockf, fcntl.LOCK_UN)


class RateCounter:
    """연속/일일 진화 횟수 카운터. 원자적 저장 + flock 보장."""

    def __init__(self, counter_path: Path):
        self.path = counter_path
        self._data = {"consecutive": 0, "daily": {}}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    @property
    def consecutive(self) -> int:
        return int(self._data.get("consecutive", 0))

    def daily_count(self, date_str: str = None) -> int:
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        return int(self._data.get("daily", {}).get(date_str, 0))

    def increment(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self._data["consecutive"] = self.consecutive + 1
        if "daily" not in self._data:
            self._data["daily"] = {}
        self._data["daily"][today] = self.daily_count(today) + 1
        self._save()

    def reset_consecutive(self):
        self._data["consecutive"] = 0
        self._save()

    def _save(self):
        lock_path = Path(str(self.path) + ".lock")
        with open(lock_path, "w") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            try:
                fd, tmp = tempfile.mkstemp(
                    dir=str(self.path.parent), suffix=".json"
                )
                try:
                    with os.fdopen(fd, "w") as f:
                        json.dump(self._data, f)
                    os.replace(tmp, str(self.path))
                except Exception:
                    os.unlink(tmp)
                    raise
            finally:
                fcntl.flock(lockf, fcntl.LOCK_UN)
