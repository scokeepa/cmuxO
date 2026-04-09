#!/usr/bin/env python3
"""jarvis_verify.py — JARVIS 독립 검증 엔진 (AI 미개입)

Usage: jarvis_verify.py <evo-id>

OpenJarvis 패턴 이식: VerifyPluginRegistry 데코레이터 기반 플러그인,
JarvisEventBus 연동, VerificationMode enum.
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import List

from jarvis_registry import VerifyPluginRegistry
from jarvis_events import JarvisEventType, get_jarvis_bus

try:
    from jarvis_telemetry import Telemetry
except ImportError:
    class Telemetry:
        def __init__(self, *a, **kw): pass
        def emit(self, *a, **kw): pass


# ─── VerificationMode — OpenJarvis security/guardrails.py RedactionMode 패턴 ──

class VerificationMode(str, Enum):
    """WARN: 경고만 출력하고 성공 반환. BLOCK: 에러 시 실패."""
    WARN = "warn"
    BLOCK = "block"


# ─── CheckResult ─────────────────────────────────────────────

class CheckResult:
    """단일 검증 항목 결과."""
    def __init__(self, name: str, passed: bool, detail: str = ""):
        self.name = name
        self.passed = passed
        self.detail = detail

    def __str__(self):
        mark = "\u2713" if self.passed else "\u2717"
        suffix = f" ({self.detail})" if self.detail else ""
        return f"{mark} {self.name}{suffix}"


# ─── Registry-based Verify Plugins ──────────────────────────

@VerifyPluginRegistry.register("settings_change")
class SettingsChangePlugin:
    """settings_change 플러그인: merge dry-run."""

    def verify(self, evo_dir: Path) -> list[CheckResult]:
        results: list[CheckResult] = []
        proposed = evo_dir / "proposed-settings.json"
        settings = Path.home() / ".claude" / "settings.json"
        if not proposed.exists() or not settings.exists():
            return results
        try:
            s = json.loads(settings.read_text())
            p = json.loads(proposed.read_text())
            merged = VerificationEngine._deep_merge(s, p)
            json.dumps(merged)
            results.append(CheckResult("settings merge dry-run 성공", True))
        except (json.JSONDecodeError, OSError, TypeError) as e:
            results.append(CheckResult("settings merge dry-run 성공", False, str(e)))
        return results


@VerifyPluginRegistry.register("hook_change")
class HookChangePlugin:
    """hook_change 플러그인: shebang + 실행 검증."""

    def verify(self, evo_dir: Path) -> list[CheckResult]:
        results: list[CheckResult] = []
        fm = evo_dir / "file-mapping.json"
        if not fm.exists():
            return results
        try:
            mapping = json.loads(fm.read_text())
        except (json.JSONDecodeError, OSError):
            return results
        for src, dst in mapping.items():
            if "hooks/" not in str(dst):
                continue
            hook_file = evo_dir / src
            if not hook_file.exists():
                results.append(CheckResult(f"hook 파일 존재: {src}", False))
                continue
            content = hook_file.read_text()
            results.append(CheckResult(f"shebang 존재: {src}", content.startswith("#!")))
        return results


@VerifyPluginRegistry.register("skill_change")
class SkillChangePlugin:
    """skill_change 플러그인: frontmatter + name 필드."""

    def verify(self, evo_dir: Path) -> list[CheckResult]:
        results: list[CheckResult] = []
        fm = evo_dir / "file-mapping.json"
        if not fm.exists():
            return results
        try:
            mapping = json.loads(fm.read_text())
        except (json.JSONDecodeError, OSError):
            return results
        for src, dst in mapping.items():
            if "SKILL.md" not in str(dst):
                continue
            skill_file = evo_dir / src
            if not skill_file.exists():
                results.append(CheckResult(f"SKILL 파일 존재: {src}", False))
                continue
            content = skill_file.read_text()
            results.append(CheckResult(f"frontmatter 존재: {src}", content.startswith("---")))
            results.append(CheckResult(f"name: 필드 존재: {src}", "name:" in content))
        return results


# ─── VerificationEngine ─────────────────────────────────────

class VerificationEngine:
    """JARVIS 진화 검증 엔진.

    Iron Law #2: 예상 결과/TDD 없이 구현 불가
    Iron Law #3: 증거 없이 완료 선언 불가
    """

    def __init__(self, evo_id: str, mode: VerificationMode = VerificationMode.BLOCK):
        self.evo_id = evo_id
        self.mode = mode
        self.jarvis_dir = Path.home() / ".claude" / "cmux-jarvis"
        self.evo_dir = self.jarvis_dir / "evolutions" / evo_id
        self.eagle_path = Path("/tmp/cmux-eagle-status.json")
        self.telemetry = Telemetry(self.jarvis_dir / "telemetry")
        self.results: list[CheckResult] = []

    def check(self, name: str, condition: bool, detail: str = "") -> bool:
        r = CheckResult(name, condition, detail)
        self.results.append(r)
        print(r)
        return condition

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    # ─── 공통 검증 ────────────────────────────────────────────

    def verify_common(self) -> str:
        """공통 검증 + STATUS 읽기. evolution_type 반환."""
        status_file = self.evo_dir / "STATUS"
        status_json = self.evo_dir / "STATUS.json"

        if status_json.exists():
            self.check("STATUS.json 존재", True)
            try:
                data = json.loads(status_json.read_text())
                self.check("STATUS.json 유효", True)
                evo_type = data.get("evolution_type", "unknown")
                phase = data.get("phase", "")
                self.check("STATUS phase=completed|verified",
                           phase in ("completed", "verified"), f"현재: {phase}")
                return evo_type
            except (json.JSONDecodeError, OSError):
                self.check("STATUS.json 유효", False, "파싱 실패")
                return "unknown"
        elif status_file.exists():
            self.check("STATUS 파일 존재", True)
            try:
                data = json.loads(status_file.read_text())
                self.check("STATUS JSON 유효", True)
                evo_type = data.get("evolution_type", "unknown")
                phase = data.get("phase", "")
                self.check("STATUS phase=completed", phase == "completed", f"현재: {phase}")
                return evo_type
            except (json.JSONDecodeError, OSError):
                self.check("STATUS JSON 유효", False, "파싱 실패")
                return "unknown"
        else:
            self.check("STATUS 파일 존재", False, "STATUS/STATUS.json 둘 다 없음")
            return "unknown"

    # ─── Iron Law #2: 예상 결과 / TDD ─────────────────────────

    def verify_iron_law_2(self, evo_type: str):
        """Iron Law #2: 예상 결과 또는 TDD 문서 존재 검증."""
        if evo_type == "settings_change":
            eo = self.evo_dir / "07-expected-outcomes.md"
            self.check("07-expected-outcomes.md 존재", eo.exists())
            if eo.exists():
                content = eo.read_text()
                self.check("expected-outcomes 비어있지 않음", len(content.strip()) > 0)
                lines = [l for l in content.strip().split("\n") if l.strip()]
                self.check("expected-outcomes 3줄 이상", len(lines) >= 3,
                           f"현재: {len(lines)}줄")
        elif evo_type in ("hook_change", "skill_change", "code_change"):
            tdd = self.evo_dir / "05-tdd.md"
            self.check("05-tdd.md 존재", tdd.exists())
            if tdd.exists():
                content = tdd.read_text()
                lines = [l for l in content.strip().split("\n") if l.strip()]
                self.check("05-tdd.md 3줄 이상", len(lines) >= 3, f"현재: {len(lines)}줄")
                has_kw = any(kw in content.lower()
                             for kw in ["test", "assert", "expect", "검증"])
                self.check("05-tdd.md test/assert 키워드", has_kw)
        elif evo_type == "mixed":
            self.check("07-expected-outcomes.md 존재",
                       (self.evo_dir / "07-expected-outcomes.md").exists())
            self.check("05-tdd.md 존재",
                       (self.evo_dir / "05-tdd.md").exists())

    # ─── proposed 검증 ────────────────────────────────────────

    def verify_proposed(self):
        """proposed-settings.json + file-mapping.json 검증."""
        proposed = self.evo_dir / "proposed-settings.json"
        fm = self.evo_dir / "file-mapping.json"

        self.check("proposed-settings.json 존재", proposed.exists())
        if proposed.exists():
            try:
                data = json.loads(proposed.read_text())
                self.check("proposed JSON 유효", True)
                self.check("proposed에 hooks 키 없음", "hooks" not in data)
            except json.JSONDecodeError:
                self.check("proposed JSON 유효", False)

        self.check("file-mapping.json 존재", fm.exists())
        if fm.exists():
            try:
                json.loads(fm.read_text())
                self.check("file-mapping JSON 유효", True)
            except json.JSONDecodeError:
                self.check("file-mapping JSON 유효", False)

    # ─── Iron Law #3: evidence 수집 ───────────────────────────

    def collect_evidence(self):
        """after-metrics 수집 + evidence.json 생성."""
        before = self.evo_dir / "before-metrics.json"
        after = self.evo_dir / "after-metrics.json"
        evidence = self.evo_dir / "evidence.json"

        if self.eagle_path.exists():
            try:
                eagle = json.loads(self.eagle_path.read_text())
                keys = ["stalled", "error", "idle", "working", "ended", "total"]
                metrics = {k: eagle.get("stats", {}).get(k, 0) for k in keys}
                metrics["timestamp"] = eagle.get("timestamp", "")
                after.write_text(json.dumps(metrics, indent=2))
            except (json.JSONDecodeError, OSError):
                pass

        if before.exists() and after.exists():
            try:
                before_data = json.loads(before.read_text())
                after_data = json.loads(after.read_text())
                ev = {
                    "evidence_type": "metric_comparison",
                    "before_snapshot": "before-metrics.json",
                    "after_snapshot": "after-metrics.json",
                    "metrics_compared": list(before_data.keys()),
                    "collection_method": "jarvis_verify.py",
                    "collected_at": after_data.get("timestamp", ""),
                }
                evidence.write_text(json.dumps(ev, indent=2))
            except (json.JSONDecodeError, OSError):
                pass

        self.check("evidence.json 생성", evidence.exists())

    # ─── Registry 기반 플러그인 디스패치 ─────────────────────

    def run_plugin(self, evo_type: str):
        """Registry 기반 플러그인 디스패치."""
        if VerifyPluginRegistry.contains(evo_type):
            plugin = VerifyPluginRegistry.create(evo_type)
            results = plugin.verify(self.evo_dir)
            self.results.extend(results)
            for r in results:
                print(r)

    @staticmethod
    def _deep_merge(base: dict, overlay: dict) -> dict:
        result = base.copy()
        for k, v in overlay.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = VerificationEngine._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    # ─── 풀 검증 실행 ─────────────────────────────────────────

    def run_all(self) -> bool:
        """전체 검증 파이프라인 실행."""
        if not self.evo_dir.exists():
            print(f"ERROR: {self.evo_dir} 없음", file=sys.stderr)
            return False

        bus = get_jarvis_bus()
        bus.publish(JarvisEventType.VERIFY_START, {"evo_id": self.evo_id})

        # 1. 공통
        evo_type = self.verify_common()
        # 2. Iron Law #2
        self.verify_iron_law_2(evo_type)
        # 3. proposed
        self.verify_proposed()
        # 4. evidence (Iron Law #3)
        self.collect_evidence()
        # 5. Registry 기반 플러그인
        print(f"--- 플러그인: {evo_type} ---")
        self.run_plugin(evo_type)

        # 6. EventBus 결과 발행
        if self.errors == 0:
            bus.publish(JarvisEventType.VERIFY_PASS, {
                "evo_id": self.evo_id, "checks": self.total, "errors": 0,
            })
        else:
            bus.publish(JarvisEventType.VERIFY_FAIL, {
                "evo_id": self.evo_id, "checks": self.total, "errors": self.errors,
                "failed": [r.name for r in self.results if not r.passed],
            })

        # 7. 텔레메트리
        self.telemetry.emit("verify", {
            "evo_id": self.evo_id, "checks": self.total,
            "errors": self.errors,
            "result": "PASS" if self.errors == 0 else "FAIL",
        })

        # 결과
        print(f"\n검증 결과: {self.total} 체크, {self.errors} 실패")
        if self.errors > 0 and self.mode == VerificationMode.BLOCK:
            print("FAIL")
            return False
        elif self.errors > 0 and self.mode == VerificationMode.WARN:
            print("WARN (errors found but mode=warn, returning success)")
            return True
        else:
            print("PASS")
            return True


def main():
    if len(sys.argv) < 2:
        print("Usage: jarvis_verify.py <evo-id>", file=sys.stderr)
        sys.exit(1)

    engine = VerificationEngine(sys.argv[1])
    success = engine.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
