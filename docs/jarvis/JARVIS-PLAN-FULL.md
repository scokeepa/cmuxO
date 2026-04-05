# JARVIS: 능동형 시스템 관리자 + 설정 진화 엔진

## Context

컨트롤 타워 3 Pane: Main(사장) + Watcher(감사실) + **JARVIS(시스템 관리자)**
아이언맨의 자비스처럼 능동적으로 오케스트레이션을 감시하고 설정을 진화시키는 시스템 관리자.

## 핵심 아키텍처 원칙 (5관점 리뷰 반영)

### 단일 정본 원칙 (FIX-01)
```
Phase 1:                          Phase 3 (Basic Memory 추가 시):
                                                      ┌─ 읽기 ─┐
JARVIS ──쓰기──→ 마크다운 파일    JARVIS ──쓰기──→ Obsidian 볼트
                    │                                 │
                    ↓                                 ↓ (WatchService)
              sqlite3 CLI FTS5                  SQLite + 벡터
                                                      │
                                                      ↓ (Sync/Git)
                                                 클라우드 백업
```
- **모든 쓰기는 마크다운 파일로** (Obsidian 볼트 디렉토리)
- SQLite는 검색 인덱스일 뿐, 정본이 아님 (split-brain 방지)
- Basic Memory SyncService가 파일→DB 단방향 동기화
- 사용자의 Obsidian 직접 편집도 WatchService가 자동 반영

### GATE 이중 강제 (FIX-02)
- SKILL.md 텍스트 제약 + **PreToolUse hook 하드 강제** (cmux-jarvis-gate.sh)
- 프롬프트만으로는 GATE 우회 가능 → hook이 경로 차단으로 100% 보장
- 진화 중 /freeze 패턴으로 settings.json 보호
  - **기본: warn 모드** — "진화 중입니다. 변경 시 JSON Patch 충돌 가능. 계속?" → 사용자 선택
  - deny 모드는 CRITICAL 진화(시스템 안정성)에만 적용
  - 사용자 긴급 변경 허용 + JARVIS에 알림 (CV-04)

### 진화 안전 제한 (FIX-03, FIX-05)
- **직렬 실행 전용** — 동시 진화 금지 (CURRENT_LOCK 파일)
- **MAX_CONSECUTIVE_EVOLUTIONS = 3** — 4회째부터 사용자 승인 필수
- **MAX_DAILY_EVOLUTIONS = 10** — 일일 상한 도달 시 중단
- 동일 설정 영역 3회 반복 → 근본 원인 재분석 에스컬레이션

### Worker 권한 분리 (FIX-04)
- Evolution Worker는 **변경 "제안"만** 생성 (proposed-settings.json)
- **JARVIS만** 설정 파일 적용 가능 (검증 + 사용자 승인 후)
- Worker의 Write/Edit은 evolutions/ 내부로 제한 (hook 강제)

### 2모드 아키텍처 (FATAL-A3 해결 — Obsidian 필수 vs 선택 모순 해소)
```
모드 A (Obsidian 활성): 정본 = {OBSIDIAN_VAULT}/JARVIS/ 마크다운
모드 B (Obsidian 없음): 정본 = ~/.claude/cmux-jarvis/ 마크다운
공통: 마크다운 = 정본, SQLite = FTS5 검색 캐시 (sqlite3 CLI, Python 불필요)
```
- config.json의 `obsidian_vault_path`가 설정되어 있으면 모드 A, 없으면 모드 B
- Basic Memory MCP는 Phase 3 선택적 기능 (Python 의존성 → 강제 안 함)
- Phase 1은 **sqlite3 CLI + 자체 FTS5** (macOS 내장, 추가 설치 없음)

### 승인 + 큐 관리 (IL1-V2, IL1-V3)
- 승인 요청은 **구조화된 선택지만** 인정: `[수립][보류][폐기]` 또는 `[실행][수정][폐기]`
- free-text ("OK", "음...", "좋아") → 승인으로 자동 해석 금지
- 승인 타임아웃: **30분** → 자동 "보류" → 다음 접속 시 리마인드
- 진화 큐 크기: **최대 5건** → 초과 시 우선순위 낮은 것 자동 폐기 + 사유 기록

### 테스트 품질 검증 (IL2-V3)
- ⑥ 검증 단계에서 spec-reviewer가 **테스트 자체도 검토:**
  - "이 테스트가 실패하려면 어떤 조건이 필요한가?"
  - "이 테스트를 통과하는 잘못된 구현이 있는가?"
- trivial 테스트 (항상 통과) → REJECT 사유에 포함

### 독립 검증 보장 (IL3-V1 + CV-07)
- jarvis-verify.sh는 **cmux 패키지에 사전 포함된 스크립트** (JARVIS가 동적 생성 금지)
- 검증 로직은 **AI 판단 없이** 자동 수집만: JSON 유효성, checksum 비교, 메트릭 스냅샷
- 진화별 최종 판단은 **사용자** (Iron Law #1)
- **플러그형 구조 (CV-07):** 진화 유형별 검증 플러그인
  ```
  scripts/jarvis-verify.sh evo-001
    → STATUS에서 evolution_type 읽기
    → [공통] Iron Law #2 물리 체크 (IL2-F1, IL2-F2):
        code/hook/skill → 05-tdd.md 존재 + 3줄 이상 + "test"|"assert" 키워드
        settings_change → 07-expected-outcomes.md 존재 + 비어있지 않음
        mixed → 양쪽 모두 체크
    → [공통] Iron Law #3: evidence.json 파일 생성 (IL3-F1)
        before-metrics.json + after-metrics.json → evidence.json 조립
    → verify-plugins/settings-change.sh (JSON 유효, 키 존재, 스키마)
    → verify-plugins/hook-addition.sh (파일 존재, 실행 권한, JSON 출력)
    → verify-plugins/skill-change.sh (YAML frontmatter 유효)
    → 미지원 유형 → 기본 검증(checksum + JSON) + 경고
  ```

### hook 설계 (Claude Code 소스 검증 반영)

**GATE hook 출력 형식 (S1 수정 — Claude Code 공식 스키마 준수):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "GATE J-1: settings.json은 phase=applying만 허용"
  }
}
```
- `permissionDecision`: `"allow"` / `"deny"` / `"ask"` (3가지)
- `"ask"` = GATE 5단계 HOLD 구현 (S6 — 사용자에게 승인 UI 표시)
- ~~`{"error":"..."}`~~ 형식은 사용하지 않음

**GATE hook matcher (S3 수정 — Bash 간접 수정 차단):**
```python
JARVIS_HOOK_MAP = {
    # PreToolUse — GATE (Edit + Write + Bash 모두 커버)
    "cmux-jarvis-gate.sh": ("PreToolUse", "Edit|Write|Bash", 3),
    # ConfigChange — 백업 + GATE 삭제 차단
    "cmux-settings-backup.sh": ("ConfigChange", None, 10),
    # SessionStart — 캐시 inject + initialUserMessage + watchPaths 등록 (S5+S7)
    "jarvis-session-start.sh": ("SessionStart", None, 5),
    # PostCompact — 컨텍스트 복원
    "jarvis-post-compact.sh": ("PostCompact", None, 5),
    # PreCompact — 진화 컨텍스트 보존 지시 주입 (S9)
    "jarvis-pre-compact.sh": ("PreCompact", None, 5),
    # FileChanged — eagle-status/watcher-alerts 변경 즉시 감지 + 디바운싱 60초 (S7+CA-02)
    "jarvis-file-changed.sh": ("FileChanged", "cmux-eagle-status.json|cmux-watcher-alerts.json", 5),
    # ~~TeammateIdle~~ 제거 (CE-01: JARVIS는 teammate 아님 → 미적용)
    # idle 방지는 FileChanged + initialUserMessage로 대체
}
```
- ~~`cmux-jarvis-worker-gate.sh`~~ 제거 → gate.sh 내부에서 Worker 체크 통합 (S4)
- matcher `"Edit|Write"` → **`"Edit|Write|Bash"`** 로 확장 (S3)

**gate.sh 내부 로직 (S3+S4 통합):**
```bash
#!/bin/bash
INPUT_JSON=$(cat)
TOOL_NAME=$(echo "$INPUT_JSON" | jq -r '.tool_name')

# 1. Edit/Write → file_path 직접 체크
if [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ]; then
  FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // ""')
  check_gate "$FILE_PATH"

# 2. Bash → 명령에서 settings.json 경로 감지 (S3)
elif [ "$TOOL_NAME" = "Bash" ]; then
  COMMAND=$(echo "$INPUT_JSON" | jq -r '.tool_input.command // ""')
  # CA-03: 쓰기 패턴만 감지 (읽기 명령 false positive 방지)
  if echo "$COMMAND" | grep -qE "(>|>>|cp |mv |tee |jq .* -w |sed -i).*settings\.json"; then
    check_settings_gate "$COMMAND"
  elif is_worker_surface; then
    check_worker_gate "$COMMAND"
  else
    allow
  fi
fi

check_gate() {
  local path="$1"
  # Worker surface → evolutions/ 내부만 허용 (S4 통합)
  if is_worker_surface && [[ "$path" != *"/cmux-jarvis/evolutions/"* ]]; then
    deny "Worker: evolutions/ 외부 쓰기 금지"
    return
  fi
  # settings.json → phase=applying 조건부 (IL1-F1)
  if [[ "$path" == *"settings.json"* ]]; then
    check_settings_gate "$path"
    return
  fi
  # 허용 경로 체크
  if [[ "$path" == *"/cmux-jarvis/"* ]] || [[ "$path" == *"$OBSIDIAN_VAULT"* ]]; then
    allow
  else
    deny "GATE J-1: 허용 경로 외 쓰기 금지"
  fi
}

deny() { echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"$1\"}}"; }
allow() { echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow\"}}"; }
hold() { echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"ask\",\"permissionDecisionReason\":\"$1\"}}"; }
```

**ConfigChange hook — GATE 삭제 차단 (S2):**
```bash
# cmux-settings-backup.sh
# ConfigChange hook에서 jarvis-gate 항목 삭제 시 exit 2로 변경 자체를 차단
INPUT_JSON=$(cat)
SOURCE=$(echo "$INPUT_JSON" | jq -r '.source')

if [ "$SOURCE" = "user_settings" ]; then
  # 변경된 settings.json에서 jarvis-gate hook 존재 확인
  if ! jq -e '.hooks.PreToolUse[]?.hooks[]? | select(.command | contains("cmux-jarvis-gate"))' \
    ~/.claude/settings.json >/dev/null 2>&1; then
    echo "JARVIS GATE hook 삭제 감지. 변경 차단." >&2
    exit 2  # ← Claude Code가 변경을 세션에 적용하지 않음
  fi
fi

# 정상 백업 로직 계속...
```

**SessionStart hook — initialUserMessage 자동 시작 (S5):**
```bash
# jarvis-session-start.sh
# JARVIS surface에서만 initialUserMessage 주입
JARVIS_SID=$(jq -r '.jarvis.surface // ""' /tmp/cmux-roles.json 2>/dev/null)
CURRENT_SID="surface:${CMUX_SURFACE_ID:-unknown}"

