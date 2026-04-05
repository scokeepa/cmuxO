# JARVIS 계획 5관점 심층 리뷰

**대상:** JARVIS-PLAN-FULL.md + 2026-04-02_repo-deep-research-full.md
**날짜:** 2026-04-02
**리뷰어:** 아키텍트, 엣지케이스, 검증스킬, 레드팀, 블루팀

---

## 1. 아키텍트 리뷰 — 구조적 정합성 + 확장성 + 의존성

### CRITICAL (설계 결함) — 5건

**A1. 1차/2차 두뇌 간 동기화 충돌 위험**
- 문제: 로컬 SQLite(1차)와 Basic Memory Obsidian(2차)이 동일 데이터를 이중 저장
- 양쪽 모두 쓰기 가능 → **split-brain** 가능성
  - JARVIS가 1차에 쓰고 2차 동기화 전에 사용자가 Obsidian에서 직접 편집
  - Basic Memory WatchService가 변경 감지 → DB 업데이트 → 1차와 불일치
- **해결안:** 단일 쓰기 소스(Single Source of Truth) 원칙 필수
  - 옵션 A: 1차가 유일한 쓰기 소스, 2차는 읽기 전용 미러
  - 옵션 B: Basic Memory가 유일한 쓰기 소스, 1차는 캐시
  - **권고:** 옵션 B — Basic Memory를 정본으로, 로컬 SQLite는 FTS5 검색 캐시로만 사용

**A2. 의존성 체인이 과도하게 깊다**
- JARVIS → Basic Memory MCP → Obsidian → 클라우드 Sync
- 중간 어디서든 장애 → 전체 지식 시스템 불능
- Basic Memory MCP 서버 다운 → JARVIS 학습 inject 불가
- Obsidian 앱 미실행 → CLI 명령 실패
- **해결안:** 각 계층 독립 동작 보장
  - Basic Memory MCP 다운 → 로컬 SQLite 폴백
  - Obsidian 미실행 → 직접 파일 쓰기 폴백 (obsidian-sync 패턴)
  - 클라우드 미연결 → 로컬만 동작 (eventual consistency)

**A3. 진화 파이프라인 11단계 + 두뇌 이중화 + Obsidian 시각화 = 범위 폭발**
- 문제: 단일 SKILL.md에 담기에 범위가 너무 넓음
  - 진화 엔진 (11단계)
  - 지식 관리 (FTS5 + 벡터 + Progressive Disclosure)
  - 두뇌 이중화 (Basic Memory + Obsidian)
  - 시각화 (Excalidraw + Mermaid + Canvas)
  - 모니터링 (eagle-status, watcher.log)
  - 하네스 추천 (harness-100)
- **해결안:** 마이크로 스킬 분리
  - `cmux-jarvis/SKILL.md` — 코어 (감지 + 승인 + 보고)
  - `cmux-jarvis/skills/evolution.md` — 진화 파이프라인
  - `cmux-jarvis/skills/knowledge.md` — 지식 관리
  - `cmux-jarvis/skills/obsidian-sync.md` — Obsidian 연동
  - `cmux-jarvis/skills/visualization.md` — 시각화

**A4. knowledge DB 스키마가 2개 시스템에서 중복 정의**
- 기존 계획: `knowledge` + `evolutions` + `settings_backups` 테이블 (SQLite 직접)
- Basic Memory: `Entity` + `Observation` + `Relation` 모델 (SQLAlchemy)
- 두 스키마가 동일 데이터를 다른 구조로 저장 → 매핑 비용 발생
- **해결안:** Basic Memory의 Entity/Observation/Relation을 정식 스키마로 채택
  - knowledge → Entity (note_type='knowledge')
  - evolution → Entity (note_type='evolution')
  - 기존 SQLite 스키마는 Basic Memory와 호환되는 뷰로 제공

**A5. hook 타임아웃 제약이 반영되지 않음**
- claude-mem hooks.json: SessionStart 60s, PostToolUse 120s, Stop 120s
- JARVIS가 SessionStart에서 Progressive Disclosure Level 0-1 inject 시
  - FTS5 검색 + 결과 포맷팅 + JSON 출력 = 60초 내 완료해야 함
  - Basic Memory MCP 호출까지 포함하면 타임아웃 위험
