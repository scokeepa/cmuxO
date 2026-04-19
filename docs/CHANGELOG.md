# Changelog

## 2026-04-20 (Phase 2.4 — JARVIS Anti-Rationalization Tables)

LLM/Worker/Boss 가 "환경 문제", "아마 동작할 것", "완료했습니다" 류 **자기 합리화**로 검증을 스킵하는 패턴이 반복 관측. Superpowers `systematic-debugging` 의 표 기반 안티패턴 리스트 + cmuxO 고유의 peer-fallback/토큰 관측 합리화 14종을 `references/anti-rationalization.md` 로 문서화. 감지 로직은 **독립 모듈** `anti_rationalization.py` 로 분리해 기존 commit-gate 훅의 블라스트 반경을 보존.

**선행 Phase 리스크 흡수** (플랜 §0)
- Phase 2.2 risk #1 (transcript missing 합리화), #2 (JSONL 파싱 실패 합리화) → Table A 에 2줄 추가
- Phase 2.2.5 risk #1 (peer fallback 합리화), risk #2 (boss peer_id 결석 합리화) → Table A/B 에 2줄씩 추가
- Phase 2.3 risk (ASSIGN/CLEAR/VERIFY_* 기록자 배선 미완) → 이 Phase 에서 함께 해결 (§0.6 지시 준수)

**신규 모듈**
- `cmux-orchestrator/scripts/anti_rationalization.py` — 순수 감지+증거조회 모듈. 7 정규식 패턴(카테고리 A/B), 5 evidence 마커, quoted-string 회피, override reason 허용, worker-scoped ledger VERIFY_PASS 조회.
- `cmux-orchestrator/references/anti-rationalization.md` — Table A/B/C + Counter 원칙(Superpowers 인용) + 훅 동작 규약 + 자동수집 appendix 블록.
- `/tmp/test_anti_rationalization.py` (시뮬) — **14/14 PASS**.

**Ledger 기록자 배선 완료** (Phase 2.3 risk 해소)
- `cmux-orchestrator/hooks/cmux-dispatch-notify.sh` — `cmux send` 감지 시 `/clear` 여부로 ASSIGN / CLEAR 분기 append (비동기).
- `cmux-orchestrator/hooks/cmux-completion-verifier.py` — VERIFY_FLAG TTL 검증 결과에 따라 VERIFY_PASS(evidence=flag mtime) / VERIFY_FAIL(evidence="no flag or expired", excerpt=command[:200]) append.
- `cmux-orchestrator/hooks/cmux-main-context.sh` — UserPromptSubmit 훅이 `python3 ledger.py context` stdout 을 `additionalContext` 에 주입(≤6KB cap, 2 s timeout).

**감지 동작**
- `classify(text, worker=None)` → `{"decision": "pass"|"ask", "matches": [...], "evidence": "text"|"ledger"|None, "reason": ...}`.
- ASK 반환 — deny 가 아닌 **사용자 확인** 유도 (자율 판단 여지).
- PASS 조건: (1) evidence 마커 in-text (`test N/N`, `VERIFY_PASS`, ...) (2) override reason 명시 (3) env issue + 구체적 binary/env var/permission/install (4) ledger 에 10분 이내 VERIFY_PASS 기록.

**Iron Law 준수**
- SSOT: 패턴 표 1 곳(references/), 감지 로직 1 모듈 ✓
- SRP: 감지/증거-조회/렌더링 분리 ✓
- 기존 L0 BLOCK commit-gate 훅 비침습 ✓
- `override reason` 탈출구 보존 (자율성) ✓

**검증**
- `test_anti_rationalization.py` 14/14 PASS (8 원안 케이스 + 흡수 6 케이스)
- 회귀: ledger 11/11, ledger-integration 5/5, peer_channel 12/12, token_observer 13/13 모두 유지 (총 55/55)
- Hook 문법 정적 검증 (python ast.parse + bash -n) 3 파일 OK

**제약 / 향후**
- `cmux-leceipts-gate.py` 내부 통합은 의도적 미수행: L0 BLOCK 훅 확장은 블라스트 반경 과대, `anti_rationalization.classify()` 를 `/cmux-check` 수동 호출 경로로 롤아웃.

---

## 2026-04-20 (Phase 2.4 보강 — Remaining risk 3건 완결)

Phase 2.4 Remaining risk 로 이관 예정이었던 3건을 같은 Phase 내에서 마감. 메모리 지시 `feedback_remaining_risk_propagation.md` 에 따라 Phase 3.1 에 불필요한 이월을 제거.

