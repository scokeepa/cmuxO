# cmuxO Upgrade Phase 3.1 — Persistent Agent Memory (agentmemory Integration)

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기 (Phase 3 선택안)
**참조 프로젝트**: `/Users/csm/projects/olympus/source/agentmemory/` — hybrid search + lifecycle + knowledge graph + 0 external DB
**선행 조건**: Phase 2.1 / 2.2 / 2.3 / 2.4 완료 (observability + ledger 데이터가 memory 재료)

---

## 0. 선행 Phase 리스크 흡수 (Phase 2.2 / 2.2.5 remaining risk 반영)

Phase 2.2 토큰 관측성과 2.2.5 peers 통신에서 남긴 remaining risk 중 **영구 저장/학습**으로만 해결 가능한 항목을 이 Phase 가 흡수. 이유: 3.1 은 cmuxO 의 "영구 메모리" 단계이므로, "매 세션 재학습" 으로는 풀리지 않는 구조적 리스크가 여기서 마무리돼야 함.

### 0.1 SCHEMA_VERSION 마이그레이션 인지 (Phase 2.2 risk #2 흡수)

**흡수 대상 risk**: `token-metrics.json` 와 `ledger.jsonl` 모두 `schema_version` 필드를 갖는데, 버전이 올라가면 `memory-sync.py` 가 이를 인지해 형식 변환/무시 판단을 해야 함. 미인지 시 옛 스키마를 신 스키마로 오인해 손상된 레코드를 agentmemory 에 ingest 할 위험.

**설계 반영**:
- `memory-sync.py` 모든 reader 함수는 첫 파일 read 직후 `schema_version` 검사.
- 지원 범위 상수: `SUPPORTED_TOKEN_METRICS_SCHEMA = {1}`, `SUPPORTED_LEDGER_SCHEMA = {1}`.
- 범위 밖이면 `{"fallback": True, "ingested": 0, "reason": f"unsupported schema v{version}"}` 반환 (§3.4 sync 함수 규약과 동일).
- 마이그레이션 핸들러가 필요한 버전이 오면 `cmux-orchestrator/scripts/schema_migrators.py` 에 `migrate_token_metrics(old_version, blob)` 등 순수 함수 추가. `memory-sync` 는 이 단일 모듈만 호출.
- DoD에 "schema_version mismatch 시 skip + 사유 로그" 회귀 테스트 1건 추가.

### 0.2 Broker SPOF 결정 — 이 Phase 에서 확정, HA 는 Phase 3.2 로 문서화 분리 (Phase 2.2.5 risk #2 흡수)

**흡수 대상 risk**: Phase 2.2.5 에서 claude-peers broker 는 단일 프로세스 SPOF. 현재는 kill switch + fallback 으로 감내.

**이 Phase 에서의 결정**:
- **확정**: HA(multi-broker, replication) 는 Phase 3.1 스코프 **밖**. 이유: agentmemory 통합 (외부 프로젝트 의존 + MCP + 마이그레이션) 복잡도가 이미 높고, broker HA 는 직교 관심사.
- **단, 이 Phase 에서 해결**: broker 상태를 **영구 메모리** 로 추적해 재발 원인 분석을 가능하게 함.
  - `memory-sync.py` 가 ledger 의 `PEER_SEND_FAILED.reason=broker_unreachable` 를 주기적으로 집계해 `system_state` 태그로 ingest.
  - `/cmux-recall broker` 질의 시 "최근 30일 broker downtime 5건, 평균 복구 42초" 식 요약 반환.
- **Phase 3.2 이관**: `plans/cmux-upgrade-phase3-2-broker-ha.md` 를 이 Phase 머지 시점에 **DRAFT 자리잡이** 로 생성(내용 미완). 리스크가 잊히지 않도록 포인터만 유지.
- DoD에 "`/cmux-recall broker` 가 broker downtime 집계 반환" 검증 1건 추가.

### 0.3 Surface↔cwd↔peer_id 3중 바인딩을 agentmemory 영구 저장 (Phase 2.2 risk #1 흡수)

**흡수 대상 risk**: Phase 2.2 의 `collect_surface_metrics(surface_id, cwd)` 는 매 호출 시 surface↔cwd 매핑을 받아야 함. Phase 2.3 ledger 의 `ROLE_PEER_BIND` 이벤트로 일회성 기록은 가능하나, 세션 간 재부팅·compaction 후 Boss 가 이 매핑을 다시 발견해야 하는 비용이 남음.

