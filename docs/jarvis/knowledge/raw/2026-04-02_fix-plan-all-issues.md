# JARVIS 전체 이슈 수정 계획

**대상:** 5관점 심층 리뷰 발견 54건 (CRITICAL 21 + HIGH 19 + MEDIUM 14)
**날짜:** 2026-04-02
**수립자:** 전문 에이전트 (아키텍트 + 검증 + 보안)

---

## 수정 원칙

1. **CRITICAL은 설계 단계에서 해결** — 구현 전 JARVIS-PLAN-FULL.md에 반영
2. **HIGH는 Phase 1 구현에 포함** — 첫 버전부터 적용
3. **MEDIUM은 Phase 2 백로그** — 기능 동작 후 점진 개선
4. **각 수정은 독립적** — 한 수정이 다른 수정을 차단하지 않음
5. **수정 후 검증 방법 포함** — 수정이 실제로 문제를 해결했는지 확인

---

## Phase 0: 아키텍처 재설계 (CRITICAL 8건 일괄)

### FIX-01. 단일 정본 원칙 — A1 해결

**문제:** 1차(로컬 SQLite) / 2차(Basic Memory) 두뇌 split-brain
**수정:**

```
[기존]
JARVIS → 1차 두뇌(SQLite) 쓰기 → 2차(Obsidian) 동기화
사용자 → Obsidian 직접 편집 → 1차와 불일치

[수정]
                    ┌─ 읽기 ─┐
JARVIS ──쓰기──→ Obsidian 볼트 (마크다운 = 정본)
                    │
                    ↓ (Basic Memory WatchService)
              SQLite 인덱스 (FTS5 + 벡터 = 검색 캐시)
                    │
                    ↓ (Obsidian Sync / iCloud / Git)
              클라우드 백업
```

**핵심 변경:**
- 모든 쓰기는 마크다운 파일로 (Obsidian 볼트 디렉토리)
- SQLite는 검색 인덱스일 뿐, 정본이 아님
- Basic Memory의 SyncService가 파일→DB 단방향 동기화
- 사용자의 Obsidian 직접 편집도 자동 반영 (WatchService)

**JARVIS-PLAN-FULL.md 수정 내용:**
- "knowledge DB 스키마" 섹션 삭제 → "Basic Memory 연동" 섹션으로 대체
- "파일 기반 → 50건 시 DB 전환" 삭제 → "처음부터 파일+인덱스 이중"
- `~/.claude/cmux-jarvis/` 구조를 Obsidian 볼트 하위로 재배치

**검증:** Obsidian에서 파일 편집 → 10초 내 FTS5 검색 결과에 반영 확인

---

### FIX-02. GATE 이중 강제 — R1 해결

**문제:** GATE J-1이 SKILL.md 텍스트만으로 정의 → 프롬프트 우회 가능
**수정:**

```bash
# ~/.claude/hooks/cmux-jarvis-gate.sh (PreToolUse hook)
#!/bin/bash
# GATE J-1 하드웨어 강제

TOOL_NAME="$1"          # Edit, Write, Bash 등
TARGET_PATH="$2"        # 대상 파일 경로

# 1. JARVIS surface 식별
JARVIS_SURFACE=$(cat /tmp/cmux-jarvis-surface-id 2>/dev/null)
CURRENT_SURFACE=$(echo "$CLAUDE_SESSION_ID" | head -c 8)

# JARVIS surface가 아니면 통과
[ "$CURRENT_SURFACE" != "$JARVIS_SURFACE" ] && echo '{"continue":true}' && exit 0

# 2. 금지 경로 체크
BLOCKED_PATHS=(
  "/tmp/cmux-orch-enabled"
  "*/cmux-start/*"
  "*/cmux-pause/*"
  "*/cmux-uninstall/*"
)

for pattern in "${BLOCKED_PATHS[@]}"; do
  if [[ "$TARGET_PATH" == $pattern ]]; then
    echo '{"error":"GATE J-1: JARVIS는 이 경로에 접근할 수 없습니다: '"$TARGET_PATH"'"}'
    exit 1
  fi
done

# 3. 진화 중 설정 파일 보호 (/freeze 패턴 — E1 해결)
LOCK_FILE="/tmp/cmux-jarvis-evolution-lock"
if [ -f "$LOCK_FILE" ] && [[ "$TARGET_PATH" == *"settings.json"* ]]; then
  LOCK_OWNER=$(cat "$LOCK_FILE")
  if [ "$LOCK_OWNER" != "$CURRENT_SURFACE" ]; then
    echo '{"error":"GATE J-1: 진화 진행 중 설정 변경 차단. 진화 완료 후 시도하세요."}'
    exit 1
  fi
fi

echo '{"continue":true}'
```

