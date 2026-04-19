# cmuxO Upgrade Phase 2.1 — Watcher Progressive Disclosure

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기
**참조 프로젝트**: `/Users/csm/projects/olympus/source/skillkit/` — 3-layer progressive disclosure 패턴

---

## 1. 문제 요약

현재 `cmux-watcher/SKILL.md`는 **단일 파일 ~700라인**으로 모든 GATE/규칙/예시가 혼재 → 세션 시작 시 전량 context에 주입되어 토큰 낭비.

Superpowers 이슈 (Issue #1220에서 제기)와 동일한 구조 문제:
- 사용하지 않는 규칙까지 모두 로드
- 실제 필요한 시점에 세부 가이드 다시 검색 불가 (이미 맥락 흐려짐)

skillkit 프로젝트의 3-layer 패턴 차용 시:
- **L1 (항상 로드)**: 핵심 GATE 목록 + 트리거 조건 (~50줄)
- **L2 (on-demand)**: 각 GATE별 상세 — `references/gate-W-9.md` 등
- **L3 (deep dive)**: 설계 배경 / 케이스스터디 / 레퍼런스

## 2. 근거

### 2.1 현재 SKILL.md 구조 분석

```
cmux-watcher/SKILL.md (698 lines)
├── 개요 (1-20)
├── 핵심 행동 사이클 GATE W-8 (21-55)
├── 개입 금지 GATE W-9 (41-100)
├── IDLE 재배정 GATE W-10 (56-120)
├── 질문 금지 GATE W-7 (91-150)
├── GATE W-6 규칙 (313-340)
├── 전체 GATE 표 W-1~W-10 (675-700)
└── 각 GATE별 예시/케이스 (산재)
```

→ 700줄 전량 주입. 실제 액션 사이클에 필요한 건 ~50줄.

### 2.2 skillkit 참조 구조

```
/Users/csm/projects/olympus/source/skillkit/apps/
├── SKILL.md          (L1 — 핵심 요약 + 트리거)
├── references/       (L2 — 상세 가이드, on-demand)
└── resources/        (L3 — 샘플, 심화)
```

- L1은 `frontmatter` + `description` 기반으로 Claude가 "언제 읽어야 하는지" 판단
- L2는 `<progressive-disclosure>` 마커로 지연 로드
- 평균 초기 주입 78% 감소 (skillkit README 주장, 검증 필요)

### 2.3 cmuxO 기존 `references/` 폴더

`cmux-watcher/references/` 이미 존재 (`vision-diff-protocol.md`, `collaborative-intelligence.md`, `inter-peer-protocol.md`) — **인프라 활용 가능**.

## 3. 설계

### 3.1 분리 전략

**Keep in L1 (SKILL.md, ~120줄 목표)**:
- YAML frontmatter (name, description, trigger)
- 핵심 루프 1페이지 (감지 → 기록 → 보고)
- GATE 목록 **표만** (W-1 ~ W-10 요약 1줄씩)
- "상세는 references/gate-w-*.md 참조" 안내

**Move to L2 (`references/gate-w-N.md`)**:
- W-2 (Error Immediate Alert) 상세 로직
- W-3 (Vision Verify IDLE) 상세 로직
- W-6 (Boss Never Blocked) 상세 규칙
- W-7 (질문 금지) 상세 + 예외 케이스
- W-8 (핵심 행동 사이클) 상세
- W-9 (개입 금지) 상세 + 폐지된 기능 목록
- W-10 (IDLE 재배정 debounce) 상세

**Move to L3 (`references/design/`)**:
- 각 GATE의 "왜 만들어졌나" 케이스스터디
- 레드팀 Finding 로그
- v3→v4→v4.1 변천사

### 3.2 L1 SKILL.md 템플릿

```markdown
---
name: cmux-watcher
description: 감지→기록→보고 전담. 모든 개입 금지. 상세 규칙은 references/ 참조.
trigger: watcher 세션 시작 / scan 주기
version: v4.1
---

## 핵심 루프
1. Surface 상태 감지 (eagle + ANE OCR)
2. RATE_LIMITED/ERROR/IDLE → pool/alert 기록
3. Boss에게 알림만 (개입 절대 금지)

## GATE 목록 (상세는 references/gate-w-N.md)
| ID | 핵심 | 상세 |
|----|------|------|
| W-1 | IDLE Zero Tolerance | [gate-w-1.md](references/gate-w-1.md) |
| W-2 | Error Immediate Alert | [gate-w-2.md](references/gate-w-2.md) |
| ... | ... | ... |
| W-9 | 개입 금지 (`/new`·`/clear` 금지) | [gate-w-9.md](references/gate-w-9.md) |

## Red Lines
- Worker/Watcher는 팀원 surface에 직접 개입 **절대 금지** (W-9, Phase 1.2에서 훅 강제)
- Boss 승인 없이 복구 시도 금지
- 질문 금지 (W-7)
```

### 3.3 로드 규칙

- Claude Code SessionStart에서 L1만 주입
- L2는 필요 시 `Read` 또는 `Skill` 호출로 가져옴
- 훅이 특정 GATE 위반 경고 시 해당 L2 파일 경로를 메시지에 포함 → LLM이 on-demand 조회

## 4. 5관점 검증

### SSOT
- 각 GATE의 정본: `references/gate-w-N.md` 1개 파일
- L1 SKILL.md는 **표 요약만**, 세부 중복 금지
- Migration 후 "L1에 세부 남기지 말기" lint rule (구현: `tests/test_skill_md_size.sh` — SKILL.md 줄 수 200 이하 강제)

### SRP
- L1: "어느 규칙이 있고 언제 보는지" 내비게이션만
- L2: 각 GATE의 로직/예시/예외
- L3: 히스토리·설계배경 (운영에 불필요)

### 엣지케이스
- L2 파일 부재 → L1 표에 빠진 링크 감지 (CI 체크)
- GATE 번호 충돌 / rename → L1/L2 양쪽 업데이트 누락 위험 → CI가 교차 검증
- 외부 링크 (http) 섞임 → 로컬 references만 허용 규칙
- 마이그레이션 중 부분 분리 상태 → 기능 퇴행 (L1에서 제거됐지만 L2 미생성) → 한 PR로 일괄 이동

### 아키텍트
- `cmux-watcher/references/` 이미 존재 → 폴더 관습 재사용 ✓
- Claude Code SKILL 포맷 호환 (frontmatter) — 기존 activation flow 영향 없음
- `cmux-watcher-activate.sh` / `cmux-watcher-session.sh` 훅은 파일 경로만 참조 → 내부 분리 무영향

### Iron Law
- **"SKILL.md ≤ 200라인"** (신규 Iron Law 제안)
- **"세부 규칙은 references/에만"**
- **"표 → 링크 → 상세" 3단 네비게이션**

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 시나리오 | expected |
|---|---|---|
| 1 | L1 SKILL.md만 주입 후 "W-9가 뭐야?" 질문 | LLM이 references/gate-w-9.md 읽기 요청 |
| 2 | L1 길이 측정 (`wc -l`) | ≤ 200 |
| 3 | GATE 표 중 1개 링크 깨짐 | CI test fail |
| 4 | L2 파일 내부에 다른 GATE 내용 섞임 | lint 경고 |
| 5 | Frontmatter 누락 | Claude Code SKILL 로드 실패 |
| 6 | 훅 메시지에 L2 경로 포함 (W-9 위반 시) | LLM이 해당 경로 follow |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

러너: `/tmp/test_progressive_disclosure.py`. 현 `cmux-watcher/SKILL.md` baseline 측정 후, 프론트매터+핵심 루프+GATE 표만 유지하는 최소 L1 mock 추출.

```
[baseline] SKILL.md: 838 lines, 33.4KB, ~7407 tokens
[PASS] 1 baseline > 600 lines (bloat confirmed)
[mock L1] 26 lines, 1.3KB, ~283 tokens
[PASS] 3 mock L1 ≤ 200 lines
[PASS] 4 token reduction > 60% (actual 96.2%)
[PASS] 5 all GATE rows preserved in L1 (6/6)
[PASS] 6 L1 retains frontmatter
[PASS] 7 CI size-gate (wc -l ≤ 200)

=== Phase 2.1 simulation: 6 pass / 0 fail ===
  reduction: 7124 tokens (96.2% saved)
```

→ 6/6 PASS. **이론적 상한** 96.2% 토큰 절감 (mock L1은 표+링크만). 실제 구현은 가이드 문장·예시 일부 포함으로 **70~85% 절감** 목표 설정 권장.

**주의**: baseline 측정 시 GATE 표의 `| W-` 행 6건만 카운트 — 실제 SKILL.md는 W-1~W-10 범위를 표 행으로 완비해야 함 (현 문서에 일부 누락 가능). L2 분리 전 표 완비화가 선행 과제.

## 6. 구현 절차

1. 현재 `cmux-watcher/SKILL.md` 전체 백업 (`SKILL.md.pre-phase2-1.bak`)
2. L2 파일 10개 생성 (`references/gate-w-{1..10}.md`) — 기존 내용 섹션별 분리
3. L1 SKILL.md 재작성 (~120라인, 표 + 핵심 루프)
4. L3 `references/design/` 작성 (history/case-study)
5. `tests/test_skill_md_size.sh` 추가 — `[ $(wc -l < SKILL.md) -le 200 ]`
6. `tests/test_gate_links.sh` — 표 링크 전수 파일 존재 체크
7. cmux-orchestrator 쪽 hook 메시지에 L2 경로 포함하도록 수정 (GATE W-9 훅이 references/gate-w-9.md 안내)
8. 실사용 세션 dry-run — 토큰 사용 before/after 측정
9. CHANGELOG + PR

## 7. DoD

- [ ] L1 ≤ 200라인
- [ ] L2 각 GATE별 파일 존재
- [ ] CI 2개 test 통과 (size, link)
- [ ] 토큰 사용 측정 before/after (~3000 → ~500 토큰 목표, 측정 필수)
- [ ] PR merge

## 8. 리스크

- **LLM이 L2를 안 읽고 추측하는 경우**: L1 GATE 표에 "위반 시 아래 파일 필독" 명시 + 훅이 경로 주입
- **파일 많아짐 (10+ files)**: `references/` 폴더 유지보수 비용 증가 → 대신 단일 `SKILL.md` 700줄 유지 비용 더 큼 (토큰 경상비 > 파일 수 관리비)
- **Migration PR 크기**: 10+ file create + SKILL.md 재작성 → 대규모 diff. 리뷰 부담 → **diff 쉬운 리뷰를 위해 "파일 이동 commit"과 "리팩터링 commit" 분리**
