#!/usr/bin/env python3
"""Phase 2.2.5 — claude-peers inter-session channel adapter.

Minimal HTTP client to the claude-peers broker on ``localhost:7899``. Designed
for **peer-registration-free system senders**: the broker accepts
``POST /send-message`` with ``{from_id, to_id, text}`` and no ``from_pid``,
tagging the sender as ``from_kind='system'`` (no registration needed).

Responsibilities (SRP):
    - HTTP send / health / list / resolve wrappers
    - W-9 extension guard: reject ``/new``, ``/clear``, compact commands
    - Append every send attempt to ``PEER_SENT_LOG_FILE`` for ledger ingestion
      in Phase 2.3.

Non-responsibilities:
    - Routing decisions (peer-first vs cmux-send fallback) — that's the caller
    - Peer registration / heartbeat loop — broker spawns from MCP server, not us
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cmux_paths import PEER_SENT_LOG_FILE

try:
    import ledger as _ledger
except ImportError:
    _ledger = None

DEFAULT_BROKER_URL = "http://127.0.0.1:7899"
DEFAULT_TIMEOUT = 3.0
DEFAULT_FROM_ID = "cmuxO"

# W-9 extension — payload patterns that must never cross the peers channel.
_FORBIDDEN_PAYLOAD_RE = re.compile(
    r"(?i)(^|\s)(/new|/clear|/compact|/quit|/exit)\b"
)


def broker_url() -> str:
    return os.environ.get("CLAUDE_PEERS_BROKER_URL", DEFAULT_BROKER_URL).rstrip("/")


def _post(path: str, payload: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
    req = urllib.request.Request(
        broker_url() + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError:
        return {"ok": False, "error": f"non-json response: {body[:200]}"}


def is_broker_alive(timeout: float = 0.5) -> bool:
    try:
        req = urllib.request.Request(broker_url() + "/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
        return False


def _is_forbidden(text: str) -> bool:
    if not text:
        return False
    return bool(_FORBIDDEN_PAYLOAD_RE.search(text))


def _append_log(entry: dict, path: Path | None = None) -> None:
    path = path or PEER_SENT_LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging failure must not break the send path


def _ledger_event_type(entry: dict) -> str:
    if entry.get("ok"):
        return "PEER_SENT"
    reason = entry.get("reason") or ""
    if reason.startswith("W-9"):
        return "PEER_PAYLOAD_DENIED"
    return "PEER_SEND_FAILED"


def _mirror_to_ledger(entry: dict) -> None:
    if _ledger is None:
        return
    try:
        _ledger.append(
            _ledger_event_type(entry),
            to=entry.get("to"),
            from_id=entry.get("from_id"),
            message_excerpt=entry.get("text_preview"),
            ok=bool(entry.get("ok")),
            reason=entry.get("reason"),
            error=entry.get("error"),
        )
    except Exception:  # noqa: BLE001 — ledger failure must not break send
        pass


def send(
    to: str,
    text: str,
    from_id: str = DEFAULT_FROM_ID,
    timeout: float = DEFAULT_TIMEOUT,
    log_path: Path | None = None,
) -> dict:
    """Send a message to a peer via the system-sender path.

    Returns a dict with ``ok`` boolean plus optional ``error``, ``skipped``,
    and ``reason`` fields. Never raises — callers should fall back to
    cmux send on ``ok=False``.
    """
    ts = int(time.time())
    log_entry = {
        "ts": ts, "to": to, "from_id": from_id,
        "text_preview": text[:120],
    }

    if _is_forbidden(text):
        result = {
            "ok": False,
            "skipped": True,
            "reason": "W-9: forbidden payload (/new|/clear|/compact) — peer send denied",
        }
        log_entry.update(result)
        _append_log(log_entry, log_path)
        _mirror_to_ledger(log_entry)
        return result

    if os.environ.get("CMUX_PEERS_ENABLED", "1") == "0":
        result = {"ok": False, "skipped": True, "reason": "CMUX_PEERS_ENABLED=0"}
        log_entry.update(result)
        _append_log(log_entry, log_path)
        _mirror_to_ledger(log_entry)
        return result

    if not is_broker_alive():
        result = {"ok": False, "skipped": True, "reason": "broker_unreachable"}
        log_entry.update(result)
        _append_log(log_entry, log_path)
        _mirror_to_ledger(log_entry)
        return result

    try:
        resp = _post(
            "/send-message",
            {"from_id": from_id, "to_id": to, "text": text},
            timeout=timeout,
        )
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        result = {"ok": False, "error": f"http_error: {exc}"}
        log_entry.update(result)
        _append_log(log_entry, log_path)
        _mirror_to_ledger(log_entry)
        return result

    result = {
        "ok": bool(resp.get("ok")),
        "broker": resp,
    }
    if not result["ok"]:
        result["error"] = resp.get("error", "unknown broker error")
    log_entry.update({"ok": result["ok"], "error": result.get("error")})
    _append_log(log_entry, log_path)
    _mirror_to_ledger(log_entry)
    return result


def list_peers(scope: str = "machine", cwd: str | None = None,
               git_root: str | None = None) -> list[dict]:
    if not is_broker_alive():
        return []
    try:
        resp = _post(
            "/list-peers",
            {"scope": scope, "cwd": cwd or os.getcwd(),
             "git_root": git_root or ""},
        )
    except (urllib.error.URLError, OSError, TimeoutError):
        return []
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict) and "peers" in resp:
        return resp.get("peers") or []
    return []


def resolve(name: str, scope: str = "machine") -> str | None:
    """Return the current peer_id for ``name`` or None.

    Matches exact logical_name or ``<name>@...`` prefix form.
    """
    if not name:
        return None
    peers = list_peers(scope=scope)
    for p in peers:
        if not isinstance(p, dict):
            continue
        if p.get("id") == name or p.get("logical_name") == name:
            return p.get("id")
        lname = p.get("logical_name") or ""
        if lname.startswith(name + "@"):
            return p.get("id")
    return None


def _cli() -> int:
    parser = argparse.ArgumentParser(description="cmux-orchestrator peers adapter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_send = sub.add_parser("send", help="send a message to a peer")
    p_send.add_argument("to", help="peer_id or logical_name")
    p_send.add_argument("text", help="message text")
    p_send.add_argument("--from", dest="from_id", default=DEFAULT_FROM_ID)
    p_send.add_argument("--resolve", action="store_true",
                        help="treat TO as logical_name and resolve first")

    sub.add_parser("health", help="check broker liveness")
    sub.add_parser("list", help="list peers (scope=machine)")

    p_resolve = sub.add_parser("resolve", help="resolve logical_name → peer_id")
    p_resolve.add_argument("name")

    args = parser.parse_args()

    if args.cmd == "health":
        alive = is_broker_alive()
        print(json.dumps({"alive": alive, "url": broker_url()}))
        return 0 if alive else 1

    if args.cmd == "list":
        print(json.dumps(list_peers(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "resolve":
        pid = resolve(args.name)
        print(json.dumps({"name": args.name, "id": pid}))
        return 0 if pid else 1

    if args.cmd == "send":
        target = args.to
        if args.resolve:
            resolved = resolve(args.to)
            if not resolved:
                print(json.dumps({"ok": False, "error": f"cannot resolve {args.to!r}"}),
                      file=sys.stderr)
                return 2
            target = resolved
        result = send(target, args.text, from_id=args.from_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
