#!/usr/bin/env python3
"""test_watcher_scan.py — watcher-scan regression tests."""
import importlib.util
import ast
import json
import os
import tempfile
from pathlib import Path


def _load_watcher_module():
    repo_root = Path(__file__).resolve().parent.parent
    watcher_path = repo_root / "cmux-watcher" / "scripts" / "watcher-scan.py"
    spec = importlib.util.spec_from_file_location("watcher_scan_test_module", watcher_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_role_script_uses_orchestrator_scripts_path():
    mod = _load_watcher_module()
    expected = mod.ORCHESTRATOR_SCRIPTS / "role-register.sh"
    assert mod.ROLE_SCRIPT == expected
    print("  role_script_uses_orchestrator_scripts_path: PASS")


def test_pipe_pane_hooks_incremental_install():
    mod = _load_watcher_module()
    calls = []
    tmp_file = tempfile.mktemp(suffix=".json")
    original_file = mod.PIPE_PANE_INSTALLED_FILE
    original_run_cmd = mod.run_cmd
    try:
        mod.PIPE_PANE_INSTALLED_FILE = Path(tmp_file)

        def _fake_run_cmd(cmd, timeout=30):
            calls.append(cmd)
            return "", 0

        mod.run_cmd = _fake_run_cmd
        base = {
            "1": {"workspace": "workspace:1", "surface": "surface:1"},
            "2": {"workspace": "workspace:1", "surface": "surface:2"},
        }
        mod.setup_pipe_pane_hooks(base)
        assert len(calls) == 2, f"Expected 2 installs, got {len(calls)}"

        expanded = {
            **base,
            "3": {"workspace": "workspace:1", "surface": "surface:3"},
        }
        mod.setup_pipe_pane_hooks(expanded)
        assert len(calls) == 3, f"Expected only new surface install, got {len(calls)} calls"

        installed = json.loads(Path(tmp_file).read_text())
        assert installed == ["1", "2", "3"], f"Unexpected installed set: {installed}"
    finally:
        mod.PIPE_PANE_INSTALLED_FILE = original_file
        mod.run_cmd = original_run_cmd
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
    print("  pipe_pane_hooks_incremental_install: PASS")


def test_run_vision_diff_timeout_degrades_to_unknown():
    mod = _load_watcher_module()
    import concurrent.futures as cf

    class _FakeFuture:
        def done(self):
            return False

    class _FakePool:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, sid):
            return _FakeFuture()

    def _fake_as_completed(futures, timeout=None):
        raise cf.TimeoutError()

    original_pool = cf.ThreadPoolExecutor
    original_as_completed = cf.as_completed
    original_prev = mod.VISION_DIFF_PREV
    tmp_prev = tempfile.mktemp(suffix=".json")
    try:
        cf.ThreadPoolExecutor = _FakePool
        cf.as_completed = _fake_as_completed
        mod.VISION_DIFF_PREV = Path(tmp_prev)
        results = mod.run_vision_diff(["11", "12"])
        assert results == {"11": "UNKNOWN", "12": "UNKNOWN"}, f"Unexpected results: {results}"
    finally:
        cf.ThreadPoolExecutor = original_pool
        cf.as_completed = original_as_completed
        mod.VISION_DIFF_PREV = original_prev
        if os.path.exists(tmp_prev):
            os.remove(tmp_prev)
    print("  run_vision_diff_timeout_degrades_to_unknown: PASS")


def test_run_ane_ocr_verify_timeout_returns_empty():
    mod = _load_watcher_module()
    import concurrent.futures as cf

    class _FakeFuture:
        pass

    class _FakePool:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, sid):
            return _FakeFuture()

    def _fake_as_completed(futures, timeout=None):
        raise cf.TimeoutError()

    original_pool = cf.ThreadPoolExecutor
    original_as_completed = cf.as_completed
    original_ane = mod.ANE_TOOL
    try:
        cf.ThreadPoolExecutor = _FakePool
        cf.as_completed = _fake_as_completed
        # Bypass early return guard
        mod.ANE_TOOL = Path(__file__)
        result = mod.run_ane_ocr_verify(["1", "2", "3"])
        assert result == {}, f"Expected empty result on timeout, got {result}"
    finally:
        cf.ThreadPoolExecutor = original_pool
        cf.as_completed = original_as_completed
        mod.ANE_TOOL = original_ane
    print("  run_ane_ocr_verify_timeout_returns_empty: PASS")


def test_read_surface_text_falls_back_without_bash():
    mod = _load_watcher_module()
    original_bash_cmd = mod.BASH_CMD
    original_run_cmd = mod.run_cmd
    try:
        mod.BASH_CMD = None
        calls = []

        def _fake_run_cmd(cmd, timeout=30):
            calls.append(cmd)
            if cmd[:4] == ["cmux", "tree", "--all", "--json"]:
                payload = {
                    "workspaces": [
                        {
                            "refId": "workspace:1",
                            "surfaces": [{"refId": "surface:9", "name": "worker"}],
                        }
                    ]
                }
                return json.dumps(payload), 0
            if cmd[0] == "cmux" and cmd[1] == "capture-pane":
                return "captured text", 0
            return "", 1

        mod.run_cmd = _fake_run_cmd
        text, rc = mod.read_surface_text("9", lines=12)
        assert rc == 0
        assert text == "captured text"
        assert any(c[:2] == ["cmux", "capture-pane"] for c in calls), f"Unexpected calls: {calls}"
    finally:
        mod.BASH_CMD = original_bash_cmd
        mod.run_cmd = original_run_cmd
    print("  read_surface_text_falls_back_without_bash: PASS")


def test_update_role_heartbeat_direct_json_fallback():
    mod = _load_watcher_module()
    tmp_roles = tempfile.mktemp(suffix=".json")
    try:
        Path(tmp_roles).write_text(
            json.dumps(
                {
                    "watcher": {
                        "surface": "surface:2",
                        "workspace": "workspace:1",
                        "last_heartbeat": "2020-01-01T00:00:00Z",
                    }
                }
            )
        )
        ok = mod.update_role_heartbeat("watcher", path=Path(tmp_roles))
        assert ok is True
        updated = json.loads(Path(tmp_roles).read_text())
        assert updated["watcher"]["last_heartbeat"] != "2020-01-01T00:00:00Z"
    finally:
        if os.path.exists(tmp_roles):
            os.remove(tmp_roles)
    print("  update_role_heartbeat_direct_json_fallback: PASS")


def test_no_literal_subprocess_cmux_invocation_in_watcher_scan():
    repo_root = Path(__file__).resolve().parent.parent
    watcher_path = repo_root / "cmux-watcher" / "scripts" / "watcher-scan.py"
    tree = ast.parse(watcher_path.read_text(encoding="utf-8"))
    literal_subprocess_cmux = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
            and func.attr == "run"
            and node.args
            and isinstance(node.args[0], ast.List)
            and node.args[0].elts
            and isinstance(node.args[0].elts[0], ast.Constant)
            and node.args[0].elts[0].value == "cmux"
        ):
            literal_subprocess_cmux.append(node.lineno)
    assert not literal_subprocess_cmux, f"Literal subprocess cmux calls found: {literal_subprocess_cmux}"
    print("  no_literal_subprocess_cmux_invocation_in_watcher_scan: PASS")