**완결 항목**
- `/cmux-check` 슬래시 커맨드 — `cmux-orchestrator/commands/cmux-check.md` + `cmux-orchestrator/scripts/cmux-check.sh`. 4 모드: 인라인 텍스트, `--stdin [worker]`, `--table` (references 테이블 출력), `--last N [worker]` (ledger tail 일괄 감사).
- `jarvis-anti-rationalization-report.py` — 월 1회 ledger 30일 윈도를 스캔해 `references/anti-rationalization.md` 의 `<!-- BEGIN AUTO --> ... <!-- END AUTO -->` 블록을 빈도표로 재작성. `jarvis-scheduler.py` 에 `handler="anti_rationalization_report"` + cron `0 0 1 * *` 로 등록. atomic rename 으로 partial write 방지.
- `role-register.sh` 확장 + `CLAUDE_PEERS_NAME_PREFIX` 주입 — `register <role> [peer_id]` 에 선택 인자 추가, 미지정 시 `peer_channel.py resolve <prefix>` 로 logical_name → peer_id 해석. 등록 직후 `ROLE_PEER_BIND {role, surface, workspace, cwd, peer_id, logical_name, ts}` 이벤트를 ledger 에 append. `cmux-orchestrator/scripts/cmux-role-exec.sh` 런처 신설: `CLAUDE_PEERS_NAME_PREFIX=<role>` 을 export 후 `claude` 를 exec → 차세대 Boss/Watcher 세션이 올바른 logical_name 으로 MCP 등록.

**검증**
- `/tmp/test_antirat_report.py` 5/5 PASS — 빈 ledger (데이터 없음 블록), 시드된 이벤트 (빈도표 + 상위 reason), 30일 윈도 경계, rewrite 가 헤더/본문 보존, 마커 부재 시 rewrite False.
- `/tmp/test_role_register.py` 4/4 PASS — 명시 peer_id 저장, broker 부재 시 peer_id 필드 없음, name_prefix 포집, ROLE_PEER_BIND ledger 이벤트 실제 발생.
- 전체 회귀: ledger 11/11, ledger-integration 5/5, anti-rationalization 14/14, antirat-report 5/5, role-register 4/4 — **39/39 PASS**.

**제약**
- `cmux-role-exec.sh` 는 **신규 세션 기동 경로만** 유효. 이미 실행 중인 Claude Code 세션의 env 에는 소급 적용 불가 — 사용자가 다음 세션부터 `bash cmux-role-exec.sh boss` 로 기동해야 logical_name 바인딩이 활성화됨.
- cron 은 `jarvis-scheduler.py run` 프로세스가 기동 중일 때만 동작. 스케줄러 미기동 시 `jarvis-anti-rationalization-report.py` 를 수동 실행 가능.

---

## 2026-04-19 (Phase 2.3 — Ledger-Based Boss State)

Boss 팀 운영 상태가 `cmux-eagle-status.json` / `cmux-task-queue.json` / `cmux-watcher-alerts.json` 에 산재 → 시간축 추적·포렌식·compaction 복구 모두 불가. **단일 append-only JSONL ledger** (`runtime/ledger/boss-ledger-YYYY-MM-DD.jsonl`) 도입으로 해결. MagenticOne/AutoGen 의 orchestrator ledger 패턴을 cmuxO 이벤트 타입에 맞춰 축약 적용.

**선행 Phase 리스크 흡수** (플랜 §0)
- Phase 2.2.5 risk #3 (PEER_SENT_LOG 의 소비자 부재) — peer_channel 이 ledger 로 `PEER_SENT`/`PEER_SEND_FAILED`/`PEER_PAYLOAD_DENIED` 를 **미러** 기록, 기존 JSONL log 도 운영 호환성 유지.
- Phase 2.2.5 risk #1 (Boss/Watcher peer_id 바인딩 기록 경로 부재) — `ROLE_PEER_BIND` 이벤트 타입 정의(기록자는 후속 role-register 스크립트).
- Phase 2.2 risk #1 (surface ↔ cwd 매핑 저장 공간 부재) — `ROLE_PEER_BIND` 에 `{surface, cwd, peer_id, logical_name}` 삼중 매핑 저장 경로 확보.
- Phase 2.2 risk #2 (SCHEMA_VERSION bumping 감시) — ledger 첫 줄을 `{"type":"SCHEMA","version":1,"started_at":ts}` 로 고정, `integrity_check()` 가 schema mismatch 를 fail-open 로 감지.

**신규 모듈**
- `cmux-orchestrator/scripts/ledger.py` — `append/tail/query/integrity_check/compact_old/compaction_replay_context` 단일 API. `fcntl.flock(LOCK_EX)` + `O_APPEND` + `fsync` 로 다중 writer 원자성. 라인 > 4000B 시 `message_excerpt` 트렁케이트, event JSON 자체는 손상 금지.
- `cmux-orchestrator/scripts/cmux-ledger.sh` — `tail [N] / worker <sid> / verify-fail / since <sec> / integrity / compact / context` 명령.
- `/tmp/test_ledger.py` (시뮬) — 11/11 PASS. 10k 라인 tail 8ms, 50×100 동시 append 5000 valid / 0 broken.
- `/tmp/test_ledger_integration.py` (통합) — peer_channel ↔ ledger 배선 5/5 PASS.

**SSOT 확장** (`cmux_paths.py`)
- `LEDGER_DIR`, `ledger_today_path(now=None)` 추가 (UTC date rotation).

**기록 지점 연결**
- `peer_channel.send()` 내부 `_mirror_to_ledger()` 헬퍼 — 성공/실패/guard 거절 3 경로 자동 기록.
- `watcher-scan.py::do_scan()` 
  - `RATE_LIMITED` 감지 시 `RATE_LIMIT_DETECTED` append.
  - Report alerts 중 HIGH/CRITICAL 은 `ALERT_RAISED` append (RATE_LIMITED 는 중복 방지 skip).

