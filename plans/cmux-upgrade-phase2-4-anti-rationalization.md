# cmuxO Upgrade Phase 2.4 — JARVIS Anti-Rationalization Tables

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기
**참조 프로젝트**: `/Users/csm/projects/olympus/source/superpowers/skills/systematic-debugging/`
**선행 조건**: Phase 2.3 (Ledger) 완료 권장 — 합리화 패턴을 ledger에서 탐지

---

## 0. 선행 Phase 리스크 흡수 (Phase 2.2 / 2.2.5 remaining risk 반영)

Phase 2.2 토큰 관측성, 2.2.5 peers 통신 완료 후 남은 remaining risk를 이 Phase의 anti-rationalization 테이블/감지 로직에 명시적으로 흡수한다. 이유: 이 Phase는 "합리화 탐지"가 목적이므로, 실제 관측된 잠재 합리화 패턴을 표 데이터로 확보하는 것이 설계 적중률을 결정함.

### 0.1 Peer fallback 합리화 추가 (Phase 2.2.5 risk #1 흡수)

**흡수 대상 risk**: Phase 2.2.5에서 peer_channel 실패 시 cmux send 로 자동 폴백되는데, 개발자/LLM이 "폴백이 돌아가니 peer 경로를 안 고쳐도 된다" 식으로 합리화해 primary 경로 파손이 은폐될 수 있음.

**Table A 확장**:

| 받은 말 | 실제 가능성 | 대응 |
|---------|-------------|------|
| "peer로 못 보내도 cmux send가 있으니 괜찮음" | PEER_SEND_FAILED 누적, primary 경로 회복 책임 유기 | ledger에서 최근 24h `PEER_SEND_FAILED` count 집계 → 임계 초과 시 ASK |
| "broker가 가끔 죽어도 fallback이 돌아감" | broker 건강성 미점검 | Phase 2.3 ledger `PEER_SEND_FAILED.reason=broker_unreachable` 빈도로 score. 5회 이상/day → ASK + "broker 복구가 primary 조치" |

### 0.2 Boss peer_id 결석 합리화 (Phase 2.2.5 risk 확장)

**흡수 대상**: watcher 가 `resolve("boss")` 실패 시 자동으로 cmux send 폴백. 매번 폴백되면 peer 경로가 한 번도 작동하지 않아도 시스템이 "정상 작동" 으로 보임.

**Table B 확장**:

| 스스로 한 생각 | 실제로 해야 할 것 |
|---------|------|
| "boss peer 등록 안 돼도 polling 돌아가니 됨" | Boss 기동 로그에 `claude-peers` MCP 초기화 확인, Phase 2.3 `ROLE_PEER_BIND` 이벤트 유무 확인 |
| "logical_name 조회 실패는 일시적" | 30분 내 3회 이상 resolve miss → 구성 오류 확정, ASK |

### 0.3 Token 관측성 "환경 문제" 합리화 (Phase 2.2 risk 흡수)

**흡수 대상 risk**: Phase 2.2 에서 JSONL 경로 미발견 시 `collect_surface_metrics` 가 빈 dict 반환 → "transcript 없어서 metrics 못 냄" 으로 합리화 가능. 실제로는 `CLAUDE_PROJECTS_DIR` 오버라이드나 surface↔cwd 매핑이 누락됐을 때 구체 원인을 감춘다.

**Table A 확장**:

| 받은 말 | 실제 가능성 | 대응 |
|---------|-------------|------|
| "transcript 없어서 token metrics 없음" | 경로 slug 미스매치 또는 surface↔cwd 매핑 공백 | 구체적으로: 어떤 cwd? slug = cwd.replace("/","-") 결과가 `~/.claude/projects/` 에 존재하는지 확인 |
| "JSONL 파싱 실패" | tail 10MiB 구간이 멀티라인 JSON 중간에 잘렸을 때 | 최근 1~2줄 스킵만 정상, 3줄 이상 skip 시 파일 재스캔/전체 읽기로 상승 |

### 0.4 Anti-rationalization 규칙에 ledger 근거 탐지 의무 명시

Phase 2.3 완성 후 `jarvis-anti-rationalization-report.py` 는 아래 세 소스를 모두 조회:
- `PEER_SEND_FAILED` (0.1, 0.2 근거)
- `TOKEN_METRIC_COLLECT_FAIL` (0.3 근거, Phase 2.3 에 신규 이벤트 추가 필요 — Phase 2.3 플랜 §0 에 함께 포함되어 있음)
- `CACHE_INEFFICIENT`, `CONTEXT_LARGE` alert 이력 (Phase 2.2 산출)

