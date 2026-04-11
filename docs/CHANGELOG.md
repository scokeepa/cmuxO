# Changelog

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
- **orchestra-config.json deprecation notice** -- Runtime fields (surfaces, main_surface, watcher_surface) marked deprecated; SSOT is `/tmp/cmux-surface-map.json` + `cmux tree --all`

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

- **GATE 7** -- Main direct work blocked when IDLE workers exist
- **JARVIS Python migration** -- Core scripts migrated to Python

## 2026-04-08

- **DONE quality gate** -- Shell-only completion reports blocked
- **Auto-restart protocol** -- Automatic recovery after Claude Code limit reset

## 2026-04-07

- **JARVIS real-time feedback pipeline**
- **Team lead work protocol** (3-phase: analyze, decide, execute)