**hooks.json 등록:**
```json
{
  "hooks": [
    {
      "matcher": "Edit|Write|Bash",
      "hooks": [{
        "type": "command",
        "command": "bash ~/.claude/hooks/cmux-jarvis-gate.sh \"$TOOL_NAME\" \"$TARGET_PATH\""
      }]
    }
  ]
}
```

**검증:**
- JARVIS surface에서 `/tmp/cmux-orch-enabled` 수정 시도 → deny 확인
- 진화 중 다른 surface에서 settings.json 수정 시도 → 경고 확인

---

### FIX-03. 진화 직렬 실행 + 잠금 — E1, E2 해결

**문제:** 동시 진화 충돌 + 진화 중 사용자 설정 수정 덮어쓰기
**수정:**

```
진화 시작 전:
  ① CURRENT_LOCK 파일 생성 → {"evo_id": "evo-001", "started": "ISO", "surface": "jarvis"}
  ② settings.json checksum 기록 → backup/evo-001/pre-checksum.txt
  ③ /freeze 활성화 → 다른 surface의 settings.json 수정 경고

진화 완료 시 (⑪ 반영 단계):
  ① 현재 settings.json checksum 비교
  ② 일치 → 직접 적용
  ③ 불일치 → 3-way merge:
     - BASE: backup/evo-001/settings.json (진화 시작 시점)
     - OURS: 진화 결과 settings.json
     - THEIRS: 현재 settings.json (사용자가 변경한 버전)
     - 충돌 시 → 사용자에게 AskUserQuestion
  ④ CURRENT_LOCK 삭제
  ⑤ /freeze 해제

새 진화 감지 시:
  - CURRENT_LOCK 존재 → 큐에 추가
  - 현재 진화 완료 후 큐에서 꺼내 실행
```

**큐 파일:** `~/.claude/cmux-jarvis/evolution-queue.json`
```json
[
  {"detected_at": "2026-04-02T15:30:00", "trigger": "dispatch_failure_3x", "priority": "high"}
]
```

**검증:**
- 진화 진행 중 `CURRENT_LOCK` 존재 확인
- 두 번째 진화 시도 → 큐에 추가 확인
- 사용자 설정 변경 후 진화 반영 → 3-way merge 동작 확인

---

### FIX-04. Evolution Worker 권한 제한 — R2 해결

**문제:** Worker가 JARVIS GATE 밖에서 설정을 직접 변경 가능
**수정:**

```
[기존]
JARVIS → 계획 전달 → Worker가 직접 구현(설정 수정 포함)

[수정]
JARVIS → 계획 전달 → Worker가 구현
  → Worker는 "변경 제안" 파일만 생성:
    evolutions/evo-001/06-implementation.md  (변경 내역)
    evolutions/evo-001/proposed-settings.json (제안된 설정)
  → Worker 완료 보고: DONE / DONE_WITH_CONCERNS / BLOCKED
  → JARVIS가 제안 검토 + 검증 + 사용자 승인 후 적용
```

**evolution-worker.md 수정:**
```markdown
## 권한 제한
- settings.json, ai-profile.json 직접 수정 **금지**
- 변경이 필요하면 `proposed-settings.json`에 제안만 기록
- JARVIS가 제안을 검증 후 적용
- allowed-tools: Read, Bash(읽기 전용 명령만), Write(evolutions/ 내부만)
```

**Worker PreToolUse hook:**
```bash
# Worker가 evolutions/ 외부에 쓰기 시도 시 차단
if [[ "$TARGET_PATH" != *"/cmux-jarvis/evolutions/"* ]]; then
  echo '{"error":"Evolution Worker: evolutions/ 디렉토리 외부 쓰기 금지"}'
  exit 1
fi
```

**검증:** Worker가 settings.json 직접 수정 시도 → hook deny 확인