if [ "$CURRENT_SID" = "$JARVIS_SID" ]; then
  # JARVIS surface → 자동 시작 프롬프트 주입
  CACHE=$(cat ~/.claude/cmux-jarvis/.session-context-cache.json 2>/dev/null || echo "")
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",
    \"additionalContext\":\"$CACHE\",
    \"initialUserMessage\":\"JARVIS 초기화. eagle-status + watcher-alerts 확인 후 감지 시작.\"}}"
else
  # 다른 surface → additionalContext만
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"\"}}"
fi
```

**GATE 5단계 판정 → Claude Code permissionDecision 매핑 (S6):**
```
GATE 판정      │ permissionDecision │ 동작
───────────────┼────────────────────┼────────────
ALLOW          │ "allow"            │ 무조건 통과
WARN           │ "allow" + stderr경고│ 경고 표시 + 실행
HOLD           │ "ask"              │ Claude Code 승인 UI 표시
BLOCK          │ "deny"             │ 즉시 거부
ESCALATE       │ "deny" + cmux notify│ 거부 + 사용자 알림
```

### CURRENT_LOCK 상세 (HIGH-E3)
```json
{
  "evo_id": "evo-001",
  "created_at": "2026-04-02T10:00:00Z",
  "ttl_minutes": 60,
  "surface_id": "jarvis",
  "worker_pid": null
}
```
- 60분 초과 → stale lock → JARVIS 재시작 시 자동 해제 + 롤백
- Worker PID 사망 + TTL 미초과 → Circuit Breaker 재시도 1회

### 모드 전환 (CV-01)
- `jarvis-maintenance.sh migrate-vault <new-path>`: 정본 마크다운을 새 경로로 이동 + config.json 업데이트 + FTS5 재구축
- 모드 A→B: Obsidian 볼트 → 로컬로 복사 + obsidian_vault_path 제거
- 모드 B→A: 로컬 → Obsidian 볼트로 복사 + obsidian_vault_path 설정

### Worker pane 환경 설정 (CV-02)
- Worker pane 생성 시 마커 파일 `/tmp/cmux-jarvis-worker-{PID}` 생성
- hook에서 `[ -f /tmp/cmux-jarvis-worker-$PPID ]` 체크 (환경변수 전달 불가 시 폴백)
- Worker 종료 시 마커 파일 자동 삭제 (trap EXIT)

### 승인 대기 비동기 (CV-03)
- 승인 대기 중 JARVIS는 block되지 않음
- 진화 상태를 "awaiting_approval"로 기록 → 모니터링은 계속 실행
- 사용자 다음 입력 시 보류 중인 승인 요청 리마인드

### 큐 우선순위 (CV-08)
- 메트릭 threshold 기반 자동 분류:
  - critical 임계 초과 → 우선순위 CRITICAL
  - warning 임계 초과 → 우선순위 HIGH
  - good 범위 내 개선 → 우선순위 LOW
- 큐 초과(5건) 시 가장 낮은 우선순위 폐기 (동일 시 FIFO)
- CRITICAL은 절대 자동 폐기하지 않음 (큐 6건째 허용)

### 의존성 폴백 체인 (FIX-09)
- 지식 검색: 로컬 FTS5 (sqlite3 CLI) → grep 폴백
- 문서 쓰기: obsidian CLI → 직접 파일 쓰기 폴백
- Phase 3+: Basic Memory MCP → 하이브리드 검색 (FTS5 + 벡터)

## JARVIS 진화 파이프라인 (11단계, 안전장치 포함)

```
① 감지 — 3가지 트리거 (S7+S5 기반)
    ├── FileChanged hook: eagle-status/watcher-alerts 변경 즉시 → bash 수치 추출 (토큰 0)
    │   → 임계값 초과 시만 additionalContext로 JARVIS에 주입
    ├── Watcher cmux send: STALL 3회+ 시 JARVIS에 직접 알림
    ├── initialUserMessage: 세션 시작 시 자동 감지 시작 (S5)
    ↓ (Inbound Gate → 2레인: Lane A 보고 / Lane B 진화 / Lane C 피드백)
    ├── 무한 루프 체크: MAX_CONSECUTIVE / MAX_DAILY / 동일 영역 반복
    ├── CURRENT_LOCK 확인: 진행 중 진화 있으면 큐에 추가
    ↓
② 분석 — 관련 설정 + 맥락 + 코드 심층 분석 + 메트릭 사전 기반 정량 분석
    ↓                              (GitHub, Claude Code 소스, 스레드, 공식문서 참고)
③ 1차 승인 — cmux notify "개선 여지 발견. 계획 수립할까요?" → [수립][보류][폐기]
    ↓ ([수립] 선택 시)
④ 백업 — 설정 스냅샷 3중화 (로컬 + Obsidian + Git) + CURRENT_LOCK(TTL 60분) + /freeze
    ↓
⑤ 개선 계획 — DAG 구조화 + 위상 정렬 검증 (순환 방지)
    ↓
⑤-b. 2차 승인 — "이 계획대로 실행할까요?" → 구체적 변경 diff 표시 → [실행][수정][폐기]
    ↓ ([실행] 선택 시 → CURRENT_LOCK의 TTL 리셋, R3-01)
⑥ 검증 — 2단계: 스펙 준수 → 품질 ("Do Not Trust the Report" 원칙)
    ↓
⑦ TDD — 유형별:
    - 코드/hook/스킬 → failing test first (엄격)
    - 설정값 변경 → expected outcome 문서화 (= 사전 예측)
    ↓
⑧ 구현 — Evolution Worker pane (Worker는 제안만, 적용 금지)
    ↓
⑨ E2E — 사전 정의 검증 스크립트 (jarvis-verify.sh, AI 판단 개입 없음)
    ↓ (실패 시 → ⑤로 순환, 진화당 최대 2회 순환. 2회 실패 → DISCARD)
⑩ Before/After 비교 — (evidence.json 존재 필수, 없으면 REJECT)
    - 메트릭 스냅샷 (Before: ④ 시점, After: ⑨ 통과 후)
    - 10분 관찰 기간 (설정 변경 시)
    - 사용자에게 diff 표시 → [유지(KEEP)][폐기(DISCARD)]
    - Simplicity criterion: 미미한 개선 + 높은 복잡성 → 폐기 권고
    ↓
    ├── DISCARD → 자동 롤백 + failure 문서화
    └── KEEP ↓
⑪ 반영 — JSON Patch (진화가 변경한 키만 적용) + CURRENT_LOCK 해제 + /freeze 해제
    ├── 충돌 키 → AskUserQuestion으로 해결
    └── Obsidian 문서로 전체 결과 저장
```

## 문서 관리 시스템 (FIX-01 + FIX-08 반영)

### 디렉토리 구조 — 이중 저장소

**1차: Obsidian 볼트 = 정본 (마크다운 + 사람 열람 가능)**
```
{OBSIDIAN_VAULT}/JARVIS/          # Obsidian 볼트 내 JARVIS 전용 폴더
├── Evolutions/                   # 진화 히스토리
│   ├── evo-001.md                # wikilink + properties + callouts
│   ├── evo-002.md
│   └── Evolution Dashboard.base  # Obsidian Bases 대시보드
├── Knowledge/                    # 학습 지식
│   ├── github/                   # 출처별 분류
│   ├── docs/
│   ├── source-code/
│   └── Knowledge Index.base
├── Backups/                      # 설정 스냅샷 (3세대 유지)
│   ├── evo-001/
│   │   ├── settings.json
│   │   └── manifest.json
│   └── evo-002/
├── Daily/                        # Daily Note 연동
└── JARVIS Dashboard.md           # 전체 현황 대시보드
```

**2차: 로컬 캐시 = 검색 인덱스 + 실행 상태**
```
~/.claude/cmux-jarvis/            # JARVIS 실행 전용 (AI 빠른 접근)
├── config.json                   # 설정 (볼트 경로, 예산, 제한)
├── metric-dictionary.json        # 메트릭 사전 (FIX-06)
├── budget-tracker.json           # 예산 추적 (FIX-16)
├── evolution-queue.json          # 진화 대기열 (FIX-03)
├── .evolution-counter            # 연속/일일 진화 카운터 (FIX-05)
├── .evolution-lock               # CURRENT_LOCK (FIX-03)
├── .session-context-cache.json   # SessionStart inject 캐시 (FIX-11)
├── evolutions/                   # 진화 실행 상태 (STATUS 파일 포함)
│   ├── evo-001/
│   │   ├── STATUS                # {"phase":"completed","worker_pid":...}
│   │   ├── nav.md
│   │   ├── 01-detection.md ~ 09-result.md
│   │   ├── proposed-settings.json  # Worker 제안 (FIX-04)
│   │   └── backup/               # 로컬 백업 (Obsidian에도 동시 저장)
│   └── evo-002/
└── knowledge/                    # 로컬 캐시 (정본은 Obsidian)
    └── raw/                      # 연구/학습 원본 문서
```

**마이크로 스킬 구조 (FIX-08):**
```
~/.claude/skills/cmux-jarvis/
├── SKILL.md                      # 최소 10줄 (SR-03) — 상세는 session-start additionalContext로 JARVIS에만 주입
├── skills/
│   ├── evolution/SKILL.md        # 진화 파이프라인 11단계
│   ├── knowledge/SKILL.md        # 지식 관리 + Progressive Disclosure
│   ├── obsidian-sync/SKILL.md    # Obsidian 연동 (선택적)
│   └── visualization/SKILL.md    # Excalidraw/Mermaid/Canvas
├── agents/
│   └── evolution-worker.md       # Worker 에이전트 (제안만 허용)
├── hooks/
│   ├── cmux-jarvis-gate.sh       # GATE J-1 PreToolUse — Edit|Write|Bash 통합 (S3+S4)
│   ├── cmux-settings-backup.sh   # ConfigChange 3중 백업 + GATE 삭제 차단 (S2)
│   ├── jarvis-session-start.sh   # SessionStart 캐시 + initialUserMessage + watchPaths (S5+S7)
│   ├── jarvis-file-changed.sh    # FileChanged eagle-status 즉시 감지 + 디바운싱 60초 (S7+CA-02)
│   ├── jarvis-pre-compact.sh     # PreCompact 진화 컨텍스트 보존 (S9)
│   └── jarvis-post-compact.sh    # PostCompact 복원 (FIX-20)
│   # ~~jarvis-prevent-idle.sh~~ 제거 (CE-01: JARVIS ≠ teammate)
└── references/
    ├── metric-dictionary.json    # 메트릭 사전 원본
    ├── red-flags.md              # Red Flags 테이블
    ├── iron-laws.md              # 3 Iron Laws
    └── test-templates.md         # TDD 유형별 템플릿 (FIX-17)
```

### 네비게이션 문서 (nav-evolutions.md)
```markdown
# 진화 히스토리

