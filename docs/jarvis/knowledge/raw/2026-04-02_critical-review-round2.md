# JARVIS 계획 2차 비판적 리뷰 — 아키텍트 × 엣지케이스 × Iron Law 검증

**대상:** FIX 반영된 JARVIS-PLAN-FULL.md (최신 버전)
**날짜:** 2026-04-02
**자세:** 매우 비판적 — "이 계획대로 구현하면 실패할 곳"을 찾는다

---

## 1. 아키텍트 — 구조적 모순 + 실현 불가능 요소

### FATAL-A1. 문서 구조가 아직도 이중 정의되어 있다

FIX-01에서 "Obsidian = 정본, SQLite = 캐시"로 결정했다고 하면서,
**문서 중반에 구버전 디렉토리 구조가 그대로 남아있다** (190~233줄):

```
~/.claude/cmux-jarvis/
├── nav-evolutions.md
├── nav-failures.md
├── success/
├── failure/
├── knowledge/raw/  (JSON 파일)
├── knowledge/summary.md
└── jarvis-db.sqlite
```

이것은 FIX-01 "마크다운 정본" 원칙과 **직접 모순**:
- `success/`, `failure/` 폴더 → Obsidian `Evolutions/` 폴더와 중복
- `knowledge/raw/` JSON → Basic Memory Observation 문법과 중복
- `knowledge/summary.md` → Obsidian Knowledge Index.base와 중복
- `jarvis-db.sqlite` → Basic Memory SyncService가 관리하는 SQLite와 중복

**판정: 구버전 잔재 미삭제. 구현 시 어느 구조를 따를지 혼란 필연적.**

---

### FATAL-A2. 구현 순서가 2벌 존재한다

324줄의 "수정/생성 파일" 섹션에 22개 파일 + 3 Phase 순서가 있고,
519줄의 "구현 순서"에 **이전 버전의 11단계**가 그대로 남아있다:

```
1. cmux-jarvis/SKILL.md 생성
2. cmux-jarvis/agents/evolution-worker.md 생성
...
11. 테스트 (설치 충돌 검증 포함)
```

이것은 324줄의 FIX 반영된 22파일 + Phase 1/2/3 구현 순서와 **완전히 다르다**.
두 번째 구현 순서는 GATE hook도 없고, Worker 제한도 없고, 3중 백업도 없다.

**판정: 구버전 구현 순서 미삭제. 실행자가 어느 것을 따를지 모호.**

---

### FATAL-A3. "Obsidian 선택적" vs "Obsidian = 정본"이 자기 모순

핵심 아키텍처 원칙에서:
- FIX-01: "모든 쓰기는 마크다운 파일로 (Obsidian 볼트 디렉토리)" = **Obsidian 필수**
- FIX-09: "Obsidian 연동은 **선택적** — 없어도 1차 두뇌만으로 완전 동작" = **Obsidian 선택**

**이 둘은 양립 불가.** 정본이 Obsidian이면 Obsidian 없이 동작할 수 없다.

**해결안:** 2가지 모드를 명시적으로 분리해야 함:
- **모드 A (Obsidian 활성):** 마크다운 = 정본, SQLite = 캐시
- **모드 B (Obsidian 없음):** `~/.claude/cmux-jarvis/` 마크다운 = 정본, SQLite = 캐시
- 두 모드 모두 "마크다운이 정본, SQLite가 캐시"는 동일
- 차이는 정본 마크다운의 **위치**만 다름 (Obsidian 볼트 vs 로컬)

---

### HIGH-A4. Basic Memory 의존이 실현 가능한가?

계획은 Basic Memory MCP 서버를 전제하지만:
- Basic Memory는 **Python 패키지** (pip install basic-memory)
- cmux는 **bash 기반** (Node.js 의존도 최소화)
- Basic Memory 설치 = Python 3.10+ 필수 + pip + SQLAlchemy + FastEmbed
- FastEmbed = ONNX 런타임 = 수백 MB 다운로드

**사용자에게 Python + pip + Basic Memory 설치를 강제할 수 있는가?**
cmux의 설계 원칙이 "bash만으로 동작, 최소 의존성"이라면 Basic Memory는 원칙 위반.

**해결안:** Basic Memory를 Phase 3 (선택적 기능)으로 격하하고,
Phase 1은 `sqlite3` CLI (macOS 내장) + 자체 FTS5 스키마로 구현.