---

### FIX-05. 무한 진화 루프 방지 — R3 해결

**문제:** 연속 진화가 끝없이 반복될 수 있음
**수정:**

```bash
# jarvis-evolution.sh에 추가
MAX_CONSECUTIVE_EVOLUTIONS=3
MAX_DAILY_EVOLUTIONS=10
COOLDOWN_AFTER_MAX=1800  # 30분

# 연속 진화 카운터
COUNTER_FILE="$JARVIS_DIR/.evolution-counter"
TODAY=$(date +%Y-%m-%d)

check_evolution_limits() {
  local consecutive=$(jq -r '.consecutive' "$COUNTER_FILE" 2>/dev/null || echo 0)
  local daily=$(jq -r ".daily[\"$TODAY\"]" "$COUNTER_FILE" 2>/dev/null || echo 0)
  local last_completed=$(jq -r '.last_completed' "$COUNTER_FILE" 2>/dev/null || echo 0)

  if [ "$consecutive" -ge "$MAX_CONSECUTIVE_EVOLUTIONS" ]; then
    echo "WARNING: 연속 $consecutive회 진화 실행. 사용자 승인 필요."
    # AskUserQuestion → "계속할까요? (연속 3회 진화 실행됨)"
    return 1
  fi

  if [ "$daily" -ge "$MAX_DAILY_EVOLUTIONS" ]; then
    echo "ERROR: 일일 진화 상한 $MAX_DAILY_EVOLUTIONS회 도달. 내일까지 대기."
    return 2
  fi

  return 0
}

# 동일 설정 영역 반복 감지
check_same_area_repeat() {
  local target_area="$1"
  local recent=$(jq -r '.recent_areas[-3:][]' "$COUNTER_FILE" 2>/dev/null)
  local repeat_count=$(echo "$recent" | grep -c "$target_area")

  if [ "$repeat_count" -ge 2 ]; then
    echo "WARNING: '$target_area' 영역에서 연속 3회 진화 시도. 근본 원인 재분석 필요."
    return 1
  fi
  return 0
}
```

**검증:**
- 연속 3회 진화 → 4번째에서 사용자 확인 요청 확인
- 일일 10회 도달 → 추가 진화 차단 확인
- 동일 영역 3회 반복 → 에스컬레이션 확인

---

### FIX-06. 메트릭 사전 정의 — V1 해결

**문제:** 진화 성공/실패 판정 기준이 정량적이지 않음
**수정:**

```json
// ~/.claude/cmux-jarvis/metric-dictionary.json
{
  "metrics": {
    "dispatch_failure_rate": {
      "source": "eagle-status.json",
      "formula": "(failed_dispatch / total_dispatch) * 100",
      "unit": "%",
      "direction": "lower_is_better",
      "threshold": {"good": 5, "warning": 20, "critical": 50}
    },
    "stall_count": {
      "source": "watcher.log",
      "formula": "grep -c 'STALL' watcher.log (최근 1시간)",
      "unit": "건",
      "direction": "lower_is_better",
      "threshold": {"good": 0, "warning": 2, "critical": 5}
    },
    "done_latency_avg": {
      "source": "eagle-status.json",
      "formula": "avg(task_completed_at - task_started_at)",
      "unit": "초",
      "direction": "lower_is_better",
      "threshold": {"good": 300, "warning": 600, "critical": 1200}
    },
    "context_overflow_count": {
      "source": "PostCompact hook 실행 횟수",
      "formula": "count(compact events) (최근 24시간)",
      "unit": "건",
      "direction": "lower_is_better",
      "threshold": {"good": 2, "warning": 5, "critical": 10}
    },
    "error_rate": {
      "source": "eagle-status.json",
      "formula": "(error_surfaces / total_surfaces) * 100",
      "unit": "%",
      "direction": "lower_is_better",
      "threshold": {"good": 0, "warning": 10, "critical": 30}
    }
  },
  "ab_test_rules": {
    "min_improvement": 0.05,
    "min_observations": 3,
    "simplicity_threshold": {"max_lines_added": 50, "max_files_changed": 3}
  }
}
```

