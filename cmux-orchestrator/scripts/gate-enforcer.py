#!/usr/bin/env python3
"""gate-enforcer.py — PostToolUse L2 경고: surface 상태 + GATE 6/8 점검."""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

EAGLE_STATUS_FILE = Path(os.environ.get("CMUX_EAGLE_STATUS_FILE", "/tmp/cmux-eagle-status.json"))
FSM_SCRIPT = Path(__file__).parent / "surface-fsm.py"
CODE_EXT = (".tsx", ".ts", ".py", ".rs", ".css", ".html")
SKIP_PARTS = (".claude/", "skills/", "hooks/", "scripts/", "config/", "SKILL.md")
GATE6_AGENT_TYPES = {"explore", "impl-worker", "search-worker"}
SHELL_SEPARATORS = {";", "&&", "||", "|", "&"}


def load_hook_payload():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def load_eagle_status():
    try:
        if EAGLE_STATUS_FILE.exists():
            return json.loads(EAGLE_STATUS_FILE.read_text())
    except Exception:
        pass
    return {}


def parse_ws_sf(value):
    text = (value or "").strip()
    if not text or ":" not in text:
        return None, None
    ws, sf = text.split(":", 1)
    if not ws.isdigit() or not sf.isdigit():
        return None, None
    return f"workspace:{ws}", f"surface:{sf}"


def get_surfaces_by_status(status):
    eagle = load_eagle_status()
    surfaces = []
    for key, info in eagle.get("surfaces", {}).items():
        if info.get("status") == status:
            ws, sf = parse_ws_sf(key)
            if ws and sf:
                surfaces.append((ws, sf))
    return surfaces


