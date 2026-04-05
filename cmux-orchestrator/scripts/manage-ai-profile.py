#!/usr/bin/env python3
"""manage-ai-profile.py — AI Profile management CLI.

Usage:
    python3 manage-ai-profile.py --detect          # 설치된 AI CLI 자동 감지
    python3 manage-ai-profile.py --list            # 현재 프로파일 표시
    python3 manage-ai-profile.py --add minimax     # AI 추가 (기본 traits)
    python3 manage-ai-profile.py --remove glm      # AI 제거
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROFILE_FILE = Path(__file__).parent.parent / "config" / "ai-profile.json"

# 기본 AI 프로파일 (--detect 시 사용)
DEFAULT_PROFILES = {
    "codex": {
        "display_name": "Codex",
        "cli_command": "codex",
        "detect_patterns": ["codex", "gpt-", "opencode"],
        "traits": {"no_init_required": True, "sandbox": True, "short_prompt": False, "two_phase_send": False},
    },
    "opencode": {
        "display_name": "OpenCode",
        "cli_command": "cco",
        "detect_patterns": ["opencode", "cco"],
        "traits": {"no_init_required": True, "sandbox": True, "short_prompt": False, "two_phase_send": False},
    },
    "minimax": {
        "display_name": "MiniMax",
        "cli_command": "ccm",
        "detect_patterns": ["minimax"],
        "traits": {"no_init_required": False, "sandbox": False, "short_prompt": False, "two_phase_send": False},
    },
    "glm": {
        "display_name": "GLM",
        "cli_command": "ccg2",
        "detect_patterns": ["glm", "chatglm"],
        "traits": {"no_init_required": False, "sandbox": False, "short_prompt": True, "two_phase_send": False},
    },
    "gemini": {
        "display_name": "Gemini",
        "cli_command": "gemini",
        "detect_patterns": ["gemini"],
        "traits": {"no_init_required": False, "sandbox": False, "short_prompt": False, "two_phase_send": True},
    },
    "claude": {
        "display_name": "Claude Code",
        "cli_command": "claude",
        "detect_patterns": ["opus", "sonnet", "haiku", "claude"],
        "traits": {"no_init_required": False, "sandbox": False, "short_prompt": False, "two_phase_send": False},
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_profile() -> dict:
    try:
        with open(PROFILE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": 1, "updated_at": utc_now(), "profiles": {}}


def save_profile(data: dict) -> None:
    data["updated_at"] = utc_now()
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # atomic write
    import tempfile, os
    tmp_path = str(PROFILE_FILE) + ".tmp"
    with open(tmp_path, "w") as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
    os.rename(tmp_path, str(PROFILE_FILE))
    print(f"Saved: {PROFILE_FILE}")


def cmd_detect() -> None:
    """PATH에서 AI CLI 자동 감지 → 프로파일 생성."""
    data = load_profile()
    profiles = data.get("profiles", {})

    print("AI CLI 자동 감지 중...\n")
    for name, default in DEFAULT_PROFILES.items():
        cli = default["cli_command"]
        found = shutil.which(cli)
        if found:
            if name not in profiles:
                profiles[name] = default
            profiles[name]["detected"] = True
            traits_str = ", ".join(k for k, v in default["traits"].items() if v)
            print(f"  [+] {cli:10s} ({name:10s}) → {found}")
            if traits_str:
                print(f"      traits: {traits_str}")
        else:
            if name in profiles:
                profiles[name]["detected"] = False
            print(f"  [-] {cli:10s} ({name:10s}) → not found")

    data["profiles"] = profiles
    print()
    save_profile(data)


def cmd_list() -> None:
    """현재 프로파일 표시."""
    data = load_profile()
    profiles = data.get("profiles", {})

    if not profiles:
        print("프로파일이 비어있습니다. --detect로 자동 감지하세요.")
        return

    print(f"AI Profile v{data.get('version', '?')} ({data.get('updated_at', '?')})\n")
    print(f"{'Name':12s} {'CLI':10s} {'Detected':10s} {'Traits'}")
    print("-" * 60)
    for name, prof in profiles.items():
        cli = prof.get("cli_command", "?")
        detected = "Yes" if prof.get("detected") else "No"
        installed = shutil.which(cli) is not None
        status = f"{'Yes':10s}" if installed else f"{'No':10s}"
        traits = ", ".join(k for k, v in prof.get("traits", {}).items() if v) or "(none)"
        print(f"{name:12s} {cli:10s} {status} {traits}")


def cmd_add(name: str, cli=None, patterns=None) -> None:
    """AI 프로파일 추가. 기본 AI 또는 커스텀 AI 등록."""
    data = load_profile()

    if name in DEFAULT_PROFILES and not cli:
        # 기본 AI 추가
        data.setdefault("profiles", {})[name] = DEFAULT_PROFILES[name]
        found_cli = DEFAULT_PROFILES[name]["cli_command"]
        data["profiles"][name]["detected"] = shutil.which(found_cli) is not None
        print(f"Added: {name} (cli: {found_cli})")
    elif cli:
        # 커스텀 AI 등록
        detect = patterns.split(",") if patterns else [name]
        profile = {
            "display_name": name.capitalize(),
            "cli_command": cli,
            "detect_patterns": detect,
            "traits": {
                "no_init_required": False,
                "sandbox": False,
                "short_prompt": False,
                "two_phase_send": False,
            },
            "detected": shutil.which(cli) is not None,
        }
        data.setdefault("profiles", {})[name] = profile
        print(f"Added custom AI: {name} (cli: {cli}, patterns: {detect})")
        if not shutil.which(cli):
            print(f"  Warning: '{cli}' not found in PATH")
    else:
        print(f"Unknown AI: {name}")
        print(f"Available: {', '.join(DEFAULT_PROFILES.keys())}")
        print(f"Custom: --add {name} --cli <command> --patterns <p1,p2>")
        sys.exit(1)

    save_profile(data)


def cmd_remove(name: str) -> None:
    """AI 프로파일 제거."""
    data = load_profile()
    profiles = data.get("profiles", {})

    if name in profiles:
        del profiles[name]
        data["profiles"] = profiles
        print(f"Removed: {name}")
        save_profile(data)
    else:
        print(f"Not found: {name}")
        print(f"Current: {', '.join(profiles.keys())}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="cmux AI Profile Manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--detect", action="store_true", help="설치된 AI CLI 자동 감지")
    group.add_argument("--list", action="store_true", help="현재 프로파일 표시")
    group.add_argument("--add", metavar="NAME", help="AI 프로파일 추가")
    group.add_argument("--remove", metavar="NAME", help="AI 프로파일 제거")
    parser.add_argument("--cli", metavar="CMD", help="커스텀 AI의 CLI 명령 (--add와 함께)")
    parser.add_argument("--patterns", metavar="P1,P2", help="커스텀 AI의 감지 패턴 (--add와 함께)")

    args = parser.parse_args()

    if args.detect:
        cmd_detect()
    elif args.list:
        cmd_list()
    elif args.add:
        cmd_add(args.add, cli=args.cli, patterns=args.patterns)
    elif args.remove:
        cmd_remove(args.remove)


if __name__ == "__main__":
    main()