**A/B 판정 로직 강화:**
```python
def judge_evolution(before, after, changes):
    improvements = {}
    for metric, config in METRIC_DICT.items():
        b = before.get(metric, 0)
        a = after.get(metric, 0)
        if config["direction"] == "lower_is_better":
            delta = (b - a) / max(b, 1)
        else:
            delta = (a - b) / max(b, 1)
        improvements[metric] = delta

    # 모든 메트릭이 악화 → discard
    if all(v < 0 for v in improvements.values()):
        return "DISCARD", "모든 메트릭 악화"

    # 개선 미미 + 복잡성 과도 → discard (Simplicity criterion)
    avg_improvement = sum(improvements.values()) / len(improvements)
    if avg_improvement < 0.05 and changes["lines_added"] > 50:
        return "DISCARD", f"미미한 개선({avg_improvement:.1%}) + 높은 복잡성({changes['lines_added']}줄)"

    # CRITICAL 메트릭 악화 → discard
    for metric, delta in improvements.items():
        if delta < -0.1 and METRIC_DICT[metric]["threshold"]["critical"]:
            return "DISCARD", f"{metric} 심각한 악화: {delta:.1%}"

    return "KEEP", f"평균 개선: {avg_improvement:.1%}"
```

**검증:**
- 메트릭 수집 스크립트로 Before/After 자동 캡처 확인
- 미미한 개선 + 높은 복잡성 → DISCARD 판정 확인
- CRITICAL 메트릭 악화 → 즉시 DISCARD 확인

---

### FIX-07. 롤백 2중화 + 3세대 유지 — B1 해결

**문제:** 백업이 로컬 단일 경로에만 존재
**수정:**

```
백업 저장 시:
  ① 로컬: ~/.claude/cmux-jarvis/evolutions/evo-001/backup/
  ② Obsidian: JARVIS/Backups/evo-001/ (마크다운 + JSON embed)
  ③ Git: 자동 커밋 (PostToolUse hook 패턴)

3세대 유지:
  - 현재 설정 (active)
  - 직전 백업 (evo-N)
  - 그 이전 백업 (evo-N-1)
  - 4번째 이상 → 로컬 삭제, Obsidian에는 보존 (아카이브)
```

**자동 git 커밋 (설정 변경 시):**
```bash
# cmux-settings-backup.sh에 추가
backup_with_git() {
  local evo_id="$1"
  local backup_dir="$JARVIS_DIR/evolutions/$evo_id/backup"

  # 로컬 백업
  cp "$SETTINGS_JSON" "$backup_dir/settings.json"
  cp "$AI_PROFILE_JSON" "$backup_dir/ai-profile.json" 2>/dev/null

  # Obsidian 백업 (선택적)
  if [ -n "$OBSIDIAN_VAULT" ]; then
    local obs_dir="$OBSIDIAN_VAULT/JARVIS/Backups/$evo_id"
    mkdir -p "$obs_dir"
    cp "$backup_dir/"* "$obs_dir/"
  fi

  # Git 커밋 (선택적)
  if command -v git >/dev/null && [ -d "$JARVIS_DIR/.git" ]; then
    cd "$JARVIS_DIR"
    git add "evolutions/$evo_id/backup/"
    git commit -m "backup: $evo_id pre-evolution snapshot" --quiet 2>/dev/null
  fi

  # 3세대 초과 로컬 정리
  cleanup_old_backups 3
}
```

**검증:**
- 백업 생성 → 로컬 + Obsidian + git 3곳 확인
- 4번째 진화 → 1번째 백업 로컬에서 삭제, Obsidian에 보존 확인
- 로컬 삭제 후 Obsidian에서 복원 가능 확인

---

### FIX-08. 마이크로 스킬 분리 — A3 해결

**문제:** 단일 SKILL.md에 진화/지식/Obsidian/시각화/모니터링 전부 포함
**수정:**

```
~/.claude/skills/cmux-jarvis/
├── SKILL.md                    # 코어: 역할 + GATE + 모니터링 + 라우팅
├── skills/
│   ├── evolution/
│   │   └── SKILL.md            # 진화 파이프라인 11단계
│   ├── knowledge/
│   │   └── SKILL.md            # 지식 관리 + Progressive Disclosure
│   ├── obsidian-sync/
│   │   └── SKILL.md            # Obsidian 연동 (선택적)
│   └── visualization/
│       └── SKILL.md            # Excalidraw/Mermaid/Canvas
├── agents/
│   └── evolution-worker.md     # Worker 에이전트 정의
├── hooks/
│   ├── cmux-jarvis-gate.sh     # GATE J-1 hook
│   ├── cmux-settings-backup.sh # ConfigChange 백업
│   └── jarvis-session-start.sh # SessionStart inject
└── references/
    ├── metric-dictionary.json  # 메트릭 사전
    ├── red-flags.md            # Red Flags 테이블
    └── iron-laws.md            # 3 Iron Laws
```

