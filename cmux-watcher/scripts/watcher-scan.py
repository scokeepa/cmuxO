#!/usr/bin/env python3
"""watcher-scan.py — Unified cmux surface health scanner.

Combines eagle_watcher, vision-monitor, and stall-detector into a single
actionable scan that returns prioritized alerts for the boss orchestrator.

Usage:
    python3 watcher-scan.py                  # Full scan (eagle + vision + stall)
    python3 watcher-scan.py --quick          # Eagle-only quick scan
    python3 watcher-scan.py --vision-only    # Vision OCR scan for IDLE surfaces
    python3 watcher-scan.py --continuous N   # Loop every N seconds (default 60)

Output: JSON with prioritized alerts + recommended actions.
"""

import json
import logging
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Central logging setup
_LOG_DIR = Path.home() / ".cmux-logs"
try:
    _LOG_DIR.mkdir(exist_ok=True)
    _log_handler = TimedRotatingFileHandler(
        str(_LOG_DIR / "watcher.log"), when="D", backupCount=7, encoding="utf-8"
    )
    _log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S"))
    logging.basicConfig(level=logging.INFO, handlers=[_log_handler])
except Exception:
    logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
# watcher와 orchestrator가 같은 skills/ 디렉토리 아래에 있음
# 실제 경로: .../skills/cmux-watcher/scripts/watcher-scan.py
#           .../skills/cmux-orchestrator/scripts/
_SKILLS_DIR = SCRIPT_DIR.parent.parent  # .../skills/
ORCHESTRATOR_SCRIPTS = _SKILLS_DIR / "cmux-orchestrator" / "scripts"
if not ORCHESTRATOR_SCRIPTS.exists():
    # fallback: 고정 경로
    ORCHESTRATOR_SCRIPTS = Path.home() / ".claude" / "skills" / "cmux-orchestrator" / "scripts"
EAGLE_WATCHER = ORCHESTRATOR_SCRIPTS / "eagle_watcher.sh"
VISION_MONITOR = ORCHESTRATOR_SCRIPTS / "vision-monitor.sh"
EAGLE_ANALYZER = ORCHESTRATOR_SCRIPTS / "eagle_analyzer.py"
ANE_TOOL = Path.home() / "Ai" / "System" / "11_Modules" / "ane-cli" / "ane_tool"

READ_SURFACE = ORCHESTRATOR_SCRIPTS / "read-surface.sh"

EAGLE_STATUS_FILE = Path("/tmp/cmux-eagle-status.json")
WATCHER_ALERTS_FILE = Path("/tmp/cmux-watcher-alerts.json")
WATCHER_HISTORY_FILE = Path("/tmp/cmux-watcher-history.jsonl")
VISION_DIFF_DIR = Path("/tmp/cmux-vdiff")
VISION_DIFF_PREV = Path("/tmp/cmux-vdiff-prev.json")  # {surface_id: cleaned_text}
PIPE_PANE_INSTALLED_FILE = Path("/tmp/cmux-pipe-pane-installed.json")
SURFACE_MAP_FILE = Path("/tmp/cmux-surface-map.json")
PAUSE_FLAG = Path("/tmp/cmux-paused.flag")
WATCHER_MUTE_FLAG = Path("/tmp/cmux-watcher-muted.flag")


def _resolve_cmux_cmd() -> str:
    """Resolve platform-specific cmux binary.

    Priority:
    1) CMUX_BIN env override
    2) platform defaults (mac/linux: cmux, windows: cmuxw then cmux)
    """
    env_cmd = os.environ.get("CMUX_BIN", "").strip()
    if env_cmd:
        return env_cmd

    candidates = ["cmux", "cmuxw"]
    if os.name == "nt":
        candidates = ["cmuxw", "cmux"]

    for candidate in candidates:
        if shutil.which(candidate):
            return candidate

    # Keep legacy default for error messages and fallback attempts.
    return "cmux"


def _resolve_bash_cmd() -> str | None:
    """Resolve bash command name/path if available."""
    for candidate in ("bash", "bash.exe"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


CMUX_CMD = _resolve_cmux_cmd()
BASH_CMD = _resolve_bash_cmd()

# Thresholds
IDLE_ALERT_SECONDS = 90       # Alert if IDLE for > 90s
STALL_ALERT_SECONDS = 300     # Alert if screen unchanged for > 5min
STALL_DIFF_SECONDS = 30       # Vision Diff comparison interval
ERROR_COOLDOWN_SECONDS = 120  # Don't re-alert same error within 2min
MAX_HISTORY_LINES = 200

# IDLE Debounce (v4.1 — 2026-03-27 lesson)
IDLE_GRACE_PERIOD = 30        # After DONE report, suppress IDLE remind for 30s
IDLE_REMIND_INTERVAL = 120    # Same surface IDLE remind min interval: 2min
DEBOUNCE_FILE = Path("/tmp/cmux-watcher-debounce.json")

def _load_debounce():
    try:
        with open(DEBOUNCE_FILE) as f:
            data = json.load(f)
        return data.get("idle", {}), data.get("done", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}, {}

def _save_debounce(idle, done):
    try:
        tmp = str(DEBOUNCE_FILE) + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"idle": idle, "done": done}, f)
        os.replace(tmp, str(DEBOUNCE_FILE))
    except Exception:
        pass

_idle_debounce, _done_reported = _load_debounce()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[str, int]:
    """Run a command and return (stdout, exit_code)."""
    actual_cmd = list(cmd)
    if actual_cmd:
        if actual_cmd[0] == "cmux":
            actual_cmd[0] = CMUX_CMD
        elif actual_cmd[0] == "bash":
            if BASH_CMD:
                actual_cmd[0] = BASH_CMD
            else:
                return "", 127
    try:
        result = subprocess.run(
            actual_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", 124
    except FileNotFoundError:
        return "", 127


def _resolve_workspace_for_surface(sid: str) -> str:
    """Resolve workspace ref for a surface via native cmux tree JSON."""
    output, rc = run_cmd(["cmux", "tree", "--all", "--json"], timeout=12)
    if rc != 0 or not output:
        return ""
    try:
        tree = json.loads(output)
    except json.JSONDecodeError:
        return ""

    sid_ref = f"surface:{sid}"
    for workspace in tree.get("workspaces", []):
        workspace_ref = workspace.get("refId") or workspace.get("id") or ""
        for surface in workspace.get("surfaces", []):
            surface_ref = surface.get("refId") or surface.get("id") or ""
            if str(surface_ref) == sid_ref or str(surface_ref).replace("surface:", "") == sid:
                return str(workspace_ref)
    return ""


def read_surface_text(sid: str, *, lines: int = 20, scrollback: bool = False) -> tuple[str, int]:
    """Read surface text with bash-script path first, native cmux fallback second."""
    if BASH_CMD and READ_SURFACE.exists():
        cmd = ["bash", str(READ_SURFACE), sid]
        if scrollback:
            cmd += ["--scrollback"]
        cmd += ["--lines", str(lines)]
        text, rc = run_cmd(cmd, timeout=10)
        if rc == 0 and text:
            return text, rc

    workspace_ref = _resolve_workspace_for_surface(sid)
    if not workspace_ref:
        return "", 127

    surface_ref = f"surface:{sid}"
    capture_cmd = [
        "cmux",
        "capture-pane",
        "--workspace",
        workspace_ref,
        "--surface",
        surface_ref,
    ]
    if scrollback:
        capture_cmd.append("--scrollback")
    capture_cmd += ["--lines", str(lines)]

    text, rc = run_cmd(capture_cmd, timeout=10)
    if rc == 0 and text:
        return text, rc

    read_cmd = [
        "cmux",
        "read-screen",
        "--workspace",
        workspace_ref,
        "--surface",
        surface_ref,
    ]
    if scrollback:
        read_cmd.append("--scrollback")
    read_cmd += ["--lines", str(lines)]
    return run_cmd(read_cmd, timeout=10)


def update_role_heartbeat(role: str, *, path: Path = Path("/tmp/cmux-roles.json")) -> bool:
    """Best-effort JSON heartbeat update when bash role script is unavailable."""
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if role not in data or not isinstance(data.get(role), dict):
        return False
    data[role]["last_heartbeat"] = utc_now()
    try:
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(path))
        return True
    except Exception:
        return False


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json_file(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_alert_history() -> dict:
    """Load recent alert history to avoid duplicate alerts."""
    history: dict[str, str] = {}
    try:
        with open(WATCHER_HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    key = entry.get("key", "")
                    ts = entry.get("timestamp", "")
                    if key:
                        history[key] = ts
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return history


def append_alert_history(key: str, timestamp: str) -> None:
    """Append an alert to history file."""
    try:
        with open(WATCHER_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "timestamp": timestamp}) + "\n")
        # Trim if too large
        try:
            lines = WATCHER_HISTORY_FILE.read_text().splitlines()
            if len(lines) > MAX_HISTORY_LINES:
                WATCHER_HISTORY_FILE.write_text(
                    "\n".join(lines[-MAX_HISTORY_LINES:]) + "\n"
                )
        except Exception:
            pass
    except Exception:
        pass