---

### HIGH-A5. hook 5개의 등록/충돌 관리가 없다

5개 hook 파일을 만들지만 어떤 settings.json hooks 섹션에 어떻게 등록하는지 상세 없음:
- `cmux-jarvis-gate.sh` → PreToolUse의 어떤 matcher?
- `cmux-jarvis-worker-gate.sh` → Worker surface에만 적용? 전체?
- `cmux-settings-backup.sh` → ConfigChange matcher
- `jarvis-session-start.sh` → SessionStart matcher
- `jarvis-post-compact.sh` → PostCompact matcher

**Worker gate hook이 전 surface에 등록되면 Main/Watcher도 영향 받는다.**
Worker surface에서만 활성화하는 방법이 설계되지 않았다.

---

## 2. 엣지케이스 — 현실에서 깨지는 시나리오

### FATAL-E1. 3-way merge는 settings.json에서 작동하지 않는다

계획: "⑪ 반영 — 3-way merge (백업 + 진화결과 + 현재상태)"

settings.json은 **JSON 파일**이다. 3-way merge는 **텍스트 기반** (git merge, diff3).
JSON에서 텍스트 기반 3-way merge를 하면:
- 같은 키의 다른 값 → 충돌 마커 `<<<<<<<` → JSON 파싱 오류
- 배열 요소 순서 변경 → 의미적으로 동일해도 텍스트 충돌
- 중첩 객체 → 라인 단위 diff가 잘못된 위치에서 끊김

**해결안:** JSON-aware merge 필요. `jq` 기반 키별 병합:
```bash
# 키별 비교: backup vs current → 사용자 변경 키 추출
# backup vs proposed → 진화 변경 키 추출
# 겹치는 키만 충돌 → AskUserQuestion
```
또는 더 단순하게: 진화가 변경한 키만 패치 적용 (JSON Patch RFC 6902).

---

### FATAL-E2. "최소 3회 반복" A/B 테스트가 설정 변경에서 불가능

계획: "⑩ A/B 테스트 — 최소 3회 반복"

설정 변경의 A/B를 3회 반복하려면:
1. 백업 복원 → 설정 적용 → 메트릭 수집 (1회)
2. 백업 복원 → 설정 적용 → 메트릭 수집 (2회)
3. 백업 복원 → 설정 적용 → 메트릭 수집 (3회)

이것은 **설정을 3번 토글**하는 것. 매번 surface 재시작이 필요할 수 있고,
오케스트레이션 중이라면 **진행 중 작업을 3번 중단**시킨다.

**판정: 설정 변경 A/B를 3회 반복하는 것은 비현실적.**

**해결안:**
- 설정 변경: 1회 적용 + 관찰 기간 (예: 10분) + 메트릭 수집
- 반복 검증이 필요한 경우: 동일 조건에서 3회 태스크 수행 후 메트릭 비교
- "3회 반복"은 코드 변경 진화에만 적용, 설정 변경에는 "관찰 기간"으로 대체

---

### HIGH-E3. CURRENT_LOCK 파일이 JARVIS 크래시 시 영구 잠금

CURRENT_LOCK 생성 → JARVIS 크래시 → CURRENT_LOCK 남음 → 모든 진화 영구 차단

FIX-19에서 "JARVIS 재시작 시 STATUS 확인 → 복구"를 했지만,
**CURRENT_LOCK과 STATUS 파일은 별개.** STATUS가 없는데 LOCK만 남아있으면?

**해결안:** LOCK 파일에 TTL(Time-To-Live) 추가:
```json
{"evo_id": "evo-001", "created_at": "2026-04-02T10:00:00Z", "ttl_minutes": 60}
```
60분 초과된 LOCK → 자동 해제 (stale lock 정리).

---

### HIGH-E4. cmux send로 proposed-settings.json 전달 경로의 크기 제한

Worker가 proposed-settings.json을 생성하면 JARVIS가 읽어야 한다.
하지만 JARVIS가 읽는 방법이 불명확:
- JARVIS 세션에서 Read 도구로 파일을 읽는다? → 누가 트리거하나?
- cmux send로 내용을 전달한다? → settings.json이 수십 KB일 수 있음 → cmux send 크기 제한?

