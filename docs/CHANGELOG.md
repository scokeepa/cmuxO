# Changelog

## 2026-04-14 (Watcher Windows-native fallback hardening)

- `watcher-scan.py`에 `read_surface_text()`를 추가해 `bash read-surface.sh` 실패 시 `cmux capture-pane/read-screen` native fallback으로 surface 텍스트를 읽도록 보강.
- `watcher-scan.py`의 watcher heartbeat를 `role-register.sh` 경로 + JSON 직접 갱신 fallback 이중 경로로 보강 (`bash` 미존재 환경 대응).
- `watcher-scan.py`에서 남아 있던 literal `subprocess.run(["cmux", ...])` 호출을 공통 `run_cmd()` 경로로 통합해 `cmuxw` 라우팅 누락 지점 제거.
- 원자적 파일 교체를 `os.replace()`로 정리하여 Windows에서 기존 파일 overwrite 실패 가능성 완화.
- pipe-pane 상태 파일 SSOT를 `cmux-pipe-pane-installed.json`으로 정렬 (`activation-hook.sh`, `cmux-watcher-session.sh`).
- 회귀 테스트 확장: `tests/test_watcher_scan.py` 4 → 7 (`bash` 없는 fallback, heartbeat direct fallback, literal subprocess cmux 재유입 차단).
- 문서 동기화: `README.md`, `docs/03-operations/cross-platform.md`, `docs/04-development/test-guide.md`.
- README Cross-Platform 섹션에 공식 바이너리 소스 명시: macOS [`manaflow-ai/cmux`](https://github.com/manaflow-ai/cmux), Windows [`scokeepa/cmuxw`](https://github.com/scokeepa/cmuxw).

## 2026-04-13 (Control Tower Guard false positive hardening)

- `cmux-control-tower-guard.py`의 `cmux close-workspace` 감지를 `is_close_workspace_command()`로 분리.
- `shlex` shell token stream 기준으로 명령 시작 또는 command boundary 뒤의 실제 `cmux close-workspace`만 감지하도록 보강.
- `echo cmux close-workspace`, `grep "close-workspace" README.md` 같은 간접 문자열 언급 false positive 회귀 테스트 추가.
- `docs/03-operations/control-tower-guard-false-positive.md`를 해결 상태로 갱신.

## 2026-04-12 (External Review Follow-up — CPU Test Path + Nudge SSOT)

**레드팀 재검증 후 차단 이슈 수정 — 78/78 tests passed**

- `tests/chromadb_test_utils.py` 추가: 직접 ChromaDB collection을 생성하는 테스트도 `ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])` 사용.
- `test_context_injection.py`, `test_palace_memory.py`, `test_failure_classifier.py`, `test_mentor_report.py`의 direct collection 생성 경로를 CPU-only helper로 교체.
- `/cmux-start` runtime role SSOT를 `roles['boss']`로 정렬. `roles['main']`은 더 이상 nudge 권한 검증 alias로 허용하지 않음.
- roles 파일이 존재하면 미등록 issuer/target은 fail-closed.
- `jarvis_nudge.py`에 reason_code enum 검증 추가. cooldown 내부 reason도 `rate_limited`로 정렬.
- nudge evidence redaction을 ChromaDB document뿐 아니라 cmux 전송 message와 stdout audit event까지 확장.
- `test_nudge.py` 12 → 18 tests: boss-only SSOT, same-timestamp audit ID, missing target fail-closed, invalid reason_code, send/audit redaction 추가.
- 갭분석 후 `/cmux-stop`의 `roles['main']` 조회와 watcher state 문서의 `main_state` 표기를 `boss`/`boss_state`로 정렬.

## 2026-04-12 (External Review — 7 Issues Root Cause Fix)

**외부 전문가 리뷰 No-Go 7건 근본 해결 — 76/76 tests passed after follow-up**

**ORT CPU-only 강제: monkey-patch → ChromaDB 공식 preferred_providers API (Issue #1-2)**
- 모든 JARVIS 모듈 `_get_collection()`에 `ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])` 적용
- `cmux-main-context.sh` hook 인라인 Python에도 동일 적용
- `tests/conftest.py` monkey-patch 제거, 환경변수만 유지
- 대상: `jarvis_palace_memory.py`, `jarvis_mentor_signal.py`, `jarvis_nudge.py`, `jarvis_failure_classifier.py`, `jarvis_mentor_report.py`

**문서 SSOT 수정 (Issue #3)**
- `palace-memory.md` L1 소스: signals.jsonl → ChromaDB `wing=cmux_mentor` 쿼리
- 저장소 표 mentor signals SSOT: `signals.jsonl` → `~/.cmux-jarvis-palace (ChromaDB)`
- Export 포맷: version 1 + signals/l0/l1 → version 2 + drawers 기반

**README 수치 정정 (Issue #4)**
- "62 unit tests" → "78 unit tests" (follow-up nudge hardening tests 포함)

**Context injection 테스트 ChromaDB 기반 재작성 (Issue #5)**
- `test_context_injection.py` 시뮬레이터를 파일 기반(L0.md/L1.md/signals.jsonl) → ChromaDB 기반으로 전면 교체
- 실제 hook(`cmux-main-context.sh`)과 동일한 palace → identity.txt + wing=cmux_mentor 쿼리 경로 검증

**Nudge 권한 매트릭스 강제 (Issue #6)**
- `_validate_issuer_authority()`에 boss→team_lead만, jarvis→boss만 허용 규칙 추가
- 기존: team_lead cross-workspace만 검사 → 문서 매트릭스 3규칙 모두 구현

**Nudge evidence redaction (Issue #7)**
- `_store_nudge_audit()`에서 `mentor_redactor.redact()` 적용 후 ChromaDB 저장

## 2026-04-12 (Red-Team Findings Root Cause Fix)

**7건 레드팀 Findings + 3건 잔여 리스크 — 전수 근본 원인 해결**

원본 레포(milla-jovovich/mempalace) `migrate.py`, `repair.py`, `exporter.py`, `tests/conftest.py` 패턴 참조.

**테스트 환경 안정화 (F1)**
- `tests/conftest.py` 신규 — pytest 최초 로드 시 `ORT_DISABLE_COREML=1` + `ANONYMIZED_TELEMETRY=False` + posthog 로거 억제
- 결과: 25 failed → 0 failed (follow-up 이후 78/78)

**Palace Restore 명령 추가 (F3)**
- `_detect_chromadb_version()` — ChromaDB SQLite 스키마로 0.5.x/0.6.x/1.x 판별 (mempalace/migrate.py 패턴)
- `_extract_drawers_from_sqlite()` — raw SQL로 drawer 직접 추출, ChromaDB API 우회 (버전 불일치/복사본 DB 호환)
- `cmd_restore()` — SQL 추출 → 임시 palace 생성 → shutil.move 교체 (ChromaDB 0.6.x disk I/O error 회피)
- argparse `restore` 서브커맨드 (`--backup-path`, `--dry-run`, `--overwrite`)

**Nudge 전송 검증 (F5)**
- `_cmux_send()` returncode 검사 추가 — 전송 실패 시 `False` 반환
- `cmd_send()` outcome: `"pending"` → `"sent"/"failed"`, 실패 시 return 3

**Surface_map 기반 역할 검증 (F6)**
- `_validate_issuer_authority()` — `/tmp/cmux-roles.json` 기반 workspace 교차 검증
- team_lead의 cross-workspace nudge 차단 (code 4)
- 런타임 파일 없으면 기존 ALLOWED_ISSUERS fallback

**Mentor.enabled config 게이팅 (F7)**
- `_is_mentor_enabled()` — `~/.claude/cmux-jarvis/config.json` `mentor.enabled` 확인
- 게이팅 지점 3곳: `cmd_emit()`, `cmd_generate_context()`, `cmd_generate()`
- 비활성화 시 signal 수집, context 생성, report 생성 모두 중단

**Wing 격리 보장 (F4)**
- `test_nudge_excluded_from_mentor_context` — cmux_nudge wing 데이터가 mentor context에 미포함 확인

**문서 SSOT 정렬 (F2)**
- `palace-memory.md` — L2/L3 저장소, embedding 정책, backup/restore ChromaDB 기준 재작성
- `system-overview.md` — 멘토 신호 SSOT 경로 `~/.cmux-jarvis-palace/ (ChromaDB)` 변경
- `privacy-policy.md` — 저장소, retention, delete, export ChromaDB 기준 + mentor.enabled 구현 반영
- `nudge-escalation.md` — workspace 교차 검증 구현 현황 업데이트
- `test-guide.md` — 78 tests, conftest.py + CPU-only helper ChromaDB 환경 설명

**Testing: 62 → 78 tests (+16 after follow-up)**
- test_palace_memory (+4): restore, restore_dry_run, extract_drawers_from_sqlite, detect_chromadb_version
- test_nudge (+11): nudge_excluded_from_mentor, send_failure_outcome, cross_workspace_blocked, same_workspace_allowed, no_roles_fallback, boss-only SSOT, same-timestamp audit ID, missing target fail-closed, invalid reason_code, send/audit redaction
- test_mentor_signal (+1): mentor_disabled_skips_emit

## 2026-04-11 (Integration Audit Fix)

**원본 레포 재검토 — 통합 오류 8건 수정**
- **telemetry**: `ANONYMIZED_TELEMETRY=False` 제거 → `logging.getLogger("chromadb.telemetry.product.posthog").setLevel(CRITICAL)` (mempalace `__init__.py:14` 동일 패턴)
- **ONNX CoreML**: arm64 Darwin에서 `ORT_DISABLE_COREML=1` 설정 (segfault 방지, mempalace `__init__.py:18-19`)
- **palace chmod**: 디렉터리 `0o700` 권한 설정 (mempalace `palace.py:41`)
- **input sanitize**: `sanitize_name()`/`sanitize_content()` 추가 — path traversal, null byte, 128자 제한 (mempalace `config.py:22-57`)
- **L4 gate**: `verification > 0.15 AND correction > 0.05` (correction 누락 수정)
- **L5 gate**: `(tool_diversity > 8 OR orchestration) AND strategic > 0.05` (왜곡 수정)
- **L6/L7 gate**: 추가 (team/orch_count/external contribution)
- **install.sh**: `ANONYMIZED_TELEMETRY` 환경변수 제거

**README 최신화**
- 배지: 216 files, 62 tests, 22 arch docs, ChromaDB 배지
- Security: chmod 0o700, sanitize, ONNX CoreML guard 추가 (11항목)
- docs 구조: 00~99 번호 체계 반영, installer 7단계

**문서 체계 정리**
- `docs/features/` 구현 완료 문서 → `docs/99-archive/` 이동

## 2026-04-11 (mempalace ChromaDB Migration)

**JSONL → ChromaDB 전면 전환**
- **jarvis_palace_memory.py** -- mempalace ChromaDB 기반 전면 재작성. L0/L1 context, 시맨틱 검색, export/import (PR #499 dedup), backup + integrity validation, legacy migration
- **jarvis_mentor_signal.py** -- signals.jsonl → ChromaDB `cmux_mentor` wing drawers. 축별 score를 metadata에 개별 저장. 시맨틱 벡터 검색 가능
- **jarvis_nudge.py** -- nudge audit → ChromaDB `cmux_nudge` wing drawers. JSONL 파일 의존 제거
- **jarvis_mentor_report.py** -- report + TIMELINE → ChromaDB `cmux_reports`/`cmux_timeline` wing drawers. vibe-sunsang growth-analyst 패턴 적용
- **jarvis_failure_classifier.py** -- ChromaDB에서 signal 읽기로 전환
- **cmux-main-context.sh** -- mempalace ChromaDB에서 직접 L0/L1 + coaching hint 읽기
- **Palace 경로**: `~/.cmux-jarvis-palace/` (ChromaDB PersistentClient)
- **Wing 구조**: cmux_mentor (6축), cmux_nudge (재촉), cmux_reports (리포트), cmux_timeline (종단), cmux_coaching (코칭)
- **Embedding**: all-MiniLM-L6-v2 (ONNX, 로컬)
- **Prerequisites**: chromadb 추가 (pip3 install chromadb)

**Testing: 62 passed** (ChromaDB 기반 테스트 전면 재작성)

## 2026-04-11 (AGI Mentor Integration)

**P0: Runtime Bug Fixes**
- **validate-config.sh `import os` fix** -- `NameError: name 'os' is not defined` resolved. JSON report now outputs correctly in no-cmux/sandbox/cmux-socket environments
- **watcher-scan.py stale AI detection fix** -- `get_available_tools()` now uses `shutil.which()` runtime check instead of stale `ai-profile.json.detected` field. Correctly detects codex/gemini/claude
- **orchestra-config.json deprecation notice** -- Runtime fields (surfaces, boss_surface, watcher_surface) marked deprecated; SSOT is `/tmp/cmux-surface-map.json` + `cmux tree --all`

**P1: JARVIS Architecture Documents (7 files)**
- **mentor-lane.md** -- Mentor Lane role definition. Lane M (coaching) separated from Lane B (evolution). Context injection policy: L0+L1 600-900 tokens, max 1 hint/round
- **mentor-ontology.md** -- 6-axis skill dimensions (DECOMP/VERIFY/ORCH/FAIL/CTX/META) adapted from vibe-sunsang. Harness Level L1-L7, Fit Score formula, Gate conditions, antipattern catalog
- **jarvis-constitution.md** -- Unified JARVIS identity + Constitutional Principles (from referense/1.jpeg as product principles, not external facts) + Iron Laws reference + common policy fields
- **jarvis-capability-targets.md** -- 5 quality targets (Security/Engineering/Alignment/Calibration/Visual Reasoning) from referense/2.jpeg. Phase 1/2/3 acceptance criteria
- **nudge-escalation-policy.md** -- 3-level nudge system (L1 text/L2 interrupt/L3 reassign). Permission matrix, cooldown/throttle, audit schema. Watcher = evidence only. badclaude patterns reinterpreted as session-scoped policy
- **mentor-privacy-policy.md** -- Raw capture OFF by default. Storage separation, 90-day retention, API key/password/token auto-redaction, user opt-out/delete/export rights
- **palace-memory-ssot.md** -- Palace memory substrate: wing/room/drawer mapping to cmux entities. L0-L3 loading policy. Signal/Drawer/Triple schemas. ChromaDB/MCP = Phase 3+ optional

**P3: Mentor Code Implementation (6 scripts, 1,193 lines)**
- **jarvis_mentor_signal.py** -- 6-axis signal engine. emit/query/tail/prune CLI. JSONL append with fcntl locking. Auto-detects antipatterns, generates coaching hints, enforces `insufficient_evidence` when confidence < 0.5 or evidence < 3
- **jarvis_palace_memory.py** -- L0/L1 context generator. L0 identity (~100 tokens), L1 essential story from signals (MAX_CHARS=3200). Token budget enforcement (900 max). Empty signals = "insufficient observation" message
- **mentor_redactor.py** -- 5-pattern sensitive data redaction (API keys, passwords, Bearer tokens, Authorization headers, secrets). File paths preserved
- **jarvis_nudge.py** -- L1 text nudge via `cmux send`. Watcher execution blocked. Cooldown 5 min/target. Rate-limited events logged. Audit JSONL with full evidence trail
- **jarvis_mentor_report.py** -- Periodic harness improvement report. 6-axis table + trends + antipatterns + Gate conditions + next-step suggestions. TIMELINE.md longitudinal tracking. Defers if signals < 3
- **jarvis_failure_classifier.py** -- Failure root cause classifier: system config (evolution rollback rate) vs user instruction (antipattern frequency) vs mixed. Iron Law #1 reminder for system classification

**P4: Context Injection + Nudge Integration**
- **cmux-main-context.sh mentor inject** -- `/cmux` prompt now includes L0/L1 mentor context + latest coaching hint. Token budget 3600 chars enforced. Hint spam prevention via `/tmp/cmux-mentor-last-hint.txt` cache

**Docs Reorganization**
- docs/ 전면 재편: `00-overview` → `01-architecture` → `02-jarvis` → `03-operations` → `04-development` → `05-research` → `99-archive`
- 신규 8건 (system-overview, orchestrator/watcher arch, security, hook-enforcement, quick-start, ai-profiles, troubleshooting, test-guide)
- deprecated 12건 → `99-archive/`

**Testing: 14 → 58 tests (+44)**
- test_mentor_signal (5), test_palace_memory (6), test_redaction (8), test_context_injection (5), test_nudge (7), test_mentor_report (6), test_failure_classifier (7)

## 2026-04-11 (Earlier)

- **Orchestrator SKILL.md rewrite** -- Boss operational directives (empty 11-line shell -> full 200+ line guide)
- **Department = workspace structure** -- Department = sidebar tab (workspace), Team Lead = lead surface (Claude Code), Workers = panes within same workspace created by Team Lead
- **Team Lead Phase 1-2-3 protocol** -- Verify -> Plan -> Execute+Verify before dispatching to workers
- **Plan Quality Gate 3-phase enforcement** -- Hook blocks ExitPlanMode unless: [Verification] 5-point sections with verdicts + [Refinement] judgment recorded + [Simulation] TC results with ALL PASS
- **LECEIPTS rules per role** -- Boss (top principles + scope), Team Lead (full leceipts + 5-section DONE), Worker (simplified), JARVIS (leceipts + Iron Laws priority)
- **Architecture section enhanced** -- State machine diagram, data flow, hook enforcement layer visualization
- **LECEIPTS Gate** -- 5-section report + diff hash binding enforced before every `git commit`
- **`is_git_commit()` hardening** -- Detects `git -C .`, `--work-tree`, `--git-dir` variants
- **`has_success` validation** -- At least one passing verification required (no all-failure reports)
- **Watcher guard reorder** -- Complete no-op when orchestration disabled (role marker included)
- **Standalone installer sync** -- HOOK_MAP aligned with activation-hook.sh
- **Runtime model alignment** -- Config stale surfaces removed (presets only), watcher role-based team_lead detection, idle-auto-dispatch Python syntax fix
- **Test fixes** -- 14/14 passing (silent exit stderr optional, malformed JSON target corrected)

## 2026-04-09

- **GATE 7** -- Boss direct work blocked when IDLE workers exist
- **JARVIS Python migration** -- Core scripts migrated to Python

## 2026-04-08

- **DONE quality gate** -- Shell-only completion reports blocked
- **Auto-restart protocol** -- Automatic recovery after Claude Code limit reset

## 2026-04-07

- **JARVIS real-time feedback pipeline**
- **Team lead work protocol** (3-phase: analyze, decide, execute)