def is_cooldown_active(key: str, history: dict, cooldown_seconds: int) -> bool:
    """Check if an alert is still in cooldown period."""
    last_ts_str = history.get(key, "")
    if not last_ts_str:
        return False
    try:
        last_ts = datetime.strptime(last_ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        now = datetime.now(timezone.utc)
        return (now - last_ts).total_seconds() < cooldown_seconds
    except (ValueError, TypeError):
        return False


AI_PROFILE_FILE = Path.home() / ".claude" / "skills" / "cmux-orchestrator" / "config" / "ai-profile.json"

_FALLBACK_PROFILES = {
    "codex": {"detect_patterns": ["codex", "gpt-", "opencode"],
              "traits": {"no_init_required": True, "sandbox": True}},
}

def load_ai_profiles() -> dict:
    try:
        with open(AI_PROFILE_FILE) as f:
            return json.load(f).get("profiles", _FALLBACK_PROFILES)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return _FALLBACK_PROFILES

def classify_surface_by_traits(ai_name: str, profiles: dict) -> set:
    ai_lower = ai_name.lower()
    for prof in profiles.values():
        patterns = prof.get("detect_patterns", [])
        if any(p in ai_lower for p in patterns):
            return {k for k, v in prof.get("traits", {}).items() if v}
    return set()

def get_system_resources(active_count: int) -> dict:
    """PC 리소스 수집. psutil 없으면 기본값."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_percent": round(mem.percent, 1),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "memory_available_gb": round(mem.available / (1024**3), 1),
            "active_surfaces": active_count,
            "max_additional_surfaces": max(0, int(mem.available / (1024**3) / 0.2)),  # ~200MB per surface
        }
    except ImportError:
        return {
            "cpu_percent": -1,
            "memory_percent": -1,
            "active_surfaces": active_count,
            "max_additional_surfaces": -1,
            "note": "psutil not installed",
        }


def build_departments(surfaces: dict, boss_surface: str, watcher_surface: str) -> dict:
    """surface_roles에서 workspace별 부서 구조 생성."""
    departments = {}
    for sid, info in surfaces.items():
        if sid in (boss_surface, watcher_surface):
            continue
        ws = info.get("workspace", "")
        if not ws:
            continue
        if ws not in departments:
            departments[ws] = {
                "name": "",
                "team_lead": None,
                "members": [],
                "status": "IDLE",
            }
        dept = departments[ws]
        ai = info.get("ai", "unknown")
        status = info.get("status", "IDLE")
        role = info.get("role", "")
        entry = {"surface": sid, "ai": ai, "status": status}
        if role == "team_lead" or (dept["team_lead"] is None and role != "member"):
            dept["team_lead"] = entry
        else:
            dept["members"].append(entry)
        # 부서 상태: 하나라도 WORKING이면 WORKING, 전부 DONE이면 DONE
        if status == "WORKING":
            dept["status"] = "WORKING"
        elif status == "DONE" and dept["status"] != "WORKING":
            dept["status"] = "DONE"
    return departments


def get_available_tools() -> dict:
    """사용자 환경의 사용 가능한 도구 목록."""
    tools = {"plugins": [], "mcp_servers": [], "ai_clis": []}
    # plugins
    settings_file = Path.home() / ".claude" / "settings.json"
    try:
        with open(settings_file) as f:
            settings = json.load(f)
        tools["plugins"] = list(settings.get("enabledPlugins", {}).keys())
        tools["mcp_servers"] = settings.get("enabledMcpjsonServers", [])
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # ai_clis from profile
    try:
        profiles = load_ai_profiles()
        for name, prof in profiles.items():
            cli_cmd = prof.get("cli_command", "")
            if cli_cmd and shutil.which(cli_cmd):
                tools["ai_clis"].append(name)
    except Exception:
        pass
    return tools


QUEUE_FILE = Path("/tmp/cmux-queue.json")

def load_queue() -> list:
    try:
        with open(QUEUE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write_surface_map(eagle_data: dict) -> None:
    """eagle scan + roles + ai-profile + resources로 surface map 자동 생성."""
    surfaces = eagle_data.get("surfaces", {})
    roles = load_json_file(ROLES_FILE)
    profiles = load_ai_profiles()

    watcher_surface = roles.get("watcher", {}).get("surface", "").replace("surface:", "")
    boss_surface = roles.get("boss", {}).get("surface", "").replace("surface:", "")

    no_init_surfaces = []
    sandbox_surfaces = []
    short_prompt_surfaces = []
    two_phase_surfaces = []
    worker_surfaces = []
    surface_roles = {}

    for sid, info in surfaces.items():
        ai = info.get("ai", "unknown")
        role = info.get("role", "worker")
        workspace = info.get("workspace", "")
        surface_roles[sid] = {"ai": ai, "role": role, "workspace": workspace}

        traits = classify_surface_by_traits(ai, profiles)

        if "no_init_required" in traits:
            no_init_surfaces.append(sid)
        if "sandbox" in traits:
            sandbox_surfaces.append(sid)
        if "short_prompt" in traits:
            short_prompt_surfaces.append(sid)
        if "two_phase_send" in traits:
            two_phase_surfaces.append(sid)

        if sid != watcher_surface and sid != boss_surface:
            worker_surfaces.append(sid)

    active_count = len(surfaces)
    departments = build_departments(surfaces, boss_surface, watcher_surface)
    resources = get_system_resources(active_count)
    tools = get_available_tools()
    queue = load_queue()

    surface_map = {
        "watcher_surface": watcher_surface,
        "boss_surface": boss_surface,
        "departments": departments,
        "queue": queue,
        "system_resources": resources,
        "available_tools": tools,
        "no_init_surfaces": sorted(no_init_surfaces),
        "sandbox_surfaces": sorted(sandbox_surfaces),
        "short_prompt_surfaces": sorted(short_prompt_surfaces),
        "two_phase_surfaces": sorted(two_phase_surfaces),
        "codex_surfaces": sorted(no_init_surfaces),  # backward compat alias
        "worker_surfaces": sorted(worker_surfaces),
        "surface_roles": surface_roles,
        "updated_at": utc_now(),
    }
    try:
        # atomic write
        import tempfile
        tmp_path = str(SURFACE_MAP_FILE) + ".tmp"
        with open(tmp_path, "w") as tmp:
            json.dump(surface_map, tmp, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(SURFACE_MAP_FILE))
        logging.info(f"Surface map updated: {len(surfaces)} surfaces, {len(departments)} depts")
    except Exception:
        pass

    # 컨트롤 타워 위치 보정: index 0으로 고정
    boss_ws = roles.get("boss", {}).get("workspace", "")
    if boss_ws:
        try:
            run_cmd(["cmux", "reorder-workspace", "--workspace", boss_ws, "--index", "0"], timeout=5)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

def run_eagle_scan() -> dict:
    """Run eagle_watcher.sh --once and return parsed status."""
    def run_native_tree_fallback(reason: str) -> dict:
        """Windows/compat fallback: query cmux tree directly without bash scripts."""
        output, exit_code = run_cmd(["cmux", "tree", "--all", "--json"], timeout=15)
        if exit_code != 0 or not output:
            return {"error": f"L1 scan unavailable: {reason}; native tree fallback failed"}
        try:
            tree = json.loads(output)
        except json.JSONDecodeError:
            return {"error": f"L1 scan unavailable: {reason}; invalid native tree json"}

        # kwcmux contract: {"workspaces":[...]} with each surface having refId/id/name.
        workspaces = tree.get("workspaces", []) if isinstance(tree, dict) else []
        surfaces = {}
        for workspace in workspaces:
            workspace_ref = workspace.get("refId") or workspace.get("id") or "workspace:1"
            for surface in workspace.get("surfaces", []):
                surface_ref = surface.get("refId") or surface.get("id") or "surface:0"
                sid = str(surface_ref).replace("surface:", "")
                surfaces[sid] = {
                    "status": "UNKNOWN",
                    "ai": surface.get("name", "unknown"),
                    "workspace": workspace_ref,
                    "surface": surface_ref,
                    "title": surface.get("name", ""),
                    "snippet": "",
                    "source": "native-tree-fallback",
                }

        if not surfaces:
            return {"error": f"L1 scan unavailable: {reason}; no surfaces in native tree output"}

        return {
            "source": "native-tree-fallback",
            "surfaces": surfaces,
            "stats": {
                "total": len(surfaces),
                "working": 0,
                "idle": 0,
                "done": 0,
                "error": 0,
                "waiting": 0,
                "stalled": 0,
                "rate_limited": 0,
                "unknown": len(surfaces),
            },
            "updated_at": utc_now(),
        }

    if not EAGLE_WATCHER.exists():
        return run_native_tree_fallback("eagle_watcher.sh not found")

    if BASH_CMD is None:
        return run_native_tree_fallback("bash not found")

    output, exit_code = run_cmd(["bash", str(EAGLE_WATCHER), "--once"], timeout=45)
    if exit_code != 0 or not output:
        # Try reading the status file directly (eagle writes to it)
        status_data = load_json_file(EAGLE_STATUS_FILE)
        if status_data.get("surfaces"):
            return status_data
        return run_native_tree_fallback(f"eagle watcher failed (exit={exit_code})")

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return load_json_file(EAGLE_STATUS_FILE)


def run_vision_scan(surface_ids: list[str]) -> dict:
    """Run vision OCR scan on specific surfaces."""
    if not VISION_MONITOR.exists() or not ANE_TOOL.exists():
        return {}

    surface_list = " ".join(surface_ids)
    output, exit_code = run_cmd(
        ["bash", str(VISION_MONITOR), surface_list], timeout=60
    )
    if exit_code != 0 or not output:
        return {}

    # vision-monitor outputs JSON followed by optional IDLE_ALERT line
    lines = output.strip().splitlines()
    json_lines = []
    for line in lines:
        if line.startswith("IDLE_ALERT:"):
            continue
        json_lines.append(line)
    json_text = "\n".join(json_lines)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {}


def classify_screen_text(text: str) -> dict:
    """Use eagle_analyzer.py to classify screen text."""
    if not EAGLE_ANALYZER.exists():
        return {"status": "UNKNOWN", "confidence": 0.0}

    try:
        result = subprocess.run(
            ["python3", str(EAGLE_ANALYZER)],
            input=text,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    return {"status": "UNKNOWN", "confidence": 0.0}


# ---------------------------------------------------------------------------
# Layer 2.5 : Vision Diff — STALLED 정밀 감지
# ---------------------------------------------------------------------------

import re

def _clean_for_diff(text: str) -> str:
    """시간/숫자 패턴 제거하여 의미 있는 변화만 비교."""
    text = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', '', text)  # HH:MM(:SS)
    text = re.sub(r'\d+', '', text)                       # 모든 숫자
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def load_vision_diff_prev() -> dict:
    """이전 스캔의 surface별 cleaned text 로드."""
    try:
        return json.loads(VISION_DIFF_PREV.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_vision_diff_prev(data: dict) -> None:
    try:
        VISION_DIFF_PREV.write_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass


def run_vision_diff(surface_ids: list[str]) -> dict[str, str]:
    """read-surface로 텍스트 캡처 → 이전 캡처와 비교 → STALLED/WORKING 판정.

    병렬 실행으로 16개 surface를 ~5초 내 처리 (순차 시 4분+ 블로킹 방지).

    Returns: {surface_id: "STALLED" | "WORKING" | "UNKNOWN"}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

    prev = load_vision_diff_prev()
    current: dict[str, str] = {}
    results: dict[str, str] = {}

    def _capture_one(sid: str) -> tuple[str, str, int]:
        text, rc = read_surface_text(sid, lines=20)
        return sid, text, rc

    # 병렬 캡처 (최대 4 동시 — cmux 소켓 과부하 방지)
    max_workers = 4
    per_task_timeout = 8
    global_timeout = max(30, math.ceil(len(surface_ids) / max_workers) * per_task_timeout + 5)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_capture_one, sid): sid for sid in surface_ids}
        try:
            for future in as_completed(futures, timeout=global_timeout):
                try:
                    sid, text, rc = future.result(timeout=per_task_timeout + 2)
                except Exception:
                    sid = futures[future]
                    results[sid] = "UNKNOWN"
                    continue

                if rc != 0 or not text:
                    results[sid] = "UNKNOWN"
                    continue

                cleaned = _clean_for_diff(text)
                current[sid] = cleaned

                prev_cleaned = prev.get(sid, "")
                if not prev_cleaned:
                    results[sid] = "UNKNOWN"
                elif cleaned == prev_cleaned:
                    results[sid] = "STALLED"
                else:
                    results[sid] = "WORKING"
        except FuturesTimeout:
            # Collect completed futures and degrade unfinished ones to UNKNOWN.
            pass

        for future, sid in futures.items():
            if not future.done():
                results[sid] = "UNKNOWN"

    # 현재 캡처를 저장 (다음 라운드 비교용)
    save_vision_diff_prev(current)
    return results