| # | 날짜 | 제목 | 결과 | 문서 |
|---|------|------|------|------|
| 001 | 2026-04-01 | traits inject 추가 | 성공 | [링크](success/2026-04-01_001_...) |
| 002 | 2026-04-02 | deadlock 방지 | 성공 | [링크](success/2026-04-02_002_...) |
```

### 각 진화 문서 내용
```markdown
# 진화 #001: {제목}

## 감지
- 어떤 패턴에서 개선 여지를 발견했는가

## 분석
- 참조 자료 (GitHub, 소스코드, 문서)
- 근본 원인

## 계획
- 변경 내역

## 검증 결과
- 레드팀/블루팀/SSOT/엣지케이스 피드백

## TDD
- 작성한 테스트

## A/B 테스트
- Before vs After 비교 데이터

## 결과
- 성공/실패/미반영 + 사유
```

### (구버전 디렉토리 구조 → 위 "이중 저장소" 섹션으로 통합됨)

## Claude Code 소스 분석 결과 (계획에 반영)

### 사용 가능한 Hook 이벤트 (28종)
소스: `/Users/csm/claude-code/source/src/entrypoints/sdk/coreTypes.ts`

JARVIS에 핵심적인 이벤트:
| 이벤트 | 용도 | JARVIS 활용 |
|--------|------|-------------|
| **ConfigChange** | settings.json 변경 시 자동 실행 | **설정 자동 백업** |
| TeammateIdle | 동료 surface IDLE | 재배정 제안 |
| TaskCompleted | 작업 완료 | 완료율 추적 |
| PostCompact | 컨텍스트 압축 후 | 컨텍스트 위험 감지 |
| FileChanged | 파일 변경 | 설정 파일 감시 |

### ConfigChange hook 상세
- **source 종류**: `user_settings`, `project_settings`, `local_settings`, `policy_settings`, `skills`
- **입력**: `{hook_event_name: "ConfigChange", source: "user_settings", file_path: "..."}`
- **등록**: settings.json hooks 섹션에 `{"matcher": "user_settings", "hooks": [...]}`
- **활용**: settings.json 변경 감지 → 즉시 백업 스냅샷 생성

### settings.json 변경 감지 메커니즘
소스: `src/utils/settings/changeDetector.ts`
- **chokidar** 파일 워치 사용 (FILE_STABILITY_THRESHOLD_MS = 1000ms)
- 내부 변경(Claude Code 자체) vs 외부 변경 구분 (INTERNAL_WRITE_WINDOW_MS = 5000ms)
- 변경 감지 → `executeConfigChangeHooks()` 자동 호출

### 설정 변경 가능한 슬래시 명령어
소스: `src/commands/` 디렉토리 분석 (80+ 명령어)

JARVIS가 다른 surface에 전달 가능:
| 명령어 | 용도 |
|--------|------|
| `/model [name]` | AI 모델 변경 |
| `/effort [level]` | 작업 노력 수준 |
| `/fast` | Fast mode 토글 |
| `/compact` | 컨텍스트 압축 |
| `/config` | settings.json 편집 |
| `/permissions` | 권한 관리 |
| `/mcp` | MCP 서버 관리 |
| `/hooks` | hook 설정 |

### Before/After 비교 구현 (Phase 1: 사용자 판단)
- Before 스냅샷: ④ 시점 eagle-status + surface 상태 자동 캡처 (jarvis-verify.sh)
- After 스냅샷: ⑨ 통과 후 동일 메트릭 자동 캡처
- Phase 1: diff를 사용자에게 표시 → [KEEP][DISCARD] 선택
- Phase 2+: metric-dictionary 기반 자동 비교 + Simplicity criterion

## 수정/생성 파일 (5관점 리뷰 FIX 반영)

### 신규 — 마이크로 스킬 (FIX-08)
1. `cmux-jarvis/SKILL.md` — 코어: GATE + 모니터링 + 스킬 라우팅
2. `cmux-jarvis/skills/evolution/SKILL.md` — 진화 11단계
3. `cmux-jarvis/skills/knowledge/SKILL.md` — 지식 + Progressive Disclosure
4. `cmux-jarvis/skills/obsidian-sync/SKILL.md` — Obsidian 연동 (선택적)
5. `cmux-jarvis/skills/visualization/SKILL.md` — 시각화

### 신규 — 에이전트 + hook + 스크립트
6. `cmux-jarvis/agents/evolution-worker.md` — Worker (제안만, FIX-04)
7. `cmux-jarvis/hooks/cmux-jarvis-gate.sh` — GATE PreToolUse (FIX-02)
8. `cmux-jarvis/hooks/cmux-settings-backup.sh` — 3중 백업 + GATE exit 2 차단 (S2)
9. `cmux-jarvis/hooks/jarvis-session-start.sh` — 캐시 + initialUserMessage + watchPaths (S5+S7)
10. `cmux-jarvis/hooks/jarvis-file-changed.sh` — FileChanged eagle-status 즉시 감지 (S7)
11. `cmux-jarvis/hooks/jarvis-pre-compact.sh` — PreCompact 진화 컨텍스트 보존 (S9)
12. `cmux-jarvis/hooks/jarvis-prevent-idle.sh` — TeammateIdle JARVIS idle 방지 (S8)
13. `cmux-jarvis/hooks/jarvis-post-compact.sh` — PostCompact 복원 (FIX-20)
14. `scripts/jarvis-evolution.sh` — 진화 CLI + 안전 제한 (FIX-03,05)
15. `scripts/jarvis-verify.sh` — 독립 검증 + 플러그형 (FIX-18, CV-07)
16. `scripts/verify-plugins/` — 유형별 검증: settings-change.sh, hook-addition.sh, skill-change.sh
17. `scripts/jarvis-maintenance.sh` — FTS5 재구축 + migrate-vault (FIX-14, CV-01)

### 신규 — 참조
18. `cmux-jarvis/references/metric-dictionary.json` — 메트릭 사전 (FIX-06)
19. `cmux-jarvis/references/test-templates.md` — TDD 템플릿 (FIX-17)
20. `cmux-jarvis/references/red-flags.md` + `iron-laws.md`
21. `cmux-jarvis/references/gate-5level.md` — GATE 5단계 + permissionDecision 매핑

### 수정
22. `cmux-start/SKILL.md` — JARVIS pane + 복구 체크 + roles.json jarvis 등록
23. `cmux-watcher/SKILL.md` — JARVIS 알림 규칙
24. `install.sh` — 초기화 + config.json + 8 hook HOOK_MAP 등록
25. `README.md` — 마이크로 스킬 구조

## JARVIS SKILL.md — 2단계 구조 (SR-03: 전 surface 컨텍스트 절약)

### 파일로 배포되는 SKILL.md (10줄 미만 — 전 surface 로드)
```markdown
---
name: cmux-jarvis
description: "JARVIS 시스템 관리자"
user-invocable: false
classification: workflow
allowed-tools: Bash, Read, Write, Edit, AskUserQuestion, WebSearch, WebFetch
---
# JARVIS
JARVIS는 오케스트레이션 설정 진화 엔진입니다.
상세 지시사항은 JARVIS surface 세션 시작 시 자동 로드됩니다.
```

### session-start additionalContext로 주입되는 전체 지시 (JARVIS surface에서만)
```markdown
# JARVIS — 능동형 시스템 관리자 (전체 지시)

역할: 아이언맨의 자비스. 오케스트레이션 상태를 모니터링하고 설정 개선을 제안.

## Phase 1 역할 한정 (CROSS-2 + CV-06: 범위 폭발 방지)
Phase 1 **코어** (필수):
1. **설정 진화 엔진** (11단계 파이프라인)
2. **모니터링** (eagle-status 읽기, 메트릭 수집)

Phase 1 **선택** (모드 A에서만):
3. **Obsidian 단순 동기화** (obsidian CLI create/append 수준, Basic Memory 불필요)

Phase 2+에서 점진 추가:
- 지식 관리 (FTS5 검색 + Progressive Disclosure)
- 시각화 (Excalidraw/Mermaid/Canvas)
- 하네스 추천 (harness-100)
- 능동적 학습 (GitHub/Docs 탐색)
- 예산 관리 (Budget enforcement)

Phase 3:
- Basic Memory MCP 연동 (하이브리드 검색)

## Iron Laws (위반 시 즉시 중단)
1. **NO EVOLUTION WITHOUT USER APPROVAL FIRST** (2단계 승인: 계획 전 + 계획 후)
2. **NO IMPLEMENTATION WITHOUT EXPECTED OUTCOME FIRST** (코드→TDD, 설정→예상 결과 문서화)
3. **NO COMPLETION CLAIMS WITHOUT VERIFICATION EVIDENCE** (evidence 스키마 필수)

### 증거(Evidence) 스키마 — Iron Law #3 강제
```json
{
  "evidence_type": "metric_comparison | test_result | user_approval",
  "before_snapshot": "evolutions/evo-001/before-metrics.json",
  "after_snapshot": "evolutions/evo-001/after-metrics.json",
  "metrics_compared": ["dispatch_failure_rate", "stall_count"],
  "collection_method": "jarvis-verify.sh (사전 정의, AI 미개입)",
  "collected_at": "2026-04-02T11:00:00Z"
}
```

## ⛔ GATE J-1: 권한 제한 (SKILL.md + hook 이중 강제)

**프롬프트 레벨 (SKILL.md):**
- /cmux-uninstall, /cmux-start, /cmux-pause 금지
- **/hooks 명령 금지** — 자기 GATE hook 제거 방지 (META-1)
- 사용자 승인 없는 설정 변경 금지
- surface 생성/삭제 금지
- /tmp/cmux-orch-enabled 조작 금지

**GATE 삭제 차단 (META-1, S2 — exit 2 활용):**
- ConfigChange hook에서 settings.json 변경 시 jarvis-gate hook 존재 확인
- 삭제 감지 시 → **exit 2로 변경 자체를 차단** (세션에 적용 안 됨)
- ~~자동 복원~~ → **차단이 복원보다 강력** (변경이 아예 적용 안 됨)

**하드웨어 레벨 (cmux-jarvis-gate.sh PreToolUse hook):**
- JARVIS Write/Edit **허용 경로**: `~/.claude/cmux-jarvis/`, Obsidian 볼트
- **settings.json은 조건부 허용** (IL1-F1):
  - CURRENT_LOCK 존재 + phase="applying" → 허용 (⑪ 반영 단계)
  - 그 외 → **deny** ("settings.json은 진화 ⑪ 반영 단계에서만 수정 가능")
- 위 외 경로 Write/Edit → permissionDecision: deny
- 진화 중 /freeze 활성 → 외부 settings.json 수정 warn (CRITICAL 시 deny)
- Evolution Worker는 evolutions/ 외부 쓰기 차단 (gate.sh 내부 Worker 분기, S4)