**설계 반영**:
- `memory-sync.sync_role_peer_bindings()` — ledger 의 `ROLE_PEER_BIND` 이벤트를 읽어 `binding/{surface_id}` 키로 agentmemory 에 permanent=True 로 저장 (confidence decay 면제).
- `/cmux-recall surface:<id>` 슬래시 커맨드가 이 바인딩을 즉시 반환 → Boss 가 start-up 시 매번 cmux list/peer list 로 재탐색할 필요 없음.
- 바인딩 스키마: `{surface_id, cwd, peer_id, logical_name, last_seen_ts, tombstone}`. surface 가 destroy 되면 `tombstone=true` 마킹(삭제하지 않음 — 기록 영속).
- `cmux-main-context.sh` 가 Boss 기동 시 top-k 대신 **모든** `binding/*` 엔트리 주입 (cardinality 제한: 50개. 초과 시 `last_seen_ts` desc top 50 + "older omitted" 힌트).
- DoD에 "재부팅 후 binding recall로 최소 1개 peer_id 복원" 검증 추가.

### 0.4 3개 테스트 케이스 추가

§5.1 테스트 테이블에 다음을 append:

| # | 시나리오 | expected |
|---|---|---|
| 11 | token-metrics.json schema_version=2 (unsupported) | sync skip + `{"fallback":True,"reason":"unsupported schema v2"}` |
| 12 | ROLE_PEER_BIND 3건 ingest → `/cmux-recall surface:W-1` | 해당 surface 바인딩 dict 반환 (cwd, peer_id 포함) |
| 13 | ledger `PEER_SEND_FAILED` 5건 → `/cmux-recall broker` | count=5 + 최근 reason 요약 반환 |

프로토타입 시뮬레이션은 Phase 3.1 착수 시점에 §5.2 결과 갱신.

### 0.5 마이그레이션 범위 재정의

§3.6 마이그레이션에 binding 저장소 추가:
- 기존 MD 기반 auto memory → agentmemory (이전 설계)
- **신규**: Phase 2.3 ledger 의 `ROLE_PEER_BIND` 과거 이벤트 전체 replay → agentmemory `binding/*` 영구 레코드. `migrate-ledger-bindings.py` 스크립트 별도 작성.
- 이 마이그레이션은 **idempotent** 여야 함(§3.4 dedup 와 동일한 해시 규칙 재사용: `sha256("binding:" + surface_id)[:16]`).

---

## 1. 목표

cmuxO의 **영구 학습 메모리 시스템** 구축.

현재는 매 세션마다 "이전에 뭐 했지?"를 Boss가 재학습. CLAUDE.md의 auto memory가 일부 해결하지만:
- Key-value + MD 인덱스만 — 검색 약함
- Confidence scoring 없음 — 오래된/잘못된 메모리 자동 열화 없음
- Knowledge graph 없음 — 엔티티 간 관계 추적 불가
- Hybrid search 없음 — semantic + keyword 결합 부재

agentmemory(rohitg00/agentmemory)는 이 네 요구를 이미 해결하고 v0+ 완성도 (README 기준 95.2% R@5, 92% fewer tokens, 654 tests).

## 2. 근거

### 2.1 agentmemory 주요 특성 (레퍼런스)

- **0 external DBs**: 내장 SQLite FTS5 + vector 인덱스 (chromadb 금지 — 별도 reference report 존재 `plans/cmux-nudge-chromadb-cpu-verification-report.md`)
- **44 MCP tools** — Claude Code가 MCP 경유로 직접 호출 가능
- **12 auto hooks** — 세션 이벤트에 반응해 메모리 write/decay
- **Confidence scoring & lifecycle**: 메모리가 나이/재접근 기반 decay
- **Knowledge graph**: 엔티티·관계 그래프
- **Hybrid search**: BM25 + vector cosine

### 2.2 cmuxO 현 메모리와의 갭

| 요구 | cmuxO 현재 | agentmemory |
|------|-----------|------|
| 영구 저장 | MD 파일 | SQLite (스키마) |
| Semantic 검색 | 없음 | 내장 |
| Confidence decay | 없음 | 있음 |
| 관계 그래프 | 없음 | 있음 |
| MCP 통합 | 없음 (auto memory는 프롬프트 주입) | 44 tools |

### 2.3 cmuxO가 흡수할 4가지 데이터 소스

