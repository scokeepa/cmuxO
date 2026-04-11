#!/usr/bin/env python3
"""tests/test_redaction.py — mentor_redactor.py 단위 테스트."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cmux-jarvis", "scripts"))
from mentor_redactor import redact


def test_redact_api_key():
    """sk-/pk-/rk-/ak- 패턴 → [REDACTED_API_KEY]."""
    text = "my key is sk-abc123def456ghi789jkl012mno"
    result = redact(text)
    assert "[REDACTED_API_KEY]" in result
    assert "sk-abc" not in result
    print("  test_redact_api_key: PASS")


def test_redact_password():
    """password=/passwd:/pwd= → [REDACTED_PASSWORD]."""
    assert "[REDACTED_PASSWORD]" in redact("password=supersecret123")
    assert "[REDACTED_PASSWORD]" in redact("passwd: mysecret")
    assert "[REDACTED_PASSWORD]" in redact("PWD=abc123")
    print("  test_redact_password: PASS")


def test_redact_bearer():
    """Bearer token → [REDACTED_TOKEN]."""
    result = redact("Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
    assert "[REDACTED_TOKEN]" in result
    assert "eyJhbG" not in result
    print("  test_redact_bearer: PASS")


def test_redact_authorization():
    """Authorization header → [REDACTED_TOKEN]."""
    result = redact("Authorization: Basic dXNlcjpwYXNz")
    assert "[REDACTED_TOKEN]" in result
    print("  test_redact_authorization: PASS")


def test_redact_secret():
    """token=/secret=/api_key= → [REDACTED_SECRET]."""
    assert "[REDACTED_SECRET]" in redact("api_key=sk_live_abc123def456ghi789")
    assert "[REDACTED_SECRET]" in redact("secret=mysupersecret")
    assert "[REDACTED_SECRET]" in redact("TOKEN=abc123def456")
    print("  test_redact_secret: PASS")


def test_preserve_file_path():
    """파일 경로는 변경하지 않음."""
    paths = [
        "/Users/csm/Downloads/cmux_orchestration/file.py",
        "/tmp/cmux-surface-map.json",
        "~/.claude/cmux-jarvis/mentor/signals.jsonl",
        "cmux-orchestrator/scripts/validate-config.sh",
    ]
    for path in paths:
        assert redact(path) == path, f"Path was modified: {path} → {redact(path)}"
    print("  test_preserve_file_path: PASS")


def test_mixed_content():
    """민감 정보와 일반 텍스트가 섞인 경우."""
    text = "파일 /tmp/test.py에서 password=secret123 으로 접속. Bearer eyJtoken 사용."
    result = redact(text)
    assert "/tmp/test.py" in result
    assert "[REDACTED_PASSWORD]" in result
    assert "[REDACTED_TOKEN]" in result
    assert "secret123" not in result
    print("  test_mixed_content: PASS")


def test_no_false_positive():
    """일반 텍스트에 false positive 없음."""
    safe_texts = [
        "이 함수는 password를 검증합니다.",
        "sk 접두사로 시작하지만 짧은 문자열",
        "Bearer 만 있고 토큰 없음",
    ]
    for text in safe_texts:
        result = redact(text)
        assert "[REDACTED" not in result, f"False positive: {text} → {result}"
    print("  test_no_false_positive: PASS")


def main():
    test_redact_api_key()
    test_redact_password()
    test_redact_bearer()
    test_redact_authorization()
    test_redact_secret()
    test_preserve_file_path()
    test_mixed_content()
    test_no_false_positive()
    print("\nAll redaction tests passed.")


if __name__ == "__main__":
    main()