→ report 스크립트는 이 세 유형 집계 column 을 고정 포함. 사용자가 보는 report 가 "텍스트 패턴 매칭" 일변도가 아니라 실측 시스템 이벤트로 뒷받침되는 구조.

### 0.5 DoD 반영

§7 DoD에 다음 체크 항목 추가:
- [ ] Table A에 peer fallback 합리화 2줄, token 관측성 합리화 2줄 포함
- [ ] Table B에 boss peer_id 결석 합리화 2줄 포함
- [ ] `jarvis-anti-rationalization-report.py` 가 `PEER_SEND_FAILED`, `TOKEN_METRIC_COLLECT_FAIL` 이벤트 집계 실행 (Phase 2.3 ledger merge 후)

### 0.6 Phase 2.3 Remaining risk 흡수 — ledger 기록자 배선 완료를 이 Phase 에서 수행

Phase 2.3 구현은 `ledger.append()` API 와 `peer_channel`/`watcher` 기록 지점만 연결 완료. dispatch/verify/clear 경로는 스키마·타입 정의만 있고 **실제 호출 지점이 없음**. 이 Phase 에서 함께 해결해야 Table A/B 의 "완료 없이 VERIFY_PASS ledger" 판정 로직이 작동함.

**흡수 대상 Phase 2.3 Remaining risks**:
1. ASSIGN/CLEAR/VERIFY_* 기록자 배선 미완
2. `cmux-main-context.sh` 의 `compaction_replay_context()` 주입 미완
3. `ROLE_PEER_BIND` 기록자(`role-register.sh`) 미완 — 단, Phase 3.1 범위로 이미 이월 결정된 건은 제외

**설계 반영**:
- `surface-dispatcher.sh` 내 배정 성공 직후: `python3 ledger.py append ASSIGN --fields '{"boss":"...","worker":"...","task":"..."}'` 1줄 삽입.
- `cmux-dispatch-notify.sh` 의 `/clear` 발화 직후: `append CLEAR`.
- `cmux-completion-verifier.py` 판정 종료 직후: `append VERIFY_PASS` 또는 `VERIFY_FAIL` with `evidence` 필드.
- `cmux-main-context.sh` UserPromptSubmit 경로에 `python3 ledger.py context` 출력을 context block 으로 주입. 30 이벤트 × 평균 200B = 6KB, 허용 범위.

**이유**: Anti-rationalization 규칙의 **객관적 판정 근거**가 ledger 의 VERIFY_* / ASSIGN 이벤트이므로, 이 배선 없이는 `cmux-leceipts-gate.py` 가 "완료했습니다" 발화를 판단할 evidence 소스가 비어있음. Phase 2.4 의 §3.3 훅 통합 설계가 Phase 2.3 기록자 배선과 **동일 PR 에 묶여야** 기능이 완성됨.

**DoD 확장**:
- [ ] `dispatch 1회 실행 → ledger 에 ASSIGN 1건` 수동 검증
- [ ] `/clear 실행 → CLEAR 이벤트 1건` 수동 검증
- [ ] `cmux-completion-verifier.py` pass/fail 각 1회 → VERIFY_PASS/VERIFY_FAIL 각 1건
- [ ] `cmux-main-context.sh` 실행 시 `[ledger]` 섹션 stdout 포함

**범위 경계**: `ROLE_PEER_BIND` 기록자는 Phase 3.1 agentmemory 통합과 함께 `role-register.sh` 확장으로 처리 (Phase 3.1 플랜 §0.3 에 이미 기록). 이 Phase 에서는 정의만 존재, 실 호출자 없음 — **의도적 이월**.

---

## 1. 문제 요약

JARVIS (cmuxO self-improvement engine) 및 Worker LLM이 작업 실패/규칙 위반을 **자기 합리화**로 회피하는 패턴이 반복 관측:

실제 관측 사례:
- "테스트 실행 환경이 없어서 검증 못함" — 구체적 차단 요소 없음 (CLAUDE.md §검증규칙 위반)
- "아마 동작할 것 같음" — 가정을 검증으로 표현
- "더 좋은 방법이 있지만 이번엔 생략" — 근본 원인 회피
- "관련 없어 보여서 안 건드림" — 실제 영향 확인 없이 범위 축소

