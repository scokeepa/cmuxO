#!/usr/bin/env python3
"""cmux-shim.py — cmux CLI 호환 래퍼 (tmux/psmux 백엔드)

macOS가 아닌 환경에서 cmux 명령어를 tmux로 변환.
기존 오케스트레이션 코드 변경 없이 Windows/Linux 지원.

사용법: cmux <subcommand> [args...]
설치: ln -s /path/to/cmux-shim.py ~/.local/bin/cmux
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

REGISTRY_PATH = os.path.join(tempfile.gettempdir(), "cmux-shim-registry.json")


# ─── 유틸리티 ───

def run(cmd, timeout=10):
    """명령어 실행 후 stdout 반환."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def surface_to_pane(surface):
    """surface:N → %N (tmux pane ID)."""
    m = re.match(r"surface:(\d+)", str(surface))
    return f"%{m.group(1)}" if m else str(surface)


def workspace_to_session(workspace):
    """workspace:N → tmux session name (registry 조회, 없으면 원본 반환)."""
    reg = load_registry()
    ws_data = reg.get("workspaces", {}).get(str(workspace), {})
    if ws_data.get("session"):
        return ws_data["session"]
    # workspace:N에서 N 추출하여 tmux session 이름으로 시도
    m = re.match(r"workspace:(\S+)", str(workspace))
    return m.group(1) if m else str(workspace)


def extract_flag(args, flag):
    """--flag value 추출 후 args에서 제거. 없으면 None."""
    try:
        idx = args.index(flag)
        val = args[idx + 1] if idx + 1 < len(args) else ""
        del args[idx : idx + 2]
        return val
    except (ValueError, IndexError):
        return None


def extract_bool_flag(args, flag):
    """--flag (값 없이) 존재 여부 확인 후 제거."""
    if flag in args:
        args.remove(flag)
        return True
    return False


def remaining_text(args):
    """args에서 남은 텍스트 (마지막 인자)."""
    return args[-1] if args else ""


# ─── Registry ───

def load_registry():
    try:
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"workspaces": {}, "surfaces": {}}


def save_registry(data):
    tmp = REGISTRY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.rename(tmp, REGISTRY_PATH)


def registry_add_workspace(ws_id, session_name):
    reg = load_registry()
    reg.setdefault("workspaces", {})[ws_id] = {"session": session_name}
    save_registry(reg)


def registry_add_surface(surface_id, tmux_pane_id, session_name):
    reg = load_registry()
    reg.setdefault("surfaces", {})[surface_id] = {
        "tmux_target": tmux_pane_id,
        "session": session_name,
    }
    save_registry(reg)


# ─── 서브커맨드 핸들러 ───

def cmd_send(args):
    """cmux send --surface surface:N [--workspace W] "text" """
    surface = extract_flag(args, "--surface")
    workspace = extract_flag(args, "--workspace")
    text = remaining_text(args)
    target = surface_to_pane(surface) if surface else ""
    subprocess.run(["tmux", "send-keys", "-t", target, text])


def cmd_send_key(args):
    """cmux send-key --surface surface:N [--workspace W] KEY"""
    surface = extract_flag(args, "--surface")
    extract_flag(args, "--workspace")  # 무시
    key = remaining_text(args)
    key_map = {
        "enter": "Enter",
        "space": "Space",
        "escape": "Escape",
        "tab": "Tab",
        "up": "Up",
        "down": "Down",
        "left": "Left",
        "right": "Right",
    }
    tmux_key = key_map.get(key.lower(), key)
    target = surface_to_pane(surface) if surface else ""
    subprocess.run(["tmux", "send-keys", "-t", target, tmux_key])


def cmd_read_screen(args):
    """cmux read-screen --surface S [--workspace W] [--lines N] [--scrollback N]"""
    surface = extract_flag(args, "--surface")
    extract_flag(args, "--workspace")
    lines = extract_flag(args, "--lines") or "20"
    scrollback = extract_flag(args, "--scrollback")
    target = surface_to_pane(surface) if surface else ""
    n = scrollback or lines
    print(run(f"tmux capture-pane -t {shlex.quote(target)} -p -S -{n}"))