- **해결안:**
  - SessionStart hook은 캐시된 요약만 inject (미리 생성)
  - 무거운 검색은 UserPromptSubmit hook 또는 lazy load

### HIGH (개선 필요) — 4건

**A6. cmux send 기반 통신이 단방향**
- JARVIS → Evolution Worker: cmux send로 계획 전달 ✓
- Evolution Worker → JARVIS: 완료 보고를 어떻게? cmux send로 역방향?
- 현재 계획에는 "결과를 문서로 저장 → JARVIS가 읽기"만 있음
- **해결안:** 명시적 완료 신호 프로토콜 필요
  - Evolution Worker가 `~/.claude/cmux-jarvis/evolutions/evo-001/09-result.md` 생성
  - JARVIS가 파일 존재 여부로 완료 감지 (polling) 또는
  - Evolution Worker가 "DONE" 출력 → Watcher가 감지 → JARVIS에 cmux send

**A7. Obsidian 볼트 경로가 하드코딩 가능성**
- 사용자마다 Obsidian 볼트 위치가 다름
- `~/Documents/Obsidian/JARVIS/`, `/Users/csm/vault/`, `~/Obsidian/` 등
- **해결안:** 최초 실행 시 볼트 경로 설정 → `~/.claude/cmux-jarvis/config.json`에 저장

**A8. install.sh의 merge 방식 settings.json 수정이 위험**
- 기존 settings.json에 hooks 추가 시 JSON merge → 파서 오류 가능
- **해결안:** jq 기반 안전한 JSON 조작 + 백업 후 수정

**A9. 진화 DAG JSON이 순환 의존성을 체크하지 않음**
- `dep` 필드로 의존성 그래프 구성 → 순환 시 무한 루프
- **해결안:** DAG 생성 시 위상 정렬(topological sort) 검증 필수

---

## 2. 엣지케이스 리뷰 — 경계 조건 + 예외 상황

### CRITICAL — 4건

**E1. 진화 중 사용자가 settings.json을 직접 수정하면?**
- JARVIS가 ④백업 → ⑧구현(설정 수정 중) → 사용자가 다른 설정 변경
- 진화 완료 후 ⑪반영 시 사용자 변경 덮어쓰기
- **해결안:**
  - 진화 시작 시 settings.json에 JARVIS lock 마커 추가
  - 또는 GStack /freeze 패턴 적용 — 진화 중 설정 파일 편집 경고
  - 반영 시 3-way merge (백업 + 진화 결과 + 현재 상태)

**E2. 동시 진화 충돌**
- JARVIS가 evo-001 진행 중 새로운 문제 감지 → evo-002 시작 시도
- 동일 settings.json을 두 진화가 동시에 수정하면 충돌
- **해결안:**
  - 진화는 직렬 실행만 허용 (동시 진화 금지)
  - `evolutions/CURRENT_LOCK` 파일로 진행 중 표시
  - 새 감지는 큐에 추가, 현재 진화 완료 후 처리

**E3. Evolution Worker pane이 예기치 않게 종료되면?**
- tmux pane kill, 시스템 크래시, OOM kill 등
- 진화가 중간 상태에서 멈춤 — 백업은 했지만 구현은 절반만 완료
- **해결안:**
  - Circuit Breaker 패턴 (Basic Memory 참조): 3회 연속 실패 → 건너뜀
  - 진화 상태 파일: `evo-001/STATUS` = detecting|planning|implementing|testing|completed|failed
  - JARVIS 재시작 시 STATUS 파일 확인 → 중단된 진화 복구 또는 롤백

**E4. FTS5 인덱스 손상 시 복구 방법 없음**
- SQLite FTS5 가상 테이블이 손상되면 검색 불가
- claude-mem의 `repairMalformedSchemaWithReopen()` 같은 복구 로직 미설계
- **해결안:**
  - FTS5 재구축 스크립트: `DROP TABLE knowledge_fts; CREATE VIRTUAL TABLE...` + 트리거 재생성
  - 마크다운 파일이 정본이므로 언제든 FTS5 인덱스 재생성 가능 (Basic Memory 패턴)

### HIGH — 5건