**코어 SKILL.md (간결):**
```markdown
---
name: cmux-jarvis
description: "JARVIS 시스템 관리자 — 오케스트레이션 감시 + 설정 진화 + 지식 관리"
user-invocable: false
---

# JARVIS — 능동형 시스템 관리자

## 역할
- 오케스트레이션 상태 모니터링
- 개선 여지 감지 → 진화 파이프라인 실행
- 학습 지식 축적 + Obsidian 동기화

## GATE J-1 (hook으로 강제)
(Iron Laws 3개 + Red Flags 참조)

## 모니터링 항목
(eagle-status, watcher.log, memories.json)

## 스킬 라우팅
- 개선 감지 → evolution/SKILL.md 호출
- 학습 필요 → knowledge/SKILL.md 호출
- 문서 동기화 → obsidian-sync/SKILL.md 호출
- 시각화 요청 → visualization/SKILL.md 호출
```

**검증:** 각 마이크로 스킬이 독립적으로 호출/테스트 가능 확인

---

## Phase 1: HIGH 이슈 수정 (12건)

### FIX-09. 의존성 폴백 체인 — A2 해결

```
지식 검색 시:
  Try 1: Basic Memory MCP (memory:// URL) → 하이브리드 검색
  Try 2: 로컬 SQLite FTS5 직접 쿼리 (MCP 불가 시)
  Try 3: 마크다운 파일 grep (SQLite 불가 시)

문서 쓰기 시:
  Try 1: obsidian CLI create/append
  Try 2: 직접 파일 쓰기 (Obsidian 미실행 시)

시각화 시:
  Try 1: Excalidraw/Mermaid (Obsidian 플러그인 사용)
  Try 2: ASCII 다이어그램 (마크다운 텍스트)
```

**검증:** MCP 서버 중지 → FTS5 폴백 동작 확인 → grep 폴백 동작 확인

---

### FIX-10. 스키마 통합 — A4 해결

**Basic Memory 모델로 통합:**
```
knowledge 테이블 → Entity (note_type='knowledge')
evolutions 테이블 → Entity (note_type='evolution')
settings_backups → Entity (note_type='backup')

기존 JSON 필드 → Observation (category별)
  - [source] github
  - [topic] FTS5 best practices
  - [finding] BM25 가중치 title 10x
  - [applicable_to] cmux-jarvis/knowledge.md

관계 → Relation
  - evo-001 --requires--> FTS5 knowledge
  - evo-001 --inspired_by--> Superpowers TDD
```

---

### FIX-11. hook 타임아웃 대응 — A5 해결

```bash
# jarvis-session-start.sh (60초 제한)
# 전략: 캐시된 요약만 inject (최대 500토큰)

CACHE_FILE="$JARVIS_DIR/.session-context-cache.json"
CACHE_AGE_LIMIT=300  # 5분

if [ -f "$CACHE_FILE" ] && [ $(($(date +%s) - $(stat -f%m "$CACHE_FILE"))) -lt $CACHE_AGE_LIMIT ]; then
  # 캐시 유효 → 즉시 반환 (<1초)
  cat "$CACHE_FILE"
else
  # 캐시 만료 → 빠른 요약 생성 (최대 5초)
  generate_quick_summary > "$CACHE_FILE"
  cat "$CACHE_FILE"
fi

# 무거운 검색은 UserPromptSubmit hook에서 lazy load
```

---

### FIX-12. Worker 완료 신호 프로토콜 — A6 해결

```
Evolution Worker 완료 시:
  ① evolutions/evo-001/STATUS 파일 업데이트
     = "DONE" | "DONE_WITH_CONCERNS" | "BLOCKED" | "NEEDS_CONTEXT"
  ② evolutions/evo-001/09-result.md 생성
  ③ cmux send --surface jarvis "진화 evo-001 완료: DONE"

JARVIS 측:
  - cmux send 수신 → 즉시 A/B 테스트 시작
  - 또는 STATUS 파일 polling (5초 간격, 최대 30분)
  - 30분 초과 → TIMEOUT → 자동 롤백
```

