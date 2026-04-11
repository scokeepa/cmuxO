#!/usr/bin/env python3
"""tests/test_context_injection.py — cmux-main-context.sh mentor inject 로직 단위 테스트."""

import json
import os
import tempfile


def _simulate_mentor_inject(l0_path, l1_path, signals_path, hint_cache_path):
    """cmux-main-context.sh의 mentor inject Python 로직을 재현."""
    mentor_section = ''
    if os.path.exists(l1_path):
        try:
            l0 = open(l0_path).read().strip() if os.path.exists(l0_path) else ''
            l1 = open(l1_path).read().strip()
            combined = l0 + '\n' + l1
            if len(combined) <= 3600:
                mentor_section = '\n\n[MENTOR CONTEXT]\n' + combined
        except Exception:
            pass

    hint_section = ''
    if os.path.exists(signals_path):
        try:
            with open(signals_path) as sf:
                lines_list = sf.readlines()
            if lines_list:
                latest = json.loads(lines_list[-1].strip())
                hint = latest.get('coaching_hint', '')
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


def test_mentor_context_injected():
    """L0+L1 존재 시 [MENTOR CONTEXT] 포함."""
    with tempfile.TemporaryDirectory() as td:
        l0 = os.path.join(td, "L0.md")
        l1 = os.path.join(td, "L1.md")
        sig = os.path.join(td, "signals.jsonl")
        hc = os.path.join(td, "hint-cache.txt")

        with open(l0, "w") as f:
            f.write("## L0 — IDENTITY\ncmux CEO.")
        with open(l1, "w") as f:
            f.write("## L1 — ESSENTIAL STORY\nHarness Level: L3.5")

        result = _simulate_mentor_inject(l0, l1, sig, hc)
        assert "[MENTOR CONTEXT]" in result
        assert "IDENTITY" in result
        assert "ESSENTIAL STORY" in result
    print("  test_mentor_context_injected: PASS")


def test_no_mentor_without_files():
    """L0/L1 파일 없으면 mentor section 없음."""
    with tempfile.TemporaryDirectory() as td:
        l0 = os.path.join(td, "L0.md")
        l1 = os.path.join(td, "L1.md")
        sig = os.path.join(td, "signals.jsonl")
        hc = os.path.join(td, "hint-cache.txt")

        result = _simulate_mentor_inject(l0, l1, sig, hc)
        assert result == ""
    print("  test_no_mentor_without_files: PASS")


def test_hint_spam_prevention():
    """같은 hint 2회 연속 → 두 번째는 skip."""
    with tempfile.TemporaryDirectory() as td:
        l0 = os.path.join(td, "L0.md")
        l1 = os.path.join(td, "L1.md")
        sig = os.path.join(td, "signals.jsonl")
        hc = os.path.join(td, "hint-cache.txt")

        signal = {"coaching_hint": "완료 조건을 명시하세요."}
        with open(sig, "w") as f:
            f.write(json.dumps(signal) + "\n")

        # First call: hint delivered
        r1 = _simulate_mentor_inject(l0, l1, sig, hc)
        assert "[MENTOR HINT]" in r1

        # Second call: same hint → skip
        r2 = _simulate_mentor_inject(l0, l1, sig, hc)
        assert "[MENTOR HINT]" not in r2

        # Third call: new hint → delivered
        signal2 = {"coaching_hint": "새로운 힌트입니다."}
        with open(sig, "w") as f:
            f.write(json.dumps(signal2) + "\n")
        r3 = _simulate_mentor_inject(l0, l1, sig, hc)
        assert "[MENTOR HINT]" in r3
    print("  test_hint_spam_prevention: PASS")


def test_token_budget_exceeded():
    """3600 chars 초과 시 mentor context inject 안 함."""
    with tempfile.TemporaryDirectory() as td:
        l0 = os.path.join(td, "L0.md")
        l1 = os.path.join(td, "L1.md")
        sig = os.path.join(td, "signals.jsonl")
        hc = os.path.join(td, "hint-cache.txt")

        with open(l0, "w") as f:
            f.write("x" * 3000)
        with open(l1, "w") as f:
            f.write("y" * 1000)

        result = _simulate_mentor_inject(l0, l1, sig, hc)
        assert "[MENTOR CONTEXT]" not in result
    print("  test_token_budget_exceeded: PASS")


def test_empty_coaching_hint():
    """coaching_hint가 빈 문자열이면 hint section 없음."""
    with tempfile.TemporaryDirectory() as td:
        l0 = os.path.join(td, "L0.md")
        l1 = os.path.join(td, "L1.md")
        sig = os.path.join(td, "signals.jsonl")
        hc = os.path.join(td, "hint-cache.txt")

        signal = {"coaching_hint": ""}
        with open(sig, "w") as f:
            f.write(json.dumps(signal) + "\n")

        result = _simulate_mentor_inject(l0, l1, sig, hc)
        assert "[MENTOR HINT]" not in result
    print("  test_empty_coaching_hint: PASS")


def main():
    test_mentor_context_injected()
    test_no_mentor_without_files()
    test_hint_spam_prevention()
    test_token_budget_exceeded()
    test_empty_coaching_hint()
    print("\nAll context injection tests passed.")


if __name__ == "__main__":
    main()