**E5. knowledge/raw/ JSON 1000개 이상 시 디렉토리 리스팅 성능**
- ext4 기준 단일 디렉토리 1000+ 파일 → ls 느림
- **해결안:** 날짜별 하위 디렉토리 분할 (`raw/2026-04/`, `raw/2026-05/`)

**E6. Obsidian 볼트가 없는 환경 (서버, CI)**
- Obsidian이 설치되지 않은 환경에서 JARVIS 실행 시 2차 두뇌 불능
- **해결안:** Obsidian 연동은 선택적(optional), 1차 두뇌만으로 완전 동작

**E7. 한국어 FTS5 토크나이징 제한**
- unicode61 tokenizer는 한국어 형태소 분석 안 함
- "설정 변경" 검색 시 "설정"과 "변경" 개별 매칭 불가할 수 있음
- **해결안:**
  - LIKE '%설정%' 폴백 (claude-mem 패턴)
  - 또는 mecab 기반 커스텀 토크나이저 (Phase 2)

**E8. A/B 테스트 메트릭이 통계적으로 유의미한지 판단 불가**
- 단일 실행 결과로 "60%→0%" 판정 — 우연일 수 있음
- **해결안:**
  - 최소 3회 반복 실행 후 중앙값 비교
  - 또는 GStack canary 패턴: 2회 연속 확인 후 alert

**E9. cmux notify 알림이 누락되면?**
- 사용자가 AFK(자리 비움) 시 승인 요청 무한 대기
- **해결안:** 타임아웃 설정 (예: 30분) → 자동 큐잉 → 다음 접속 시 안내

---

## 3. 검증스킬 리뷰 — 테스트 가능성 + 증거 기반 검증

### CRITICAL — 3건

**V1. 진화 성공/실패 판정 기준이 정량적이지 않음**
- "실패율 60%→0%" — 이 메트릭은 어디서 수집? 어떻게 측정?
- eagle-status.json의 어떤 필드가 "실패율"인지 정의 없음
- **해결안:** 메트릭 사전(metric dictionary) 정의 필수
  ```
  dispatch_failure_rate = (failed_dispatch / total_dispatch) * 100
  response_quality = user_satisfaction_score (1-5)
  stall_count = watcher.log의 STALL 이벤트 수
  context_overflow_count = PostCompact hook 실행 횟수
  ```

**V2. TDD 단계(⑦)에서 "테스트 먼저"의 대상이 불명확**
- 설정 변경의 테스트 = ?
  - settings.json 스키마 검증?
  - 변경 후 surface 정상 동작 확인?
  - hook 실행 검증?
- **해결안:** 진화 유형별 테스트 템플릿 정의
  - 설정 변경: JSON 스키마 검증 + 해당 surface 재시작 후 정상 동작
  - hook 추가: hook 트리거 시뮬레이션 + 출력 검증
  - 스킬 수정: SKILL.md 파싱 + 예상 동작 시뮬레이션

**V3. "Do Not Trust the Report" 원칙의 구현 방법 미정의**
- Evolution Worker 보고를 신뢰하지 않고 독립 검증 — 누가, 어떻게?
- JARVIS가 직접 검증? → 자기 계획의 결과를 자기가 검증 = 편향
- **해결안:**
  - 자동 검증: 메트릭 수집 스크립트가 수치 비교 (JARVIS/Worker 무관)
  - 수동 검증: 사용자에게 diff 표시 + "이 변경이 맞나요?" 확인

### HIGH — 3건

**V4. 롤백 검증이 정의되지 않음**
- 백업 복원 후 "이전 상태로 돌아갔는가"를 어떻게 확인?
- **해결안:** 롤백 후 settings.json checksum = 백업 checksum 비교

**V5. Obsidian 동기화 검증 방법 없음**
- 로컬에 쓴 문서가 Obsidian 볼트에 정확히 반영되었는지 확인 방법 미정의
- **해결안:** 쓰기 후 `obsidian read` 또는 파일 checksum 비교

**V6. 재현 가능한 테스트 환경이 없음**
- 설정 변경 테스트는 실제 surface가 필요 → 격리된 테스트 환경?
- **해결안:**
  - dry-run 모드: 실제 적용 없이 변경 계획만 검증
  - 테스트 surface: 별도 tmux 세션에서 테스트 전용 Claude 실행

