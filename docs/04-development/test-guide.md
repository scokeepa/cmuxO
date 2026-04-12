# Test Guide

> 78 tests 구조, 실행 방법, 패턴. (ChromaDB 기반)

## 실행

```bash
python3 -m pytest tests/ -v
```

## 테스트 구조

| 파일 | 테스트 수 | 대상 |
|------|-----------|------|
| `test_cmux_utils.py` | 9 | 핵심 유틸리티 (atomic write, locked update, queue) |
| `test_hooks.py` | 5 | Hook 강제 (fail-closed, fail-open, silent, approve) |
| `test_mentor_signal.py` | 7 | 6축 signal (emit, insufficient, fit score, antipattern, prune, query, disabled) |
| `test_palace_memory.py` | 13 | L0/L1 context, search, export/import, backup, restore, SQL extract, version detect |
| `test_redaction.py` | 8 | 민감 정보 redaction (5 patterns + path + mixed + false positive) |
| `test_context_injection.py` | 5 | Mentor context inject (present, absent, spam, budget, empty hint) |
| `test_nudge.py` | 18 | L1 nudge (send, block, cooldown, same-timestamp audit, targets, wing 격리, send failure, cross-ws, fallback, boss-only SSOT, reason enum, redaction) |
| `test_mentor_report.py` | 6 | Report (generate, insufficient, timeline, disclaimer, trend, gate) |
| `test_failure_classifier.py` | 7 | Failure classify (system, user, mixed, none, iron law, empty, evidence) |

## 패턴

- `tempfile.TemporaryDirectory()`로 격리된 테스트 환경
- 모듈 전역 경로를 임시 디렉터리로 교체 후 복원
- `assert` + `print("  test_name: PASS")` 패턴
- `main()` 함수에서 순차 실행 (pytest 호환)

## ChromaDB 테스트 환경

`tests/conftest.py`가 pytest 최초 로드 시 다음을 설정하고, 직접 ChromaDB collection을 생성하는 테스트는 `tests/chromadb_test_utils.py`의 CPU-only helper를 사용한다:

- `ORT_DISABLE_COREML=1` — Apple Silicon에서 ONNX Runtime CoreML provider segfault 방지
- `ANONYMIZED_TELEMETRY=False` — ChromaDB posthog telemetry 비활성화
- posthog 로거 CRITICAL 레벨 설정 — `capture()` signature 불일치 경고 억제
- `ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])` — 테스트 직접 seeding 경로의 CoreML provider 우회

근거: mempalace `tests/conftest.py` + `mempalace/__init__.py` 패턴.