**이벤트 타입 정의** (enum)
`SCHEMA, ASSIGN, ASSIGN_SKIP, REPORT_DONE_CLAIMED, VERIFY_PASS, VERIFY_FAIL, CLEAR, RATE_LIMIT_DETECTED, ALERT_RAISED, HOOK_BLOCK, PEER_SENT, PEER_SEND_FAILED, PEER_PAYLOAD_DENIED, ROLE_PEER_BIND`

**스키마**
- 파일 첫 줄: `{"type":"SCHEMA","version":1,"started_at":<ts>}`
- 각 이벤트 라인: `{"ts":<epoch>, "type":<EVENT>, ...fields}`. UTC epoch, 타임존 모호성 제거.
- 라인 크기 상한 4000B(`O_APPEND` 원자성). `message_excerpt` 는 200B 까지 clamp, 초과 시 `truncated=true` 플래그.

**운영**
- 30일 이상 파일 `gzip` 압축, 90일 경과 시 삭제 (`ledger.compact_old()`). 월 1회 cron 또는 수동 `cmux-ledger.sh compact` 실행.
- Compaction 복구: `compaction_replay_context(n=30)` 가 Boss UserPromptSubmit 훅용 텍스트 블록 반환 (후속 `cmux-main-context.sh` 통합).

**Iron Law 준수**
- Append-only ✓, 원자적 쓰기 ✓, fail-open 정책(권한/디스크 실패 시 stderr 경고 + 호출자 차단 X) ✓, 감사 로그 훼손 불가 (각 줄 즉시 `fsync`) ✓.

**제약 / 향후**
- `cmux-main-context.sh` 가 ledger tail 을 실제 Boss 세션에 주입하도록 배선 필요 (Phase 2.3.1 또는 2.4 통합).
- `ASSIGN`/`CLEAR`/`VERIFY_*` 기록은 dispatch/verifier 경로에 함수 호출 1 줄 삽입 대기(현재는 스키마·타입만 정의). Boss 루프가 정상 작동 중이라 회귀 없이 점진 배선 가능.
- 테스트 `Case 8` 은 권한 오류 로그 1 줄 stderr 출력(정상). CI 파이프에서 `2>/dev/null` 로 숨길지 결정 필요.

---

## 2026-04-19 (Phase 2.2.5 — claude-peers Inter-Session Channel)

Boss ↔ Watcher ↔ Worker 통신이 `cmux send + enter` 로 tmux 표면에 직접 타이핑하는 방식이라 **사용자 프롬프트와 보고 메시지가 뒤섞이고**, 메시지 메타(from_kind/from_cwd)가 손실되며, 표면 죽음 시 드롭. `claude-peers-oneclick` 브로커의 **peer-registration-free system 송신자 경로**(`POST /send-message` with `from_id` 만, `from_pid` 생략 → `from_kind='system'`) 를 도입해 구조화 + 이중 발행 guard.

**신규 모듈**
- `cmux-orchestrator/scripts/peer_channel.py` — HTTP 어댑터 (send / is_broker_alive / list_peers / resolve) + W-9 확장 guard (정규식으로 `/new|/clear|/compact|/quit|/exit` payload 거절) + `PEER_SENT_LOG_FILE` JSONL append.
- `plans/cmux-upgrade-phase2-2-5-peers-integration.md` — 범위/설계/5관점 검증.
- `/tmp/test_peer_channel_mock.py` (시뮬) — mock HTTP broker 상대 12/12 PASS.

**SSOT 확장**
- `cmux_paths.py`: `PEER_DIR`, `PEER_SENT_LOG_FILE` 상수 추가.
- `CLAUDE_PEERS_BROKER_URL` / `CMUX_PEERS_ENABLED` 환경변수 override.

**Watcher 통합** (`cmux-watcher/scripts/watcher-scan.py::notify_boss_surface`)
- peer-first routing: `peer_channel.send()` 성공 시 `cmux send + enter` **스킵** (이중 발행 금지).
- 실패(broker dead / peer 미해석 / guard 거절) 시 기존 cmux send 로 자동 fallback.
- `CMUX_PEERS_ENABLED=0` kill switch 로 즉시 비활성 가능.

**W-9 확장**
- peers 채널은 `cmux-send-guard.py` 범위 밖 → `peer_channel._is_forbidden()` 에서 payload 정규식으로 `/new`·`/clear`·`/compact`·`/quit`·`/exit` 거절.
- 허용: `[WATCHER→BOSS] DONE: ...`, `[BOSS→WATCHER] ACK: ...`, 기타 보고 태그.

**검증**
- mock broker 12/12 PASS (정상 send / broker down / unknown peer / logical_name resolve / guard / 로그 append / kill switch / health / list).
- 실 브로커 E2E 스모크: `peer_channel.py health` 및 `list` 정상 (peers=4).
- 현 환경 peer 이름이 전부 `claude@…` 라 `resolve("boss")` 는 None → watcher 가 자동 cmux send fallback 으로 동작 (correctness 유지).

