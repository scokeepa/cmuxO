#!/usr/bin/env python3
"""tests/test_context_injection.py — cmux-main-context.sh mentor inject 로직 단위 테스트.

실제 hook은 ChromaDB palace에서 identity.txt(L0)와
wing=cmux_mentor 메타데이터(L1)를 읽는다. 이 테스트는 해당 경로를 재현한다.
"""

import json
import os
import tempfile

import chromadb

from chromadb_test_utils import get_collection, get_or_create_collection

COLLECTION_NAME = "cmux_mentor_signals"


def _simulate_mentor_inject(palace_path, hint_cache_path):
    """cmux-main-context.sh의 mentor inject Python 로직을 재현 (ChromaDB 기반)."""
    mentor_section = ''
    hint_section = ''

    identity_file = os.path.join(palace_path, 'identity.txt')
    if not os.path.exists(palace_path):
        return ''

    l0 = ''
    if os.path.exists(identity_file):
        l0 = open(identity_file).read().strip()

    try:
        client = chromadb.PersistentClient(path=palace_path)
        try:
            col = get_collection(client, COLLECTION_NAME)
        except Exception:
            col = None

        if col and col.count() > 0:
            res = col.get(where={'wing': 'cmux_mentor'}, include=['metadatas'], limit=10)
            metas = sorted(res.get('metadatas', []), key=lambda m: m.get('ts', ''), reverse=True)
            if metas:
                latest = metas[0]
                l1_lines = ['[MENTOR L1] Harness Level: L' + str(latest.get('harness_level', '?'))]
                hint = latest.get('coaching_hint', '')
                if hint:
                    l1_lines.append('Hint: ' + hint)
                l1 = '\n'.join(l1_lines)
                combined = l0 + '\n' + l1 if l0 else l1
                if len(combined) <= 3600:
                    mentor_section = '\n\n[MENTOR CONTEXT]\n' + combined

                # Coaching hint spam 방지
                if hint:
                    prev_hint = ''
                    if os.path.exists(hint_cache_path):
                        prev_hint = open(hint_cache_path).read().strip()
                    if hint != prev_hint:
                        hint_section = '\n[MENTOR HINT] ' + hint
                        with open(hint_cache_path, 'w') as hf:
                            hf.write(hint)
    except Exception:
        pass

    return mentor_section + hint_section


def _seed_palace(palace_path, identity=None, signals=None):
    """테스트용 palace를 ChromaDB로 세팅."""
    os.makedirs(palace_path, exist_ok=True)
    if identity:
        with open(os.path.join(palace_path, 'identity.txt'), 'w') as f:
            f.write(identity)
    if signals:
        client = chromadb.PersistentClient(path=palace_path)
        col = get_or_create_collection(client, COLLECTION_NAME)
        for i, sig in enumerate(signals):
            meta = {"wing": "cmux_mentor", "ts": sig.get("ts", f"2026-04-01T00:0{i}:00Z")}
            meta["harness_level"] = sig.get("harness_level", 3)
            if sig.get("coaching_hint"):
                meta["coaching_hint"] = sig["coaching_hint"]
            col.add(
                ids=[f"sig-{i}"],
                documents=[f"signal {i}"],
                metadatas=[meta],
            )


def test_mentor_context_injected():
    """identity.txt + ChromaDB signal 존재 시 [MENTOR CONTEXT] 포함."""
    with tempfile.TemporaryDirectory() as td:
        palace = os.path.join(td, "palace")
        hc = os.path.join(td, "hint-cache.txt")

        _seed_palace(palace,
                     identity="## L0 — IDENTITY\ncmux CEO.",
                     signals=[{"harness_level": 3.5}])

        result = _simulate_mentor_inject(palace, hc)
        assert "[MENTOR CONTEXT]" in result
        assert "IDENTITY" in result
        assert "Harness Level: L3.5" in result
    print("  test_mentor_context_injected: PASS")


def test_no_mentor_without_palace():
    """palace 디렉토리 없으면 mentor section 없음."""
    with tempfile.TemporaryDirectory() as td:
        palace = os.path.join(td, "nonexistent")
        hc = os.path.join(td, "hint-cache.txt")

        result = _simulate_mentor_inject(palace, hc)
        assert result == ""
    print("  test_no_mentor_without_palace: PASS")


def test_hint_spam_prevention():
    """같은 hint 2회 연속 → 두 번째는 skip."""
    with tempfile.TemporaryDirectory() as td:
        palace = os.path.join(td, "palace")
        hc = os.path.join(td, "hint-cache.txt")

        _seed_palace(palace, signals=[{"coaching_hint": "완료 조건을 명시하세요.", "harness_level": 3}])

        # First call: hint delivered
        r1 = _simulate_mentor_inject(palace, hc)
        assert "[MENTOR HINT]" in r1

        # Second call: same hint → skip
        r2 = _simulate_mentor_inject(palace, hc)
        assert "[MENTOR HINT]" not in r2

        # Third call: new hint via new signal (higher ts to be sorted first)
        client = chromadb.PersistentClient(path=palace)
        col = get_collection(client, COLLECTION_NAME)
        col.add(
            ids=["sig-new"],
            documents=["new signal"],
            metadatas=[{"wing": "cmux_mentor", "ts": "2026-04-02T00:00:00Z",
                        "harness_level": 4, "coaching_hint": "새로운 힌트입니다."}],
        )
        r3 = _simulate_mentor_inject(palace, hc)
        assert "[MENTOR HINT]" in r3
    print("  test_hint_spam_prevention: PASS")


def test_token_budget_exceeded():
    """3600 chars 초과 시 mentor context inject 안 함."""
    with tempfile.TemporaryDirectory() as td:
        palace = os.path.join(td, "palace")
        hc = os.path.join(td, "hint-cache.txt")

        _seed_palace(palace,
                     identity="x" * 3600,
                     signals=[{"harness_level": 3}])

        result = _simulate_mentor_inject(palace, hc)
        assert "[MENTOR CONTEXT]" not in result
    print("  test_token_budget_exceeded: PASS")


def test_empty_coaching_hint():
    """coaching_hint가 빈 문자열이면 hint section 없음."""
    with tempfile.TemporaryDirectory() as td:
        palace = os.path.join(td, "palace")
        hc = os.path.join(td, "hint-cache.txt")

        _seed_palace(palace, signals=[{"coaching_hint": "", "harness_level": 2}])

        result = _simulate_mentor_inject(palace, hc)
        assert "[MENTOR HINT]" not in result
    print("  test_empty_coaching_hint: PASS")


def main():
    test_mentor_context_injected()
    test_no_mentor_without_palace()
    test_hint_spam_prevention()
    test_token_budget_exceeded()
    test_empty_coaching_hint()
    print("\nAll context injection tests passed.")


if __name__ == "__main__":
    main()
