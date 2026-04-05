#!/usr/bin/env python3
"""eagle_analyzer.py — Surface screen text classifier for cmux eagle watcher.

Reads screen text from stdin (or --test for built-in test cases) and outputs
a JSON classification of the surface state.

Usage:
    echo "some screen text" | python3 eagle_analyzer.py
    python3 eagle_analyzer.py --test
"""

import json
import re
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

WORKING_PATTERNS = [
    # Braille spinners (exact char match)
    *[re.escape(c) for c in SPINNERS],
    # Progress block chars
    r"[■⬝█░▓]{2,}",
    # Keyword phrases (case-sensitive common forms)
    r"Working[.\s]",
    r"Thinking[.\s]",
    r"Generating[.\s]",
    r"Inferring[.\s]",
    r"Baking[.\s]",
    r"Searching[.\s]",
    r"Reading[.\s]",
    r"Writing[.\s]",
    r"Editing[.\s]",
    r"interrupt to stop",
    r"Working\.\.\.",
    r"Thinking\.\.\.",
    # Claude Code running indicators
    r"ESC to interrupt",
    r"esc to interrupt",
]

DONE_PATTERNS = [
    r"DONE:",
    r"done:",
    r"완료",
    r"finished",
    r"completed",
    r"TASK COMPLETE",
    r"작업 완료",
    r"구현 완료",
    r"생성 완료",
    r"수정 완료",
]

# Patterns that by themselves indicate DONE (strong signal)
DONE_STRONG_PATTERNS = [
    r"DONE:",
    r"TASK COMPLETE",
    r"완료$",
]

ERROR_PATTERNS = [
    # Generic error words
    r"error",
    r"Error",
    r"ERROR",
    r"에러",
    r"failed",
    r"Failed",
    r"FAILED",
    r"실패",
    r"오류",
    # HTTP error codes
    r"\b429\b",
    r"\b529\b",
    r"\b502\b",
    r"\b503\b",
    r"\b401\b",
    r"\b403\b",
    r"\b1008\b",
    # Timeout/resource
    r"timeout",
    r"TIMEOUT",
    r"\bOOM\b",
    r"exceeded",
    r"insufficient",
    r"not found",
    r"초과",
    r"불가",
    # Service issues
    r"overloaded",
    r"rate limit",
    r"rate_limit",
    r"RateLimitError",
    r"context limit",
    r"too long",
    r"model not exist",
    r"crashed",
    r"SIGKILL",
    r"OOMKilled",
    r"ECONNREFUSED",
    r"authentication.failed",
    r"invalid.api.key",
    r"\[Errno ",
    r"API_TIMEOUT",
    r"Settings Error",
    r"502 Bad Gateway",
    r"503 Service",
    r"insufficient.balance",
    r"QuotaExceeded",
    r"quota.exceeded",
    r"MaxTokens.*exceed",
    r"token.limit",
]

# Error subtype classification patterns
ERROR_SUBTYPE_PATTERNS = {
    "timeout": [r"timeout", r"TIMEOUT", r"API_TIMEOUT", r"timed? out"],
    "rate_limit": [r"429", r"rate.?limit", r"RateLimitError", r"quota.exceeded", r"QuotaExceeded"],
    "context_exceeded": [r"context.limit", r"too long", r"MaxTokens.*exceed", r"token.limit", r"Context.*exceed"],
    "auth_failed": [r"401", r"403", r"authentication.failed", r"invalid.api.key", r"unauthorized"],
    "server_error": [r"502", r"503", r"529", r"1008", r"overloaded", r"crashed", r"SIGKILL", r"OOMKilled", r"ECONNREFUSED"],
    "resource": [r"\bOOM\b", r"OOMKilled", r"insufficient.balance", r"exceeded"],
}

IDLE_PATTERNS = [
    # Prompt indicators at line start
    r"^❯\s",
    r"^› ",
    r"^> ",
    r"^\$ ",
    # Claude Code specific
    r"Type your message",
    r"bypass permissions",
    # AI model identifiers at bottom
    r"🤖",
    r"claude-opus",
    r"claude-sonnet",
    r"claude-haiku",
    r"gemini.*pro",
    r"gpt-[0-9]",
    r"ccm.*>",
    r"minimax.*ready",
    r"MCP /status",
    r"Sisyphus",
    # Completion markers that imply return to idle
    r"Brewed",
    r"Cooked",
    r"Find and fix",
    # Gemini/OpenCode
    r"^\s*\*\s",
    r"YOLO",
    r"\([0-9]+/[0-9]+\)",
    r"- [0-9]+ skills",
    r"\bsandbox\b",
    r"Ask anything",
    r"tab agents",
    r"ctrl\+p commands",
]

WAITING_PATTERNS = [
    r"Would you like",
    r"Would you prefer",
    r"y/n",
    r"Y/n",
    r"\[Y/n\]",
    r"\[y/N\]",
    r"confirm",
    r"approve",
    r"계속할까",
    r"진행할까",
    r"승인",
    r"Do you want to",
    r"Shall I",
    r"proceed\?",
    r"continue\?",
    r"install.*\?",
    r"create.*\?",
    r"overwrite.*\?",
    r"replace.*\?",
]

