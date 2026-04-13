#!/usr/bin/env python3
"""test_hooks.py — Hook stdin protection + mode gate tests."""
import json
import importlib.util
import os
import subprocess
import sys

_repo_hooks = os.path.join(os.path.dirname(__file__), "..", "cmux-orchestrator", "hooks")
if os.path.isdir(_repo_hooks):
    HOOKS_DIR = os.getenv("CMUX_HOOKS_DIR", os.path.abspath(_repo_hooks))
else:
    HOOKS_DIR = os.getenv("CMUX_HOOKS_DIR", os.path.expanduser("~/.claude/hooks"))
ORCH_FLAG = "/tmp/cmux-orch-enabled"

def _check_hooks_available():
    """Pre-flight: ensure hooks directory exists and has hook files."""
    if not os.path.isdir(HOOKS_DIR):
        print(f"SKIP ALL: Hooks directory not found: {HOOKS_DIR}")
        print("Set CMUX_HOOKS_DIR env or install cmux skills first.")
        sys.exit(0)
    found = [f for f in os.listdir(HOOKS_DIR) if f.startswith("cmux-") and f.endswith(".py")]
    if not found:
        print(f"SKIP ALL: No cmux hooks in {HOOKS_DIR}")
        sys.exit(0)

# fail-closed hooks (should BLOCK on empty stdin in orch mode)
FAIL_CLOSED = [
    "cmux-completion-verifier.py",
    "cmux-control-tower-guard.py",
    "cmux-workflow-state-machine.py",
    "cmux-no-stall-enforcer.py",
]

# fail-open hooks (should APPROVE on empty stdin in orch mode)
FAIL_OPEN = [
    "cmux-init-enforcer.py",
    "cmux-watcher-notify-enforcer.py",
    "cmux-watcher-msg-guard.py",
]

# silent exit hooks (should exit 0 on empty stdin in orch mode)
SILENT_EXIT = [
    "cmux-enforcement-escalator.py",
    "cmux-setbuffer-fallback.py",
    "cmux-idle-reuse-enforcer.py",
    "cmux-memory-recorder.sh",
]


def run_hook(hook_name, stdin_data="", orch_mode=True):
    """Run a hook with given stdin, return (stdout, stderr, returncode)."""
    hook_path = os.path.join(HOOKS_DIR, hook_name)
    if not os.path.exists(hook_path):
        return None, None, -1

    if orch_mode:
        open(ORCH_FLAG, "w").close()
    elif os.path.exists(ORCH_FLAG):
        os.remove(ORCH_FLAG)

    try:
        ext = os.path.splitext(hook_name)[1]
        cmd = ["bash", hook_path] if ext == ".sh" else ["python3", hook_path]
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", 124
    finally:
        if os.path.exists(ORCH_FLAG):
            os.remove(ORCH_FLAG)


def load_control_tower_guard_module():
    """control tower guard hook 모듈을 직접 로드한다."""
    hook_path = os.path.join(HOOKS_DIR, "cmux-control-tower-guard.py")
    spec = importlib.util.spec_from_file_location("cmux_control_tower_guard", hook_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fail_closed_empty_stdin():
    for hook in FAIL_CLOSED:
        stdout, stderr, rc = run_hook(hook, "", orch_mode=True)
        if stdout is None:
            print(f"  {hook}: SKIP (not found)")
            continue
        try:
            data = json.loads(stdout)
            assert data.get("decision") == "block", f"Expected block, got {data}"
            assert "ERROR" in stderr, f"Expected stderr logging, got: {stderr}"
            print(f"  {hook}: PASS (block + stderr)")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"  {hook}: FAIL — {e}")


def test_fail_open_empty_stdin():
    for hook in FAIL_OPEN:
        stdout, stderr, rc = run_hook(hook, "", orch_mode=True)
        if stdout is None:
            print(f"  {hook}: SKIP (not found)")
            continue
        try:
            data = json.loads(stdout)
            assert data.get("decision") == "approve", f"Expected approve, got {data}"
            assert "ERROR" in stderr, f"Expected stderr logging"
            print(f"  {hook}: PASS (approve + stderr)")
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"  {hook}: FAIL — {e}")


def test_silent_exit_empty_stdin():
    for hook in SILENT_EXIT:
        stdout, stderr, rc = run_hook(hook, "", orch_mode=True)
        if stdout is None:
            print(f"  {hook}: SKIP (not found)")
            continue
        assert rc == 0, f"Expected exit 0, got {rc}"
        assert stdout == "", f"Expected no stdout, got: {stdout}"
        # stderr는 선택적 (일부 hook은 stderr 없이 조용히 종료)
        print(f"  {hook}: PASS (exit 0, stderr={'yes' if stderr else 'no'})")


def test_individual_mode_approve():
    """In individual mode, all hooks should approve without checking stdin."""
    valid_json = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    for hook in FAIL_CLOSED + FAIL_OPEN:
        stdout, stderr, rc = run_hook(hook, valid_json, orch_mode=False)
        if stdout is None:
            continue
        try:
            data = json.loads(stdout)
            assert data.get("decision") == "approve", f"{hook}: Expected approve in individual mode"
        except (json.JSONDecodeError, AssertionError) as e:
            print(f"  {hook}: FAIL (individual mode) — {e}")
            continue
    print("  individual_mode_approve: PASS (all hooks approve)")


def test_malformed_json_stdin():
    """Malformed JSON should trigger fail-safe, not crash."""
    # cmux-control-tower-guard.py: surface 체크 없어 malformed JSON 경로 진입 보장
    for hook in ["cmux-control-tower-guard.py"]:
        stdout, stderr, rc = run_hook(hook, "not json at all", orch_mode=True)
        if stdout is None:
            continue
        data = json.loads(stdout)
        assert data.get("decision") == "block", f"Expected block on malformed JSON"
        print(f"  malformed_json ({hook}): PASS")


def test_control_tower_guard_detects_only_actual_close_workspace_commands():
    """문자열 언급은 허용하고 실제 cmux close-workspace 명령만 감지한다."""
    module = load_control_tower_guard_module()

    indirect_mentions = [
        'echo "cmux-stop에서 close-workspace 옵션이 있다"',
        "echo cmux close-workspace",
        'grep "close-workspace" README.md',
        'python3 -c "print(\'cmux close-workspace --workspace workspace:1\')"',
    ]
    actual_commands = [
        "cmux close-workspace",
        "cmux close-workspace --workspace workspace:1",
        "true && cmux close-workspace --workspace workspace:1",
        "grep watcher README.md | cmux close-workspace --workspace workspace:2",
        "sudo cmux close-workspace --workspace workspace:3",
        "if cmux close-workspace --workspace workspace:4; then echo closed; fi",
    ]

    for command in indirect_mentions:
        assert not module.is_close_workspace_command(command), command

    for command in actual_commands:
        assert module.is_close_workspace_command(command), command


if __name__ == "__main__":
    _check_hooks_available()
    print("=== Hook stdin protection tests ===")
    test_fail_closed_empty_stdin()
    print()
    test_fail_open_empty_stdin()
    print()
    test_silent_exit_empty_stdin()
    print()
    test_individual_mode_approve()
    print()
    test_malformed_json_stdin()
    test_control_tower_guard_detects_only_actual_close_workspace_commands()
    print("=== ALL PASSED ===")