def cmd_capture_pane(args):
    """cmux capture-pane --surface S [--workspace W] [--scrollback] [--lines N]"""
    surface = extract_flag(args, "--surface")
    extract_flag(args, "--workspace")
    lines = extract_flag(args, "--lines") or "2000"
    has_scrollback = extract_bool_flag(args, "--scrollback")
    target = surface_to_pane(surface) if surface else ""
    if has_scrollback:
        print(run(f"tmux capture-pane -t {shlex.quote(target)} -p -S -"))
    else:
        print(run(f"tmux capture-pane -t {shlex.quote(target)} -p -S -{lines}"))


def cmd_identify(_args):
    """cmux identify → JSON (cmux 형식 호환)."""
    pane_id = os.environ.get("TMUX_PANE", "")
    num = pane_id.lstrip("%") if pane_id else ""
    session = run("tmux display-message -p '#{session_name}'") if pane_id else ""
    # registry에서 workspace 역방향 조회
    reg = load_registry()
    ws_ref = ""
    for ws_id, ws_data in reg.get("workspaces", {}).items():
        if ws_data.get("session") == session:
            ws_ref = ws_id
            break
    if not ws_ref and session:
        ws_ref = f"workspace:{session}"
    print(
        json.dumps(
            {
                "caller": {
                    "surface_ref": f"surface:{num}" if num else "",
                    "workspace_ref": ws_ref,
                }
            }
        )
    )


def cmd_tree(args):
    """cmux tree [--all] → cmux 형식 출력."""
    sessions_raw = run("tmux list-sessions -F '#{session_name}'")
    if not sessions_raw:
        print("(no sessions)")
        return
    sessions = sessions_raw.splitlines()
    # 현재 세션
    current = run("tmux display-message -p '#{session_name}'")
    print("  window window:0 [current] ◄ active")
    for session in sessions:
        panes_raw = run(
            f"tmux list-panes -t {shlex.quote(session)} "
            f"-F '#{{pane_id}} #{{pane_active}} #{{window_index}}'"
        )
        ws_id = f"workspace:{session}"
        current_flag = " [current]" if session == current else ""
        print(f'    ├── workspace {ws_id} "{session}"{current_flag}')
        if panes_raw:
            for pane_line in panes_raw.splitlines():
                parts = pane_line.split()
                if len(parts) >= 2:
                    pid = parts[0]
                    active = parts[1]
                    num = pid.lstrip("%")
                    flag = " [focused]" if active == "1" else ""
                    print(
                        f"    │       ├── surface surface:{num}{flag}"
                    )


def cmd_rename_workspace(args):
    """cmux rename-workspace --workspace W "name" """
    workspace = extract_flag(args, "--workspace")
    name = remaining_text(args)
    session = workspace_to_session(workspace) if workspace else ""
    # registry 업데이트
    reg = load_registry()
    old_ws = str(workspace)
    new_ws = f"workspace:{name}"
    if old_ws in reg.get("workspaces", {}):
        reg["workspaces"][new_ws] = {"session": name}
        del reg["workspaces"][old_ws]
    else:
        reg.setdefault("workspaces", {})[new_ws] = {"session": name}
    save_registry(reg)
    result = run(f"tmux rename-session -t {shlex.quote(session)} {shlex.quote(name)}")
    print(f"OK {workspace}")
    if result:
        print(result)


def cmd_rename_tab(args):
    """cmux rename-tab [--tab T] --surface S "name" """
    extract_flag(args, "--tab")
    surface = extract_flag(args, "--surface")
    name = remaining_text(args)
    target = surface_to_pane(surface) if surface else ""
    result = run(f"tmux rename-window -t {shlex.quote(target)} {shlex.quote(name)}")
    print(f"OK action=rename tab={target} workspace={target}")
    if result:
        print(result)


def cmd_new_workspace(args):
    """cmux new-workspace --name "name" """
    name = extract_flag(args, "--name") or "workspace"
    result = run(
        f"tmux new-session -d -s {shlex.quote(name)} -P -F '#{{session_name}}'"
    )
    session_name = result or name
    ws_id = f"workspace:{session_name}"
    registry_add_workspace(ws_id, session_name)
    print(f"new-workspace result: OK {ws_id}")