**해결안:** Worker 완료 시 cmux send는 "DONE" 신호만, 파일 경로를 포함:
```
cmux send --surface jarvis "EVOLUTION_DONE evo-001 /path/to/proposed-settings.json"
```
JARVIS가 경로를 파싱하여 Read로 읽음.

---

### HIGH-E5. "⑤로 돌아가 순환"의 종료 조건이 없다

파이프라인에서: "⑨ E2E — 문제 발생 시 → ⑤로 돌아가 순환, Circuit Breaker: 재시도 1회"

Circuit Breaker가 **진화 단위**인지 **루프 단위**인지 모호:
- 진화 단위: evo-001 전체에서 1회만 재시도 → 합리적
- 루프 단위: ⑤→⑨ 반복마다 1회 재시도 → 무한 가능 (매번 새 루프니까 "1회")

**판정: "재시도 1회"의 범위가 불명확.**

**해결안:** 명시적으로: "단일 진화(evo-001) 내에서 ⑤→⑨ 순환은 최대 2회.
2회 실패 → DISCARD + failure 문서화. 새 진화로 재시도하지 않음."

---

## 3. Iron Law 검증 — 3개 Iron Law가 실제로 지켜지는지

### Iron Law #1: "NO EVOLUTION WITHOUT USER APPROVAL FIRST"

**위반 시나리오 3개:**

**IL1-V1. 승인 후 계획 변경**
사용자가 ③에서 승인 → JARVIS가 ⑤에서 계획 수립 → 계획이 승인 시점과 다름
승인은 "진화하겠습니다" 수준이었는데, 실제 계획은 사용자가 모르는 내용.

**판정: 승인 시점과 실행 시점의 정보 비대칭. 사실상 blank check.**

**해결안:** 2단계 승인:
- ③ 1차 승인: "개선 여지가 있습니다. 계획을 수립할까요?" (가벼움)
- ⑤ 이후 2차 승인: "이 계획대로 실행할까요?" (구체적 diff 표시)

---

**IL1-V2. cmux notify가 도달하지 않는 경우**
cmux notify → 사용자가 AFK → 타임아웃 없음 → JARVIS 무한 대기
→ 이 상태에서 새 진화 감지 → 큐에 쌓임 → 사용자 돌아왔을 때 큐 10개

**판정: 타임아웃 미정의로 Iron Law는 지켜지지만 시스템이 정체.**

**해결안:** 승인 요청 타임아웃 30분 → 자동 "보류" → 다음 접속 시 리마인드.
큐 크기 제한 = 5. 초과 시 우선순위 낮은 것 자동 폐기.

---

**IL1-V3. "사용자 승인"의 정의가 모호**
사용자가 "OK"만 입력하면 승인인가? "좋아 해봐"도 승인? "음..."은?
자동 파싱으로 "OK/예/yes/좋아" = 승인 처리하면 오탐 가능.

**해결안:** AskUserQuestion의 선택지를 명확히:
```
"traits inject 진화를 실행할까요?"
[실행] [보류] [폐기] [상세 보기]
```
free-text 아닌 구조화된 선택만 승인으로 인정.

---

### Iron Law #2: "NO IMPLEMENTATION WITHOUT FAILING TEST FIRST"

**위반 시나리오 3개:**

**IL2-V1. "설정 변경"의 failing test가 무엇인가?**
settings.json의 키 하나 변경 → 이것의 "실패하는 테스트"란?
- JSON 스키마 테스트? → 키 추가는 항상 유효, 테스트가 실패할 수 없음
- 동작 테스트? → 설정 적용 전에 동작을 테스트할 수 없음 (적용해야 동작이 바뀜)

**판정: 설정 변경에 TDD가 의미론적으로 적용 불가한 경우가 있다.**

**해결안:** Iron Law #2를 수정:
- 코드/hook/스킬 변경: TDD 엄격 적용
- 설정값 변경: **예상 결과 문서화** (= "테스트") + 적용 후 결과 대조 (= "검증")
- "failing test first"를 "expected outcome documented first"로 완화

---

**IL2-V2. test-templates.md가 존재하지만 강제 메커니즘이 없다**
테스트 템플릿을 참조하라고 했지만, Evolution Worker가 무시하면?
SKILL.md에 "TDD 필수"라고 적어도 LLM이 건너뛸 수 있다.