Superpowers 프로젝트의 `systematic-debugging` 스킬은 이런 안티패턴을 **표 형태 체크리스트**로 제시해 LLM이 대응하게 함.

## 2. 근거

### 2.1 Superpowers anti-rationalization 패턴 (레퍼런스)

Superpowers v5 `systematic-debugging/SKILL.md`에 테이블:

| Excuse | Counter | When applicable |
|--------|---------|-----------------|
| "It's probably fine" | State exact failure mode you're assuming doesn't happen | Any claim of "probably" |
| "Edge case, unlikely" | Write input that reproduces it now | Any dismissal of reported issue |
| "Environment issue" | Name the specific env variable / binary / permission | "Won't reproduce locally" |

→ LLM이 이 표를 읽으면 **자기 검열** 효과 관측 (Superpowers 저자 주장, 사용자 체감으로 재확인).

### 2.2 cmuxO 내 현황

- `CLAUDE.md`에 "leceipts Working Rules" — 이미 일부 rationalization 금지 명시 ("환경 문제로 뭉뚱그리기 금지 → 구체적 차단 요소 명시")
- 하지만 **테이블 형태가 아니어서 참조 효율 낮음**
- 훅 차원의 탐지는 없음

### 2.3 cmuxO 특화 합리화 패턴

ledger/훅 로그 분석으로 수집 가능한 패턴 (Phase 2.3 data 활용):

| cmux 특유 excuse | 실제 의미 | Counter |
|------------------|-----------|---------|
| "Worker가 완료 보고했으니 믿음" | 검증 스킵 | evidence 필드 확인, 실제 테스트 파일 존재·pass 증거 요구 |
| "Watcher가 idle 판정" | OCR false positive 가능 | pipe-pane hook + vision-diff 이중 확인 |
| "Rate-limit은 자동 회복" | pool 미구현 | Phase 1.4로 실측 회복 시간 기록 |
| "다른 surface 문제" | 실제 본인 책임 회피 | ledger로 책임 추적 |

## 3. 설계

### 3.1 위치

`cmux-orchestrator/references/anti-rationalization.md` — SKILL.md에서 링크만, on-demand 참조.

### 3.2 구조

```markdown
# Anti-Rationalization Tables

## Table A — 보고 합리화 (Boss가 보고 받을 때)
| 받은 말 | 실제 가능성 | 대응 |
|---------|-------------|------|
| "완료했습니다" | DONE_CLAIMED, 미검증 | `cmux-completion-verifier.py` 호출 |
| "테스트 통과" | 실행 안 했을 수 있음 | ledger에서 VERIFY 이벤트 확인 |
| "환경 문제" | 구체적 원인 미파악 | "어떤 바이너리/env/permission?" 재질문 |

## Table B — 작업 회피 합리화 (Worker 자신)
| 스스로 한 생각 | 실제로 해야 할 것 |
|---------|------|
| "이건 범위 밖" | 범위를 1문장으로 재정의 후 사용자 확인 |
| "아마 동작할 것" | 테스트/시뮬레이션 실제 실행 |
| "리팩터링은 별도" | 해당 PR 범위 내에서는 명시적 생략 이유 기록 |

## Table C — JARVIS 자기개선 합리화
...
```

### 3.3 훅 통합

`cmux-leceipts-gate.py` (기존 PreToolUse:Bash 훅) 확장:
- tool_input.command 또는 선행 assistant 메시지에 합리화 패턴 매칭
- 매칭 시 **deny** 대신 **ask** (사용자에게 판단 요청) + reference/anti-rationalization.md 링크 첨부

### 3.4 자동 수집

Phase 2.3 ledger + Phase 2.2 metrics 조합으로:
- VERIFY_FAIL 비율이 높은 worker
- DONE_CLAIMED → 실제 artifact 없음 사례
- 합리화 문구 빈도 (ledger.message_excerpt 필드)

월 1회 `jarvis-anti-rationalization-report.py`가 자동 생성하여 references/anti-rationalization.md 표를 업데이트(**appendix 섹션**에 근거 누적).

## 4. 5관점 검증

### SSOT
- Anti-rationalization 표 정본: `references/anti-rationalization.md` 1개 파일
- 훅 매칭 패턴: `cmux-leceipts-gate.py` 내부 상수 (단일 위치)
- 자동 수집기 1개 (jarvis-anti-rationalization-report.py)