## 안전 제한
- 진화 직렬 실행 전용: CURRENT_LOCK 파일 (동시 진화 금지)
- MAX_CONSECUTIVE_EVOLUTIONS = 3 (연속 제한)
- MAX_DAILY_EVOLUTIONS = 10 (일일 제한)
- 동일 영역 3회 반복 → 에스컬레이션
- Worker는 proposed-settings.json만 생성 (직접 적용 금지)

## Red Flags
(상세: references/red-flags.md 참조 — SS-02: SSOT 단일 정의)
주요 항목: 테스트 생략 충동 → TDD 필수, 자기 옹호 → 독립 검증, 승인 생략 → 반드시 요청
| "내가 만든 거니까 잘 됐을 거야" | 독립 검증 스크립트 실행 |
| "사용자한테 물어보면 귀찮아할 거야" | 반드시 승인 요청 (Iron Law #1) |
| "이전에 비슷한 게 잘 됐으니까" | 새로 검증 (Iron Law #3) |
| "롤백하면 되니까 바로 적용하자" | 3중 백업 먼저, 적용은 승인 후 |
| "빨리 해야 하니까 GATE 우회하자" | GATE는 hook으로 강제됨, 우회 불가 |

## 스킬 라우팅
- 개선 감지 → `skills/evolution/SKILL.md` 호출
- 학습 필요 → `skills/knowledge/SKILL.md` 호출
- Obsidian 동기화 → `skills/obsidian-sync/SKILL.md` 호출 (선택적)
- 시각화 → `skills/visualization/SKILL.md` 호출

## 모니터링 항목 (메트릭 사전 기반)
- dispatch_failure_rate: eagle-status.json (임계: good<5%, warning<20%, critical<50%)
- stall_count: watcher.log STALL 이벤트 (임계: good=0, warning>2, critical>5)
- done_latency_avg: 태스크 완료 소요시간 (임계: good<300s, warning<600s, critical<1200s)
- context_overflow_count: PostCompact 횟수 (임계: good<2, warning<5, critical>10)
- error_rate: ERROR surface 비율 (임계: good=0%, warning<10%, critical<30%)
```

## Evolution Worker 에이전트 (FIX-04 권한 제한 반영)

```markdown
## 권한 제한 (hook으로 강제)
- settings.json, ai-profile.json 직접 수정 **금지**
- 변경이 필요하면 `proposed-settings.json`에 제안만 기록
- JARVIS가 제안을 검증 + 사용자 승인 후 적용
- evolutions/ 디렉토리 외부 Write/Edit → hook deny

## 완료 보고 프로토콜 (Superpowers 4상태 + TDD 증거 필수)
- DONE — 모든 단계 성공
- DONE_WITH_CONCERNS — 완료했으나 우려사항 있음 (목록 첨부)
- BLOCKED — 진행 불가 (사유 + 시도한 방법)
- NEEDS_CONTEXT — 정보 부족 (필요한 정보 명시)

## STATUS 파일 필수 필드 (Iron Law #2 강제, CV-09 반영)
```json
{
  "evo_id": "evo-001",
  "evolution_type": "settings_change",
  "phase": "completed",
  "status": "DONE",
  "tests_written": 2,
  "tests_passed": 2,
  "tests_failed_before_fix": 2,
  "expected_outcomes_documented": true,
  "test_file_paths": ["evolutions/evo-001/05-tdd.md"],
  "proposed_changes_path": "evolutions/evo-001/proposed-settings.json"
}
```
**evolution_type별 검증 (CV-09 + CV2-02):**
- `settings_change` → `expected_outcomes_documented == true` 필수 (TDD 면제)
- `hook_change | skill_change | code_change` → `tests_failed_before_fix > 0` 필수 (TDD 엄격)
- `mixed` (복합 변경) → **모든 유형의 검증 적용** (TDD + expected_outcomes + 플러그인 전부)
- evolution_type은 **JARVIS가 ⑤ 계획 시 결정**, Worker는 변경 불가

**Worker 제안 범위 (CV-05 + CV2-01):**
모든 파일 변경은 `evolutions/evo-XXX/` 내부에 제안 파일로 생성.
JARVIS가 검증 후 실제 경로에 복사/적용. (git staging area와 유사)
제안 파일과 함께 **file-mapping.json** 생성 (제안→실제 경로 매핑):
```json
{"proposed-hooks/gate.sh": "~/.claude/skills/cmux-jarvis/hooks/cmux-jarvis-gate.sh",
 "proposed-settings.json": "~/.claude/settings.json"}
```

## 에스컬레이션 트리거 (작업 즉시 중단)
- 아키텍처 결정이 필요한 경우
- 시스템 이해가 불충분한 경우
- 접근 방식의 정확성이 불확실한 경우
- 예상외 코드 구조 변경이 필요한 경우
```

### Superpowers (obra/superpowers) — 130K stars, 에이전트 스킬 프레임워크 + 개발 방법론

**JARVIS의 기본 모체. 초능력 급 센스의 원천.**

**핵심 철학**:
- "코드 작성 전에 먼저 뭘 만드는지 물어본다" → brainstorming
- "열정적이지만 취향 없고 판단력 없는 주니어 개발자도 따를 수 있는 계획" → writing-plans
- "테스트가 실패하는 걸 보지 않았으면 테스트가 맞는지 모른다" → TDD
- "완료 주장 전에 증거 먼저" → verification-before-completion
- "증상 수정은 실패, 근본 원인부터" → systematic-debugging

**JARVIS에 도입할 핵심 패턴:**

| # | Superpowers 패턴 | cmux JARVIS 적용 | 중요도 |
|---|-----------------|-----------------|--------|
| **S1** | **brainstorming → writing-plans → subagent-driven-development** 자동 파이프라인 | JARVIS 진화 파이프라인 ①~⑧이 정확히 이 흐름 | **CRITICAL** |
| **S2** | **HARD-GATE** — 설계 승인 없이 구현 금지 | GATE J-1 + 사용자 승인 강화 | **CRITICAL** |
| **S3** | **"NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"** | 진화 ⑦ TDD 단계의 Iron Law | **CRITICAL** |
| **S4** | **"NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"** | 진화 ⑨ E2E에서 실제 실행 결과로만 판정 | **CRITICAL** |
| **S5** | **"NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST"** | JARVIS 감지(①) 시 증상이 아닌 근본 원인 분석 필수 | HIGH |
| **S6** | **Two-stage review** (spec compliance → code quality) | 진화 ⑥ 검증을 2단계로: 계획 준수 → 품질 | HIGH |
| **S7** | **Fresh subagent per task** (컨텍스트 오염 방지) | Evolution Worker를 매 진화마다 새 pane으로 (세션 재사용 X) | HIGH |
| **S8** | **Bite-sized tasks (2-5분)** + 체크박스 추적 | 진화 DAG 태스크를 2-5분 단위로 분해 | HIGH |
| **S9** | **Model selection by complexity** (cheap→standard→capable) | 진화 실행 시 태스크 복잡도에 따라 AI 모델 자동 선택 | MED |
| **S10** | **Simplicity criterion** (YAGNI + DRY) | A/B 테스트에서 복잡성 비용 vs 개선 가치 비교 | HIGH |
| **S11** | **writing-skills (TDD for documentation)** | JARVIS SKILL.md 자체를 TDD로 개선 (pressure test → 수정 → 검증) | MED |
| **S12** | **Red Flags 테이블** — "이런 생각이 들면 멈춰라" | GATE J-1에 Red Flags 추가 | HIGH |

**Superpowers → JARVIS 매핑 (진화 파이프라인 강화):**

```
Superpowers 워크플로우              JARVIS 진화 파이프라인
──────────────────────────────────────────────────────────
brainstorming (설계)              → ① 감지 + ② 분석
  HARD-GATE (승인)                → ③ 사용자 승인
using-git-worktrees (격리)        → ④ 백업 (설정 스냅샷 = worktree)
writing-plans (계획)              → ⑤ 개선 계획 (DAG + bite-sized tasks)
subagent-driven-development       → ⑥~⑨ (Evolution Worker pane)
  test-driven-development         →   ⑦ TDD (Iron Law: 테스트 먼저)
  verification-before-completion  →   ⑨ E2E (증거 먼저)
  two-stage review                →   ⑥ 검증 (spec → quality)
requesting-code-review            → ⑩ A/B 테스트
finishing-a-development-branch    → ⑪ 보고 + 반영/롤백
```

### (구버전 Iron Laws/Red Flags/구현순서 → 위 SKILL.md 섹션으로 통합됨)

## 설치 시 충돌 방지 원칙

- JARVIS 전용 경로 `~/.claude/cmux-jarvis/`는 기존 `~/.claude/skills/`, `~/.claude/hooks/`, `~/.claude/memory/`와 완전 분리
- 하네스 템플릿은 `~/.claude/cmux-jarvis/harnesses/`에 저장 (프로젝트 `.claude/`와 충돌 없음)
- install.sh가 기존 settings.json의 permissions/plugins 보존 (jq 기반 안전 병합, 덮어쓰기 금지)
- activation-hook.sh가 기존 hook 건드리지 않고 신규만 추가 (symlink 존재 체크)
- ConfigChange hook은 flock으로 1회만 실행 (Main/Watcher/JARVIS 중복 방지)
- Worker gate hook은 **JARVIS_WORKER_SURFACE_ID 환경변수**로 Worker surface에서만 활성화

## Microsoft JARVIS 연구 분석 + 도입 가능 패턴

소스: https://github.com/microsoft/JARVIS (HuggingGPT)

### JARVIS 아키텍처 (4단계)
```
① Task Planning — LLM이 사용자 요청 → DAG 태스크 분해
② Model Selection — 각 태스크에 최적 모델 선택 (메타데이터 기반)
③ Task Execution — 선택된 모델이 실행, 의존성 순서대로
④ Response Generation — 전체 결과 종합하여 사용자에게 보고
```

### 핵심 프롬프트 구조 (tprompt)
```
Task Planning: parse user input → [{"task": type, "id": N, "dep": [deps], "args": {...}}]
- <GENERATED>-dep_id: 의존 태스크 출력을 참조
- dep 필드: 선행 태스크 ID 배열
- 최소 태스크 수로 분해 (불필요한 분할 방지)
```

### cmux JARVIS에 도입 가능한 6개 패턴

| # | JARVIS 패턴 | cmux 적용 | 구현 방법 |
|---|------------|----------|----------|
| **J1** | **DAG 기반 태스크 분해** | 진화 계획을 의존성 그래프로 구조화 | `jarvis-evolution.sh`에서 태스크 DAG JSON 생성 |
| **J2** | **모델 메타데이터 기반 선택** | ai-profile.json traits 기반 surface 매칭 | 태스크 요구사항 ↔ surface traits 자동 매칭 |
| **J3** | **`<GENERATED>-dep_id` 출력 참조** | 이전 진화 결과를 다음 진화의 입력으로 참조 | knowledge/raw/ JSON에서 applicable_to 필드로 체이닝 |
| **J4** | **Few-shot demos (demo_parse_task.json)** | 진화 성공/실패 사례를 프롬프트 예시로 활용 | success/failure/ 문서 → JARVIS 컨텍스트에 자동 inject |
| **J5** | **logit_bias 기반 출력 제어** | A/B 테스트에서 중립성 강제 | 평가 프롬프트에 "옹호 금지" 명시 + 수치만 비교 |
| **J6** | **Hybrid inference (local > remote fallback)** | surface 장애 시 다른 surface로 자동 fallback | Watcher가 ERROR 감지 → JARVIS가 대체 surface 제안 |

### J1 상세: DAG 태스크 분해 → 진화 계획

기존 계획의 "개선 계획" 단계(⑤)를 DAG 구조로 강화:
```json
{
  "evolution_id": "evo-001",
  "tasks": [
    {"id": 0, "task": "analyze", "dep": [-1], "args": {"target": "settings.json"}},
    {"id": 1, "task": "backup", "dep": [0], "args": {"source": "<GENERATED>-0"}},
    {"id": 2, "task": "write_test", "dep": [0], "args": {"spec": "<GENERATED>-0"}},
    {"id": 3, "task": "implement", "dep": [2], "args": {"test": "<GENERATED>-2"}},
    {"id": 4, "task": "e2e_test", "dep": [3], "args": {"code": "<GENERATED>-3"}},
    {"id": 5, "task": "ab_test", "dep": [4], "args": {"before": "<GENERATED>-1", "after": "<GENERATED>-4"}}
  ]
}
```

### J4 상세: Few-shot 학습 → 진화 품질 향상

JARVIS가 `demos/demo_parse_task.json`으로 LLM에 예시를 제공하듯,
cmux JARVIS도 과거 성공/실패 사례를 프롬프트에 inject:
```
[이전 성공 사례]
- evo-003: deadlock 방지 300초 타임아웃 → Main 차단 0건 달성

[이전 실패 사례]
- evo-002: short_prompt 200자 → GLM이 지시 이해 못함 → 300자로 상향

현재 진화 계획을 위 사례를 참고하여 검토하세요.
```

## scokeepa 포크 레포 + 원본 연구 결과

JARVIS 직접 관련 레포 없음. 대신 3개 관련 프로젝트 분석:

### Paperclip (paperclipai/paperclip) — 제로 휴먼 회사 오케스트레이션
**도입 가능 패턴:**
| # | Paperclip 패턴 | cmux JARVIS 적용 |
|---|---------------|-----------------|
| P1 | **Goal ancestry** — 태스크에 "왜"까지 포함 | 진화 계획에 mission→project→task 계층 추가 |
| P2 | **Atomic checkout** — 중복 작업 방지 | 진화 DAG에서 동일 설정 동시 수정 방지 lock |
| P3 | **Budget enforcement** — 토큰 한도 | JARVIS 학습에 일일 API 비용 상한 설정 |
| P4 | **Immutable audit trail** — 불변 감사 로그 | knowledge/raw/ JSON은 수정 불가, append-only |
| P5 | **Heartbeat 기반 wake cycle** — 주기적 체크 | JARVIS 주기적 모니터링 + 학습 사이클 |

### GStack (garrytan/gstack) — 역할 기반 에이전트 팀
**도입 가능 패턴:**
| # | GStack 패턴 | cmux JARVIS 적용 |
|---|------------|-----------------|
| G1 | **Think→Plan→Build→Review→Test→Ship→Reflect** | 진화 파이프라인 11단계와 매핑 |
| G2 | **Safety layers** (/careful, /freeze, /guard) | GATE J-1 강화 — /freeze로 진화 중 설정 잠금 |
| G3 | **Role-based prompting** (CEO, QA, Security) | JARVIS 내부 페르소나 전환 (분석모드/검증모드/보고모드) |
| G4 | **Output chaining** — 이전 명령 출력이 다음 입력 | 진화 단계별 결과를 다음 단계 컨텍스트로 전달 |

### Harness (revfactory/harness) — 에이전트 팀 자동 생성
**도입 가능 패턴:**
| # | Harness 패턴 | cmux JARVIS 적용 |
|---|-------------|-----------------|
| R1 | **6개 조정 패턴** (Pipeline, Fan-out, Expert Pool, Producer-Reviewer, Supervisor, Hierarchical) | 진화 유형에 따라 패턴 자동 선택 |
| R2 | **Progressive Disclosure** — 필요한 컨텍스트만 로드 | JARVIS 학습 문서 선택적 로드 (summary만 먼저, raw는 필요시) |
| R3 | **Producer-Reviewer** — 생성→품질검증 분리 | 진화 구현(⑧) → 검증(⑥) 분리 (자기 검증 방지) |
| R4 | **Dry-run + Comparative analysis** | A/B 테스트 전 dry-run으로 부작용 사전 감지 |

### 통합 도입 계획

기존 JARVIS 진화 파이프라인에 위 패턴 반영:

```
기존 11단계                MS JARVIS          Paperclip       GStack          Harness
─────────────────────────────────────────────────────────────────────────────────────
① 감지                    -                  Heartbeat(P5)   -               -
② 분석                    Model metadata(J2) Goal ancestry(P1) -            Progressive Disclosure(R2)
③ 승인 요청               -                  Approval gate   -               -
④ 백업                    -                  Audit trail(P4) /freeze(G2)     -
⑤ 개선 계획               DAG 분해(J1)       -               Think→Plan(G1)  패턴 자동 선택(R1)
⑥ 검증                    -                  -               QA role(G3)     Producer-Reviewer(R3)
⑦ TDD                    -                  -               Test(G1)        Dry-run(R4)
⑧ 구현                    Task Execution     Atomic(P2)      Build(G1)       Pipeline/Fan-out(R1)
⑨ E2E                    -                  -               Review(G1)      Comparative(R4)
⑩ A/B 테스트              logit_bias(J5)     Budget(P3)      -               -
⑪ 보고                    Response Gen       -               Reflect(G1)     -
   학습                    Few-shot(J4)       -               -               -
```

### CMS — Claude Memory System (scokeepa/claude-memory-system)
**가장 직접적으로 관련된 프로젝트.** Claude Code용 자기 발전형 메모리 시스템.

**핵심 아키텍처:**
```
Session Start → UserPromptSubmit hook: FTS5 검색 → 관련 메모리 5개 inject
    ↓
Claude 응답 생성 (과거 메모리 활용)
    ↓
Stop hook: 트랜스크립트 JSONL 파싱 → 메모리 추출 → SQLite 저장
    ↓
다음 세션에서 자동 순환
```

**JARVIS에 도입할 핵심 패턴:**

| # | CMS 패턴 | cmux JARVIS 적용 | 우선순위 |
|---|---------|-----------------|---------|
| **M1** | **SQLite + FTS5 하이브리드 검색** | JARVIS knowledge DB에 FTS5 적용 → 학습 문서 즉시 검색 | HIGH |
| **M2** | **가중합산 중요도 판정 (0.12~0.65)** | 학습 문서에 importance score → 관련성 높은 것만 inject | HIGH |
| **M3** | **증분 JSONL 파싱 (offset 기반)** | journal.jsonl 증분 처리 (이미 agent-memory에서 유사 구현) | MED |
| **M4** | **UserPromptSubmit hook → 메모리 자동 inject** | JARVIS 학습 내용을 Main/JARVIS 컨텍스트에 자동 주입 | HIGH |
| **M5** | **user_facts 테이블 — 사용자 프로필 자동 추출** | 사용자 선호도/패턴 자동 학습 (어떤 AI 선호, 작업 스타일 등) | MED |
| **M6** | **LIKE 폴백 검색 (한국어 2글자)** | 한국어 학습 문서 검색 지원 | HIGH |
| **M7** | **세션 요약 (sessions.summary)** | 진화 세션마다 요약 자동 생성 → nav 문서에 반영 | MED |

**JARVIS 지식 모델 — Basic Memory 통합 (FIX-01, FIX-10)**

기존 독자 SQLite 스키마 → **Basic Memory Entity/Observation/Relation 모델로 통합**

```
마크다운 파일 (정본)                 Basic Memory 인덱스 (검색 캐시)
─────────────────────               ──────────────────────────────
JARVIS/Knowledge/                   Entity (note_type)
  fts5-best-practices.md     →       type='knowledge'
  superpowers-patterns.md    →       type='knowledge'

JARVIS/Evolutions/                  Entity (note_type)
  evo-001.md                 →       type='evolution'
  evo-002.md                 →       type='evolution'

파일 내 관찰 (Observation 문법):
  - [source] github                 Observation (category='source')
  - [finding] BM25 title 10x       Observation (category='finding')
  - [tip] confidence >= 5           Observation (category='tip')
  - [applicable_to] settings.json   Observation (category='applicable_to')

파일 내 관계 (Relation 문법):
  - requires [[SQLite FTS5]]        Relation (relation_type='requires')
  - inspired_by [[Superpowers]]     Relation (relation_type='inspired_by')

검색 인덱스:
  FTS5 + FastEmbed 벡터 → 하이브리드 검색 (Basic Memory 제공)
  BM25 가중치: title 10x, tags 5x, content 1x
```

**기존 계획과의 차이:**
- ~~독자 SQLite 스키마~~ → Basic Memory가 관리 (SyncService)
- ~~파일→DB 50건 시 마이그레이션~~ → **처음부터 파일+인덱스 이중**
- ~~FTS5만~~ → **하이브리드 검색** (FTS5 + 벡터)
- ~~knowledge/raw/ JSON~~ → **마크다운 + Observation 문법** (사람도 읽기 가능)

**학습 inject 시 confidence 필터 (FIX-15):**
- confidence >= 5인 Observation만 inject 대상
- 참조 파일 삭제 시 자동 무효화 (GStack /learn 패턴)
- 상태 태그: `status/to-evaluate` → `status/evaluated` → `status/adopted`

### Harness-100 (revfactory/harness-100) — 100개 도메인별 에이전트 팀 하네스

**핵심 구조**: 도메인당 4-5 전문 에이전트 + 오케스트레이터 스킬 + 확장 스킬
- 904개 .md 파일 (한/영 각 100 하네스)
- 각 하네스 = agents/ + skills/ + CLAUDE.md

**JARVIS에 도입할 핵심 패턴:**

| # | Harness-100 패턴 | cmux JARVIS 적용 |
|---|-----------------|-----------------|
| **H1** | **도메인별 하네스 선택** — 100개 중 작업에 맞는 하네스 자동 선택 | JARVIS가 업무 분석 → 적합한 하네스 추천 → 부서에 적용 |
| **H2** | **3계층 스킬** (Orchestrator → Agent-Extending → External) | JARVIS가 부서 편성 시 오케스트레이터+확장 스킬 함께 배포 |
| **H3** | **_workspace/ 산출물 관리** — 단계별 파일 저장 | 진화 문서 evo-001/ 구조와 동일 패턴 |
| **H4** | **병렬 실행 + review-synthesizer 통합** | 진화 검증 시 레드팀/블루팀 병렬 → synthesizer 통합 |
| **H5** | **규모별 모드 (풀/단일 영역)** | 진화 규모에 따라 full/partial 파이프라인 선택 |
| **H6** | **에이전트 간 SendMessage 교차 검증** | 부서 간 팀장끼리 SendMessage로 정보 공유 |
| **H7** | **에러 핸들링 (1회 재시도 → 스킵 → 보고)** | 진화 실패 시 graceful degradation |
| **H8** | **도메인 프레임워크 내장** (OWASP, SOLID, Porter 등) | JARVIS 학습 DB에 프레임워크 지식 축적 |

**JARVIS가 하네스를 적용하는 시나리오:**

```
[업무 분석] 사용자가 "보안 감사해줘" 요청
    ↓
[JARVIS 감지] "보안 감사" → harness-100에서 28-security-audit 매칭
    ↓
[하네스 추천] 사용자에게 "보안 감사 하네스를 적용할까요?" 승인 요청
    ↓ (승인)
[부서 편성] Main에 cmux send:
  "security-audit 하네스 구조로 부서를 편성하세요:
   - 팀장: vulnerability-scanner
   - 팀원1: dependency-auditor
   - 팀원2: config-reviewer
   - 팀원3: report-synthesizer
   오케스트레이터 스킬: security-audit/skill.md"
    ↓
[모니터링] JARVIS가 하네스 실행 품질 모니터링 → 개선점 학습
```

**업무 부적합 감지 시나리오:**
```
[JARVIS 관찰] 현재 부서가 "풀스택 개발" 하네스로 운영 중
  → 하지만 프론트엔드 작업만 반복, 백엔드 에이전트 IDLE 비율 80%
    ↓
[JARVIS 제안] "프론트엔드 전용 하네스로 전환하면 효율 향상됩니다.
  현재: fullstack (5 에이전트) → 제안: frontend-webapp (4 에이전트)
  적용할까요?"
```

### Claude-Mem (thedotmack/claude-mem) — 44K stars, Claude Code 영구 메모리 압축 시스템

**JARVIS 두뇌의 핵심 참조 프로젝트.**

**아키텍처**: 5 Lifecycle Hooks + Worker Service + SQLite + Chroma(벡터 검색)
```
SessionStart → UserPromptSubmit → PostToolUse → Summary → SessionEnd
                ↑ 메모리 inject    ↑ 관찰 저장      ↑ AI 압축    ↑ 세션 요약
```

**JARVIS에 도입할 핵심 패턴:**

| # | claude-mem 패턴 | cmux JARVIS 적용 | 중요도 |
|---|----------------|-----------------|--------|
| **CM1** | **Progressive Disclosure** — 계층적 메모리 주입 (전체 X, 관련 5개만) | JARVIS 학습 inject 시 관련 knowledge 5건만 선별 | **CRITICAL** |
| **CM2** | **5 Hook 생명주기** — 세션 전체를 자동 추적 | JARVIS에 SessionStart(학습 로드) + SessionEnd(세션 요약 저장) hook 추가 | HIGH |
| **CM3** | **Worker Service (포트 37777)** — 비동기 AI 처리 | 대규모 학습 처리는 worker로 분리 (hook 타임아웃 회피) | MED |
| **CM4** | **Chroma 벡터 검색** — 의미 기반 유사도 | FTS5 키워드 + Chroma 의미 하이브리드 검색 (Phase 2) | LOW (초기 FTS5만) |
| **CM5** | **AI 관찰 압축** — PostToolUse에서 도구 사용 관찰 → AI가 요약 | 오케스트레이션 이벤트 → AI가 패턴 요약 → knowledge 저장 | HIGH |
| **CM6** | **Privacy tags** `<private>` — 민감 정보 필터링 | JARVIS 학습에서 credentials, API keys 자동 제외 | MED |
| **CM7** | **Web Viewer UI (localhost:37777)** — 메모리 시각화 | 진화 히스토리 + 학습 현황 웹 대시보드 (Phase 3) | LOW |

**Progressive Disclosure 전략 (CM1) — JARVIS 적용:**
```
Level 0: 항상 inject — 현재 오케스트레이션 상태 요약 (1줄)
Level 1: 첫 턴 inject — 이전 세션 진화 결과 + 사용자 프로필 (3-5줄)
Level 2: 요청 시 inject — knowledge DB에서 FTS5 검색 → 관련 5건 (20-30줄)
Level 3: 명시적 조회 — jarvis-nav.sh로 전체 히스토리 (파일)
```
→ 컨텍스트 비용을 최소화하면서 필요한 정보만 주입

### Karpathy autoresearch (karpathy/autoresearch) — 63K stars, AI 자율 연구 루프

**AI 창시자급 프로젝트. JARVIS 진화 엔진의 정확한 원형.**

**핵심 철학**: "program.md를 프로그래밍하여 AI 에이전트가 자율적으로 연구"
- 사람은 코드(train.py)를 직접 수정하지 않음 → program.md(지시서)만 수정
- AI가 코드 수정 → 실행(5분) → 결과 비교 → keep/discard → 반복
- **NEVER STOP** — 사람이 자는 동안 ~100개 실험 자동 수행

**JARVIS에 도입할 핵심 패턴:**

| # | autoresearch 패턴 | cmux JARVIS 적용 | 중요도 |
|---|-------------------|-----------------|--------|
| **K1** | **Keep/Discard 루프** — 개선되면 keep, 아니면 revert | 진화 A/B 테스트 → keep(설정 적용) or discard(롤백) | **CRITICAL** |
| **K2** | **results.tsv 실험 로그** — commit, metric, status, description | evolutions 테이블 (SQLite) — 동일 구조 | HIGH |
| **K3** | **NEVER STOP** — 사람이 멈출 때까지 자율 실행 | JARVIS 자율 학습 + 모니터링 루프 무한 실행 | HIGH |
| **K4** | **program.md = 스킬** — 에이전트 행동을 MD로 프로그래밍 | JARVIS SKILL.md가 곧 program.md | HIGH |
| **K5** | **Fixed time budget (5분)** — 실험마다 동일 시간 | 진화마다 시간 상한 설정 (무한 루프 방지) | MED |
| **K6** | **Simplicity criterion** — 개선이 미미하면 복잡성 비용 비교 | A/B 테스트에서 "0.001 개선 + 20줄 추가 = 불채택" 판단 기준 | HIGH |
| **K7** | **git branch per experiment** — 실험 격리 | 진화마다 git branch 생성 → keep시 merge, discard시 삭제 | MED |
| **K8** | **Crash handling** — 쉬운 수정은 재시도, 근본 문제는 skip | 진화 실패 시 1회 재시도 → 실패면 failure/ 문서화 후 다음 진행 | MED |
| **K9** | **stdout 리다이렉트** — `> run.log 2>&1` (컨텍스트 보호) | 진화 결과는 파일로 저장, 컨텍스트에 직접 넣지 않음 | HIGH |

**autoresearch → JARVIS 진화 루프 매핑:**

```
autoresearch                          JARVIS 진화
─────────────────────────────────────────────────────
1. train.py 수정 (실험 아이디어)      → ⑤ 개선 계획
2. git commit                        → ④ 백업 (설정 스냅샷)
3. uv run train.py > run.log         → ⑧ 구현 (Evolution Worker pane)
4. grep val_bpb run.log              → ⑩ A/B 테스트 (수치 비교)
5. keep → 브랜치 전진                → ⑪ 반영 (설정 적용)
   discard → git reset               → 롤백 (백업 복원)
6. results.tsv에 기록                → evolutions DB + 문서
7. LOOP FOREVER                      → JARVIS 자율 모니터링 루프
```

**Simplicity criterion 구현 (K6):**
```python
# A/B 결과 판정 로직
improvement = before_metric - after_metric  # 낮을수록 좋은 경우
complexity_cost = lines_added + files_changed
if improvement < 0.001 and complexity_cost > 10:
    decision = "discard"  # 미미한 개선 + 높은 복잡성 = 불채택
elif improvement < 0 and complexity_cost < 0:
    decision = "keep"     # 동등 성능 + 코드 간소화 = 채택!
else:
    decision = "keep" if improvement > 0 else "discard"
```

## 진화 실행: 별도 pane + 단계별 문서 분산

### 진화 실행 아키텍처 (FIX-02,03,04,12,13 반영)

JARVIS가 직접 진화를 구현하지 않음 → **별도 pane에 신규 세션 AI를 생성하여 위임**.
이유: 객관성 확보 + 컨텍스트 분산 + **Worker 권한 분리 (FIX-04)**.

```
JARVIS (계획 + 감독 + 적용)      Evolution Worker (새 pane, 제한된 권한)
────────────────────────          ─────────────────────────────────────
① 감지 + ② 분석
  └── 무한 루프 체크 (FIX-05)
  └── CURRENT_LOCK 확인 (FIX-03)
③ 승인 요청 (cmux notify)
④ 3중 백업 + CURRENT_LOCK 생성 + /freeze (FIX-03,07)
⑤ 개선 계획 (DAG + 위상 정렬)
                                  ← cmux send로 계획 전달
                                  ⑥ 검증 (스펙→품질 2단계, "Do Not Trust" 원칙)
                                  ⑦ TDD (유형별 템플릿 기반, FIX-17)
                                  ⑧ 구현 → proposed-settings.json 생성 (직접 적용 금지!)
                                  ⑨ E2E → 문서 저장
                                  → STATUS 파일 + cmux send "DONE" (FIX-12)
JARVIS가 STATUS 확인 ←            (타임아웃 30분, FIX-13)
  └── Worker 비정상 종료 → Circuit Breaker (재시도 1회)
JARVIS가 proposed-settings.json 검증
  └── jarvis-verify.sh 독립 검증 (FIX-18)
⑩ A/B 테스트 (메트릭 사전 기반, 최소 3회 반복)
  └── DISCARD → 자동 롤백 + failure 문서화
  └── KEEP ↓
⑪ 반영 (3-way merge + 사용자 승인)
  └── CURRENT_LOCK 해제 + /freeze 해제
  └── 큐에서 다음 진화 처리 (있으면)
```

**Worker 권한 강제:** `cmux-jarvis-gate.sh` 내부 Worker 분기가 evolutions/ 외부 쓰기를 deny (S4)
**완료 신호:** Worker가 STATUS 파일 업데이트 + cmux send → JARVIS 즉시 감지 (폴백: 5초 폴링)

### 단계별 문서 분산 (컨텍스트 관리)

진화 11단계를 단일 세션에 모두 담으면 컨텍스트 초과.
**각 단계를 독립 문서로 저장하고, 네비게이션 문서로 연결.**

```
~/.claude/cmux-jarvis/evolutions/evo-001/
├── nav.md                    # 네비게이션 — 이 진화의 전체 흐름 + 각 단계 링크
├── 01-detection.md           # ① 감지: 어떤 패턴에서 발견했는가
├── 02-analysis.md            # ② 분석: 참조 자료, 근본 원인
├── 03-plan.md                # ⑤ 개선 계획: DAG JSON + 변경 내역
├── 04-review.md              # ⑥ 검증: 레드팀/블루팀 피드백
├── 05-tdd.md                 # ⑦ TDD: 작성된 테스트
├── 06-implementation.md      # ⑧ 구현: 변경된 파일 diff
├── 07-e2e.md                 # ⑨ E2E: 테스트 결과
├── 08-ab-test.md             # ⑩ A/B: Before/After 수치
├── 09-result.md              # ⑪ 최종 결과 + 사용자 판단
└── backup/                   # ④ 설정 스냅샷
    ├── settings.json
    └── ai-profile.json
```

**네비게이션 문서 (nav.md) 구조:**
```markdown
# Evolution #001: traits inject 추가

상태: 성공 ✓
날짜: 2026-04-01

## 진행 순서
1. [감지](01-detection.md) — surface:12 dispatch 3회 실패
2. [분석](02-analysis.md) — short_prompt trait 미적용
3. [계획](03-plan.md) — DAG 3태스크
4. [검증](04-review.md) — 레드팀 0건, SSOT 정합
5. [TDD](05-tdd.md) — 2개 테스트
6. [구현](06-implementation.md) — 1파일 수정
7. [E2E](07-e2e.md) — PASS
8. [A/B](08-ab-test.md) — 실패율 60%→0%
9. [결과](09-result.md) — 사용자 승인, 적용됨
```

**Evolution Worker에게 전달할 때:**
- nav.md + 필요한 단계 문서만 전달 (전체 X)
- 예: 구현 단계 → nav.md + 03-plan.md + 05-tdd.md만 cmux send

## 40년차 기획자+개발자 리뷰

### CRITICAL (설계 재검토 필요) — 3건

**C1. AskUserQuestion이 JARVIS 탭에서만 보인다**
- JARVIS가 승인을 요청하면 JARVIS 탭에 질문이 뜸
- 사용자가 Main 탭에서 작업 중이면 질문을 놓칠 수 있음
- **해결안**: AskUserQuestion 대신 `cmux notify`로 알림 → 사용자가 JARVIS 탭으로 이동 → 거기서 승인. 또는 cmux send로 Main에 요약 전달.

**C2. ConfigChange hook이 전 surface에서 실행됨**
- settings.json hook은 global — Main/Watcher/JARVIS 3곳 모두에서 실행
- 백업 hook이 3번 실행되면 동일 백업 3개 생성
- **해결안**: hook 내부에서 lock file 체크 → 최초 1회만 실행 (flock 패턴)

**C3. JARVIS surface에서 /model 변경은 JARVIS에만 적용됨**
- Claude Code의 /model은 해당 세션에만 적용 (settings.json의 model은 global이지만 세션 override가 우선)
- JARVIS가 다른 surface 모델을 변경하려면 `cmux send --surface X "/model sonnet"` 전송 필요
- **해결안**: JARVIS SKILL.md에 명시 — "다른 surface 설정 변경은 반드시 cmux send로 전달"

### HIGH (구현 리스크) — 4건

**H1. 진화 파이프라인 11단계가 단일 세션에서 완료될 수 있는가?**
- TDD + 구현 + E2E + A/B 테스트 → 컨텍스트 소모가 큼
- JARVIS surface 하나에서 이 모든 과정을 수행하면 컨텍스트 초과 위험
- **해결안**: 진화 단계별 /compact, 또는 큰 진화는 Main에 부서 편성 요청 (JARVIS가 기획, 부서가 구현)

**H2. 능동적 학습의 트리거가 불명확**
- "모든 surface IDLE시 학습" → 누가 감지하나? JARVIS 자체가 IDLE이면 실행 안 됨
- TeammateIdle hook은 teammate 전용 — JARVIS에 적용 불가
- **해결안**: UserPromptSubmit hook에서 JARVIS에 "학습 시간" 알림 전달. 또는 Watcher가 전체 IDLE 감지 시 JARVIS에 cmux send.

**H3. 학습 문서 knowledge/raw/ JSON이 대량으로 쌓이면 읽기 비용**
- 1000개 JSON 파일 → JARVIS 시작 시 전부 로드? 선택적 로드?
- **해결안**: summary.md를 인덱스로 사용, raw/는 필요 시만 접근. SQLite 마이그레이션을 50건으로 앞당기기.

**H4. A/B 테스트의 "중립성" 보장 방법**
- JARVIS가 구현한 것을 JARVIS가 평가 → 본질적 이해충돌
- **해결안**: A/B 비교 메트릭을 자동 수집 (eagle-status diff, error count, DONE 소요시간 등) → 수치 기반 판단. 주관적 평가 배제.

### MEDIUM (개선 권장) — 3건

**M1. 백업 naming convention 개선**
- `2026-04-01_001_개선전_traits미적용_백업` → 한글 폴더명이 일부 시스템에서 문제
- **해결안**: `2026-04-01_001_pre-traits-inject/` 영문 + manifest.json에 한글 설명

**M2. JARVIS SKILL.md가 너무 길어질 위험**
- 진화 파이프라인 11단계 + 학습 시스템 + GATE + 모니터링 → 수백 줄
- **해결안**: SKILL.md는 핵심만, 상세는 references/로 분리

**M3. jarvis-evolution.sh가 bash로 11단계 파이프라인을 구현하기 어려움**
- TDD, A/B 테스트, 레드팀/블루팀 리뷰 → bash 스크립트로는 한계
- **해결안**: jarvis-evolution.sh는 진입점(CLI)만, 실제 파이프라인은 JARVIS Claude Code 세션이 SKILL.md에 따라 수행. 스크립트는 상태 관리(현재 단계, 백업/복원)만 담당.

### LOW — 2건

**L1. SQLite 의존성은 Python 3.9 내장 (sqlite3 모듈)**
- 추가 설치 불필요 — Python 표준 라이브러리에 포함

**L2. ~/.claude/cmux-jarvis/ 경로가 Claude Code의 미래 업데이트와 충돌 가능**
- Claude Code가 ~/.claude/ 하위에 jarvis/ 폴더를 사용할 가능성은 낮지만 0은 아님
- **해결안**: ~/.claude/cmux-jarvis/ 로 네이밍하여 cmux 네임스페이스 내 유지

## 리뷰 반영 수정사항

### 1차 리뷰 (40년차 기획자)
| # | 이슈 | 반영 |
|---|------|------|
| C1 | AskUserQuestion 가시성 | cmux notify로 알림 + JARVIS 탭에서 승인 |
| C2 | ConfigChange 중복 실행 | hook 내부 flock으로 1회만 실행 |
| C3 | /model 세션 scope | cmux send로 다른 surface 설정 전달 명시 |
| H1 | 컨텍스트 초과 | 단계별 /compact + PostCompact 복원 (FIX-20) |
| H2 | 학습 트리거 | Watcher가 전체 IDLE 감지 시 JARVIS에 cmux send |
| H3 | 학습 문서 비용 | 처음부터 파일+인덱스 이중 (FIX-01) |
| H4 | A/B 중립성 | 메트릭 사전 기반 자동 비교 (FIX-06) |
| M1 | 백업 naming | 영문 폴더 + manifest |
| M2 | SKILL.md 비대 | 마이크로 스킬 5개 분리 (FIX-08) |
| M3 | bash 한계 | CLI는 상태 관리만, 파이프라인은 SKILL.md 기반 |
| L2 | 경로 충돌 | ~/.claude/cmux-jarvis/ 유지 |

### 2차 리뷰 (5관점 심층 — 54건)
| Phase | 이슈 수 | 해결 |
|-------|---------|------|
| **Phase 0 CRITICAL** | 8건 | ✅ 반영 완료 |
| **Phase 1 HIGH** | 12건 | ✅ 반영 완료 |
| **Phase 2 MEDIUM** | 14건 | 백로그 (FIX-21~34) |

### 3차 리뷰 (비판적 재검토 — FATAL 7건 + HIGH 9건)
| 이슈 | 해결 |
|------|------|
| FATAL-A1 구버전 잔재 | ✅ 삭제 완료 |
| FATAL-A2 구현 순서 이중 | ✅ 삭제 완료 |
| FATAL-A3 Obsidian 필수/선택 모순 | ✅ 2모드 (A: Obsidian, B: 로컬) |
| FATAL-E1 JSON 3-way merge 불가 | ✅ JSON Patch로 대체 |
| FATAL-E2 A/B 3회 반복 불가 | ✅ 관찰 기간 + 사용자 판단 |
| CROSS-2 역할 7개 범위 폭발 | ✅ Phase 1 = 진화+모니터링만 |
| CROSS-3 A/B 메트릭 비현실적 | ✅ Phase 1 = 사용자 판단 |
| HIGH-A4 Basic Memory Python 의존 | ✅ Phase 3, Phase 1은 sqlite3 CLI |
| HIGH-A5 hook 등록 충돌 | ✅ surface별 환경변수 체크 |
| HIGH-E3 LOCK 영구 잠금 | ✅ TTL 60분 + stale lock 자동 해제 |
| HIGH-E5 순환 범위 모호 | ✅ 진화당 최대 2회 |
| IL1-V1 blank check 승인 | ✅ 2단계 승인 |
| IL1-V2 승인 타임아웃 없음 | ✅ 30분 타임아웃 + 큐 5건 제한 |
| IL1-V3 승인 정의 모호 | ✅ 구조화된 선택지만 인정 |
| IL2-V1 설정 TDD 불가 | ✅ expected outcome 문서화 |
| IL2-V2 TDD 강제 없음 | ✅ STATUS 필수 필드 |
| IL2-V3 테스트 품질 미검증 | ✅ spec-reviewer가 테스트도 검토 |
| IL3-V1 독립 검증 = 자기 검증 | ✅ 사전 정의 스크립트 (AI 미개입) |
| IL3-V2 증거 형식 미정의 | ✅ evidence 스키마 |

상세: `knowledge/raw/2026-04-02_5-perspective-deep-review.md`
3차 리뷰: `knowledge/raw/2026-04-02_critical-review-round2.md`
수정 계획: `knowledge/raw/2026-04-02_fix-plan-all-issues.md`

## 검증 (3차 리뷰 반영)
- /cmux-start → 3 pane (Main + Watcher + JARVIS)
- 재시작 → 중복 pane 없음 + 중단 진화 복구 + stale lock 자동 해제
- JARVIS에서 금지 경로 접근 → **hook deny**
- Worker가 evolutions/ 외부 쓰기 → **hook deny** (환경변수 CMUX_JARVIS_WORKER 체크)
- 진화 중 다른 surface 설정 수정 → **/freeze 경고**
- 연속 4회 진화 → **사용자 확인 요청**
- 승인 요청 → **구조화된 선택지** [실행][보류][폐기] (free-text 불인정)
- 승인 30분 무응답 → **자동 보류** + 큐 최대 5건
- settings.json 변경 → **3중 백업** (로컬+Obsidian+Git)
- 설정 반영 → **JSON Patch** (변경 키만 적용, 충돌 키만 AskUserQuestion)
- Before/After → **10분 관찰 + 사용자 판단** [KEEP][DISCARD]
- Worker 완료 → **STATUS 필수 필드** 검증 (tests_failed_before_fix > 0)
- 테스트 품질 → **spec-reviewer가 trivial 테스트 검출**
- 독립 검증 → **사전 정의 jarvis-verify.sh** (AI 판단 미개입)
- /compact 후 → **nav.md 자동 재주입**
- FTS5 폴백 → grep 폴백 (sqlite3 CLI, Python 불필요)
- JARVIS Write/Edit → **GATE hook 허용 경로만** (settings.json, cmux-jarvis/, 볼트)
- 2차 승인 완료 → **CURRENT_LOCK TTL 리셋** (승인 대기 시간 제외)

### 순환검증 (R1~R10, 총 10회)
| 라운드 | 관점 | HIGH | MED | LOW | 누적 해결 |
|--------|------|------|-----|-----|----------|
| R1 | 해결안 교차 | 2 | 5 | 2 | 9건 ✅ |
| R2 | R1 해결안 재검증 | 0 | 0 | 2 | 2건 ✅ |
| R3 | 시간축 | 0 | 1 | 0 | 1건 ✅ |
| R4 | 데이터 흐름 | 0 | 0 | 1 | 설계 명확화 |
| R5 | 실패 경로 | 0 | 0 | 0 | 문제 없음 |
| R6 | 보안 | **1** | 0 | 0 | 1건 ✅ |
| R7 | 일관성 | 0 | 0 | 3 | 3건 ✅ |
| R8 | 운영 호환 | 0 | 0 | 1 | 구현 시 확인 |
| R9 | 확장성 | 0 | 0 | 1 | Phase 2 |
| R10 | Iron Law 종합 | 0 | 0 | 0 | **3 Iron Law 봉쇄 확인** |
| **합계** | | **3** | **6** | **10** | **수렴 확인** |

**R10 Iron Law 봉쇄 결과 (순환검증 시점):**
- IL#1~#3: 구조적 봉쇄 확인 (프롬프트 + hook 이중)

### Zero-Trust Iron Law 감사 (기존 검증 불신, 원문 직접 재검증)
| # | 발견 | 심각도 | 해결 |
|---|------|--------|------|
| **IL1-F1** | GATE가 settings.json 항상 허용 | **CRITICAL** | ✅ phase="applying"일 때만 허용으로 수정 |
| **META-1** | /hooks로 GATE 자체 제거 가능 | **CRITICAL** | ✅ /hooks 금지 + ConfigChange에서 자동 복원 |
| **IL2-F1** | ⑦→⑧ 순서 프롬프트만 | HIGH | ✅ 05-tdd.md 파일 물리적 존재 체크 |
| **IL2-F2** | expected_outcomes 자기보고 | HIGH | ✅ 07-expected-outcomes.md 파일 체크 |
| **IL3-F1** | evidence 파일 생성 주체 불명 | HIGH | ✅ jarvis-verify.sh가 evidence.json 생성 명시 |
| IL1-F2 | 구조화 선택지 = 프롬프트 | MED | Red Flags에 추가 |
| IL3-F3 | JARVIS가 제안 파일 조작 가능 | MED | phase 체크로 완화 |

**Iron Law 최종 봉쇄 확인 (Zero-Trust 감사 후 + Claude Code 소스 검증):**
- IL#1: settings.json = **phase="applying" 조건부** + /hooks 금지 + GATE 삭제 **exit 2 차단** (S2)
  + **Bash 간접 수정도 차단** (matcher "Edit|Write|Bash", S3)
- IL#2: 05-tdd.md/07-expected-outcomes.md **파일 물리적 존재** 체크 (자기보고 불신)
- IL#3: jarvis-verify.sh가 **evidence.json 생성** + ⑩에서 존재 체크

**Claude Code 소스 기반 개선 (6건):**
| # | 개선 | 반영 |
|---|------|------|
| S1 | GATE 출력 → `hookSpecificOutput.permissionDecision` | ✅ |
| S2 | ConfigChange exit 2로 GATE 삭제 차단 | ✅ |
| S3 | Bash matcher 추가 (CRITICAL) | ✅ |
| S4 | worker-gate → gate.sh 통합 | ✅ |
| S5 | initialUserMessage 자동 시작 | ✅ |
| S6 | HOLD = permissionDecision:"ask" | ✅ |

상세: `knowledge/raw/2026-04-02_iron-law-zero-trust-audit.md`

### 5관점 순환 검토 (2026-04-03 — 아키텍트/엣지케이스/SSOT/SRP/의존성)
| # | 이슈 | 관점 | 심각도 | 해결 |
|---|------|------|--------|------|
| CA-02 | FileChanged hook 폭주 | 아키텍트 | HIGH | ✅ 디바운싱 60초 추가 |
| CE-01 | TeammateIdle JARVIS 미적용 | 엣지케이스 | HIGH | ✅ S8 제거, FileChanged+initialUserMessage로 대체 |
| SR-03 | SKILL.md 100줄 전 surface 로드 | SRP | HIGH | ✅ 10줄 최소화, additionalContext로 JARVIS에만 주입 |
| CA-03 | Bash grep false positive | 아키텍트 | MED | ✅ 쓰기 패턴만 감지 |
| SS-01 | 임계값 2곳 하드코딩 | SSOT | MED | ✅ metric-dictionary.json에서 읽기 |
| SS-02 | Red Flags 2곳 | SSOT | MED | ✅ SKILL.md 참조 링크만 |
| SS-03 | GATE 규칙 3곳 분산 | SSOT | MED | Phase 2 외부 config |
| D1 | jq 미설치 | 의존성 | MED | fail-open 폴백 |

상세: `knowledge/raw/2026-04-03_5-agent-circular-review.md`

---

## [2026-04-02] 전수 조사 2차 — 14개 레포 심층 연구 완료

**상세 문서:** `knowledge/raw/2026-04-02_repo-deep-research-full.md`

### 조사 완료 레포 (14개)

| # | 레포 | Stars | 핵심 가치 |
|---|------|-------|----------|
| 1 | obra/superpowers | 130K | 에이전트 스킬 프레임워크 — implementer/reviewer/TDD |
| 2 | thedotmack/claude-mem | 44K | Worker Service + SQLite + FTS5 + Progressive Disclosure |
| 3 | paperclipai/paperclip | - | Heartbeat 오케스트레이션 + Budget + Goals + Issues |
| 4 | garrytan/gstack | - | 42개 스킬 — /ship /review /investigate /autoplan /learn |
| 5 | kepano/obsidian-skills | - | 공식 Obsidian 스킬 (MD/Bases/Canvas/CLI/Defuddle) |
| 6 | YishenTu/claudian | 5,628 | Obsidian 내 Claude Code 임베드 |
| 7 | jylkim/obsidian-sync | 신규 | 멀티 에이전트 세션→Obsidian 동기화 + qmd 시맨틱 리콜 |
| 8 | willynikes2/knowledge-base-server | 121 | SQLite FTS5 + MCP + Obsidian Sync + Knowledge Promotion |
| 9 | b2bvic/subtlebodhi | 1 | 도메인 라우팅 + BM25 + 자기복구 스킬 |
| 10 | ballred/obsidian-claude-pkm | 1,292 | Goal Cascade + 4에이전트 + /adopt 볼트 감지 |
| 11 | ZanderRuss/obsidian-claude | 8 | 29명령 + 16에이전트 + PARA + 학술 파이프라인 |
| 12 | Knowledge Vault (gist) | - | 4기둥 PKM (Digestion/Knowledge/Tasks/Meetings) |
| 13 | **basicmachines-co/basic-memory** | **2,741** | **JARVIS 두뇌 이중화 핵심 — Entity/Observation/Relation 지식그래프 + 양방향 Sync + 하이브리드 검색 + MCP** |
| 14 | **axtonliu/obsidian-visual-skills** | **2,074** | **시각화 3종세트 — Excalidraw(8유형) + Mermaid(6유형) + Canvas** |

### CRITICAL 발견 — JARVIS 두뇌 이중화 아키텍처

```
1차 두뇌: 로컬 (~/.claude/cmux-jarvis/)
  ├── SQLite + FTS5 (knowledge DB)
  ├── JSON + MD 파일 (AI 전용 빠른 접근)
  └── 진화 실행 중 실시간 사용
        ↓ (Basic Memory 양방향 동기화)
2차 두뇌: Obsidian 볼트
  ├── Entity/Observation/Relation 지식 그래프
  ├── 하이브리드 검색 (FTS5 + FastEmbed 벡터)
  ├── MCP 서버 → Claude가 memory:// URL로 직접 탐색
  ├── WatchService → 실시간 파일 변경 감지
  ├── obsidian-sync → 멀티 에이전트 세션 동기화
  └── Visual Skills → Excalidraw/Mermaid/Canvas 자동 시각화
        ↓ (클라우드 동기화)
3차 백업: Obsidian Sync / iCloud / Git
  → 로컬 사고 시 완전 복원 가능
```

### 진화 파이프라인 강화 — 17개 신규 패턴 도입

| # | 패턴 | 출처 | 우선순위 |
|---|------|------|---------|
| F1 | "Do Not Trust the Report" 독립 검증 | Superpowers | CRITICAL |
| F2 | 4상태 보고 프로토콜 (DONE/CONCERNS/BLOCKED/NEEDS_CONTEXT) | Superpowers+GStack | CRITICAL |
| F3 | Worker Service 3단계 시작 | claude-mem | CRITICAL |
| F4 | Heartbeat 큐 기반 모델 (폴링→이벤트) | Paperclip | CRITICAL |
| F5 | Budget enforcement at run claim | Paperclip | CRITICAL |
| F6 | FTS5 + 트리거 자동 동기화 + BM25 가중 (title 10x) | claude-mem+KB-server | HIGH |
| F7 | 세션 컴팩션 정책 (maxRuns/Tokens/Age) | Paperclip | HIGH |
| F8 | Progressive Disclosure 4레벨 inject | claude-mem | HIGH |
| F9 | HOLD SCOPE 모드 (스코프 크리프 방지) | GStack | HIGH |
| F10 | Learnings JSONL (confidence, 중복허용, 자동무효화) | GStack | HIGH |
| F11 | 다단계 승인 (pending→revision→approved/rejected) | Paperclip | HIGH |
| F12 | 불변 감사 로그 (ReadonlySet, append-only) | Paperclip | HIGH |
| F13 | Basic Memory 양방향 동기화 (워터마크+Circuit Breaker) | Basic Memory | CRITICAL |
| F14 | Entity/Observation/Relation 지식 그래프 | Basic Memory | CRITICAL |
| F15 | memory:// URL 프로토콜 (깊이 탐색) | Basic Memory | HIGH |
| F16 | Excalidraw/Mermaid/Canvas 자동 시각화 | Visual Skills | HIGH |
| F17 | /autoplan 6원칙 자동 결정 + Dual Voice | GStack | MED |