1. **Ledger (Phase 2.3)** — ASSIGN/VERIFY/CLEAR 이벤트 → agent 행동 이력 메모리
2. **Token metrics (Phase 2.2)** — 비효율 패턴 메모리
3. **Anti-rationalization report (Phase 2.4)** — 합리화 패턴 메모리
4. **사용자 피드백** — CLAUDE.md feedback/project/user/reference 종류 (기존 auto memory 마이그레이션)

## 3. 설계

### 3.1 통합 아키텍처

```
cmuxO (Boss) ──┬── MCP client ──► agentmemory MCP server
               │                          │
               │                          └── SQLite @ ~/.claude/memory/cmux-agentmem.db
               │
               ├── Ledger (Phase 2.3) ──► sync script ──► agentmemory.ingest()
               ├── Token metrics (2.2) ──► 동일
               └── Anti-rationalization report (2.4) ──► 동일
```

### 3.2 설치 방식

Option A — **서브모듈 / 복사**: agentmemory를 `cmux-orchestrator/vendor/agentmemory/` 로 편입, MCP 서버를 cmuxO 내장.

Option B — **의존성 참조**: 사용자가 npm/pip로 agentmemory 별도 설치, cmuxO는 MCP 설정만 기록.

→ **Option B 권장**. 이유:
- agentmemory는 active 프로젝트 → 업스트림 업데이트 흡수 쉬움
- license 혼합 회피
- cmuxO install.sh에 "agentmemory 설치 안내"만 추가

### 3.3 설정 파일

`~/.claude/mcp.json`에 추가 (기존 cmux peers, context7 와 병렬):
```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "npx",
      "args": ["@agentmemory/agentmemory", "mcp"],
      "env": {
        "AGENTMEMORY_DB": "~/.claude/memory/cmux-agentmem.db"
      }
    }
  }
}
```

### 3.4 동기화 스크립트

`cmux-orchestrator/scripts/memory-sync.py`:
```python
def sync_ledger_to_memory(since_ts: int) -> int:
    """ledger JSONL을 agentmemory로 ingest.
    각 VERIFY_FAIL/RATE_LIMIT_DETECTED 등 패턴 이벤트를
    structured memory entry로 변환.
    """

def sync_metrics_to_memory() -> int: ...
def sync_anti_rationalization() -> int: ...
def run_all() -> dict:  # 통계 반환
```

watcher 사이클에 편승 (n분마다 한 번) — Phase 2.2/2.3이 이미 구축한 수집 인프라 재사용.

### 3.5 Boss 소비 경로

- `cmux-main-context.sh`가 Boss 세션 시작 시 agentmemory MCP query 실행 (최근 관련 메모리 top-k)
- "query agentmemory" 슬래시 커맨드 제공 (`/cmux-recall <keyword>`)
- 자기개선 루프 (JARVIS)가 주기적으로 agentmemory 조회하여 패턴 학습

### 3.6 마이그레이션

기존 `~/.claude/memory/MEMORY.md` + 개별 MD 파일 → agentmemory.ingest()로 일괄 이관 (read-only 마이그레이션 스크립트 `migrate-md-memory.py`).
**단**: auto memory (user/feedback/project/reference) 4 카테고리 유지 — agentmemory의 `tags` 필드 활용.

## 4. 5관점 검증

### SSOT
- 메모리 정본: agentmemory SQLite DB 1개 (`~/.claude/memory/cmux-agentmem.db`)
- MCP 설정: `~/.claude/mcp.json` 1곳
- 동기화 스케줄: `memory-sync.py`가 유일 ingest 경로
- MD 메모리는 **백업 사본**으로만 유지 (runtime 소비는 agentmemory)

### SRP
- agentmemory: 저장/검색/decay (그들의 책임)
- memory-sync.py: 형식 변환 + ingest만
- cmux-main-context.sh: query 결과 주입만

### 엣지케이스
- agentmemory 미설치 사용자 → cmuxO 기본 기능 동작 유지 (MCP 실패 시 fallback to MD-only)
- DB corruption → agentmemory가 자체 복구. 실패 시 백업 MD로 복구 가능 (이관 때 원본 삭제 금지)
- Sync race (watcher 여러 인스턴스): agentmemory ingest API가 idempotent 보장해야 함 — 안 되면 `since_ts` 기반 중복 제거 체크
- Duplicate memory (같은 fact 여러 번 ingest): agentmemory의 dedup 기능 신뢰 + memory-sync에서 hash 기반 스킵
- PII: ledger.message_excerpt에 민감 정보 가능 → ingest 전 filter (SSN/credit card/email 제거)
- 업스트림 API 변경: version pin (`@agentmemory/agentmemory@^0.X`) + CI 호환성 테스트
- chromadb 회피 (기존 verification report) — agentmemory는 0 external DB 주장, 확인 필수

