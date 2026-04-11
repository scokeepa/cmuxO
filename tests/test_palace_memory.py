#!/usr/bin/env python3
"""tests/test_palace_memory.py — jarvis_palace_memory.py ChromaDB 단위 테스트."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
import jarvis_palace_memory as pm


def _setup(td):
    """Set palace path to temp dir for test isolation."""
    pm.PALACE_PATH = os.path.join(td, "palace")
    pm.IDENTITY_PATH = os.path.join(pm.PALACE_PATH, "identity.txt")
    pm.COLLECTION_NAME = "test_signals"


def _add_test_signals(td, n=5):
    """Add test signals directly to ChromaDB."""
    import chromadb
    os.makedirs(pm.PALACE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=pm.PALACE_PATH)
    try:
        col = client.get_collection(pm.COLLECTION_NAME)
    except Exception:
        col = client.create_collection(pm.COLLECTION_NAME)

    for i in range(n):
        sid = f"sig-test-{i}"
        doc = f"decomp {0.7+i*0.02} verify 0.5 orch 0.8"
        meta = {
            "wing": "cmux_mentor", "room": "verify",
            "signal_id": sid, "ts": f"2026-04-{i+1:02d}T12:00:00Z",
            "fit_score": 0.65 + i * 0.01, "harness_level": 3.5,
            "confidence": 0.7, "evidence_count": "5",
            "coaching_hint": "완료 조건을 명시하세요." if i == 0 else "",
            "calibration_note": "ok",
            "antipatterns": "verification_skip" if i % 2 == 0 else "",
        }
        col.add(ids=[sid], documents=[doc], metadatas=[meta])
    return col


def test_generate_l0_default():
    """L0 identity.txt 기본값 생성."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        text = pm.generate_l0()
        assert "CEO" in text or "컨트롤 타워" in text
        assert os.path.exists(pm.IDENTITY_PATH)
    print("  test_generate_l0_default: PASS")


def test_generate_l0_custom():
    """사용자 identity.txt 유지."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        os.makedirs(pm.PALACE_PATH, exist_ok=True)
        with open(pm.IDENTITY_PATH, "w") as f:
            f.write("Custom identity.")
        assert pm.generate_l0() == "Custom identity."
    print("  test_generate_l0_custom: PASS")


def test_generate_l1_from_signals():
    """ChromaDB signals → L1 요약."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_test_signals(td, 5)
        text = pm.generate_l1()
        assert "ESSENTIAL STORY" in text
        assert "Harness Level" in text
    print("  test_generate_l1_from_signals: PASS")


def test_l1_no_signals():
    """signals 없으면 '충분한 관찰이 없습니다'."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        text = pm.generate_l1()
        assert "충분한 관찰이 없습니다" in text
    print("  test_l1_no_signals: PASS")


def test_semantic_search():
    """ChromaDB 시맨틱 검색."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        import chromadb
        os.makedirs(pm.PALACE_PATH, exist_ok=True)
        client = chromadb.PersistentClient(path=pm.PALACE_PATH)
        col = client.create_collection(pm.COLLECTION_NAME)
        col.add(ids=["s1"], documents=["testing validation review check"], metadatas=[{"wing": "cmux_mentor", "room": "verify"}])
        col.add(ids=["s2"], documents=["task decomposition breakdown clear"], metadatas=[{"wing": "cmux_mentor", "room": "decomp"}])

        results = col.query(query_texts=["testing"], n_results=1)
        assert results["ids"][0][0] == "s1"
    print("  test_semantic_search: PASS")


def test_export_import_roundtrip():
    """export → import → drawer 수 일치."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_test_signals(td, 3)

        export_file = os.path.join(td, "export.json")
        pm.cmd_export(export_file)

        # New palace for import
        pm.PALACE_PATH = os.path.join(td, "palace2")
        pm.COLLECTION_NAME = "test_signals"
        pm.cmd_import(export_file)

        col = pm._get_collection()
        assert col.count() == 3, f"Expected 3, got {col.count()}"
    print("  test_export_import_roundtrip: PASS")


def test_import_dedup():
    """같은 export 2회 import → drawer 수 변화 없음."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_test_signals(td, 2)

        export_file = os.path.join(td, "export.json")
        pm.cmd_export(export_file)

        pm.cmd_import(export_file)  # all skipped
        col = pm._get_collection()
        assert col.count() == 2, f"Expected 2, got {col.count()}"
    print("  test_import_dedup: PASS")


def test_import_version_rejection():
    """미래 version → 거부."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        future = {"format": "cmux_mentor_export", "version": 99, "drawers": []}
        f_path = os.path.join(td, "future.json")
        with open(f_path, "w") as f:
            json.dump(future, f)
        rc = pm.cmd_import(f_path)
        assert rc == 1
    print("  test_import_version_rejection: PASS")


def test_backup():
    """backup 생성."""
    with tempfile.TemporaryDirectory() as td:
        _setup(td)
        _add_test_signals(td, 2)
        rc = pm.cmd_backup(max_backups=2)
        assert rc == 0
    print("  test_backup: PASS")


def main():
    test_generate_l0_default()
    test_generate_l0_custom()
    test_generate_l1_from_signals()
    test_l1_no_signals()
    test_semantic_search()
    test_export_import_roundtrip()
    test_import_dedup()
    test_import_version_rejection()
    test_backup()
    print("\nAll palace memory (ChromaDB) tests passed.")


if __name__ == "__main__":
    main()