def get_idle_surfaces():
    idle = get_surfaces_by_status("IDLE")
    if idle:
        return idle

    try:
        script = os.path.join(os.path.dirname(__file__), "surface-dispatcher.sh")
        if not os.path.exists(script):
            return []
        result = subprocess.run(
            ["bash", script, "39 32 41 42 43 44"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        surfaces = []
        for token in result.stdout.split():
            if token.startswith("S:") and "=IDLE" in token:
                sid = token.split("=", 1)[0].replace("S:", "", 1).strip()
                if sid.isdigit():
                    surfaces.append(("workspace:1", f"surface:{sid}"))
        return surfaces
    except Exception:
        return []


def format_surface(surface_pair):
    workspace, surface = surface_pair
    return f"{workspace}/{surface}"


def example_read(surface_pair, lines=20, scrollback=False):
    workspace, surface = surface_pair
    extra = " --scrollback" if scrollback else ""
    return f'cmux read-screen --workspace "{workspace}" --surface "{surface}"{extra} --lines {lines}'


def example_send(surface_pair, content):
    workspace, surface = surface_pair
    safe = content.replace('"', '\\"')
    return (
        f'cmux send --workspace "{workspace}" --surface "{surface}" "{safe}"'
        f' && cmux send-key --workspace "{workspace}" --surface "{surface}" enter'
    )


def surface_workspace_map():
    mapping = {}
    eagle = load_eagle_status()
    for key, info in eagle.get("surfaces", {}).items():
        ws, sf = parse_ws_sf(key)
        if not ws or not sf:
            continue
        mapping.setdefault(sf, set()).add(ws)
        sid = info.get("surface")
        if sid:
            mapping.setdefault(f"surface:{sid}", set()).add(ws)
    return {k: sorted(v) for k, v in mapping.items()}


def shell_tokens(command):
    try:
        lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except Exception:
        return command.split()


def iter_cmux_commands(command):
    tokens = shell_tokens(command)
    i = 0
    while i < len(tokens):
        if tokens[i] != "cmux" or i + 1 >= len(tokens):
            i += 1
            continue
        subcommand = tokens[i + 1]
        argv = ["cmux", subcommand]
        j = i + 2
        while j < len(tokens) and tokens[j] not in SHELL_SEPARATORS:
            argv.append(tokens[j])
            j += 1
        yield subcommand.lower(), argv
        i = j + 1 if j < len(tokens) else j


def find_option(argv, option):
    for idx, token in enumerate(argv):
        if token == option and idx + 1 < len(argv):
            return argv[idx + 1]
    return ""


def detect_workspace_missing(command):
    warnings = []
    ws_map = surface_workspace_map()
    for subcommand, argv in iter_cmux_commands(command):
        if subcommand not in ("send", "read-screen"):
            continue
        if "--workspace" in argv:
            continue

        surface = find_option(argv, "--surface") or "surface:N"
        if not surface.startswith("surface:"):
            surface = "surface:N"
        workspace = ws_map.get(surface, ["workspace:1"])[0]
        if subcommand == "send":
            example = example_send((workspace, surface), "내용")
        else:
            example = example_read((workspace, surface), lines=20, scrollback=False)
        warnings.append(
            f'[GATE 8] cmux {subcommand} 에 --workspace 누락: {surface}. '
            f'예: `{example}`'
        )
    return warnings


def code_edit_warning(file_path):
    if not file_path:
        return ""
    if not any(file_path.endswith(ext) for ext in CODE_EXT):
        return ""
    if any(part in file_path for part in SKIP_PARTS):
        return ""

    idle = get_idle_surfaces()
    if not idle:
        return ""

    target = idle[0]
    return (
        f"[GATE] Boss 코드 수정 감지: {os.path.basename(file_path)}. "
        f"{format_surface(target)} 에 구현 위임 권장. "
        f'예: `{example_send(target, f"TASK: {os.path.basename(file_path)} 구현/수정해줘")}`'
    )


def surface_state_warnings():
    warnings = []
    working = get_surfaces_by_status("WORKING")
    waiting = get_surfaces_by_status("WAITING")
    error = get_surfaces_by_status("ERROR")

    if waiting:
        preview = ", ".join(format_surface(s) for s in waiting[:3])
        warnings.append(
            f"[GATE 1] WAITING surface 감지: {preview}. 먼저 질문/확인 처리 필요. "
            f"예: `{example_read(waiting[0], lines=20)}`"
        )
    if error:
        preview = ", ".join(format_surface(s) for s in error[:3])
        warnings.append(
            f"[GATE 1] ERROR surface 감지: {preview}. 원인 확인 후 재배정/복구 필요. "
            f"예: `{example_read(error[0], lines=50, scrollback=True)}`"
        )
    if working:
        preview = ", ".join(format_surface(s) for s in working[:3])
        warnings.append(
            f"[GATE 1] WORKING surface 존재: {preview}. 라운드 종료/완료 선언 금지. "
            f"예: `{example_read(working[0], lines=10)}`"
        )
    return warnings


def gate6_warning(tool_name, tool_input):
    if tool_name.lower() != "agent":
        return ""

    agent_type = (
        tool_input.get("subagent_type")
        or tool_input.get("agent_type")
        or tool_input.get("subagentType")
        or ""
    ).strip()
    if agent_type.lower() not in GATE6_AGENT_TYPES:
        return ""

    idle = get_idle_surfaces()
    if not idle:
        return ""

    target = idle[0]
    examples = {
        "explore": "이 파일/폴더 탐색해줘",
        "impl-worker": "TASK: 이 코드 구현해줘",
        "search-worker": "python3 search_executor.py --query '주제' --full",
    }
    example = example_send(target, examples.get(agent_type.lower(), "TASK: 이 작업 해줘"))
    return (
        f"[GATE 6] Agent({agent_type}) 호출 감지 + IDLE surface 존재: "
        f"{format_surface(target)}. Agent 대신 cmux send로 위임해야 함. "
        f"예: `{example}`"
    )


def fsm_transition(surface_id, action):
    """surface-fsm.py 호출로 FSM 상태 전이. 실패해도 조용히 넘어감."""
    if not FSM_SCRIPT.exists():
        return
    try:
        subprocess.run(
            ["python3", str(FSM_SCRIPT), action, surface_id],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass


def extract_target_surface_from_command(command):
    """cmux 명령어에서 --surface surface:N 추출."""
    import re
    m = re.search(r"--surface\s+[\"']?(surface:\d+)[\"']?", command)
    if m:
        return m.group(1)
    # surface:N 단독 패턴 (--surface 없이)
    m = re.search(r"\bsurface:(\d+)\b", command)
    if m:
        return f"surface:{m.group(1)}"
    return None


def detect_cmux_send(command):
    """cmux send 또는 set-buffer+paste-buffer 패턴 감지 -> target surface 반환."""
    if not command:
        return None
    # 직접 send 패턴
    for subcommand, argv in iter_cmux_commands(command):
        if subcommand in ("send", "set-buffer"):
            surface = find_option(argv, "--surface")
            if surface:
                return surface
    # 전체 명령어에서 surface 추출 (paste-buffer 포함 패턴)
    if "cmux send" in command or ("set-buffer" in command and "paste-buffer" in command):
        return extract_target_surface_from_command(command)
    return None


def detect_done_in_output(tool_result):
    """cmux read-screen 결과에서 DONE: 키워드 감지 -> True/False."""
    if not tool_result:
        return False
    if isinstance(tool_result, dict):
        tool_result = tool_result.get("stdout", "") or tool_result.get("output", "") or str(tool_result)
    return "DONE:" in str(tool_result)


def detect_read_screen_surface(command):
    """cmux read-screen 명령에서 target surface 추출."""
    if not command:
        return None
    for subcommand, argv in iter_cmux_commands(command):
        if subcommand in ("read-screen", "capture-pane"):
            surface = find_option(argv, "--surface")
            if surface:
                return surface
    return None


def auto_fsm_transitions(tool_name, tool_input, tool_result):
    """PostToolUse에서 자동 FSM 전이를 수행.
    - cmux send 감지 -> target surface를 ASSIGNED로 전이
    - cmux read-screen 결과에 DONE: 감지 -> target surface를 DONE으로 전이
    """
    if tool_name.lower() != "bash":
        return []

    transitions = []
    command = tool_input.get("command", "") or tool_input.get("cmd", "")
    result_str = str(tool_result) if tool_result else ""

    # 1. cmux send 감지 -> ASSIGNED + dispatch 신호 파일 생성
    send_target = detect_cmux_send(command)
    if send_target:
        fsm_transition(send_target, "assign")
        transitions.append(f"[FSM] {send_target}: -> ASSIGNED (cmux send 감지)")
        # dispatch 신호 → 와쳐 자동 감시 시작 트리거
        try:
            import json as _json
            from datetime import datetime as _dt, timezone as _tz
            signal = {"dispatched_at": _dt.now(_tz.utc).isoformat(), "target": send_target, "command": command[:200]}
            Path("/tmp/cmux-dispatch-signal.json").write_text(_json.dumps(signal, indent=2))
        except Exception:
            pass

    # 2. cmux read-screen 결과에서 DONE: 감지 -> DONE 전이
    read_target = detect_read_screen_surface(command)
    if read_target and detect_done_in_output(result_str):
        # WORKING -> DONE 전이 시도, ASSIGNED -> WORKING -> DONE 순서로
        fsm_transition(read_target, "working")
        fsm_transition(read_target, "done")
        transitions.append(f"[FSM] {read_target}: -> DONE (DONE: 키워드 감지)")

    return transitions


def main():
    try:
        data = load_hook_payload()
        if not data:
            return

        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        tool_result = data.get("tool_result", None)
        warnings = []

        warnings.extend(surface_state_warnings())

        if tool_name in ("Edit", "Write", "MultiEdit"):
            warning = code_edit_warning(tool_input.get("file_path", ""))
            if warning:
                warnings.append(warning)

        if tool_name.lower() == "bash":
            command = tool_input.get("command", "") or tool_input.get("cmd", "")
            warnings.extend(detect_workspace_missing(command))

        gate6 = gate6_warning(tool_name, tool_input)
        if gate6:
            warnings.append(gate6)

        # 자동 FSM 전이 (PostToolUse)
        fsm_notes = auto_fsm_transitions(tool_name, tool_input, tool_result)
        warnings.extend(fsm_notes)

        if warnings:
            print(json.dumps({"additionalContext": "\n".join(warnings)}, ensure_ascii=False))
    except Exception:
        pass


if __name__ == "__main__":
    main()