NOT_STARTED_PATTERNS = [
    r"Claude Code v[0-9]",
    r"^$",
]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def _match_any(text: str, patterns: list, flags: int = 0) -> list[str]:
    """Return list of matched patterns."""
    matched = []
    for pat in patterns:
        try:
            if re.search(pat, text, flags | re.MULTILINE):
                matched.append(pat)
        except re.error:
            pass
    return matched


def _extract_done_summary(text: str) -> Optional[str]:
    """Extract text after DONE: keyword."""
    match = re.search(r"DONE:\s*(.+?)(?:\n|$)", text)
    if match:
        return match.group(1).strip()[:200]
    match = re.search(r"완료[:\s]*(.+?)(?:\n|$)", text)
    if match:
        candidate = match.group(1).strip()[:200]
        if candidate:
            return candidate
    return None


def _extract_error_message(text: str) -> Optional[str]:
    """Extract the most relevant error line."""
    lines = text.splitlines()
    for line in reversed(lines):
        if re.search(r"error|Error|ERROR|failed|Failed|에러|오류|실패", line):
            cleaned = line.strip()[:200]
            if cleaned:
                return cleaned
    return None


def _extract_question_text(text: str) -> Optional[str]:
    """Extract question/confirmation text."""
    for pat in WAITING_PATTERNS:
        match = re.search(pat + r".{0,100}", text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(0).strip()[:200]
    return None


def _classify_error_subtype(text: str) -> Optional[str]:
    """Determine specific error subtype."""
    for subtype, patterns in ERROR_SUBTYPE_PATTERNS.items():
        for pat in patterns:
            try:
                if re.search(pat, text, re.IGNORECASE):
                    return subtype
            except re.error:
                pass
    return "generic"


def _is_not_started(text: str) -> bool:
    """Detect blank or banner-only screen."""
    stripped = text.strip()
    if not stripped:
        return True
    # Only Claude Code version banner with no conversation
    if re.match(r"^Claude Code v[0-9]", stripped) and len(stripped.splitlines()) <= 5:
        return True
    return False


def classify(text: str) -> dict:
    """Classify screen text into a status dict."""
    raw_indicators: list[str] = []
    details: Optional[str] = None
    error_subtype: Optional[str] = None
    confidence: float = 0.5

    # Priority 0: NOT_STARTED
    if _is_not_started(text):
        return {
            "status": "NOT_STARTED",
            "confidence": 0.9,
            "details": None,
            "error_subtype": None,
            "raw_indicators": ["empty_or_banner"],
        }

    # Priority 1: ERROR (highest — catches broken states)
    error_matches = _match_any(text, ERROR_PATTERNS, re.IGNORECASE)
    if error_matches:
        error_subtype = _classify_error_subtype(text)
        details = _extract_error_message(text)
        raw_indicators = error_matches[:5]
        confidence = min(0.6 + 0.05 * len(error_matches), 0.99)
        return {
            "status": "ERROR",
            "confidence": round(confidence, 2),
            "details": details,
            "error_subtype": error_subtype,
            "raw_indicators": raw_indicators,
        }

    # Priority 2: WAITING (user input needed)
    waiting_matches = _match_any(text, WAITING_PATTERNS, re.IGNORECASE)
    if waiting_matches:
        details = _extract_question_text(text)
        raw_indicators = waiting_matches[:5]
        confidence = min(0.7 + 0.05 * len(waiting_matches), 0.99)
        return {
            "status": "WAITING",
            "confidence": round(confidence, 2),
            "details": details,
            "error_subtype": None,
            "raw_indicators": raw_indicators,
        }

    # Priority 3: WORKING (spinner or active keyword)
    working_matches = _match_any(text, WORKING_PATTERNS)
    if working_matches:
        raw_indicators = working_matches[:5]
        confidence = min(0.75 + 0.04 * len(working_matches), 0.99)
        return {
            "status": "WORKING",
            "confidence": round(confidence, 2),
            "details": None,
            "error_subtype": None,
            "raw_indicators": raw_indicators,
        }

    # Priority 4: DONE (explicit completion keywords)
    done_matches = _match_any(text, DONE_PATTERNS)
    done_strong = _match_any(text, DONE_STRONG_PATTERNS)
    # DONE wins over IDLE if strong marker present, or multiple weaker markers
    if done_strong or (len(done_matches) >= 2):
        details = _extract_done_summary(text)
        raw_indicators = done_matches[:5]
        confidence = 0.95 if done_strong else 0.80
        return {
            "status": "DONE",
            "confidence": round(confidence, 2),
            "details": details,
            "error_subtype": None,
            "raw_indicators": raw_indicators,
        }

    # Priority 5: IDLE (prompt visible, AI waiting)
    idle_matches = _match_any(text, IDLE_PATTERNS, re.IGNORECASE | re.MULTILINE)
    if idle_matches:
        raw_indicators = idle_matches[:5]
        # DONE keyword present alongside IDLE prompt -> DONE wins at lower confidence
        if done_matches:
            details = _extract_done_summary(text)
            return {
                "status": "DONE",
                "confidence": 0.75,
                "details": details,
                "error_subtype": None,
                "raw_indicators": done_matches[:3] + idle_matches[:2],
            }
        confidence = min(0.65 + 0.04 * len(idle_matches), 0.95)
        return {
            "status": "IDLE",
            "confidence": round(confidence, 2),
            "details": None,
            "error_subtype": None,
            "raw_indicators": raw_indicators,
        }

    # Priority 6: NOT_STARTED (fallback for sparse content)
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) <= 2:
        return {
            "status": "NOT_STARTED",
            "confidence": 0.6,
            "details": None,
            "error_subtype": None,
            "raw_indicators": ["sparse_content"],
        }

    # Fallback: UNKNOWN
    return {
        "status": "UNKNOWN",
        "confidence": 0.3,
        "details": None,
        "error_subtype": None,
        "raw_indicators": [],
    }