---

## 4. 레드팀 리뷰 — 악의적/극단적 시나리오

### CRITICAL — 5건

**R1. JARVIS가 자기 자신의 GATE를 우회할 수 있다**
- GATE J-1은 SKILL.md에 텍스트로 정의 → 프롬프트 레벨 제약
- LLM은 프롬프트 제약을 100% 보장하지 않음
- 극단적 시나리오: JARVIS가 "이건 GATE 위반이 아니야"라고 자기 합리화
- **해결안:**
  - GATE는 SKILL.md + hook 이중 강제
  - 설정 파일 쓰기 전에 PreToolUse hook으로 경로 검증 (GStack /freeze 패턴)
  - `/tmp/cmux-orch-enabled` 접근 시 hook에서 deny

**R2. Evolution Worker가 악의적/잘못된 설정을 적용할 수 있다**
- Evolution Worker는 새 pane의 독립 세션 → JARVIS의 GATE 적용 안 됨
- Worker가 settings.json을 잘못 수정 → 전체 오케스트레이션 붕괴
- **해결안:**
  - Evolution Worker에도 별도 GATE 적용 (worker-specific SKILL.md)
  - 설정 변경은 JARVIS만 가능, Worker는 변경 "제안"만 → JARVIS가 적용
  - 또는 Worker의 allowed-tools에서 Write/Edit 제거, Bash만 허용

**R3. 무한 진화 루프**
- JARVIS가 evo-001 적용 → 문제 감지 → evo-002 시작 → 적용 → 다시 문제 → evo-003...
- autoresearch의 "NEVER STOP"이 위험하게 작동할 수 있음
- **해결안:**
  - 연속 진화 횟수 제한: MAX_CONSECUTIVE_EVOLUTIONS = 3
  - 동일 설정 영역에 대한 연속 진화 감지 → 사용자 에스컬레이션
  - 일일 진화 횟수 상한: MAX_DAILY_EVOLUTIONS = 10

**R4. 학습 데이터 오염**
- JARVIS가 잘못된 패턴을 "학습"으로 저장
- Few-shot inject 시 잘못된 예시가 향후 진화 품질 저하
- **해결안:**
  - 학습 데이터에 confidence 점수 (GStack learn 패턴)
  - confidence < 5인 학습은 inject 대상에서 제외
  - 주기적 prune: 참조 파일 삭제된 학습 → 자동 무효화
  - 사용자가 학습 검토/삭제 가능한 인터페이스

**R5. API 비용 폭주**
- 능동적 학습 (WebSearch, WebFetch) + 진화 파이프라인 (Evolution Worker) + Obsidian 시각화 (Excalidraw 생성)
- 사용자 부재 시 JARVIS가 자율 학습 → 예상치 못한 API 비용
- **해결안:**
  - Paperclip Budget enforcement 도입: 일일 토큰 상한
  - 학습 비용 추적: discovery_tokens (claude-mem 패턴)
  - 80% 경고 → 100% 초과 시 학습 중단 + 사용자 알림

### HIGH — 3건

**R6. 사용자 승인 피로(approval fatigue)**
- 매 진화마다 승인 요청 → 사용자가 자동 승인하기 시작 → 위험한 변경도 통과
- **해결안:**
  - 위험도 분류: LOW(자동)/MED(요약 보고)/HIGH(상세 승인)
  - LOW 진화는 사용자 승인 없이 적용 + 사후 보고

**R7. JARVIS가 Watcher 역할을 침범**
- JARVIS가 모니터링하면서 Watcher의 감시 영역과 중복
- JARVIS가 Watcher보다 먼저 문제를 감지하면 Watcher 무력화
- **해결안:** 역할 분리 명확화
  - Watcher: 실시간 surface 상태 감시 (IDLE/ERROR/STALL 감지)
  - JARVIS: 패턴 분석 + 개선 제안 (Watcher 데이터 소비자)

**R8. Obsidian 볼트의 민감 정보 노출**
- settings.json 백업에 API 키, 토큰 등 포함 가능
- Obsidian Sync로 클라우드에 업로드 → 민감 정보 유출
- **해결안:**
  - 백업 시 민감 필드 마스킹 (claude-mem Privacy tags 패턴)
  - `.gitignore` 패턴으로 백업 폴더 제외
  - Obsidian 동기화 시 backups/ 폴더 제외 설정

