# cmux-nudge-chromadb-cpu Verification Report

- **Ticket**: cmux-nudge-chromadb-cpu
- **Branch / Commit**: `main` / `4bb9b6c`
- **Date**: 2026-04-12
- **Author**: Codex

## 1. Root cause / 문제 원인

- 테스트가 `chromadb.PersistentClient(...).create_collection()`을 직접 호출하면서 프로덕션 `_get_collection()`의 CPU-only embedding policy를 우회했다. 그 결과 Apple Silicon 환경에서 ChromaDB 기본 embedding 경로가 `CoreMLExecutionProvider`를 포함했고, `python3 -m pytest tests -v`가 `25 failed, 47 passed`로 실패했다.
- `/cmux-start`는 사장 pane을 `roles['main']`으로 등록했지만 `jarvis_nudge.py`의 권한 검증은 issuer `boss`를 canonical role로 사용했다. roles 파일이 존재해도 issuer/target이 누락되면 검증을 스킵하는 fail-open 경로가 있었다.
- nudge evidence redaction은 ChromaDB audit document 저장 경로에만 적용됐고, cmux 전송 message와 stdout audit event에는 raw evidence가 남을 수 있었다.

## 2. Change / 수정 내용

- `tests/chromadb_test_utils.py` — 테스트 직접 seeding 경로용 CPU-only ChromaDB helper 추가.
- `tests/test_context_injection.py` — context injection 시뮬레이터와 seed helper가 CPU-only collection helper를 사용하도록 변경.
- `tests/test_palace_memory.py` — direct collection 생성/조회 경로를 CPU-only helper로 변경.
- `tests/test_failure_classifier.py` — signal seed collection 생성/조회 경로를 CPU-only helper로 변경.
- `tests/test_mentor_report.py` — report seed collection 생성/조회 경로를 CPU-only helper로 변경.
- `cmux-start/SKILL.md` — runtime role registration SSOT를 `roles['boss']`로 정렬.
- `cmux-jarvis/scripts/jarvis_nudge.py` — `main` legacy alias 처리, roles-present missing issuer/target fail-closed, reason_code enum validation, `rate_limited` reason 정렬, message/stdout/audit evidence redaction 적용.
- `tests/test_nudge.py` — boss/main alias, missing target fail-closed, invalid reason_code, send/audit redaction 회귀 테스트 추가.
- `README.md`, `docs/04-development/test-guide.md`, `docs/02-jarvis/nudge-escalation.md`, `docs/CHANGELOG.md` — 76 tests 및 nudge/ChromaDB 정책으로 문서 정렬.

## 3. Recurrence prevention / 재발 방지

- [x] Root-cause fix (not a symptom patch)
- [x] Guardrail added (validation / quality check / UI constraint)
- [x] Regression test added or updated (must fail on the previous bug)
- [ ] Failure visibility logging
- [ ] Intentional omission

## 4. Verification / 검증 결과

| Item | Command | Result |
|---|---|---|
| Python syntax | `python3 -m py_compile cmux-jarvis/scripts/jarvis_palace_memory.py cmux-jarvis/scripts/jarvis_mentor_signal.py cmux-jarvis/scripts/jarvis_nudge.py cmux-jarvis/scripts/jarvis_failure_classifier.py cmux-jarvis/scripts/jarvis_mentor_report.py tests/chromadb_test_utils.py tests/test_context_injection.py tests/test_palace_memory.py tests/test_failure_classifier.py tests/test_mentor_report.py tests/test_nudge.py` | passed |
| Shell syntax | `bash -n cmux-orchestrator/hooks/cmux-main-context.sh` | passed |
| Direct ChromaDB scan | `rg -n "client\.(get_collection|create_collection|get_or_create_collection)\(" tests -S` | only `tests/chromadb_test_utils.py` direct calls remained |
| Targeted tests | `python3 -m pytest tests/test_context_injection.py tests/test_palace_memory.py tests/test_failure_classifier.py tests/test_mentor_report.py tests/test_nudge.py -v` | 47 passed, 474 warnings |
| Full tests | `python3 -m pytest tests -v` | 76 passed, 515 warnings |

Key output excerpts:

```text
collected 76 items
======================= 76 passed, 515 warnings in 4.65s =======================
```

### Unverifiable items

- Real cmux send behavior — local test suite mocks `_cmux_send`; live cmux pane ownership and UI interaction are external runtime behavior.

## 5. Remaining risk / 남은 리스크

- ChromaDB/ONNX warnings remain from third-party packages (`urllib3` LibreSSL warning, Pydantic deprecation warnings). They did not fail the current suite but may need dependency-level handling if CI treats warnings as errors later.

## DoD Checklist

- [ ] Changed files committed
- [ ] Commit SHA present on base branch (`git branch --contains <sha>`)
- [x] Build / test suite passed, or unverifiable reason given
- [ ] Result pasted into the ticket/issue comment