# ---------------------------------------------------------------------------
# Built-in test cases
# ---------------------------------------------------------------------------

TEST_CASES = [
    # 0: WORKING — spinner
    {
        "name": "WORKING spinner",
        "input": "⠋ Thinking...\nProcessing your request\nESC to interrupt",
        "expected_status": "WORKING",
    },
    # 1: WORKING — keyword
    {
        "name": "WORKING keyword",
        "input": "Working on it...\nReading files\ninterrupt to stop",
        "expected_status": "WORKING",
    },
    # 2: DONE — explicit keyword
    {
        "name": "DONE explicit",
        "input": "All done!\nDONE: 리서치 완료 + 파일 3개 생성\n❯ ",
        "expected_status": "DONE",
    },
    # 3: DONE — Korean completion
    {
        "name": "DONE Korean",
        "input": "작업 완료\n구현이 성공적으로 완료되었습니다.\n❯ ",
        "expected_status": "DONE",
    },
    # 4: ERROR — rate limit
    {
        "name": "ERROR rate limit",
        "input": "RateLimitError: 429 Too Many Requests\nRetrying...",
        "expected_status": "ERROR",
    },
    # 5: ERROR — server overloaded
    {
        "name": "ERROR server overloaded",
        "input": "HTTP 529: overloaded\nPlease try again later.",
        "expected_status": "ERROR",
    },
    # 6: IDLE — prompt visible
    {
        "name": "IDLE prompt",
        "input": "Previous output here\n❯ Type your message...",
        "expected_status": "IDLE",
    },
    # 7: WAITING — yes/no prompt
    {
        "name": "WAITING y/n",
        "input": "Do you want to overwrite existing file? [Y/n]",
        "expected_status": "WAITING",
    },
    # 8: WAITING — Korean confirmation
    {
        "name": "WAITING Korean",
        "input": "파일을 삭제할까요? 계속할까요? (y/n)",
        "expected_status": "WAITING",
    },
    # 9: NOT_STARTED — empty screen
    {
        "name": "NOT_STARTED empty",
        "input": "",
        "expected_status": "NOT_STARTED",
    },
    # 10: NOT_STARTED — banner only
    {
        "name": "NOT_STARTED banner",
        "input": "Claude Code v1.2.3\n\n",
        "expected_status": "NOT_STARTED",
    },
    # 11: ERROR — context exceeded
    {
        "name": "ERROR context exceeded",
        "input": "Error: context limit exceeded. MaxTokens limit reached.",
        "expected_status": "ERROR",
    },
    # 12: WORKING — progress bar
    {
        "name": "WORKING progress bar",
        "input": "Generating response ████████░░░░░░ 60%\nWriting...",
        "expected_status": "WORKING",
    },
    # 13: UNKNOWN — ambiguous
    {
        "name": "UNKNOWN ambiguous",
        "input": "Some random text without clear indicators\nLine two\nLine three\nLine four",
        "expected_status": "UNKNOWN",
    },
]


def run_tests() -> None:
    passed = 0
    failed = 0
    for i, tc in enumerate(TEST_CASES):
        result = classify(tc["input"])
        status_ok = result["status"] == tc["expected_status"]
        mark = "PASS" if status_ok else "FAIL"
        if status_ok:
            passed += 1
        else:
            failed += 1
        print(f"[{mark}] #{i:02d} {tc['name']}")
        print(f"       expected={tc['expected_status']}  got={result['status']}  confidence={result['confidence']}")
        if result["raw_indicators"]:
            print(f"       indicators={result['raw_indicators'][:3]}")
        if not status_ok:
            print(f"       input={repr(tc['input'][:80])}")
        print()

    print(f"Results: {passed}/{len(TEST_CASES)} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if "--test" in sys.argv:
        run_tests()
        return

    text = sys.stdin.read()
    result = classify(text)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