---

## 5. 블루팀 리뷰 — 방어적 설계 + 복원력 + 운영 안정성

### CRITICAL — 4건

**B1. 롤백 경로가 단일 포인트**
- 백업이 `~/.claude/cmux-jarvis/backups/`에만 존재
- 이 디렉토리 손상/삭제 시 롤백 불가
- **해결안:**
  - 백업의 2중화: 로컬 + Obsidian 볼트
  - 또는 git 기반 설정 버전 관리 (각 진화 = git commit)
  - 최소 3세대 백업 유지 (현재 + 이전 2개)

**B2. JARVIS 자체 장애 시 오케스트레이션 영향 범위**
- JARVIS pane 크래시 → 진행 중 진화 중단
- 예상 영향: 진화만 중단 (Main/Watcher는 독립 → 오케스트레이션 계속)
- BUT: ConfigChange hook이 JARVIS에서 실행 중이었다면 백업 누락 가능
- **해결안:**
  - ConfigChange hook은 JARVIS 독립으로 실행 (flock + 별도 스크립트)
  - JARVIS 재시작 시 자동 복구 (STATUS 파일 기반)
  - cmux-start 시 JARVIS pane 자동 재생성

**B3. 세션 컨텍스트 소진 시 진화 지식 손실**
- JARVIS 세션이 /compact되면 이전 진화 맥락 손실
- 연속 진화 시 이전 진화 결과를 참조해야 하는데 컨텍스트에서 사라짐
- **해결안:**
  - 모든 진화 맥락은 파일로 영속화 (이미 설계됨)
  - /compact 후 자동으로 현재 진화 nav.md 재로드
  - PostCompact hook에서 JARVIS 컨텍스트 복원 트리거

**B4. Basic Memory MCP 서버 포트 충돌**
- Basic Memory가 특정 포트 사용 → 다른 MCP 서버와 충돌 가능
- claude-mem도 37777 포트 사용
- **해결안:**
  - 포트 설정 가능하게 (config.json)
  - 또는 stdio 기반 MCP 통신 (포트 불필요)

### HIGH — 4건

**B5. 학습 데이터 마이그레이션 실패 시 데이터 손실**
- 파일 기반 → SQLite 전환 시 일부 JSON 파싱 실패 → 해당 학습 누락
- **해결안:**
  - 마이그레이션 전 전체 백업
  - 실패한 파일은 `knowledge/migration-failures/`에 보존
  - 마이그레이션 보고서 생성 (성공/실패/건너뜀 수)

**B6. 진화 중 시스템 전원 차단**
- ⑧구현 중 전원 차단 → settings.json 부분 기록 → JSON 파싱 오류
- **해결안:**
  - 원자적 파일 쓰기: 임시 파일에 쓰고 rename (POSIX atomic rename)
  - 또는 settings.json.bak 항상 유지

**B7. Obsidian 동기화 지연으로 인한 데이터 불일치**
- 로컬에 쓰고 Obsidian Sync 중 → 다른 기기에서 이전 버전 읽음
- **해결안:**
  - Obsidian 동기화는 "최종 일관성(eventual consistency)" 명시
  - 충돌 시 타임스탬프 기준 최신 우선

**B8. tmux 세션 이름 충돌**
- JARVIS pane 이름이 다른 사용자 tmux 세션과 충돌
- **해결안:** `cmux-jarvis-{PID}` 형식으로 유니크 보장

---

## 6. 통합 발견사항 — 우선순위별 조치 권고

### 즉시 조치 필요 (구현 차단)

| # | 이슈 | 관점 | 조치 |
|---|------|------|------|
| **A1** | 1차/2차 두뇌 split-brain | 아키텍트 | Basic Memory를 정본으로, 로컬은 캐시 |
| **E1** | 진화 중 사용자 설정 수정 | 엣지케이스 | /freeze 패턴 + 3-way merge |
| **E2** | 동시 진화 충돌 | 엣지케이스 | 직렬 실행 + CURRENT_LOCK |
| **R1** | GATE 우회 가능 | 레드팀 | hook 이중 강제 |
| **R2** | Worker 악의적 설정 변경 | 레드팀 | Worker는 제안만, JARVIS가 적용 |
| **R3** | 무한 진화 루프 | 레드팀 | MAX_CONSECUTIVE=3, MAX_DAILY=10 |
| **V1** | 성공/실패 메트릭 미정의 | 검증스킬 | metric dictionary 정의 |
| **B1** | 롤백 단일 포인트 | 블루팀 | 백업 2중화 + 3세대 유지 |