### SRP
- references 파일: "규칙 + 대응 기술"만
- 훅: "감지 + ask 발화"만
- Report: "ledger 조회 + 표 업데이트"만

### 엣지케이스
- False positive (정상 용례): "환경 문제"가 나왔지만 뒤이어 구체 원인 서술 → 훅이 메시지 전체 스캔해서 추가 context 있으면 PASS
- 국어/영어 혼재: 한/영 패턴 양쪽 목록 유지
- 표 자동 업데이트가 manual 편집과 충돌: appendix 섹션만 자동, 상단 정적 표는 수동만 — 마크다운 주석으로 섹션 분리
- 훅이 **ask** 반환하면 flow 중단 — LLM 자율 판단 가능하도록 "override reason" 필드 제공

### 아키텍트
- 기존 `cmux-leceipts-gate.py` 확장 (새 훅 추가 X) ✓
- Phase 2.1 progressive disclosure 패턴과 호환 — references/에 배치
- Phase 2.3 ledger 데이터 소비자 → 먼저 2.3 완료 필요

### Iron Law
- **"검증 없이 완료 보고 금지"** (CLAUDE.md leceipts §최상위원칙) ✓
- **"추측을 사실로 표현 금지"** ✓
- **"구체적 차단 요소 명시"** ✓

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 입력 | expected |
|---|------|----------|
| 1 | "환경 문제로 테스트 못 함" (추가 설명 없음) | ASK + 참조 링크 |
| 2 | "환경 문제: sqlite3 CLI가 CI에 없어 install 중" | PASS (구체적) |
| 3 | "아마 동작할 것 같아요" | ASK |
| 4 | "완료했습니다" (VERIFY 이벤트 없음) | ASK |
| 5 | "완료, 테스트 12/12 pass" + VERIFY_PASS ledger | PASS |
| 6 | "환경 문제" 한/영 혼재 | ASK |
| 7 | Override reason 포함 | PASS |
| 8 | 정규식 false positive (코드 문자열 내 "환경 문제") | PASS |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

프로토타입: `/tmp/anti_rationalization_prototype.py`, 러너: `/tmp/test_anti_rationalization.py`.

```
[PASS] 1 환경 문제 bare → ask
[PASS] 2 환경 문제 with specific binary → allow
[PASS] 3 아마 동작 → ask
[PASS] 4 완료 without evidence → ask
[PASS] 5 완료 with VERIFY_PASS + test ratio → allow
[PASS] 6 mixed KO/EN environment issue → ask
[PASS] 7 override reason present → allow
[PASS] 8 quoted string shouldn't trigger → allow

=== Phase 2.4 simulation: 8 pass / 0 fail ===
```

→ 8/8 PASS.

### 5.3 패턴 보강

프로토타입에 `"완료"` 패턴 추가 (plan Table A의 "완료했습니다 → evidence 확인" 규칙 기계화). EVIDENCE 패턴에 `VERIFY_PASS`, `test N/N` 포함 — ledger 연동 전에도 텍스트 자체에서 증거 존재 판정 가능.

Phase 2.3 ledger 가 완성되면 `collect_surface_metrics` 호출로 외부 증거 신뢰성 강화.

## 6. 구현 절차

1. `references/anti-rationalization.md` 초안 작성 (Table A-C)
2. `cmux-leceipts-gate.py` 패턴 매칭 확장 + ask 반환 로직
3. 8 테스트 PASS
4. `jarvis-anti-rationalization-report.py` 작성 (ledger 쿼리)
5. 월 1회 실행 스크립트 등록 (cron 또는 수동)
6. CLAUDE.md leceipts 섹션에 "references/anti-rationalization.md 참조" 링크 추가
7. CHANGELOG + PR

## 7. DoD

- [ ] 8 테스트 PASS
- [ ] 훅 ask 반환 실제 세션에서 동작 확인
- [ ] report 스크립트로 지난 30일 ledger 분석 실행
- [ ] references/ 링크 CLAUDE.md 반영
- [ ] PR merge

## 8. 리스크

- **LLM 회피 학습**: 같은 합리화를 다른 표현으로 포장 → report 주기 업데이트로 대응
- **ask 피로**: 너무 자주 질문하면 워크플로 방해 → 임계값 조정 (명확한 증거 없을 때만)
- **Phase 2.3 미완 시 불완전**: ledger 없으면 report 스크립트 미구현 — 2.3 전에는 "훅 차원만" 구현하고 report는 2.3 후 따라오기