---

### FIX-13. Circuit Breaker + STATUS 파일 — E3 해결

```json
// evolutions/evo-001/STATUS
{
  "evo_id": "evo-001",
  "phase": "implementing",  // detecting|analyzing|planning|implementing|testing|ab_testing|reporting
  "started_at": "2026-04-02T10:30:00Z",
  "updated_at": "2026-04-02T10:35:00Z",
  "worker_pid": 12345,
  "retry_count": 0,
  "max_retries": 1
}
```

**JARVIS 재시작 시 복구 로직:**
```
STATUS 파일 확인:
  - phase=completed/failed → 정상 종료, 무시
  - phase=implementing + worker_pid 살아있음 → 대기
  - phase=implementing + worker_pid 죽음 + retry_count < max → 재시도
  - phase=implementing + worker_pid 죽음 + retry_count >= max → 롤백 + failure 문서화
```

---

### FIX-14. FTS5 인덱스 재구축 — E4 해결

```bash
# jarvis-maintenance.sh rebuild-fts
rebuild_fts_index() {
  echo "FTS5 인덱스 재구축 시작..."
  sqlite3 "$JARVIS_DB" <<'SQL'
    DROP TABLE IF EXISTS knowledge_fts;
    CREATE VIRTUAL TABLE knowledge_fts USING fts5(
      topic, content, summary, tags,
      content='knowledge', content_rowid='id',
      tokenize='unicode61'
    );
    INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild');
SQL
  echo "FTS5 인덱스 재구축 완료."
}
```

---

### FIX-15. 학습 데이터 오염 방지 — R4 해결

```json
// 학습 저장 시 필수 필드
{
  "confidence": 7,           // 1-10, 5 미만은 inject 제외
  "verified_by": "observed", // observed|user-stated|automated
  "valid_until": null,       // 참조 파일 삭제 시 자동 무효화
  "referenced_files": ["settings.json"],
  "contradicts": null        // 이전 학습과 모순 시 경고
}
```

**inject 필터:**
```python
def select_knowledge_for_inject(query, max_items=5):
    results = fts5_search(query)
    # confidence 5 이상만
    results = [r for r in results if r.confidence >= 5]
    # 무효화된 학습 제외
    results = [r for r in results if not is_invalidated(r)]
    # 최근 + 관련성 높은 순 정렬
    results.sort(key=lambda r: (r.relevance, r.confidence, -r.age), reverse=True)
    return results[:max_items]
```

---

### FIX-16. Budget enforcement — R5 해결

```json
// ~/.claude/cmux-jarvis/config.json
{
  "budget": {
    "daily_token_limit": 500000,
    "daily_api_calls_limit": 100,
    "warning_threshold": 0.8,
    "hard_stop_threshold": 1.0,
    "learning_budget_ratio": 0.3,
    "evolution_budget_ratio": 0.7
  }
}
```

```bash
# 각 API 호출 전 체크
check_budget() {
  local today=$(date +%Y-%m-%d)
  local used=$(jq -r ".usage[\"$today\"].tokens" "$JARVIS_DIR/budget-tracker.json" 2>/dev/null || echo 0)
  local limit=$(jq -r ".budget.daily_token_limit" "$JARVIS_DIR/config.json")
  local ratio=$(echo "scale=2; $used / $limit" | bc)

  if (( $(echo "$ratio >= 1.0" | bc -l) )); then
    echo "BUDGET_EXCEEDED"
    return 1
  elif (( $(echo "$ratio >= 0.8" | bc -l) )); then
    echo "BUDGET_WARNING: ${ratio}%"
    # cmux notify "JARVIS 일일 예산 80% 소진"
  fi
  return 0
}
```

---

### FIX-17. TDD 유형별 테스트 템플릿 — V2 해결