**운영 롤아웃 (다음 단계, Phase 2.3 연계)**
- Boss Claude Code 세션을 `CLAUDE_PEERS_NAME_PREFIX=boss` 로 기동 → `logical_name=boss@<surface_id_8>` 등록.
- 또는 `cmux-roles.json` 에 `peer_id` 필드 확장 — watcher 가 우선 조회.

**Iron Law 준수**
- 경로는 `cmux_paths` SSOT ✓, watcher 루프 non-blocking(HTTP 3 s timeout + broker health 0.5 s) ✓, 이중 발행 배타 routing ✓, W-9 확장 guard ✓.

**제약 / 향후**
- 브로커 SPOF — cmux send fallback 으로 완화, 완전 HA 는 Phase 3 범위.
- logical_name 정규화는 `[a-z0-9._-]` 만 허용 → Watcher/Boss 이름은 ASCII 고정 (한글 라벨은 메시지 본문으로만).
- Phase 2.3 ledger 가 `PEER_SENT_LOG_FILE` 를 소스로 audit trail 생성 예정.

---

## 2026-04-19 (Phase 2.2 — Token/Cache Observability)

각 Worker(AI 팀원)의 input/output 토큰·캐시 히트율·턴 수가 불투명 → Superpowers 류 context bloat 을 사후에만 발견 가능했던 문제 해결. Claude Code가 남기는 `~/.claude/projects/<slug>/<uuid>.jsonl` transcripts 를 **tail 파싱 집계**하여 watcher 스캔 주기마다 runtime 에 persist.

**신규 파일**
- `cmux-orchestrator/scripts/token_observer.py` — JSONL tail 파서 + 집계 + 원자적 쓰기 + CLI (`collect|dump|alerts`). Claude 전용, 기타 AI 는 `cache_hit_ratio=None`.
- `cmux-orchestrator/scripts/cmux-metrics.sh` — 표 형식 조회 스크립트 (`--json|--alerts|--refresh`).
- `cmux-orchestrator/commands/cmux-metrics.md` — `/cmux-metrics` 슬래시 커맨드 등록.
- `tests/../test_token_observer_real.py` (시뮬) — 13/13 PASS.

**SSOT 확장**
- `cmux-orchestrator/scripts/cmux_paths.py`:
  - `TELEMETRY_DIR`, `TOKEN_METRICS_FILE` 추가 (runtime 디렉토리 기반).
  - `cwd_to_slug()`, `surface_to_slug()`, `claude_projects_dir()` 헬퍼 추가 (slug 생성 1 곳 강제).
  - `CLAUDE_PROJECTS_DIR` 환경 변수 override 지원 (테스트/격리).

**저장 포맷** — `runtime/telemetry/token-metrics.json`
```
{version:1, updated_at, surfaces:{
  "slug:...": {ai, input_tokens_total, output_tokens_total,
               cache_read_total, cache_creation_total,
               cache_hit_ratio, turns, last_turn_ts, sessions, cwd, slug}
}}
```
- `cache_hit_ratio = cache_read / (input + cache_creation + cache_read)` — 플랜 §3.3 보정 반영.
- 최근 3 개 transcript 만 합산, 10 MiB tail 윈도, 15 MiB 파일 ~76ms.

**Watcher 통합** (`cmux-watcher/scripts/watcher-scan.py`)
- `do_scan()` 끝부분에서 `collect_all()` + `generate_alerts()` 호출 (try/except, W-6 non-blocking).
- `CACHE_INEFFICIENT` (cache_hit<50% & turns≥10) / `CONTEXT_LARGE` (input>200K) 경고를 기존 `WATCHER_ALERTS_FILE` report.alerts 에 MEDIUM 으로 병합.

**검증**
- 시뮬 13/13 PASS (원안 8 + 통합 5). 15MB tail 파싱 78ms (목표 500ms 대비 6배 여유).
- 실제 `~/.claude/projects` 18 slug 에 대해 `cmux-metrics.sh --refresh` 동작 확인 (최대 turns 1832, cache_hit 94~98% 구간).
- `~/.claude/skills/cmux-orchestrator/` 에 `cmux_paths.py`·`token_observer.py`·`cmux-metrics.sh`·`commands/cmux-metrics.md` 동기화 완료.

**Iron Law 준수**
- 경로는 `cmux_paths` SSOT ✓, 원자적 쓰기(`tempfile.mkstemp` + `os.replace` + flock sibling lock) ✓, watcher 루프 non-blocking ✓, AI 분기(`ai != "claude"` 조기 반환) ✓.

**제약 / 향후**
- surface ↔ cwd 매핑은 `cmux tree` 에 cwd 노출되지 않아 v1 은 slug-key 사용. 향후 `lsof` 기반 tty→pwd 보강 가능.
- Anthropic usage 필드 rename 대비 `SCHEMA_VERSION=1` 도입 — 변경 시 bumping + migration.

---

## 2026-04-19 (Phase 2.1 — Watcher Progressive Disclosure)

`cmux-watcher/SKILL.md` 가 839라인(~6272 토큰) 단일 파일로 모든 GATE/규칙/예시가 혼재 → 세션 시작 시 전량 context 주입되어 토큰 낭비. skillkit 의 3-layer progressive-disclosure 패턴으로 분리.