# ---------------------------------------------------------------------------
# Layer 3 : pipe-pane 이벤트 훅 (DONE 즉시 감지)
# ---------------------------------------------------------------------------

def setup_pipe_pane_hooks(surface_map: dict) -> None:
    """모든 surface에 pipe-pane 훅 설치 — DONE 키워드 플래그 파일 생성.

    surface 단위로 증분 설치. 신규 surface에만 hook 적용.
    """
    try:
        installed = set(json.loads(PIPE_PANE_INSTALLED_FILE.read_text()))
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        installed = set()

    current_surfaces = set(surface_map.keys())
    to_install = sorted(current_surfaces - installed)
    if not to_install:
        return

    newly_installed = set()

    for sid in to_install:
        info = surface_map.get(sid, {})
        workspace = info.get("workspace", "")
        surface_ref = info.get("surface", f"surface:{sid}")
        if not workspace:
            continue

        flag_path = f"/tmp/cmux-done-s{sid}.flag"
        grep_cmd = f"grep -m1 -iE 'DONE:|TASK COMPLETE' > {flag_path}"

        _, rc = run_cmd([
            "cmux", "pipe-pane",
            "--surface", surface_ref,
            "--command", grep_cmd,
            "--workspace", workspace,
        ], timeout=5)
        if rc == 0:
            newly_installed.add(sid)

    next_installed = sorted((installed & current_surfaces) | newly_installed)
    try:
        PIPE_PANE_INSTALLED_FILE.write_text(json.dumps(next_installed))
    except Exception:
        pass