```markdown
## 진화 유형별 테스트 템플릿

### 설정 변경 진화
1. JSON 스키마 검증: `python -c "import json; json.load(open('settings.json'))"`
2. 해당 hook 트리거 시뮬레이션: ConfigChange hook 실행 → 오류 없음
3. surface 재시작 후 정상 동작: `cmux send --surface X "eagle status"` → 응답 확인

### hook 추가/수정 진화
1. hook 파일 존재 + 실행 권한: `[ -x "$HOOK_PATH" ]`
2. 트리거 이벤트 시뮬레이션: 해당 이벤트 발생 → hook 실행 확인
3. hook 출력 JSON 유효성: `echo "$OUTPUT" | python -m json.tool`
4. 기존 hook 비간섭: 다른 hook 정상 동작 확인

### 스킬 수정 진화
1. SKILL.md YAML frontmatter 파싱: `yq '.name' SKILL.md`
2. 스킬 호출 시뮬레이션: 해당 트리거 조건 → 스킬 활성화 확인
3. 기존 스킬 비간섭: 다른 스킬 정상 호출 확인
```

---

### FIX-18. 독립 검증 메커니즘 — V3 해결

```bash
# jarvis-verify.sh — JARVIS/Worker 무관한 독립 검증
verify_evolution() {
  local evo_id="$1"
  local plan="$JARVIS_DIR/evolutions/$evo_id/03-plan.md"
  local result="$JARVIS_DIR/evolutions/$evo_id/06-implementation.md"

  echo "=== 독립 검증: $evo_id ==="

  # 1. 파일 변경 확인 (계획 vs 실제)
  local planned_files=$(grep -oP '(?<=파일: ).*' "$plan")
  local actual_files=$(grep -oP '(?<=수정: ).*' "$result")
  diff <(echo "$planned_files" | sort) <(echo "$actual_files" | sort) && echo "✓ 파일 일치" || echo "✗ 파일 불일치"

  # 2. 설정 유효성
  python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))" && echo "✓ JSON 유효" || echo "✗ JSON 오류"

  # 3. 메트릭 자동 수집
  collect_metrics "after" "$evo_id"

  # 4. Before/After 비교
  compare_metrics "$evo_id"
}
```

---

### FIX-19. JARVIS 자체 장애 복구 — B2 해결

```bash
# cmux-start/SKILL.md에 추가
# JARVIS pane 생성 시 자동 복구 체크

jarvis_recovery_check() {
  local status_files=$(ls "$JARVIS_DIR/evolutions"/*/STATUS 2>/dev/null)

  for sf in $status_files; do
    local phase=$(jq -r '.phase' "$sf")
    local pid=$(jq -r '.worker_pid' "$sf")

    case "$phase" in
      completed|failed)
        continue ;;
      *)
        if ! kill -0 "$pid" 2>/dev/null; then
          local evo_id=$(basename $(dirname "$sf"))
          echo "WARNING: 진화 $evo_id가 비정상 종료 (phase=$phase). 롤백 실행."
          jarvis_rollback "$evo_id"
        fi ;;
    esac
  done
}
```

---

### FIX-20. PostCompact 컨텍스트 복원 — B3 해결

```bash
# hooks.json에 PostCompact hook 추가
{
  "matcher": "PostCompact",
  "hooks": [{
    "type": "command",
    "command": "bash ~/.claude/hooks/jarvis-post-compact.sh"
  }]
}

# jarvis-post-compact.sh
# /compact 후 현재 진화 컨텍스트 재주입
CURRENT_LOCK="$JARVIS_DIR/.evolution-lock"
if [ -f "$CURRENT_LOCK" ]; then
  EVO_ID=$(jq -r '.evo_id' "$CURRENT_LOCK")
  NAV="$JARVIS_DIR/evolutions/$EVO_ID/nav.md"
  if [ -f "$NAV" ]; then
    # nav.md 내용을 컨텍스트에 재주입
    echo '{"hookSpecificOutput":{"additionalContext":"'"$(cat "$NAV" | jq -Rs .)"'"}}'
  fi
fi
```

---

## Phase 2: MEDIUM 이슈 수정 (14건)

### FIX-21 ~ FIX-34 (백로그)