**판정: 테스트 작성을 hook으로 강제하는 방법이 없다.**

**해결안:** Worker 완료 보고에 **테스트 결과 필수 필드** 추가:
```json
// STATUS 파일
{
  "tests_written": 2,
  "tests_passed": 2,
  "tests_failed_before_fix": 2,  // TDD 증거: 수정 전 실패 수
  "test_file_paths": ["evolutions/evo-001/05-tdd.md"]
}
```
JARVIS가 `tests_failed_before_fix == 0`이면 TDD 미준수로 REJECT.

---

**IL2-V3. 테스트 자체의 품질을 누가 검증하나?**
Worker가 항상 통과하는 trivial 테스트를 작성하면 TDD를 형식적으로 충족:
```bash
# 항상 성공하는 테스트
test_settings() { echo "PASS"; }
```

**판정: 테스트가 실제로 변경 사항을 검증하는지 보장 불가.**

**해결안:** ⑥ 검증 단계에서 spec-reviewer가 테스트 품질도 검토:
- "이 테스트가 실패하려면 어떤 조건이 필요한가?"
- "이 테스트를 통과하는 잘못된 구현이 있는가?"

---

### Iron Law #3: "NO COMPLETION CLAIMS WITHOUT VERIFICATION EVIDENCE"

**위반 시나리오 2개:**

**IL3-V1. "독립 검증"의 독립성이 확보되지 않는다**
jarvis-verify.sh가 JARVIS 세션 내에서 실행됨.
JARVIS가 만든 검증 스크립트로 JARVIS가 만든 진화를 검증 = 자기 검증.

**판정: Superpowers의 "Do Not Trust the Report" 원칙 위반.
검증자가 피검증자의 도구를 사용하면 독립성 제로.**

**해결안:**
- jarvis-verify.sh는 **JARVIS가 만들지 않은** 사전 정의 스크립트
- 또는 제3자 검증: Worker도 JARVIS도 아닌 **별도 pane의 Verifier 에이전트**
- 최소한: 메트릭 수집은 자동화 스크립트 (AI 판단 개입 없음)

---

**IL3-V2. "증거"의 형식이 정의되지 않았다**
Worker가 "DONE" 보고에 "테스트 통과, 잘 됨"이라고 적으면 증거인가?
eagle-status.json 스냅샷이 증거? 그렇다면 어떤 필드가 필수?

**판정: 증거의 최소 요건이 미정의.**

**해결안:** 증거 스키마 정의:
```json
{
  "evidence_type": "metric_comparison",
  "before_snapshot": "evolutions/evo-001/08-ab-test-before.json",
  "after_snapshot": "evolutions/evo-001/08-ab-test-after.json",
  "metrics_compared": ["dispatch_failure_rate", "stall_count"],
  "collection_method": "jarvis-verify.sh",
  "collected_at": "2026-04-02T11:00:00Z",
  "human_auditable": true
}
```

---

## 4. 교차 발견 — 3개 관점이 동시에 지적하는 문제

### CROSS-1. 계획 문서에 구버전 잔재가 대량으로 남아있다 (3/3 일치)

- **아키텍트:** 디렉토리 구조 이중 정의 (FATAL-A1)
- **엣지케이스:** 구현 순서 이중 (FATAL-A2)에 따라 어느 것을 실행할지 혼란
- **Iron Law:** Red Flags 테이블이 2곳에 정의 (396~404줄 + 496~504줄, 내용 다름)

**문서가 "진화"되면서 이전 버전을 삭제하지 않고 새 버전을 추가만 했다.**
이것은 JARVIS가 자기 문서에 대해 Iron Law #3 ("증거 기반 완료 주장")을 위반한 것.

---

### CROSS-2. "JARVIS가 뭘 하는 시스템인가"의 범위가 여전히 모호하다 (3/3 일치)

문서를 읽으면 JARVIS는:
1. 설정 진화 엔진 (11단계 파이프라인)
2. 지식 관리 시스템 (Basic Memory + Obsidian)
3. 시각화 도구 (Excalidraw/Mermaid/Canvas)
4. 하네스 추천 엔진 (harness-100 매칭)
5. 모니터링 시스템 (eagle-status, watcher.log)
6. 학습 엔진 (GitHub/Docs/Source 탐색)
7. 예산 관리 (Budget enforcement)

