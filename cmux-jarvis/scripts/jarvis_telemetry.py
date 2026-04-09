#!/usr/bin/env python3
"""jarvis-telemetry.py — JARVIS 진화 텔레메트리 레이어

OpenJarvis traces/telemetry 패턴 참고.
진화 이벤트를 JSONL로 구조화 저장 + 링 버퍼 인메모리 캐시 + EventBus 연동.

Usage (CLI):
    jarvis-telemetry.py query [--type TYPE] [--since YYYY-MM-DD] [--summary]
    jarvis-telemetry.py tail [N]

Usage (Python):
    from jarvis_telemetry import Telemetry
    t = Telemetry()
    t.emit("backup", {"evo_id": "evo-1"})
    t.query(event_type="apply", since="2026-04-01")
"""

from __future__ import annotations

import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from jarvis_events import JarvisEventType, get_jarvis_bus


# ─── 링 버퍼 ────────────────────────────────────────────────

class TelemetryRingBuffer:
    """인메모리 링 버퍼 — OpenJarvis telemetry/session.py 패턴."""

    def __init__(self, maxlen: int = 10000):
        self._buffer: deque[dict] = deque(maxlen=maxlen)

    def push(self, event: dict):
        self._buffer.append(event)

    def recent(self, n: int = 20) -> list[dict]:
        items = list(self._buffer)
        return items[-n:]

    def window(self, start_ts: float, end_ts: float) -> list[dict]:
        """시간 윈도우 쿼리."""
        return [e for e in self._buffer if start_ts <= e.get("ts_epoch", 0) <= end_ts]

    def __len__(self):
        return len(self._buffer)


# ─── 텔레메트리 엔진 ────────────────────────────────────────

class Telemetry:
    """진화 이벤트 구조화 로깅 엔진."""

    def __init__(self, telemetry_dir: Path = None, *, bus=None):
        self.dir = telemetry_dir or (Path.home() / ".claude" / "cmux-jarvis" / "telemetry")
        self.dir.mkdir(parents=True, exist_ok=True)
        self._bus = bus if bus is not None else get_jarvis_bus()
        self._ring = TelemetryRingBuffer()

    def _log_path(self, date_str: str = None) -> Path:
        """일별 JSONL 파일 경로."""
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        return self.dir / f"events-{date_str}.jsonl"

    def emit(self, event_type: str, data: dict = None):
        """이벤트 기록: 링 버퍼 + JSONL + EventBus 트리플 라이트."""
        now = datetime.now(timezone.utc)
        event = {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ts_epoch": now.timestamp(),
            "type": event_type,
            "data": data or {},
        }
        # 1) 링 버퍼
        self._ring.push(event)
        # 2) JSONL append
        log_path = self._log_path()
        with open(log_path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        # 3) EventBus
        self._bus.publish(JarvisEventType.TELEMETRY_EMIT, {
            "event_type": event_type,
            **event,
        })

    def read_events(self, since: str = None, event_type: str = None) -> list[dict]:
        """이벤트 조회. since: YYYY-MM-DD, event_type: 필터."""
        events = []
        for log_file in sorted(self.dir.glob("events-*.jsonl")):
            date_part = log_file.stem.replace("events-", "")
            if since and date_part < since:
                continue
            try:
                for line in log_file.read_text().strip().split("\n"):
                    if not line:
                        continue
                    ev = json.loads(line)
                    if event_type and ev.get("type") != event_type:
                        continue
                    events.append(ev)
            except (json.JSONDecodeError, OSError):
                continue
        return events

    def query(self, event_type: str = None, since: str = None, summary: bool = False) -> dict:
        """집계 쿼리."""
        events = self.read_events(since=since, event_type=event_type)
        if summary:
            return self._summarize(events)
        return {"count": len(events), "events": events}

    def query_window(self, start_ts: float, end_ts: float) -> list[dict]:
        """링 버퍼 시간 윈도우 쿼리."""
        return self._ring.window(start_ts, end_ts)

    def tail(self, n: int = 20) -> list[dict]:
        """최근 N개 이벤트."""
        all_events = self.read_events()
        return all_events[-n:]

    def _summarize(self, events: list[dict]) -> dict:
        """이벤트 요약 통계."""
        type_counts: dict[str, int] = {}
        evo_ids: set[str] = set()
        first_ts = None
        last_ts = None

        for ev in events:
            t = ev.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
            evo_id = ev.get("data", {}).get("evo_id")
            if evo_id:
                evo_ids.add(evo_id)
            ts = ev.get("ts")
            if ts:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts

        applies = type_counts.get("apply", 0)
        rollbacks = type_counts.get("rollback", 0)
        total_completions = applies + rollbacks
        success_rate = (applies / total_completions * 100) if total_completions > 0 else 0
        avg_duration = self._calc_avg_duration(events)

        return {
            "total_events": len(events),
            "type_counts": type_counts,
            "unique_evolutions": len(evo_ids),
            "success_rate_pct": round(success_rate, 1),
            "avg_duration_seconds": avg_duration,
            "period": {"from": first_ts, "to": last_ts},
        }

    @staticmethod
    def _calc_avg_duration(events: list[dict]) -> float | None:
        """backup -> apply/rollback 간 평균 소요시간(초) 계산."""
        backup_times: dict[str, str] = {}
        durations: list[float] = []
        for ev in events:
            evo_id = ev.get("data", {}).get("evo_id")
            ts = ev.get("ts")
            if not evo_id or not ts:
                continue
            if ev.get("type") == "backup":
                backup_times[evo_id] = ts
            elif ev.get("type") in ("apply", "rollback") and evo_id in backup_times:
                try:
                    t0 = datetime.fromisoformat(backup_times[evo_id].replace("Z", "+00:00"))
                    t1 = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    durations.append((t1 - t0).total_seconds())
                except (ValueError, TypeError):
                    pass
        if not durations:
            return None
        return round(sum(durations) / len(durations), 1)

    def prune(self, keep_days: int = 30):
        """오래된 로그 정리."""
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
        removed = 0
        for log_file in self.dir.glob("events-*.jsonl"):
            date_part = log_file.stem.replace("events-", "")
            if date_part < cutoff_date:
                log_file.unlink()
                removed += 1
        return removed


# ─── CLI 엔트리포인트 ─────────────────────────────────────────

def main():
    telemetry = Telemetry()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "query":
        event_type = None
        since = None
        summary = False
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
                event_type = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--since" and i + 1 < len(sys.argv):
                since = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--summary":
                summary = True
                i += 1
            else:
                i += 1
        result = telemetry.query(event_type=event_type, since=since, summary=summary)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "tail":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        events = telemetry.tail(n)
        for ev in events:
            print(json.dumps(ev, ensure_ascii=False))

    elif cmd == "prune":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        removed = telemetry.prune(days)
        print(f"OK: {removed}개 로그 파일 삭제 (>{days}일)")

    else:
        print("Usage: jarvis-telemetry.py <query|tail|prune> [options]")
        print("  query [--type TYPE] [--since YYYY-MM-DD] [--summary]")
        print("  tail [N]")
        print("  prune [DAYS]")


if __name__ == "__main__":
    main()