def cmd_new_pane(args):
    """cmux new-pane --workspace W"""
    workspace = extract_flag(args, "--workspace")
    session = workspace_to_session(workspace) if workspace else ""
    result = run(
        f"tmux split-window -t {shlex.quote(session)} -d -P -F '#{{pane_id}}'"
    )
    if result:
        num = result.lstrip("%")
        surface_id = f"surface:{num}"
        registry_add_surface(surface_id, result, session)
        print(f"new-pane result: OK {surface_id} pane:{num} workspace:{workspace}")
    else:
        print("new-pane result: FAIL", file=sys.stderr)
        sys.exit(1)


def cmd_close_workspace(args):
    """cmux close-workspace --workspace W"""
    workspace = extract_flag(args, "--workspace")
    session = workspace_to_session(workspace) if workspace else ""
    subprocess.run(["tmux", "kill-session", "-t", session])


def cmd_notify(args):
    """cmux notify --title T --body B"""
    title = extract_flag(args, "--title") or ""
    body = extract_flag(args, "--body") or ""
    msg = f"{title}: {body}" if title and body else title or body
    run(f"tmux display-message {shlex.quote(msg)}")


def cmd_set_status(args):
    """cmux set-status → no-op (cmux 전용 사이드바 기능)."""
    pass


def cmd_wait_for(args):
    """cmux wait-for [--signal "name"] [-S "name"] [--timeout N] "name" """
    signal_flag = extract_bool_flag(args, "-S")
    signal_name = extract_flag(args, "--signal")
    extract_flag(args, "--timeout")  # tmux wait-for에 timeout 없음
    name = signal_name or remaining_text(args)
    if signal_flag:
        subprocess.run(["tmux", "wait-for", "-S", name])
    else:
        subprocess.run(["tmux", "wait-for", name])


def cmd_display_message(args):
    """cmux display-message "text" """
    text = remaining_text(args)
    subprocess.run(["tmux", "display-message", text])


def cmd_set_buffer(args):
    """cmux set-buffer --surface S "text" """
    surface = extract_flag(args, "--surface")
    text = remaining_text(args)
    target = surface_to_pane(surface) if surface else ""
    run(f"tmux set-buffer {shlex.quote(text)}")
    subprocess.run(["tmux", "paste-buffer", "-t", target])


def cmd_paste_buffer(args):
    """cmux paste-buffer --surface S"""
    surface = extract_flag(args, "--surface")
    target = surface_to_pane(surface) if surface else ""
    subprocess.run(["tmux", "paste-buffer", "-t", target])


def cmd_version(_args):
    """cmux --version"""
    tmux_ver = run("tmux -V") or "tmux not found"
    print(f"cmux-shim 1.0.0 (backend: {tmux_ver})")


# cmux 전용 기능 — no-op
def cmd_claude_hook(_args):
    pass


def cmd_log(_args):
    pass


# ─── 디스패처 ───

COMMANDS = {
    "send": cmd_send,
    "send-key": cmd_send_key,
    "read-screen": cmd_read_screen,
    "capture-pane": cmd_capture_pane,
    "identify": cmd_identify,
    "tree": cmd_tree,
    "rename-workspace": cmd_rename_workspace,
    "rename-tab": cmd_rename_tab,
    "new-workspace": cmd_new_workspace,
    "new-pane": cmd_new_pane,
    "close-workspace": cmd_close_workspace,
    "notify": cmd_notify,
    "set-status": cmd_set_status,
    "wait-for": cmd_wait_for,
    "display-message": cmd_display_message,
    "set-buffer": cmd_set_buffer,
    "paste-buffer": cmd_paste_buffer,
    "claude-hook": cmd_claude_hook,
    "log": cmd_log,
    "--version": cmd_version,
}


def main():
    if len(sys.argv) < 2:
        print("Usage: cmux <subcommand> [args...]", file=sys.stderr)
        print("cmux-shim: tmux/psmux 백엔드 호환 래퍼", file=sys.stderr)
        print(f"지원 명령어: {', '.join(sorted(COMMANDS.keys()))}", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]
    handler = COMMANDS.get(subcmd)
    if handler:
        handler(list(sys.argv[2:]))
    else:
        # 미지원 서브커맨드 → tmux에 직접 전달
        os.execvp("tmux", ["tmux"] + sys.argv[1:])


if __name__ == "__main__":
    main()