def check_pipe_pane_flags(surface_ids: list[str]) -> dict[str, bool]:
    """pipe-pane이 생성한 DONE 플래그 파일 확인."""
    results = {}
    for sid in surface_ids:
        flag = Path(f"/tmp/cmux-done-s{sid}.flag")
        results[sid] = flag.exists() and flag.stat().st_size > 0
    return results


# ---------------------------------------------------------------------------
# Layer 2 : ANE Vision OCR 강제 실행 (IDLE/UNKNOWN + WORKING 재검증)
# ---------------------------------------------------------------------------

def run_ane_ocr_verify(surface_ids: list[str]) -> dict[str, dict]:
    """ANE OCR로 surface 스크린 텍스트 재추출 → eagle_analyzer로 분류.

    병렬 실행으로 블로킹 방지.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

    if not ANE_TOOL.exists():
        return {}

    def _ocr_one(sid: str) -> tuple[str, dict]:
        text, rc = read_surface_text(sid, lines=15)
        if rc != 0 or not text:
            return sid, {}
        return sid, classify_screen_text(text)

    results = {}
    max_workers = 4
    per_task_timeout = 8
    global_timeout = max(30, math.ceil(len(surface_ids) / max_workers) * per_task_timeout + 5)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_ocr_one, sid): sid for sid in surface_ids}
        try:
            for future in as_completed(futures, timeout=global_timeout):
                try:
                    sid, classification = future.result(timeout=per_task_timeout + 2)
                    if classification:
                        results[sid] = classification
                except Exception:
                    continue
        except FuturesTimeout:
            # Degrade gracefully when some surfaces exceed global timeout.
            pass
    return results


# ---------------------------------------------------------------------------
# Boss Health Check
# ---------------------------------------------------------------------------

ROLES_FILE = Path("/tmp/cmux-roles.json")
ROLE_SCRIPT = ORCHESTRATOR_SCRIPTS / "role-register.sh"
BOSS_DEAD_THRESHOLD = 120  # 2min no heartbeat = dead


def check_boss_health(timestamp: str, history: dict):
    """Check if Boss orchestrator is alive. Return alert if dead."""
    if not ROLES_FILE.exists():
        return None

    try:
        roles = json.loads(ROLES_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    boss_info = roles.get("boss")
    if not boss_info:
        return None

    hb_str = boss_info.get("last_heartbeat", "")
    if not hb_str:
        return None

    try:
        hb_dt = datetime.strptime(hb_str, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        age = int((datetime.now(timezone.utc) - hb_dt).total_seconds())
    except (ValueError, TypeError):
        return None

    if age <= BOSS_DEAD_THRESHOLD:
        return None  # Boss is alive

    # Boss is dead — generate CRITICAL alert
    alert_key = "boss_dead"
    if is_cooldown_active(alert_key, history, BOSS_DEAD_THRESHOLD):
        return None

    surface = boss_info.get("surface", "?")
    workspace = boss_info.get("workspace", "?")

    append_alert_history(alert_key, timestamp)
    return {
        "priority": "CRITICAL",
        "surface_id": surface.replace("surface:", ""),
        "surface_ref": surface,
        "workspace": workspace,
        "ai": "Boss (Opus)",
        "status": "BOSS_DEAD",
        "message": f"BOSS ({surface}) DEAD — {age}s since last heartbeat!",
        "action": "RECOVER_BOSS",
        "action_detail": (
            f"cmux send --workspace {workspace} --surface {surface} '/compact' && "
            f"sleep 5 && cmux send --workspace {workspace} --surface {surface} "
            f"'이전 작업을 이어서 진행해. role-register.sh heartbeat boss 실행 후 계속.' && "
            f"cmux send-key --workspace {workspace} --surface {surface} enter"
        ),
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# Alert Generation
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}


def generate_alerts(eagle_data: dict, vision_data: dict) -> list[dict]:
    """Generate prioritized alerts from scan data."""
    alerts: list[dict] = []
    history = load_alert_history()
    timestamp = utc_now()
    surfaces = eagle_data.get("surfaces", {})

    if eagle_data.get("error"):
        alerts.append({
            "priority": "CRITICAL",
            "surface_id": "watcher",
            "surface_ref": "",
            "workspace": "",
            "ai": "Watcher",
            "status": "SCAN_BACKEND_ERROR",
            "message": str(eagle_data.get("error", "Watcher L1 scan backend unavailable")),
            "action": "CHECK_WATCHER_BACKEND",
            "action_detail": "Verify bash/eagle_watcher.sh availability or use native cmux tree fallback.",
            "timestamp": timestamp,
        })

    for sid, info in surfaces.items():
        status = info.get("status", "UNKNOWN")
        ai_name = info.get("ai", "unknown")
        workspace = info.get("workspace", "")
        surface_ref = info.get("surface", f"surface:{sid}")
        snippet = info.get("snippet", "")[:80]

        # --- ERROR alerts (CRITICAL) ---
        if status == "ERROR":
            alert_key = f"error:{sid}"
            if not is_cooldown_active(alert_key, history, ERROR_COOLDOWN_SECONDS):
                alerts.append({
                    "priority": "CRITICAL",
                    "surface_id": sid,
                    "surface_ref": surface_ref,
                    "workspace": workspace,
                    "ai": ai_name,
                    "status": status,
                    "message": f"surface:{sid} ({ai_name}) ERROR: {snippet}",
                    "action": "RECOVER",
                    "action_detail": f"cmux send --workspace {workspace} --surface {surface_ref} '/new' && sleep 2 && cmux send-key --workspace {workspace} --surface {surface_ref} enter",
                    "timestamp": timestamp,
                })
                append_alert_history(alert_key, timestamp)

        # --- RATE_LIMITED alerts (HIGH) ---
        elif status == "RATE_LIMITED":
            reset_time = info.get("reset_time", "")
            alert_key = f"ratelimit:{sid}"
            if not is_cooldown_active(alert_key, history, ERROR_COOLDOWN_SECONDS):
                alerts.append({
                    "priority": "HIGH",
                    "surface_id": sid,
                    "surface_ref": surface_ref,
                    "workspace": workspace,
                    "ai": ai_name,
                    "status": status,
                    "message": f"surface:{sid} ({ai_name}) RATE LIMITED{' reset: ' + reset_time if reset_time else ''}",
                    "action": "WAIT_OR_SKIP",
                    "action_detail": f"Skip surface:{sid} until rate limit resets. Reassign tasks to other surfaces.",
                    "timestamp": timestamp,
                })
                append_alert_history(alert_key, timestamp)

        # --- STALLED alerts (HIGH) ---
        elif status == "STALLED":
            alert_key = f"stalled:{sid}"
            if not is_cooldown_active(alert_key, history, STALL_ALERT_SECONDS):
                alerts.append({
                    "priority": "HIGH",
                    "surface_id": sid,
                    "surface_ref": surface_ref,
                    "workspace": workspace,
                    "ai": ai_name,
                    "status": status,
                    "message": f"surface:{sid} ({ai_name}) STALLED (no change >5min): {snippet}",
                    "action": "NUDGE_OR_RESTART",
                    "action_detail": f"cmux read-screen --workspace {workspace} --surface {surface_ref} --lines 20 로 확인 후 /new 로 재시작 고려",
                    "timestamp": timestamp,
                })
                append_alert_history(alert_key, timestamp)

        # --- WAITING alerts (HIGH) ---
        elif status == "WAITING":
            alert_key = f"waiting:{sid}"
            if not is_cooldown_active(alert_key, history, 60):
                alerts.append({
                    "priority": "HIGH",
                    "surface_id": sid,
                    "surface_ref": surface_ref,
                    "workspace": workspace,
                    "ai": ai_name,
                    "status": status,
                    "message": f"surface:{sid} ({ai_name}) WAITING for input: {snippet}",
                    "action": "RESPOND",
                    "action_detail": f"cmux read-screen --workspace {workspace} --surface {surface_ref} --lines 10 으로 질문 확인 후 응답",
                    "timestamp": timestamp,
                })
                append_alert_history(alert_key, timestamp)

        # --- IDLE alerts (MEDIUM — the core watcher purpose) ---
        elif status in ("IDLE", "ENDED"):
            # Check idle duration from activity data
            activity = eagle_data.get("surfaces_activity", {}).get(sid, {})
            last_activity_str = activity.get("last_activity", "")
            idle_seconds = 0

            if last_activity_str:
                try:
                    last_ts = datetime.strptime(
                        last_activity_str, "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                    idle_seconds = int(
                        (datetime.now(timezone.utc) - last_ts).total_seconds()
                    )
                except (ValueError, TypeError):
                    pass

            # Also check vision data for more accurate idle detection
            vision_surface = vision_data.get("surfaces", {}).get(sid, {})
            vision_idle_seconds = vision_surface.get("idle_seconds", 0)
            if vision_idle_seconds > idle_seconds:
                idle_seconds = vision_idle_seconds

            if idle_seconds >= IDLE_ALERT_SECONDS or status == "ENDED":
                alert_key = f"idle:{sid}"
                now_ts = time.time()
                # Debounce: skip if within grace period after DONE report
                done_time = _done_reported.get(sid, 0)
                if now_ts - done_time < IDLE_GRACE_PERIOD:
                    pass  # Grace period — Boss is likely reassigning
                # Debounce: skip if reminded too recently
                elif sid in _idle_debounce and now_ts - _idle_debounce[sid] < IDLE_REMIND_INTERVAL:
                    pass  # Already reminded recently
                elif not is_cooldown_active(alert_key, history, IDLE_ALERT_SECONDS):
                    alerts.append({
                        "priority": "MEDIUM",
                        "surface_id": sid,
                        "surface_ref": surface_ref,
                        "workspace": workspace,
                        "ai": ai_name,
                        "status": status,
                        "idle_seconds": idle_seconds,
                        "message": f"surface:{sid} ({ai_name}) IDLE {idle_seconds}s — assign work!",
                        "action": "DISPATCH",
                        "action_detail": f"cmux send --workspace {workspace} --surface {surface_ref} '{{task}}' && cmux send-key --workspace {workspace} --surface {surface_ref} enter",
                        "timestamp": timestamp,
                    })
                    _idle_debounce[sid] = now_ts
                    append_alert_history(alert_key, timestamp)

        # --- DONE alerts (HIGH — 즉시 Boss에 보고하여 다음 작업 배정) ---
        elif status == "DONE":
            alert_key = f"done:{sid}"
            # Record DONE time for IDLE debounce grace period
            _done_reported[sid] = time.time()
            if not is_cooldown_active(alert_key, history, 30):
                alerts.append({
                    "priority": "HIGH",
                    "surface_id": sid,
                    "surface_ref": surface_ref,
                    "workspace": workspace,
                    "ai": ai_name,
                    "status": status,
                    "message": f"surface:{sid} ({ai_name}) DONE — 즉시 결과 확인 + 다음 작업 배정!",
                    "action": "REVIEW_AND_DISPATCH",
                    "action_detail": f"cmux read-screen --workspace {workspace} --surface {surface_ref} --scrollback --lines 30 으로 결과 확인 후 다음 작업 배정",
                    "timestamp": timestamp,
                })
                append_alert_history(alert_key, timestamp)

    # --- Boss health check (CRITICAL — watcher's unique duty) ---
    boss_alert = check_boss_health(timestamp, history)
    if boss_alert:
        alerts.append(boss_alert)

    # Sort by priority
    alerts.sort(key=lambda a: PRIORITY_ORDER.get(a.get("priority", "INFO"), 99))

    # Debounce 상태 영속화 (스캔 사이클당 1회)
    _save_debounce(_idle_debounce, _done_reported)

    # MEMBER REQUEST 감지
    for sid, info in surfaces.items():
        if info.get("member_request") == "true" or info.get("member_request") is True:
            alert_key = f"member_request:{sid}"
            if not is_cooldown_active(alert_key, history, 120):
                alerts.append({
                    "priority": "HIGH",
                    "surface_id": sid,
                    "surface_ref": f"surface:{sid}",
                    "status": "MEMBER_REQUEST",
                    "message": f"팀장(s:{sid})이 팀원 요청",
                    "action": "CREATE_MEMBER",
                    "timestamp": timestamp,
                })
                append_alert_history(alert_key, timestamp)

    # 고아 surface 감지 (3-strike + infra 장애 보호)
    ORPHAN_COUNTER_FILE = Path("/tmp/cmux-orphan-counter.json")
    if surfaces and "error" not in eagle_data:
        try:
            orphan_counters = load_json_file(ORPHAN_COUNTER_FILE) if ORPHAN_COUNTER_FILE.exists() else {}
            roles = load_json_file(ROLES_FILE)
            active_sids = set(surfaces.keys())
            counters_changed = False

            for role_name in ("boss", "watcher"):
                role_surface = roles.get(role_name, {}).get("surface", "").replace("surface:", "")
                if not role_surface:
                    continue
                if role_surface not in active_sids:
                    orphan_counters[role_surface] = orphan_counters.get(role_surface, 0) + 1
                    counters_changed = True
                    count = orphan_counters[role_surface]
                    if count >= 3:
                        alerts.append({
                            "priority": "HIGH",
                            "surface_id": role_surface,
                            "status": "ORPHAN_CONFIRMED",
                            "message": f"{role_name}(s:{role_surface}) 3회 연속 미감지",
                            "timestamp": timestamp,
                        })
                    else:
                        alerts.append({
                            "priority": "MEDIUM",
                            "surface_id": role_surface,
                            "status": "ORPHAN_SUSPECTED",
                            "message": f"{role_name}(s:{role_surface}) 미감지 {count}/3",
                            "timestamp": timestamp,
                        })
                else:
                    if role_surface in orphan_counters:
                        del orphan_counters[role_surface]
                        counters_changed = True

            # 50%+ orphan → infra 장애, 카운팅 무효
            if orphan_counters and len(orphan_counters) > max(1, len(roles) * 0.5):
                logging.warning("50%+ orphans — infra failure suspected, skipping")
                orphan_counters = {}
                counters_changed = True

            if counters_changed:
                write_json_atomic(str(ORPHAN_COUNTER_FILE), orphan_counters)
        except Exception:
            pass

    logging.info(f"Alerts generated: {len(alerts)}")
    return alerts


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_report(eagle_data: dict, alerts: list[dict]) -> dict:
    """Generate the final watcher report."""
    stats = eagle_data.get("stats", {})
    timestamp = utc_now()
    surfaces = eagle_data.get("surfaces", {})

    if not stats and surfaces:
        derived = {
            "total": len(surfaces),
            "working": 0,
            "idle": 0,
            "done": 0,
            "error": 0,
            "waiting": 0,
            "stalled": 0,
            "rate_limited": 0,
            "unknown": 0,
        }
        for info in surfaces.values():
            status = str(info.get("status", "UNKNOWN")).lower()
            if status in derived:
                derived[status] += 1
            else:
                derived["unknown"] += 1
        stats = derived

    # Summary counts
    summary = {
        "total_surfaces": stats.get("total", 0),
        "working": stats.get("working", 0),
        "idle": stats.get("idle", 0),
        "done": stats.get("done", 0),
        "error": stats.get("error", 0),
        "waiting": stats.get("waiting", 0),
        "stalled": stats.get("stalled", 0),
        "rate_limited": stats.get("rate_limited", 0),
        "unknown": stats.get("unknown", 0),
    }

    # Action needed flag
    action_needed = any(
        a["priority"] in ("CRITICAL", "HIGH", "MEDIUM") for a in alerts
    )

    # Idle surface IDs for quick reference
    idle_surface_ids = [
        a["surface_id"]
        for a in alerts
        if a.get("action") in ("DISPATCH", "REVIEW_AND_DISPATCH")
    ]

    # Error surface IDs
    error_surface_ids = [
        a["surface_id"]
        for a in alerts
        if a.get("action") in ("RECOVER", "NUDGE_OR_RESTART")
    ]

    report = {
        "timestamp": timestamp,
        "action_needed": action_needed,
        "summary": summary,
        "alerts": alerts,
        "idle_surfaces": idle_surface_ids,
        "error_surfaces": error_surface_ids,
        "alert_count": {
            "critical": sum(1 for a in alerts if a["priority"] == "CRITICAL"),
            "high": sum(1 for a in alerts if a["priority"] == "HIGH"),
            "medium": sum(1 for a in alerts if a["priority"] == "MEDIUM"),
            "low": sum(1 for a in alerts if a["priority"] == "LOW"),
        },
    }

    return report


def format_text_report(report: dict) -> str:
    """Format report as human-readable text for the boss agent."""
    lines: list[str] = []
    summary = report.get("summary", {})
    alerts = report.get("alerts", [])
    counts = report.get("alert_count", {})

    # Header
    lines.append(f"[WATCHER SCAN] {report.get('timestamp', '')}")
    lines.append(
        f"Surfaces: {summary.get('total_surfaces', 0)} total | "
        f"W:{summary.get('working', 0)} "
        f"I:{summary.get('idle', 0)} "
        f"D:{summary.get('done', 0)} "
        f"E:{summary.get('error', 0)} "
        f"RL:{summary.get('rate_limited', 0)} "
        f"ST:{summary.get('stalled', 0)}"
    )

    if not report.get("action_needed"):
        lines.append("All surfaces nominal. No action needed.")
        return "\n".join(lines)

    # Alert summary
    lines.append(
        f"Alerts: C:{counts.get('critical', 0)} "
        f"H:{counts.get('high', 0)} "
        f"M:{counts.get('medium', 0)}"
    )
    lines.append("")

    # Individual alerts
    for alert in alerts:
        priority = alert.get("priority", "INFO")
        marker = {"CRITICAL": "!!!!", "HIGH": "!!!", "MEDIUM": "!!", "LOW": "!", "INFO": "i"}
        lines.append(f"[{marker.get(priority, '?')}] {alert.get('message', '')}")
        lines.append(f"    Action: {alert.get('action', '')} — {alert.get('action_detail', '')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    quick_mode = "--quick" in args
    continuous_mode = "--continuous" in args
    continuous_interval = 60

    if continuous_mode:
        idx = args.index("--continuous")
        if idx + 1 < len(args):
            try:
                continuous_interval = int(args[idx + 1])
            except ValueError:
                pass

    # JSON output mode
    json_output = "--json" in args

    def do_scan() -> dict:
        # =============================================================
        # Layer 1 : Eagle scan (텍스트 패턴 매칭 — 항상 실행)
        # =============================================================
        eagle_data = run_eagle_scan()
        surfaces = eagle_data.get("surfaces", {})
        all_sids = list(surfaces.keys())

        # Layer 3 : pipe-pane 이벤트 훅 설치 (첫 스캔 시 1회)
        setup_pipe_pane_hooks(surfaces)

        # Layer 3 : pipe-pane 플래그 확인 (DONE 즉시 감지)
        pipe_done_flags = check_pipe_pane_flags(all_sids)
        for sid, done in pipe_done_flags.items():
            if done and surfaces.get(sid, {}).get("status") != "DONE":
                # Eagle이 못 잡았지만 pipe-pane이 감지한 DONE
                surfaces.setdefault(sid, {})["status"] = "DONE"
                surfaces[sid]["pipe_pane_detected"] = True

        # non-DONE surface 목록 (Layer 2 OCR 대상)
        active_sids = [
            sid for sid, info in surfaces.items()
            if info.get("status") not in ("DONE",)
        ]
        # 전체 surface 목록 (Layer 2.5 Vision Diff는 DONE 포함 — 거짓 DONE 감지용)
        all_non_self_sids = [
            sid for sid in surfaces.keys()
        ]

        # =============================================================
        # Layer 2 : ANE Vision OCR 재검증 (모든 active surface — 강제)
        # =============================================================
        vision_data: dict = {}
        if not quick_mode and active_sids:
            # 기존 vision-monitor.sh (IDLE/UNKNOWN만)
            idle_unknown_sids = [
                sid for sid in active_sids
                if surfaces.get(sid, {}).get("status") in ("IDLE", "UNKNOWN", "ENDED")
            ]
            if idle_unknown_sids and ANE_TOOL.exists():
                vision_data = run_vision_scan(idle_unknown_sids)

            # ANE OCR 재검증 — WORKING 포함 전 active surface
            ocr_results = run_ane_ocr_verify(active_sids)
            for sid, classification in ocr_results.items():
                ocr_status = classification.get("status", "UNKNOWN")
                eagle_status = surfaces.get(sid, {}).get("status", "UNKNOWN")
                confidence = classification.get("confidence", 0.0)

                # Eagle=WORKING but OCR=IDLE/ERROR → OCR 결과 우선 (높은 신뢰도)
                if eagle_status == "WORKING" and ocr_status in ("IDLE", "ERROR", "STALLED") and confidence >= 0.8:
                    surfaces[sid]["status"] = ocr_status
                    surfaces[sid]["ocr_override"] = True
                    surfaces[sid]["ocr_confidence"] = confidence

                # Eagle=IDLE but OCR=WORKING → OCR 결과 우선
                if eagle_status in ("IDLE", "UNKNOWN") and ocr_status == "WORKING" and confidence >= 0.7:
                    surfaces[sid]["status"] = "WORKING"
                    surfaces[sid]["ocr_override"] = True

        # =============================================================
        # Layer 2.5 : Vision Diff — STALLED 정밀 감지 (강제, DONE 포함)
        # Eagle이 DONE으로 오판할 수 있으므로 전 surface 대상
        # =============================================================
        if not quick_mode and all_non_self_sids:
            try:
                vdiff_results = run_vision_diff(all_non_self_sids)
            except Exception:
                vdiff_results = {}
            for sid, vdiff_status in vdiff_results.items():
                eagle_status = surfaces.get(sid, {}).get("status", "UNKNOWN")
                if vdiff_status == "STALLED" and eagle_status == "WORKING":
                    # Eagle은 WORKING이라 했지만 화면이 안 변함 → STALLED
                    surfaces[sid]["status"] = "STALLED"
                    surfaces[sid]["vdiff_override"] = True
                elif vdiff_status == "WORKING" and eagle_status in ("IDLE", "STALLED"):
                    # Eagle은 IDLE이라 했지만 화면이 변하고 있음 → WORKING
                    surfaces[sid]["status"] = "WORKING"
                    surfaces[sid]["vdiff_override"] = True

        # Update eagle_data with corrected surfaces
        eagle_data["surfaces"] = surfaces

        # Write dynamic surface map for hooks
        write_surface_map(eagle_data)

        # =============================================================
        # Phase 3-4 : Alert 생성 + 리포트
        # =============================================================
        alerts = generate_alerts(eagle_data, vision_data)
        report = generate_report(eagle_data, alerts)

        # 관리 세션 정보 추가
        managed_sessions = {}
        excluded_roles = {"boss", "watcher", "jarvis"}
        if ROLES_FILE.exists():
            try:
                roles = json.loads(ROLES_FILE.read_text())
                for role_name, role_info in roles.items():
                    if role_name in excluded_roles or not isinstance(role_info, dict):
                        continue
                    sf = role_info.get("surface", "").replace("surface:", "")
                    if sf and sf in surfaces:
                        managed_sessions[sf] = {
                            "role": role_name,
                            "status": surfaces[sf].get("status", "UNKNOWN"),
                            "ai": surfaces[sf].get("ai", "unknown"),
                            "title": surfaces[sf].get("title", ""),
                        }
                    elif sf:
                        managed_sessions[sf] = {
                            "role": role_name,
                            "status": "NOT_IN_EAGLE",
                            "ai": role_info.get("ai", "unknown"),
                            "title": "",
                        }
            except Exception:
                pass
        report["managed_sessions"] = managed_sessions

        # 리포트에 감지 계층 활성 현황 추가
        report["layers_active"] = {
            "L1_eagle": "error" not in eagle_data,
            "L2_ane_vision": not quick_mode and ANE_TOOL.exists(),
            "L2_5_vision_diff": not quick_mode and len(all_non_self_sids) > 0,
            "L3_pipe_pane": PIPE_PANE_INSTALLED_FILE.exists(),
        }

        # Save report
        try:
            WATCHER_ALERTS_FILE.write_text(
                json.dumps(report, ensure_ascii=False, indent=2)
            )
        except Exception:
            pass

        return report

    notify_boss = "--notify-boss" in args

    def notify_boss_surface(report: dict) -> None:
        """Send alert summary to Boss surface via cmux send + enter.

        항상 호출 — action_needed 여부 무관하게 상태 리포트 전송.
        WATCHER_MUTE_FLAG 존재 시 알림 전송 스킵 (스캔은 계속).
        """
        if WATCHER_MUTE_FLAG.exists():
            return
        if not ROLES_FILE.exists():
            return
        try:
            roles = json.loads(ROLES_FILE.read_text())
            boss_info = roles.get("boss")
            if not boss_info:
                return
            surface = boss_info["surface"]
            workspace = boss_info["workspace"]
        except (json.JSONDecodeError, KeyError, OSError):
            return

        summary = report.get("summary", {})
        alerts = report.get("alerts", [])
        critical = [a for a in alerts if a["priority"] == "CRITICAL"]
        high = [a for a in alerts if a["priority"] == "HIGH"]

        # 관리 세션 현황
        managed = report.get("managed_sessions", {})

        # 변동 감지: 이전 상태와 비교
        prev_managed_file = Path("/tmp/cmux-watcher-prev-managed.json")
        prev_managed = {}
        if prev_managed_file.exists():
            try:
                prev_managed = json.loads(prev_managed_file.read_text())
            except Exception:
                pass

        managed_changed = prev_managed != managed
        if managed:
            try:
                prev_managed_file.write_text(json.dumps(managed, ensure_ascii=False))
            except Exception:
                pass

        # 상태 요약 항상 포함
        lines = [
            f"[WATCHER→BOSS] W:{summary.get('working',0)} I:{summary.get('idle',0)} "
            f"D:{summary.get('done',0)} E:{summary.get('error',0)} ST:{summary.get('stalled',0)}"
        ]

        # 관리 세션 표시 (변동 시 또는 첫 리포트)
        if managed and managed_changed:
            lines.append("  📋 관리 세션:")
            for sf, info in managed.items():
                status_icon = {"WORKING": "🔵", "IDLE": "⚪", "DONE": "✅", "ERROR": "🔴"}.get(info["status"], "❓")
                title = info.get("title", "")
                name = title if title else info["role"]
                lines.append(f"    {status_icon} {name} [{info['status']}]")

        # CRITICAL/HIGH 알림
        for a in (critical + high)[:5]:
            lines.append(f"  {a['message']}")

        # IDLE/DONE surface 목록 — 재배정 촉구 강제
        idle_sfs = report.get("idle_surfaces", [])
        if idle_sfs:
            lines.append(f"  IDLE: s:{', s:'.join(idle_sfs[:10])}")

        # 전부 DONE/IDLE이면 강조
        total = summary.get("total_surfaces", 0)
        working = summary.get("working", 0)
        if total > 0 and working == 0:
            lines.append("  ALL WORKERS IDLE")

        msg = "\n".join(lines[:8])

        run_cmd(["cmux", "send", "--workspace", workspace,
                 "--surface", surface, msg], timeout=5)
        import time as _time
        _time.sleep(0.5)
        run_cmd(["cmux", "send-key", "--workspace", workspace,
                 "--surface", surface, "enter"], timeout=5)

    def do_heartbeat() -> None:
        """Update watcher heartbeat."""
        if ROLE_SCRIPT.exists() and BASH_CMD:
            _, rc = run_cmd(["bash", str(ROLE_SCRIPT), "heartbeat", "watcher"], timeout=5)
            if rc == 0:
                return
        update_role_heartbeat("watcher")

    # 판정 불가 카운터 (3회 UNKNOWN 연속 → STALLED)
    _boss_unknown_counts: dict[str, int] = {}

    def read_boss_response() -> str:
        """알림 전송 후 Boss 화면을 읽어 상태 파악."""
        if not ROLES_FILE.exists():
            return "UNKNOWN"
        try:
            roles = json.loads(ROLES_FILE.read_text())
            boss_info = roles.get("boss")
            if not boss_info:
                return "UNKNOWN"
            sid = boss_info["surface"].replace("surface:", "")
        except (json.JSONDecodeError, KeyError, OSError):
            return "UNKNOWN"

        text, rc = read_surface_text(sid, lines=10)
        if rc != 0 or not text:
            return "UNKNOWN"

        # Boss 상태 판정 — WORKING 신호 우선
        working_signals = ["Working", "Choreographing", "thinking", "Compiling",
                           "Running", "Processing", "tokens", "thought for",
                           "Retrying", "attempt",
                           "recent", "cmux", "capture", "read-screen", "scrollback"]
        for sig in working_signals:
            if sig in text:
                _boss_unknown_counts.pop(sid, None)
                return "WORKING"

        # IDLE 신호 — 프롬프트 문자 (UTF-8 멀티바이트 포함)
        idle_signals = ["\u276f", "\u203a", "❯", "›", "bypass permissions"]
        for sig in idle_signals:
            if sig in text:
                _boss_unknown_counts.pop(sid, None)
                return "IDLE"

        # 판정 불가 시 UNKNOWN 반환, 3회 연속 UNKNOWN → STALLED
        if sid not in _boss_unknown_counts:
            _boss_unknown_counts[sid] = 0
        _boss_unknown_counts[sid] += 1
        if _boss_unknown_counts[sid] >= 3:
            del _boss_unknown_counts[sid]
            return "STALLED"
        return "UNKNOWN"

    def adaptive_interval(boss_state: str, has_working_workers: bool) -> int:
        """Boss 상태 + worker 상태에 따라 폴링 간격 자동 조절.

        - Boss WORKING + workers WORKING: 60초 (정상 감시)
        - Boss IDLE + workers WORKING: 30초 (곧 완료될 수 있음)
        - Boss IDLE + workers IDLE: 120초 (모두 대기 — 느린 폴링)
        - Boss WORKING + workers IDLE: 15초 (Boss가 배정 중 — 빠른 감시)
        """
        if boss_state == "WORKING" and has_working_workers:
            return 60
        elif boss_state == "IDLE" and has_working_workers:
            return 30
        elif boss_state == "IDLE" and not has_working_workers:
            return 120  # 모두 대기 — 느린 폴링
        elif boss_state == "WORKING" and not has_working_workers:
            return 15   # Boss 배정 시작 — 빠른 전환
        return continuous_interval

    if continuous_mode:
        iteration = 0

        while True:
            # --- Pause gate ---
            if PAUSE_FLAG.exists():
                try:
                    Path("/tmp/cmux-watcher-state.json").write_text(
                        json.dumps({
                            "boss_state": "PAUSED",
                            "has_working_workers": False,
                            "interval": 0,
                            "iteration": iteration,
                            "timestamp": utc_now(),
                            "paused": True,
                        }, ensure_ascii=False)
                    )
                except Exception:
                    pass
                run_cmd(["cmux", "set-status", "watcher", "⏸ PAUSED",
                         "--icon", "pause", "--color", "#ffaa00"], timeout=3)
                time.sleep(5)
                iteration += 1
                continue
            # --- End pause gate ---
            report = do_scan()
            if json_output:
                print(json.dumps(report, ensure_ascii=False))
            else:
                print(format_text_report(report))
            sys.stdout.flush()

            summary = report.get("summary", {})
            has_working = summary.get("working", 0) > 0

            # Boss 반응 읽기 (scan 직후 — notify 전에)
            boss_state = read_boss_response()

            # 상태 파일 즉시 기록 (notify 블로킹 무관하게 watchdog이 참조)
            try:
                Path("/tmp/cmux-watcher-state.json").write_text(
                    json.dumps({
                        "boss_state": boss_state,
                        "has_working_workers": has_working,
                        "interval": adaptive_interval(boss_state, has_working),
                        "iteration": iteration,
                        "timestamp": utc_now(),
                    }, ensure_ascii=False)
                )
            except Exception:
                pass

            # Heartbeat
            do_heartbeat()

            # Sidebar
            is_muted = WATCHER_MUTE_FLAG.exists()
            status_text = (
                f"{'🔇 ' if is_muted else ''}"
                f"W:{summary.get('working',0)} "
                f"I:{summary.get('idle',0)} "
                f"D:{summary.get('done',0)} "
                f"E:{summary.get('error',0)}"
            )
            color = "#ff0000" if summary.get("error", 0) > 0 else "#00ff00"
            if is_muted:
                color = "#ffaa00"
            elif boss_state == "IDLE" and not has_working:
                color = "#888888"
            run_cmd(["cmux", "set-status", "watcher", status_text,
                     "--icon", "eye", "--color", color], timeout=3)

            # Notify Boss — 항상 (블로킹 방지: 별도 스레드)
            if notify_boss:
                import threading
                t = threading.Thread(target=notify_boss_surface, args=(report,), daemon=True)
                t.start()
                t.join(timeout=5)  # 최대 5초 대기, 블로킹되면 버림

            iteration += 1
            interval = adaptive_interval(boss_state, has_working)
            time.sleep(interval)
    else:
        report = do_scan()
        if json_output:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(format_text_report(report))
        if notify_boss:
            notify_boss_surface(report)
        do_heartbeat()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 에러를 alerts에 기록 (watchdog이 프로세스 재시작)
        import traceback
        error_msg = f"WATCHER CRASH: {e}\n{traceback.format_exc()}"
        try:
            WATCHER_ALERTS_FILE.write_text(json.dumps({
                "timestamp": utc_now(),
                "status": "WATCHER_ERROR",
                "message": error_msg,
            }, ensure_ascii=False))
        except Exception:
            pass
        sys.exit(1)