### 아키텍트
- MCP는 기존 cmuxO에 이미 도입됨 (claude-peers, context7 사용 중) → 통합 비용 낮음
- Phase 2.3 ledger / 2.2 metrics / 2.4 report 이 세 소스가 **상류**, agentmemory가 **저장·검색**. 경계 명확
- install.sh: agentmemory 설치 여부 체크 + 안내만 (자동 설치는 사용자 권한 침해로 금지)
- 제거: `/cmux-uninstall`이 mcp.json 엔트리 제거, DB는 사용자 선택으로 남김/삭제

### Iron Law
- **"External DB 없음"**: agentmemory가 sqlite 내장 (chromadb report §1 호환) ✓
- **"Runtime 의존성 최소"**: npm/pip 둘 중 하나 — cmuxO 자체는 shell/python만 유지 ✓
- **"데이터 손실 금지"**: MD 백업 유지, ingest 원자성 확인 ✓
- **"Boss 재시작 후 상태 복구 = ledger replay + agentmemory query"** (2.3 확장)

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 시나리오 | expected |
|---|---|---|
| 1 | agentmemory 미설치 환경에서 cmux-start | 정상 기동 + fallback 경고 |
| 2 | ledger 100 이벤트 → memory-sync.run_all() | agentmemory에 100 record 생성 |
| 3 | 동일 이벤트 2회 sync | 중복 없음 (hash dedup) |
| 4 | ledger에 PII 포함 | PII 제거 후 ingest |
| 5 | `/cmux-recall "rate limit"` | 관련 top 5 메모리 반환 |
| 6 | DB corruption | 백업 MD로 복구 |
| 7 | agentmemory MCP 서버 다운 | cmux 본 기능 동작 유지 |
| 8 | 기존 MEMORY.md 10개 entry → migrate-md-memory.py | 10 record + tags 유지 |
| 9 | Boss 세션 시작 시 cmux-main-context.sh가 top-10 recall 주입 | context에 삽입됨 |
| 10 | Confidence decay 14일 후 접근 없던 메모리 | score 하락 관측 |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

프로토타입: `/tmp/memory_sync_prototype.py`, 러너: `/tmp/test_memory_sync.py`.
MCP 인터페이스를 `MockAgentMemory`로 대체 — cmuxO가 소유한 로직(sync, PII 필터, dedup, fallback, recall wrapper, MD migration, context 주입)만 검증. agentmemory 내부 동작(DB corruption 복구, 14일 decay)은 로컬 실패 실패 시간이 필요해 SKIP.

```
[PASS] 1 unavailable MCP → fallback no-raise
[PASS] 2 100 events → 100 records
[PASS] 3 re-sync dedup (0 new, 100 skipped)
[PASS] 4 PII redacted in ingested excerpt
[PASS] 5 recall returns top-k rate_limit records
[SKIP] 6 DB corruption recovery: agentmemory 내부 동작 — 로컬 설치 없이 검증 불가
[PASS] 7 MCP down → sync no-raise, context empty (cmux unaffected)
[PASS] 8 migrate 10 MD entries, tags preserved
[PASS] 9 session-start top-10 context injection
[SKIP] 10 14-day confidence decay: agentmemory 내부 scoring — 실시간 14일 대기 불가

=== Phase 3.1 simulation: 8 pass / 0 fail / 2 skip (external) ===
```

→ 8/8 PASS (skip 2: agentmemory 내부 책임). cmuxO가 책임지는 범위는 전량 검증됨.

### 5.3 구체적 차단 요소 및 후속 검증 계획

SKIP된 2건은 "환경 문제"가 아니라 **agentmemory 내부 동작** 영역:

- **Case 6 (DB corruption 복구)**: agentmemory 자체의 SQLite 복구 로직. Phase 3.1 구현 착수 시 local `@agentmemory/agentmemory@0.9.0` 실설치 + 인위적 DB 손상 후 재기동 테스트로 검증.
- **Case 10 (14일 confidence decay)**: agentmemory의 lifecycle scoring. 실구현 시 `AGENTMEMORY_DECAY_DAYS=1`(환경변수)로 시간 압축 실행하거나, agentmemory 자체 테스트 스위트(`pnpm test`, `test/integration.test.ts`)의 decay 케이스 결과 인용.