**구조 변경**
- `cmux-watcher/SKILL.md` 재작성: 839 → **152 라인** (~1399 토큰, **81.9% 라인 감소 / 77.7% 토큰 감소**).
  - 프론트매터 + 핵심 루프(W-8 요약) + 세션 시작 1-커맨드 + GATE 표(W-1~W-10) + Peer/감지/출력 간추림만 유지.
  - 모든 상세는 `references/` 로 이관, L1 은 네비게이션 역할.
- `cmux-watcher/SKILL.md.pre-phase2-1.bak` — 백업 (원본 839라인 보존).

**L2 파일 신규 (9개)**
- `cmux-watcher/references/gate-w-1.md` — IDLE Zero Tolerance
- `cmux-watcher/references/gate-w-2.md` — Error / Rate-Limit Immediate Alert (Phase 1.4 pool 연계)
- `cmux-watcher/references/gate-w-3.md` — Vision Verify IDLE (Layer 2/2.5 상세 + ANE 4기능 + Vision Diff 판정표)
- `cmux-watcher/references/gate-w-4.md` — Cooldown Respect (쿨다운 표)
- `cmux-watcher/references/gate-w-5.md` — Action-Only Report (우선순위/보고 시점 표)
- `cmux-watcher/references/gate-w-6.md` — Boss Never Blocked (백그라운드 운영 형태)
- `cmux-watcher/references/gate-w-7.md` — 질문 금지 (허용/금지 예시 + Phase 1.2 hook 연계)
- `cmux-watcher/references/gate-w-8.md` — 핵심 행동 사이클 (Adaptive Polling + PHASE 표 + 금지 행동)
- `cmux-watcher/references/gate-w-10.md` — IDLE 재배정 촉구 + Debounce (grace 30s, 재촉 2분)
- `cmux-watcher/references/gate-w-9.md` — 이미 Phase 1.2 에서 생성됨

**CI 가드**
- `tests/test_skill_md_structure.py` 신규. 4개 assertion:
  1. `test_skill_md_size_gate` — L1 200 라인 이하 강제.
  2. `test_gate_table_links_resolve` — GATE 표 링크가 실제 `references/gate-w-N.md` 파일로 해석.
  3. `test_all_gates_w1_through_w10_linked` — W-1~W-10 전부 표에 포함.
  4. `test_no_detailed_sections_leaked_to_l1` — `Step 1:`, 구체 OCR 커맨드 등 상세 예시가 L1 에 잔류하면 FAIL (regression guard).

**검증**
- 4/4 `test_skill_md_structure.py` PASS.
- 기존 `tests/test_watcher_scan.py` 7/7, `tests/test_cmux_utils.py` 9/9, `tests/test_redaction.py` 8/8 회귀 없음.
- 토큰 측정: before 839 lines / 25088 B / ~6272 tok → after 152 lines / 5597 B / ~1399 tok. 감소율 77.7% (DoD §7 목표 70~85% 범위 적합).
- `~/.claude/skills/cmux-watcher/` 설치 위치 동기화 완료 (SKILL.md + 10 references/gate-w-*.md).

**SSOT 기준**
- 각 GATE 정본은 해당 `references/gate-w-N.md` 1 개 파일. L1 표는 요약 1줄 + 링크.
- CI 가드가 향후 상세 내용이 L1 로 누수되면 자동 차단.

## 2026-04-19 (Phase 1.4 — Rate-limit pool SSOT)

`/tmp/cmux-rate-limited-pool.json` 이 프로토콜 문서에만 존재하고 실제 write 경로가 없었음 (orphan spec). Watcher가 RATE_LIMITED를 감지해도 Boss/dispatch가 참조할 데이터가 없어 rate-limited surface에 반복 배정 발생. GC 없으면 stale entry 누적으로 quota 회복 후에도 회피되는 2차 문제.

**추가**
- `cmux-orchestrator/scripts/rate_limit_pool.py` — pool CRUD + 3-tier GC SSOT 모듈. `upsert_entry / is_limited / list_limited / gc_expired / load` + CLI (`check / list / gc / dump`). 경로는 `cmux_paths.RATE_LIMITED_POOL_FILE` (env `CMUX_RATE_LIMITED_POOL_FILE` 오버라이드). MAX_ENTRIES=100 (초과 시 `detected_at` 오래된 순 축출), DEFAULT_TTL=3600s.
  - 동시성: 별도 sibling `.lock` 파일 + `fcntl.flock(LOCK_EX)` (pool 자체에 flock하면 atomic rename이 inode 교체해 잠금 무효화됨).
  - 손상 복원: JSON parse 실패 시 `.json.corrupt` 로 백업 후 빈 pool 재초기화, stderr 경고.

**연결**
- `cmux-watcher/scripts/watcher-scan.py:62-66` — `rate_limit_pool` import (ImportError fallback).
- `cmux-watcher/scripts/watcher-scan.py:951-963` — RATE_LIMITED 분기에서 `upsert_entry` 호출 (예외 시 `logging.warning` 으로 watcher crash 방지).
- `cmux-watcher/scripts/watcher-scan.py:1167-1174` — `generate_alerts` 반환 직전 `gc_expired()` 호출 (명시적 GC 주기 트리거).
- `cmux-orchestrator/scripts/smart-dispatch.sh:12-17` — Step 0 pool precheck (`rate_limit_pool.py check $SF` → exit 2면 즉시 return). 결과 JSON에 `source:"pool"` 마커.
- `cmux-orchestrator/scripts/idle-auto-dispatch.sh:237-242` — `dispatch_to_surface` 내부 pre-check (skip + log).