**7가지 역할을 하나의 surface(JARVIS pane)에서 수행한다.
이것은 단일 책임 원칙 위반이자 컨텍스트 폭발의 원인.**

FIX-08에서 마이크로 스킬로 분리했지만, **실행 주체는 여전히 JARVIS 1개.**
스킬을 분리해도 SKILL.md를 읽는 것은 같은 세션이므로 컨텍스트는 동일하게 소모.

**해결안:** Phase 1에서는 JARVIS의 역할을 **2가지로 한정:**
1. 설정 진화 엔진 (핵심)
2. 모니터링 (기존 eagle-status 읽기만)

나머지(지식 관리, 시각화, 하네스, 학습, 예산)는 Phase 2 이후 점진 추가.

---

### CROSS-3. A/B 테스트 설계가 비현실적이다 (3/3 일치)

- **아키텍트:** metric-dictionary의 5개 메트릭 중 실시간 수집 가능한 것은 stall_count뿐
- **엣지케이스:** 설정 변경 3회 반복 불가 (FATAL-E2)
- **Iron Law:** A/B 테스트 결과가 "증거"로 인정되려면 통계적 유의성 필요한데 검정 방법 없음

**dispatch_failure_rate**: eagle-status.json에서 어떻게 계산? 기간은? 직전 1시간?
**done_latency_avg**: 진화 전/후에 동일한 태스크를 실행해야 비교 가능. 어떤 태스크?
**context_overflow_count**: PostCompact는 사용자 행동 의존. 진화와 무관하게 변동.

**판정: 대부분의 메트릭이 진화의 효과를 정확히 측정하지 못한다.**

**해결안:**
- Phase 1: 단순 Before/After 스냅샷 + 관찰 기간 (10분) + **사용자 주관 판단**
- "자동 수치 비교로 판단"이라는 이상을 Phase 1에서 강제하지 말 것
- 사용자에게: "이 변경 전후 차이입니다. 유지할까요?" (결국 사람이 판단)

---

## 5. 최종 판정

### 구현 차단 (이것을 해결하지 않으면 구현 불가)

| # | 문제 | 해결 |
|---|------|------|
| **FATAL-A1** | 구버전 디렉토리 구조 잔재 | **190~233줄 삭제**, 새 구조(82~151줄)만 유지 |
| **FATAL-A2** | 구버전 구현 순서 잔재 | **519~531줄 삭제**, 324~355줄만 유지 |
| **FATAL-A3** | Obsidian 필수 vs 선택 모순 | **2모드 명시** (Obsidian 활성/비활성, 정본 위치만 다름) |
| **FATAL-E1** | JSON 3-way merge 불가 | **JSON Patch** (변경 키만 적용)로 대체 |
| **FATAL-E2** | 설정 A/B 3회 반복 불가 | **관찰 기간**으로 대체 (설정 변경 전용) |
| **CROSS-2** | 역할 7개 = 범위 폭발 | Phase 1은 **진화 + 모니터링만**, 나머지 Phase 2+ |
| **CROSS-3** | A/B 메트릭 비현실적 | Phase 1은 **사용자 판단**, 자동 비교는 Phase 2 |

### 구현 시 주의 (해결 안 하면 실패 가능성 높음)

| # | 문제 | 해결 |
|---|------|------|
| HIGH-A4 | Basic Memory Python 의존 | Phase 1은 sqlite3 CLI, Basic Memory는 Phase 3 |
| HIGH-A5 | hook 등록/충돌 | surface별 hook 활성화 메커니즘 설계 |
| HIGH-E3 | LOCK 영구 잠금 | TTL 추가 (60분) |
| HIGH-E5 | 순환 재시도 범위 모호 | "진화당 최대 2회 순환" 명시 |
| IL1-V1 | blank check 승인 | 2단계 승인 (계획 전/계획 후) |
| IL2-V1 | 설정 변경 TDD 불가 | "expected outcome" 문서화로 대체 |
| IL2-V2 | TDD 강제 없음 | STATUS 파일에 test 증거 필수 필드 |
| IL3-V1 | 독립 검증 = 자기 검증 | 사전 정의 스크립트 또는 Verifier pane |
| IL3-V2 | 증거 형식 미정의 | evidence 스키마 정의 |