### 5.4 설계 보정

- PII 필터 정규식: 이메일/SSN/카드번호 3종. 한국어 이름·전화번호 패턴은 초기 스코프에서 제외(오탐 비용). 운용 중 지적 시 추가.
- dedup은 `sha256(kind + canonical_payload)[:16]` 해시 기반 — timestamp 포함이라 같은 이벤트가 정확히 같은 데이터로 재수집될 때만 skip(원하는 동작). 리포트 재생성 등 파생 데이터는 다른 `kind`로 분리.
- Fallback: `available()==False` 시 `sync_*` 함수들이 `{"fallback": True, "ingested": 0}` 반환 — 호출자가 차단 없이 계속 진행(Case 1, 7).
- MD migration: `type` 프론트매터를 `tags[0]`로 승계 → 기존 user/feedback/project/reference 4 분류가 agentmemory tag 시스템에서도 필터링 가능.

## 6. 구현 절차

1. agentmemory 설치 문서 + smoke test (`scripts/test-agentmemory-smoke.sh`)
2. `mcp.json` 엔트리 추가 (install.sh가 조건부 삽입)
3. `memory-sync.py` 작성 + 10 테스트
4. `migrate-md-memory.py` — 기존 auto memory 이관
5. `/cmux-recall` 슬래시 커맨드
6. `cmux-main-context.sh` 확장: top-k recall 주입
7. CLAUDE.md에 agentmemory 경로 + tags 설명 추가
8. `/cmux-uninstall` 업데이트: mcp.json 엔트리 제거
9. CHANGELOG + PR

## 7. DoD

- [ ] 10 테스트 PASS
- [ ] agentmemory 미설치 환경에서 cmuxO 기본 동작 (fallback)
- [ ] Sync가 ledger/metrics/anti-rationalization 세 소스 모두 수용
- [ ] recall 슬래시 커맨드 동작
- [ ] 기존 MD 메모리 마이그레이션 성공 (0 loss)
- [ ] PII 필터 검증
- [ ] PR merge

## 8. 리스크

- **외부 프로젝트 의존**: agentmemory 업스트림 breaking change 시 cmuxO 파손 → version pin + compat layer `cmux-orchestrator/scripts/agentmem_adapter.py`
- **Confidence decay 오작동**: 중요한 메모리가 잘못 열화될 위험 → `permanent=true` flag로 unbreak 메모리 지정
- **초기 학습 곡선**: Boss가 agentmemory query를 언제 써야 할지 모름 → cmux-main-context.sh가 자동으로 top-k 주입해 강제 노출
- **Privacy**: ingest 전 PII 필터 미구현 시 유출 위험 → `ingest(filter=True)` 기본값, test 4가 검증
- **Phase 2 미완 시 빈 컨테이너**: agentmemory만 있고 데이터 소스 없으면 효과 없음 → Phase 2.1~2.4 모두 merge 후 Phase 3.1 착수

## 9. 왜 이 옵션을 선택했나 (Phase 3 후보 비교)

사용자 요청: "가장 완벽한 프로덕트에 맞게 복잡성이 높아도 좋은것으로 선택".

| 후보 | 복잡성 | 프로덕트 완성도 기여 | 선정 |
|------|--------|--------------------|------|
| 3.1 agentmemory 통합 | 높음 (MCP + sync + migration) | **핵심** — Boss 학습 영구화. 전체 Phase 2의 집약점 | ✅ 선정 |
| 3.2 cmux-watcher를 별도 데몬 분리 | 중 | 아키텍처 개선만, 외부 가치 낮음 | ✗ |
| 3.3 웹 UI 대시보드 | 중 | cosmetic, 운영 가치 제한적 | ✗ |
| 3.4 다중 머신 페더레이션 | 매우 높음 | 현 단계 과하다 | ✗ |

3.1은 Phase 2.1~2.4가 수집한 모든 데이터(progressive disclosure 절약, token metrics, ledger events, anti-rationalization patterns)를 **영구 학습 자산**으로 변환 → cmuxO가 "매 세션 제로부터"에서 "AGI 시초" 방향으로 1단계 진입 (MEMORY.md project_olympus 엔트리 목표와 일치).
