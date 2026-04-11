#!/usr/bin/env python3
"""mentor_redactor.py — signal/drawer 저장 전 민감 정보 자동 redaction.

SSOT: docs/jarvis/architecture/mentor-privacy-policy.md

Usage:
    python3 mentor_redactor.py --text "password=secret123 and sk-abc..."
    echo "Bearer eyJ..." | python3 mentor_redactor.py --stdin
"""

import argparse
import re
import sys

REDACTION_PATTERNS = [
    (re.compile(r'(?:sk|pk|rk|ak)-[A-Za-z0-9_-]{20,}'), '[REDACTED_API_KEY]'),
    (re.compile(r'(?:password|passwd|pwd)\s*[=:]\s*\S+', re.IGNORECASE), '[REDACTED_PASSWORD]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9._-]+'), '[REDACTED_TOKEN]'),
    (re.compile(r'Authorization:\s*\S+', re.IGNORECASE), '[REDACTED_TOKEN]'),
    (re.compile(r'(?:token|secret|api_key)\s*[=:]\s*\S+', re.IGNORECASE), '[REDACTED_SECRET]'),
]


def redact(text):
    """Apply all redaction patterns to text. File paths are preserved."""
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Mentor Redactor")
    parser.add_argument("--text", help="Text to redact")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    args = parser.parse_args()

    if args.text:
        print(redact(args.text))
    elif args.stdin:
        print(redact(sys.stdin.read()))
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