### 다음 버전 반영 (HIGH)

| # | 이슈 | 관점 | 조치 |
|---|------|------|------|
| A2 | 의존성 체인 깊이 | 아키텍트 | 각 계층 독립 동작 + 폴백 |
| A3 | 범위 폭발 | 아키텍트 | 마이크로 스킬 분리 |
| A4 | 스키마 중복 | 아키텍트 | Basic Memory 모델 채택 |
| A5 | hook 타임아웃 | 아키텍트 | 캐시된 요약만 inject |
| E3 | Worker pane 종료 | 엣지케이스 | Circuit Breaker + STATUS 파일 |
| E4 | FTS5 인덱스 손상 | 엣지케이스 | 재구축 스크립트 |
| R4 | 학습 데이터 오염 | 레드팀 | confidence 기반 필터 |
| R5 | API 비용 폭주 | 레드팀 | Budget enforcement |
| V2 | TDD 대상 불명확 | 검증스킬 | 유형별 테스트 템플릿 |
| V3 | 독립 검증 방법 | 검증스킬 | 자동 메트릭 수집 |
| B2 | JARVIS 자체 장애 | 블루팀 | 자동 복구 + 독립 hook |
| B3 | 컨텍스트 소진 | 블루팀 | PostCompact 복원 트리거 |

### 선택적 개선 (MEDIUM)

| # | 이슈 | 관점 |
|---|------|------|
| A6 | cmux send 단방향 | 아키텍트 |
| A7 | 볼트 경로 하드코딩 | 아키텍트 |
| A9 | DAG 순환 체크 | 아키텍트 |
| E5 | 1000+ 파일 디렉토리 | 엣지케이스 |
| E7 | 한국어 FTS5 토크나이징 | 엣지케이스 |
| E8 | A/B 통계 유의성 | 엣지케이스 |
| E9 | 알림 누락 타임아웃 | 엣지케이스 |
| R6 | 승인 피로 | 레드팀 |
| R7 | Watcher 역할 침범 | 레드팀 |
| R8 | 민감 정보 노출 | 레드팀 |
| B4 | MCP 포트 충돌 | 블루팀 |
| B5 | 마이그레이션 실패 | 블루팀 |
| B6 | 전원 차단 | 블루팀 |
| B7 | Obsidian 동기화 지연 | 블루팀 |

---

## 7. 5관점 교차 검증 — 의견 일치/불일치

### 전원 일치 (5/5)

1. **Basic Memory를 정본으로 채택** — split-brain 방지의 유일한 해법
2. **GATE는 프롬프트 + hook 이중 강제** — 프롬프트만으로 불충분
3. **진화는 직렬 실행** — 동시 진화는 리스크 대비 이점 없음
4. **메트릭 사전 정의 필수** — 정량적 판단 없이는 진화 품질 보장 불가
5. **무한 루프 방지** — MAX_CONSECUTIVE + MAX_DAILY 상한

### 다수 일치 (4/5)

6. **마이크로 스킬 분리** (아키텍트/검증/블루팀/레드팀 동의, 엣지케이스 중립)
7. **Evolution Worker는 제안만** (레드팀/블루팀/아키텍트/검증 동의, 엣지케이스: 성능 우려)
8. **Budget enforcement** (레드팀/블루팀/아키텍트/엣지케이스 동의, 검증: Phase 2 가능)

### 의견 분기 (3:2)

9. **Obsidian 연동 필수 vs 선택적**
   - 필수파 (아키텍트/블루팀/레드팀): 두뇌 이중화의 핵심 가치
   - 선택파 (검증/엣지케이스): 의존성 증가 + Obsidian 없는 환경 고려
   - **결론:** 선택적으로 구현하되, 활성화 시 완전 동작 보장
