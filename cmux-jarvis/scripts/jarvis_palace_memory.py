#!/usr/bin/env python3
"""jarvis_palace_memory.py — mempalace ChromaDB 기반 Palace Memory.

SSOT: docs/02-jarvis/palace-memory.md
Token budget: L0+L1 합산 600-900 token (mentor-lane.md)

Usage:
    python3 jarvis_palace_memory.py generate-context
    python3 jarvis_palace_memory.py status
    python3 jarvis_palace_memory.py search "query" [--wing W] [--room R]
    python3 jarvis_palace_memory.py export --output /path/to/export.json
    python3 jarvis_palace_memory.py import --input /path/to/export.json
    python3 jarvis_palace_memory.py backup [--max-backups 5]
    python3 jarvis_palace_memory.py migrate  # signals.jsonl → ChromaDB 이관
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb

PALACE_PATH = os.path.expanduser("~/.cmux-jarvis-palace")
COLLECTION_NAME = "cmux_mentor_signals"
IDENTITY_PATH = os.path.join(PALACE_PATH, "identity.txt")
LEGACY_SIGNALS = Path.home() / ".claude" / "cmux-jarvis" / "mentor" / "signals.jsonl"

MAX_TOTAL_TOKENS = 900
EXPORT_FORMAT = "cmux_mentor_export"
EXPORT_VERSION = 2  # v2: ChromaDB-based

L0_DEFAULT = """cmux 오케스트레이션 시스템의 CEO 사용자.
Boss(Main), Watcher, JARVIS로 구성된 컨트롤 타워를 운영.
부서별 팀장-팀원 구조로 멀티 AI 작업을 조율."""

AXES = ("decomp", "verify", "orch", "fail", "ctx", "meta")


def _get_collection():
    """Get or create the cmux mentor palace collection."""
    os.makedirs(PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=PALACE_PATH)
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return client.create_collection(COLLECTION_NAME)


def _estimate_tokens(text):
    return len(text) // 4


# ── L0 / L1 ────────────────────────────────────────────────────────


def generate_l0():
    """Generate L0 identity context from identity.txt."""
    if os.path.exists(IDENTITY_PATH):
        with open(IDENTITY_PATH) as f:
            return f.read().strip()
    os.makedirs(PALACE_PATH, exist_ok=True)
    with open(IDENTITY_PATH, "w") as f:
        f.write(L0_DEFAULT)
    return L0_DEFAULT


def generate_l1():
    """Generate L1 essential story from recent palace drawers."""
    col = _get_collection()
    try:
        results = col.get(
            where={"wing": "cmux_mentor"},
            include=["metadatas"],
            limit=500,
        )
    except Exception:
        return "## L1 — ESSENTIAL STORY\n아직 충분한 관찰이 없습니다."

    metas = results.get("metadatas", [])
    if not metas:
        return "## L1 — ESSENTIAL STORY\n아직 충분한 관찰이 없습니다."

    # Sort by timestamp, get latest
    sorted_metas = sorted(metas, key=lambda m: m.get("ts", ""), reverse=True)
    latest = sorted_metas[0]

    # Aggregate scores from recent signals
    recent = sorted_metas[:10]
    avg_scores = {}
    for axis in AXES:
        vals = [float(m.get(axis, m.get(f"score_{axis}", 0))) for m in recent if m.get(axis) or m.get(f"score_{axis}")]
        avg_scores[axis] = round(sum(vals) / len(vals), 2) if vals else 0.0

    sorted_axes = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
    strong = [f"{a.upper()} ({v:.2f})" for a, v in sorted_axes[:2]]
    weak = [f"{a.upper()} ({v:.2f})" for a, v in sorted_axes[-2:]]

    lines = [
        "## L1 — ESSENTIAL STORY",
        "최근 하네스 상태:",
        f"- Harness Level: L{latest.get('harness_level', '?')}",
        f"- 강한 축: {', '.join(strong)}",
        f"- 약한 축: {', '.join(weak)}",
    ]

    # Antipatterns from recent
    patterns = []
    for m in recent[:5]:
        ap = m.get("antipatterns", "")
        if ap:
            patterns.extend(ap.split(",") if isinstance(ap, str) else ap)
    if patterns:
        unique = list(dict.fromkeys(p.strip() for p in patterns if p.strip()))[:3]
        lines.append(f"- 최근 안티패턴: {', '.join(unique)}")

    hint = latest.get("coaching_hint", "")
    if hint:
        lines.append(f'- 코칭 힌트: "{hint}"')

    if latest.get("calibration_note") == "insufficient_evidence":
        lines.append("- 주의: 표본 부족으로 신뢰도가 낮습니다.")

    text = "\n".join(lines)
    return text[:3200]


def cmd_generate_context():
    """Generate L0 + L1 and print."""
    l0 = generate_l0()
    l1 = generate_l1()

    l0_tokens = _estimate_tokens(l0)
    l1_tokens = _estimate_tokens(l1)
    total = l0_tokens + l1_tokens

    if total > MAX_TOTAL_TOKENS:
        budget = MAX_TOTAL_TOKENS - l0_tokens
        l1 = l1[:budget * 4]
        l1_tokens = _estimate_tokens(l1)
        total = l0_tokens + l1_tokens

    print(f"L0 ({l0_tokens} tokens):\n{l0}\n")
    print(f"L1 ({l1_tokens} tokens):\n{l1}\n")
    print(f"Total: {total}/{MAX_TOTAL_TOKENS} tokens")
    return 0


# ── Search ──────────────────────────────────────────────────────────


def cmd_search(query, wing=None, room=None, n_results=5):
    """Semantic search across palace drawers."""
    col = _get_collection()
    where = {}
    if wing and room:
        where = {"$and": [{"wing": wing}, {"room": room}]}
    elif wing:
        where = {"wing": wing}
    elif room:
        where = {"room": room}

    kwargs = {"query_texts": [query], "n_results": n_results, "include": ["documents", "metadatas", "distances"]}
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)

    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    if not ids:
        print("No results found.")
        return 0

    for i, (did, doc, meta, dist) in enumerate(zip(ids, docs, metas, dists)):
        sim = round(1 - dist, 3)
        wing_r = meta.get("wing", "?")
        room_r = meta.get("room", "?")
        snippet = (doc[:120] + "...") if len(doc) > 120 else doc
        print(f"[{i+1}] {wing_r}/{room_r} (sim={sim}) — {snippet}")
        print(f"     id={did} ts={meta.get('ts', '?')}")

    return 0


# ── Status ──────────────────────────────────────────────────────────


def cmd_status():
    """Show palace status."""
    col = _get_collection()
    total = col.count()

    wings = {}
    if total > 0:
        all_data = col.get(include=["metadatas"], limit=min(total, 1000))
        for m in all_data.get("metadatas", []):
            w = m.get("wing", "unknown")
            wings[w] = wings.get(w, 0) + 1

    status = {
        "palace_path": PALACE_PATH,
        "collection": COLLECTION_NAME,
        "total_drawers": total,
        "wings": wings,
        "identity_exists": os.path.exists(IDENTITY_PATH),
        "legacy_signals_exists": LEGACY_SIGNALS.exists(),
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


# ── Export / Import / Backup (PR #499 pattern) ──────────────────────


def cmd_export(output_file):
    """Export palace data to JSON."""
    col = _get_collection()
    total = col.count()

    drawers = []
    offset = 0
    while offset < total:
        batch = col.get(include=["documents", "metadatas"], limit=500, offset=offset)
        ids = batch.get("ids", [])
        if not ids:
            break
        for did, doc, meta in zip(ids, batch["documents"], batch["metadatas"]):
            drawers.append({"id": did, "document": doc, "metadata": meta})
        offset += len(ids)

    export_data = {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "palace_path": PALACE_PATH,
        "drawers": drawers,
    }

    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(drawers)} drawers → {out}")
    print("Note: embeddings not included. ChromaDB auto re-embeds on import.")
    return 0


def cmd_import(input_file, skip_existing=True):
    """Import palace data from JSON."""
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("format") != EXPORT_FORMAT:
        print(f"Error: unknown format '{data.get('format')}'")
        return 1
    if data.get("version", 0) > EXPORT_VERSION:
        print(f"Error: version {data.get('version')} > supported ({EXPORT_VERSION})")
        return 1

    col = _get_collection()
    existing_ids = set()
    if skip_existing:
        offset = 0
        while True:
            batch = col.get(limit=500, offset=offset)
            batch_ids = batch.get("ids", [])
            if not batch_ids:
                break
            existing_ids.update(batch_ids)
            offset += len(batch_ids)

    imported, skipped = 0, 0
    batch_ids, batch_docs, batch_metas = [], [], []

    for drawer in data.get("drawers", []):
        did = drawer["id"]
        if skip_existing and did in existing_ids:
            skipped += 1
            continue
        batch_ids.append(did)
        batch_docs.append(drawer["document"])
        batch_metas.append(drawer["metadata"])

        if len(batch_ids) >= 100:
            col.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            imported += len(batch_ids)
            batch_ids, batch_docs, batch_metas = [], [], []

    if batch_ids:
        col.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
        imported += len(batch_ids)

    print(f"Imported {imported} drawers ({skipped} skipped)")
    return 0


def cmd_backup(max_backups=5):
    """Create timestamped backup of palace directory."""
    if not os.path.exists(PALACE_PATH):
        print("No palace to backup.")
        return 0

    parent = Path(PALACE_PATH).parent
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = parent / f"cmux-jarvis-palace-backup-{ts}"

    shutil.copytree(PALACE_PATH, backup_dir)

    # Integrity: check SQLite if present
    import sqlite3
    for db_file in backup_dir.rglob("*.sqlite3"):
        try:
            conn = sqlite3.connect(str(db_file))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if result[0] != "ok":
                print(f"Warning: integrity issue in {db_file.name}")
        except Exception as e:
            print(f"Warning: {db_file.name}: {e}")

    # Retention
    if max_backups > 0:
        all_backups = sorted(parent.glob("cmux-jarvis-palace-backup-*"))
        while len(all_backups) > max_backups:
            oldest = all_backups.pop(0)
            shutil.rmtree(oldest)

    size = sum(f.stat().st_size for f in backup_dir.rglob("*") if f.is_file())
    print(f"Backup OK: {backup_dir} ({size:,} bytes)")
    return 0


# ── Migration (signals.jsonl → ChromaDB) ───────────────────────────


def cmd_migrate():
    """Migrate legacy signals.jsonl to ChromaDB palace."""
    if not LEGACY_SIGNALS.exists():
        print("No legacy signals.jsonl found.")
        return 0

    col = _get_collection()
    existing_ids = set(col.get(limit=10000).get("ids", []))

    migrated, skipped = 0, 0
    with open(LEGACY_SIGNALS) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                signal = json.loads(line)
            except json.JSONDecodeError:
                continue

            sid = signal.get("signal_id", f"legacy-{migrated}")
            if sid in existing_ids:
                skipped += 1
                continue

            scores = signal.get("scores", {})
            weakest = min(AXES, key=lambda a: scores.get(a, 1))
            doc = json.dumps(scores) + " " + " ".join(signal.get("antipatterns", []))
            meta = {
                "wing": "cmux_mentor",
                "room": weakest,
                "signal_id": sid,
                "ts": signal.get("ts", ""),
                "fit_score": float(signal.get("fit_score", 0)),
                "harness_level": float(signal.get("harness_level", 0)),
                "confidence": float(signal.get("confidence", 0)),
                "evidence_count": str(signal.get("evidence_count", 0)),
                "coaching_hint": signal.get("coaching_hint", ""),
                "calibration_note": signal.get("calibration_note", ""),
                "antipatterns": ",".join(signal.get("antipatterns", [])),
            }

            col.add(ids=[sid], documents=[doc], metadatas=[meta])
            existing_ids.add(sid)
            migrated += 1

    print(f"Migrated {migrated} signals ({skipped} skipped)")
    if migrated > 0:
        print(f"Legacy file kept at: {LEGACY_SIGNALS}")
        print("Delete manually after verifying: rm {LEGACY_SIGNALS}")
    return 0


# ── Main ────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="JARVIS Palace Memory (ChromaDB)")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("generate-context", help="Generate L0 + L1 context")
    sub.add_parser("status", help="Show palace status")

    p_search = sub.add_parser("search", help="Semantic search")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--wing", default=None)
    p_search.add_argument("--room", default=None)
    p_search.add_argument("--n", type=int, default=5)

    p_export = sub.add_parser("export", help="Export palace to JSON")
    p_export.add_argument("--output", required=True)

    p_import = sub.add_parser("import", help="Import palace from JSON")
    p_import.add_argument("--input", required=True)
    p_import.add_argument("--no-skip-existing", action="store_true")

    p_backup = sub.add_parser("backup", help="Create backup")
    p_backup.add_argument("--max-backups", type=int, default=5)

    sub.add_parser("migrate", help="Migrate legacy signals.jsonl → ChromaDB")

    args = parser.parse_args()

    if args.cmd == "generate-context":
        return cmd_generate_context()
    elif args.cmd == "status":
        return cmd_status()
    elif args.cmd == "search":
        return cmd_search(args.query, args.wing, args.room, args.n)
    elif args.cmd == "export":
        return cmd_export(args.output)
    elif args.cmd == "import":
        return cmd_import(args.input, skip_existing=not args.no_skip_existing)
    elif args.cmd == "backup":
        return cmd_backup(args.max_backups)
    elif args.cmd == "migrate":
        return cmd_migrate()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