**검증**
- `/tmp/test_rate_limit_pool_real.py` — 실제 모듈 9/9 PASS (upsert/is_limited, TTL 0 만료, 덮어쓰기, 손상 JSON 복원, 100개 제한, 20 concurrent subprocess writer, gc_expired, CLI exit=2 limited, CLI exit=0 healthy).
- E2E 수동: `smart-dispatch.sh` pool hit → `{"status":"RATE_LIMITED","source":"pool"}` + exit 2 (cmux stub로 검증).
- `bash -n` 전 파일 통과. `python3 -c "import ast; ast.parse(...)"` rate_limit_pool.py + watcher-scan.py 통과.
- `tests/test_watcher_scan.py` 기존 7/7 회귀 없음. `tests/test_cmux_utils.py` 9/9, `tests/test_redaction.py` 8/8 통과.

**SSOT 기준**
- pool 파일 경로: `cmux_paths.py:89` 유일. 모든 소비자는 `rate_limit_pool` 모듈 경유.
- TTL/MAX_ENTRIES 상수: `rate_limit_pool.py` 유일.
- dispatch 차단 결정: `is_limited()` 유일 (exit 2 convention은 `smart-dispatch.sh:4` 기존 주석과 정합).

## 2026-04-19 (Phase 1.3 — ANE path SSOT)

`ane_tool` (Apple Neural Engine OCR 바이너리) 경로가 5개 호출자에 하드코딩되어 있어 위치 변경 시 전량 수정 필요. SSOT 리졸버로 통합.

**추가**
- `cmux-orchestrator/scripts/cmux_paths.py::ane_tool_path()` — CMUX_ANE_TOOL → ANE_TOOL → PATH lookup → `~/Ai/System/11_Modules/ane-cli/ane_tool` 순으로 실행 가능한 경로 반환. 미발견 시 None.
- `cmux-orchestrator/scripts/cmux-paths.sh::cmux_ane_tool` — 동일 정책의 bash 헬퍼. 미발견 시 빈 문자열 + exit 1.

**리팩터**
- `cmux-orchestrator/scripts/detect-surface-models.py:131-148`, `:238-244` — 2 곳 `os.path.expanduser(...)` 제거, `ane_tool_path()` 호출로 교체.
- `cmux-orchestrator/scripts/eagle_watcher.sh:18-29` — `ANE_TOOL` 환경변수 직접 참조 → `cmux_ane_tool` 헬퍼 호출 후 fallback.
- `cmux-orchestrator/scripts/vision-monitor.sh:8-19` — 동일 패턴.
- `cmux-watcher/scripts/watcher-scan.py:53-62` — 하드코딩 `Path.home() / "Ai"...` → `ane_tool_path()` 호출 (ImportError fallback 유지).
- `cmux-watcher/scripts/vision-stall-detector.py:20-30` — 동일.
- `cmux-watcher/scripts/surface-monitor.py:25-35` — 동일.

**검증**
- `python3 -m py_compile` + `bash -n` 전 파일 통과.
- `/tmp/test_ane_path_real.py` — 실제 `cmux_paths.ane_tool_path()` 로 7/7 PASS (env 우선순위, PATH 발견, 비실행 파일 fallthrough, 빈 env 스킵).
- bash 헬퍼 3-tier 수동 확인 PASS.
- `python3 tests/test_watcher_scan.py` 기존 7/7 회귀 없음.

**SSOT 기준**
- 하드코딩 grep: `grep -rn "Ai/System/11_Modules/ane-cli"` → references md + SKILL.md 문서 멘션만 (런타임 코드 0건).
- 문서 경로 멘션은 사용자 안내용으로 의도적 유지.

## 2026-04-19 (Phase 1.2 — GATE W-9 send-guard)

Worker/Watcher 역할이 동료 surface에 `/new` 또는 `/clear`를 `tmux send-keys` / `cmux send-keys` 로 전송하지 못하도록 PreToolUse:Bash 훅으로 차단. 세션 리셋은 Boss 권한이라는 개입 금지 원칙(GATE W-9)을 훅 차원에서 강제.

**추가**
- `cmux-orchestrator/hooks/cmux-send-guard.py` — PreToolUse:Bash, `permissionDecision:"deny"`. `cmux identify` + `/tmp/cmux-roles.json` 으로 현재 역할 판정, `tmux|cmux send-keys -t <target> ... /new|/clear ...` 패턴 매칭. 자기 surface·변수 치환·비-send-keys는 fail-open 통과.
- `cmux-watcher/references/gate-w-9.md` — 규칙 본문. 훅 deny 메시지가 이 경로를 안내.
- `cmux-orchestrator/install.sh`, `cmux-orchestrator/activation-hook.sh` HOOK_MAP 에 등록 (`"PreToolUse", "Bash", 3`).