| # | 이슈 | 수정 방향 | 복잡도 |
|---|------|----------|--------|
| FIX-21 | A7 볼트 경로 | config.json + 초기 설정 마법사 | LOW |
| FIX-22 | A8 settings.json merge | jq 기반 안전 조작 + 백업 | LOW |
| FIX-23 | A9 DAG 순환 | Python topological_sort 검증 | LOW |
| FIX-24 | E5 1000+ 파일 | 날짜별 하위 디렉토리 분할 | LOW |
| FIX-25 | E7 한국어 FTS5 | LIKE 폴백 + 2글자 이상 매칭 | MED |
| FIX-26 | E8 A/B 통계 유의성 | 최소 3회 반복 + 중앙값 비교 | MED |
| FIX-27 | E9 알림 타임아웃 | 30분 타임아웃 → 큐잉 | LOW |
| FIX-28 | R6 승인 피로 | 위험도 분류 LOW/MED/HIGH | MED |
| FIX-29 | R7 Watcher 역할 | 역할 분리 문서 명확화 | LOW |
| FIX-30 | R8 민감 정보 | 백업 시 API키 마스킹 | MED |
| FIX-31 | B4 MCP 포트 | stdio 기반 통신 또는 설정 가능 포트 | LOW |
| FIX-32 | B5 마이그레이션 | 전체 백업 + failure 보존 + 보고서 | MED |
| FIX-33 | B6 전원 차단 | 원자적 쓰기 (tmp→rename) | LOW |
| FIX-34 | B7 Obsidian 지연 | eventual consistency 명시 | LOW |

---

## 구현 순서 총정리

```
Phase 0 — 아키텍처 재설계 (JARVIS-PLAN-FULL.md 수정)
  FIX-01: 단일 정본 원칙 (A1)
  FIX-02: GATE hook 이중 강제 (R1)
  FIX-03: 진화 직렬 + 잠금 (E1, E2)
  FIX-04: Worker 권한 제한 (R2)
  FIX-05: 무한 루프 방지 (R3)
  FIX-06: 메트릭 사전 (V1)
  FIX-07: 롤백 2중화 (B1)
  FIX-08: 마이크로 스킬 분리 (A3)

Phase 1 — 핵심 기능 구현 시 반영
  FIX-09: 의존성 폴백 (A2)
  FIX-10: 스키마 통합 (A4)
  FIX-11: hook 타임아웃 (A5)
  FIX-12: Worker 완료 신호 (A6)
  FIX-13: Circuit Breaker (E3)
  FIX-14: FTS5 재구축 (E4)
  FIX-15: 학습 오염 방지 (R4)
  FIX-16: Budget enforcement (R5)
  FIX-17: TDD 템플릿 (V2)
  FIX-18: 독립 검증 (V3)
  FIX-19: 장애 복구 (B2)
  FIX-20: PostCompact 복원 (B3)

Phase 2 — 점진 개선 (백로그)
  FIX-21 ~ FIX-34: MEDIUM 14건
```

---

## 검증 매트릭스

| FIX | 검증 방법 | 자동화 |
|-----|----------|--------|
| 01 | Obsidian 편집 → FTS5 반영 (<10s) | 수동 |
| 02 | GATE 차단 경로 접근 → deny | 자동 (테스트 스크립트) |
| 03 | 동시 진화 시도 → 큐잉 | 자동 |
| 04 | Worker 외부 쓰기 → deny | 자동 |
| 05 | 연속 4회 → 사용자 확인 | 자동 |
| 06 | A/B 메트릭 수집 → JSON 출력 | 자동 |
| 07 | 백업 3곳 존재 확인 | 자동 |
| 08 | 각 스킬 독립 호출 | 수동 |
| 09 | MCP 중지 → FTS5 폴백 | 자동 |
| 10 | Entity 생성 → 기존 검색 호환 | 자동 |
| 11 | SessionStart <5s | 자동 (타이밍) |
| 12 | Worker DONE → JARVIS 수신 | 자동 |
| 13 | Worker 강제 종료 → STATUS 복구 | 자동 |
| 14 | FTS5 손상 → rebuild 후 검색 | 수동 |
| 15 | confidence<5 학습 → inject 제외 | 자동 |
| 16 | 예산 80% → 경고 | 자동 |
| 17 | 설정 변경 → JSON 유효성 | 자동 |
| 18 | Before/After 메트릭 비교 | 자동 |
| 19 | JARVIS 재시작 → 중단 진화 롤백 | 자동 |
| 20 | /compact → nav.md 재주입 | 자동 |