**검증**
- `python3 -m py_compile cmux-orchestrator/hooks/cmux-send-guard.py` 통과.
- 통합 테스트 `/tmp/test_cmux_send_guard_hook.py` — 실제 훅에 stdin JSON 주입, 임시 PATH 에 `cmux` stub 배치, 10/10 PASS (worker/watcher deny, boss/self/변수/non-send-keys/orch-off/non-Bash allow).
- 단위 시뮬레이션 `/tmp/test_cmux_send_guard.py` 8/8 PASS.

## 2026-04-19 (Hook schema migration — SyncHookJSONOutputSchema 전수 정합)

**PreToolUse:Bash hook "Invalid input" 에러 연속 발생 근본 해결 (PR #8 + PR #9).**

Claude Code 코어 `SyncHookJSONOutputSchema` (coreSchemas.ts:907) 위반 전수 수정. top-level 허용 키는 `{continue, suppressOutput, stopReason, decision("approve"|"block" 레거시), systemMessage, reason, hookSpecificOutput}` 뿐이며, 모든 permission/context 주입은 `hookSpecificOutput` 안에 위치해야 한다.

**Tier A — decision:"allow" 제거 (PR #8)**
- 훅 pass-through는 `exit 0 + 빈 stdout`이 정본. `{"decision":"allow"}`는 decision enum 밖이므로 즉시 validation 실패. `cmux-read-guard.sh` 외 다수 훅에서 제거.

**Tier B — 레거시 decision:"approve"|"block" → permissionDecision (PR #8)**
- PreToolUse 차단/승인을 `hookSpecificOutput.permissionDecision:"deny"|"allow"` + `permissionDecisionReason`으로 이관.

**Tier C — PostToolUse 경고 → additionalContext (PR #8)**
- `cmux-enforcement-escalator.py`, `cmux-idle-reuse-enforcer.py`, `cmux-setbuffer-fallback.py`의 systemMessage 스타일 → `hookSpecificOutput.hookEventName:"PostToolUse"` + `additionalContext` 이관. `cmux-dispatch-notify.sh`, `cmux-memory-recorder.sh`도 pass-through로 정리.

**Phase 4 — hook_output SSOT 헬퍼 추출 (PR #8)**
- `cmux-orchestrator/scripts/hook_output.py` 신규 — `deny_pretool()`, `ask_pretool()`, `allow_pretool_with_updated_input()`, `inject_posttool_context()`, `warn()`. 13개 Python 훅이 `from hook_output import deny_pretool as deny` 방식으로 호출.
- `cmux-orchestrator/scripts/hook_output.sh` 신규 — bash 동반 헬퍼. env var heredoc 패턴으로 `hook_deny_pretool`, `hook_ask_pretool`, `hook_allow_pretool_cmd`, `hook_inject_posttool`, `hook_warn` 제공.

**Tier D — gate-blocker.sh + 참조 문서 (PR #9)**
- `cmux-orchestrator/scripts/gate-blocker.sh` — 5개 `echo '{"decision":"block",...}'` → `hook_deny_pretool`. `hook_output.sh` SSOT 소스 사용.
- `cmux-orchestrator/references/gate-enforcement.md` — "gate-blocker.sh가 PreToolUse 훅으로 등록됨" 잘못된 주장 정정 (실제로는 settings.json 미등록 통합 게이트 참조 스크립트). 예시 블록을 modern 스키마로 갱신.
- `cmux-orchestrator/references/gate-matrix.md` — Legend를 `hookSpecificOutput.permissionDecision` / `additionalContext` 현재 스키마로 교체.

**Tier E — 시뮬레이션 검증으로 발견한 top-level additionalContext (PR #9)**
- `/tmp/hook-schema-sim.py`로 등록 21개 훅 × 4 시나리오(A:orch-off / B:benign / C:git-commit / D:bad-stdin) = 84회 실행 후 7건 스키마 위반 추가 발견.
- `cmux-orchestrator/hooks/cmux-model-profile-hook.sh` (SessionStart) — heredoc `{"additionalContext":"..."}` → `hookSpecificOutput.hookEventName:"SessionStart"` 래핑.
- `cmux-orchestrator/hooks/cmux-idle-reminder.sh` (UserPromptSubmit) — IDLE/WAITING heredoc 2곳 → `hookSpecificOutput.hookEventName:"UserPromptSubmit"` 래핑.

**검증**
- ast.parse / `bash -n` 전 훅 OK.
- pass-through 시뮬레이션 (orch-off) 전 훅 빈 stdout + exit 0.
- deny-shape 엔드투엔드 테스트 (gate-blocker + leceipts-gate + control-tower-guard) modern JSON 출력 확인.
- 최종 시뮬레이션: **81 pass / 0 fail** (이전 74 pass / 7 fail).
- 잔존 legacy `"decision":"(approve|block|allow)"` grep: 의도적 SSOT docstring 경고 3건뿐.
- 설치 위치 `/Users/csm/.claude/skills/cmux-orchestrator/` 동기화 완료.

## 2026-04-15 (leceipts artifact gate + detect_surfaces archive + Boss role minimal)

**외부 리뷰 Conditional Go 4 Phase 중 3/4 Phase + Phase 1/2 축소판 실행. (PR #6)**

**Phase 4 — leceipts artifact gate (vendored)**
- `scripts/leceipts/check-reports.ts` — upstream `0oooooooo0/leceipts` (MIT) 1:1 vendor. 5-section 보고서 린터 (Root cause / Change / Recurrence prevention / Verification / Remaining risk).
- `scripts/leceipts/{LICENSE,README.md}` — MIT 사본 + 출처/핀(md5 64a4f9bdbc1b0092558fc4bcb3c6ac21, upstream mtime 2026-04-11 16:22) + 업그레이드 가이드 + 책임 경계.
- 루트 `verification-kit.config.json` — reportsDir=plans, reportPattern=`-verification-report\.md$`.
- 루트 `package.json` — `"private": true`, tsx/@types/node devDependency, `leceipts:check{,:all,:file}` npm scripts.
- `.gitignore` — `node_modules/`, `package-lock.json` 추가.
- `plans/verification-report-template.md` — upstream template 1:1.
- `docs/04-development/test-guide.md` — "Verification Report Gate (leceipts)" 섹션 추가. runtime checker(`cmux-orchestrator/scripts/leceipts-checker.py`)와 artifact checker 책임 경계 명시.

**Phase 3 — detect_surfaces.py archive**
- `cmux-orchestrator/scripts/detect_surfaces.py` → `docs/99-archive/scripts/detect_surfaces.py` (git mv + archive header comment).
- 근거: 활성 소비자 0건. `is_boss_surface()`가 `cmux-orchestrator/scripts/cmux_utils.py:119`에 이미 SSOT로 존재.

**Phase 2 — Boss role SSOT 축소 정렬**
- `docs/00-overview.md:23` — "Boss/Main: 디스패치, 수집, 커밋" → "Boss: 디스패치, 수집, 커밋".
- `cmux-orchestrator/hooks/cmux-stop-guard.sh:4` — "메인에 /cmux 엔터" → "Boss에 /cmux 엔터".
- 브로더 Phase 1/2 (`cmux-watcher/SKILL.md`, `eagle-patterns.md`, `subagent-definitions.md`, `worker-protocol.md`, `worktree-workflow.md`, `cmux-no-stall-enforcer.py`)는 병렬 세션의 runtime dir SSOT 마이그레이션에 위임.

**검증**
- `npm install` → 7 packages, 0 vulnerabilities.
- `npm run leceipts:check:all` → 6/6 pass.
- `python3 -m pytest tests -q` → 80 passed, 6 failed (baseline regression 0; 실패 6건 전부 pre-existing `test_watcher_scan.py`, 본 PR 무관).
- `bash -n cmux-stop-guard.sh`, `py_compile detect_surfaces.py` OK.

## 2026-04-14 (Watcher Windows-native fallback hardening)

- `watcher-scan.py`에 `read_surface_text()`를 추가해 `bash read-surface.sh` 실패 시 `cmux capture-pane/read-screen` native fallback으로 surface 텍스트를 읽도록 보강.
- `watcher-scan.py`의 watcher heartbeat를 `role-register.sh` 경로 + JSON 직접 갱신 fallback 이중 경로로 보강 (`bash` 미존재 환경 대응).
- `watcher-scan.py`에서 남아 있던 literal `subprocess.run(["cmux", ...])` 호출을 공통 `run_cmd()` 경로로 통합해 `cmuxw` 라우팅 누락 지점 제거.
- 원자적 파일 교체를 `os.replace()`로 정리하여 Windows에서 기존 파일 overwrite 실패 가능성 완화.
- pipe-pane 상태 파일 SSOT를 `cmux-pipe-pane-installed.json`으로 정렬 (`activation-hook.sh`, `cmux-watcher-session.sh`).
- 회귀 테스트 확장: `tests/test_watcher_scan.py` 4 → 7 (`bash` 없는 fallback, heartbeat direct fallback, literal subprocess cmux 재유입 차단).
- 문서 동기화: `README.md`, `docs/03-operations/cross-platform.md`, `docs/04-development/test-guide.md`.
- README Cross-Platform 섹션에 공식 바이너리 소스 명시: macOS [`manaflow-ai/cmux`](https://github.com/manaflow-ai/cmux), Windows [`scokeepa/cmuxw`](https://github.com/scokeepa/cmuxw).
- 브랜딩 리뉴얼: 프로젝트 명칭을 `cmuxO`로 표기하고 README 상단에 신규 SVG 로고(`assets/cmux-o-mark.svg`) + 슬로건(`cmux Orchestration JARVIS Watcher Pack`) 반영.
- README 본문 브랜드 톤 정렬: 컴포넌트 표기와 구조 설명을 `cmuxO` 네이밍(`cmuxO Orchestrator Core`, `cmuxO Watcher Engine`, `cmuxO JARVIS Core`)으로 통일.
- 루트 최상단 로고 파일 `cmuxO-logo.svg` 추가 후 README 최상단에서 해당 파일을 직접 참조하도록 변경.
- README 다국어 진입점 추가: 영어 `README.md`와 한국어 `README.ko.md`를 상단 링크로 상호 이동 가능하도록 구성.

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
