# 서브에이전트 상세 정의 + 스킬 최적화

## 전용 에이전트 요약

| 컴포넌트 | 종류 | 모델/비용 | 역할 | 상시/온디맨드 |
|---------|------|----------|------|-------------|
| **eagle_watcher.sh** | bash 스크립트 | **API 0원** | 20초 자동 폴링 → JSON 상태 파일 | **상시** (백그라운드) |
| **cmuxeagle** | 서브에이전트 | haiku | 상태 판단 + cmux send 작업 전달 | 온디맨드 |
| **cmuxreview** | 서브에이전트 | **Sonnet** | 코드 리뷰 (code-reviewer-pro) | 온디맨드 |
| **cmuxgit** | 서브에이전트 | haiku | 커밋/푸시 (git-workflow-manager) | 온디맨드 |
| **cmuxplanner** | 서브에이전트 | sonnet | 작업 큐 생성 (태스크 분해) | 온디맨드 |
| **cmuxdiagnostic** | 서브에이전트 | haiku | 사전 검증 (테스트 실행) | 온디맨드 |

## 에이전트 상세 정의

### cmuxreview (Sonnet) — 코드 리뷰어

**역할**: cmux AI가 코드를 반환하면, git diff를 리뷰하고 이슈를 보고.
**모델**: **Sonnet** (⚠️ Opus 금지 — Main Opus와 동시 실행 시 529 위험)
**장착 스킬**: code-reviewer-pro (correctness→security→performance→maintainability)

> **왜 Sonnet?**: 계정 통합 rate limit이므로 Opus 2개(Main+Sub) 동시 = 529 위험.
> Sonnet은 코드리뷰에 충분한 품질이며 비용도 1/5.

```
Agent(subagent_type="code-reviewer-pro", model="sonnet", name="cmuxreview",
  run_in_background=true, prompt="""
  You are cmuxreview — code reviewer for cmux AI outputs.

  When reviewing:
  1. cd $CLAUDE_PLUGIN_ROOT  # 프로젝트 루트
  2. git diff -- {specified_path}
  3. Priority: Correctness > Security > Performance > Maintainability
  4. Check: edge cases, null checks, error handling, type safety
  5. Verdict: APPROVE (no critical issues) or REJECT ([file:line] issue → fix)

  Focus on issues only. No praise. No style nitpicks.
""")
```

### cmuxgit (haiku) — 커밋/푸시 담당

**역할**: 메인이 커밋 지시하면 즉시 실행. 시크릿 보호 + 메시지 생성.
**모델**: haiku (빠른 실행, 판단 불필요)
**subagent_type**: `git-workflow-manager` (Claude Code 내장 — Git 전문: branching, conventional commits, conflict resolution)

```
Agent(subagent_type="git-workflow-manager", model="haiku", name="cmuxgit",
  run_in_background=true, prompt="""
  You are cmuxgit — git commit/push handler.

  When main sends a commit request with files and summary:
  1. cd $CLAUDE_PLUGIN_ROOT  # 프로젝트 루트
  2. git status --short (변경 확인)
  3. git add {specified_files} (절대 .env, secrets, credentials 포함 금지)
  4. git diff --cached --stat (커밋될 내용 확인)
  5. Generate commit message (conventional commits: feat/fix/chore)
  6. git commit -m "{message}\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  7. git push origin main
  8. Report: "COMMITTED: {hash} — {1줄 요약}"

  시크릿 보호 규칙:
  - .env, credentials.json, secrets/ → 절대 커밋 금지
  - 발견 시 즉시 보고하고 커밋 중단
""")
```

### cmuxplanner (sonnet) — 작업 큐 생성기

**역할**: 대규모 작업을 AI별 적정 크기로 분해하고 작업 큐를 생성.

```
Agent(subagent_type="general-purpose", model="sonnet", name="cmuxplanner",
  prompt="""
  You are cmuxplanner — work queue generator.

  Given a large task description and available surfaces:
  1. Break into 4-8 independent sub-tasks
  2. Each sub-task: minimum 10 minutes of work (no micro-tasks)
  3. Assign difficulty: Codex=hard, Gemini=medium+research, GLM=simple+files
  4. Ensure file scope isolation (no overlap)
  5. Output JSON: [{"id":1, "task":"...", "target":"codex|gemini|glm", "files":["..."], "estimated_minutes":15}]
""")
```

### cmuxdiagnostic (haiku) — 코드 리뷰 전 사전 검사

**역할**: 커밋 전 빠른 검증 (테스트 실행, 구문 검사).

```
Agent(subagent_type="general-purpose", model="haiku", name="cmuxdiagnostic",
  run_in_background=true, prompt="""
  You are cmuxdiagnostic — pre-commit verification.

  You will receive a verify request with:
  - working_dir: <path>
  - test_commands: ["<cmd1>", "<cmd2>"]

  Execute each command in the specified directory and report results.
  If no test_commands specified, run: git diff --name-only HEAD | head -20
  Report: "TESTS: X/Y PASSED" or "TESTS: FAILED — {details}"
""")
```

## 상황별 추가 에이전트 (온디맨드, 529 예산 내)

| 상황 | subagent_type (내장) | 모델 | 용도 |
|------|---------------------|------|------|
| 보안 민감 코드 수정 | `security-auditor` | sonnet | OWASP Top 10 + 취약점 검사 |
| 구현 완료 후 | `test-automator` | sonnet | 테스트 자동 생성 |
| surface ERROR 장애 | `debugger` | sonnet | 에러 근본 원인 분석 |
| 코드베이스 탐색 | `Explore` | haiku | 파일 구조 파악 (빠름) |
| API 설계 | `backend-architect` | sonnet | 아키텍처 설계 검증 |

> **모두 Claude Code 내장 subagent_type.** 별도 설치 불필요.
> 529 예산: Main(1) + 서브에이전트(최대 1) = 동시 2개. 순차 사용은 자유.

## 서브에이전트 스킬 주입 메커니즘

> **서브에이전트는 Skill() 도구를 호출할 수 없다. 대신 `skills` 프론트매터로 스킬 콘텐츠를 미리 주입받는다.**

**방법: `.claude/agents/` 에이전트 정의 파일에서 `skills:` 필드 사용**

```yaml
# ~/.claude/agents/my-code-reviewer.md
---
name: code-reviewer-pro
skills:
  - karpathy-guidelines      # 코딩 실수 방지
  - code-review              # 리뷰 프로세스
  - production-code-audit    # 프로덕션 품질
  - security-insecure-defaults # 보안 기본값
  - trinity                  # 코드 품질 평가
  - tob-differential-review  # 차이점 분석
  - tob-fp-check            # 오탐 제거
  - tob-sharp-edges         # 위험 API 감지
model: inherit
---
```

## 현재 장착 스킬

| 에이전트 | subagent_type | 장착 스킬 수 | 주요 스킬 |
|---------|-------------|-----------|----------|
| cmuxreview | `code-reviewer` | **0개** | A/B 5회 테스트 결과: 0스킬이 4승1패로 최적. 지시 준수율↑, 버그 감지율 동등, 출력 10x 절약 |
| security-auditor | `security-auditor` | **15개** | tob-codeql, tob-semgrep, trivy, guardrails, tob-supply-chain-risk-auditor 등 |
| cmuxgit | `git-workflow-manager` | 기본 | Git 전문 (branching, conventional commits) |
| debugger | `debugger` | 기본 | 에러 근본 원인 분석 |
| test-automator | `test-automator` | 기본 | 테스트 자동 생성 |

> 스킬은 에이전트 시작 시 **컨텍스트에 자동 주입**됨. 런타임에 Skill() 호출이 아님.
> 에이전트 정의 파일은 `~/.claude/agents/`에 위치.

## 번들 에이전트 (이 스킬에 포함)

| 에이전트 | 스킬 수 | 모델 | 용도 |
|---------|--------|------|------|
| cmux-reviewer | 5개 (A/B 최적화) | Sonnet | 코드리뷰 |
| cmux-git | 2개 | Haiku | 커밋/푸시 |
| cmux-security | 4개 | Sonnet | 보안감사 |

에이전트 정의 파일은 `skills/cmux-orchestrator/agents/`에 번들.
`--install` 시 `~/.claude/agents/`에 복사.
이미 설치된 에이전트는 스킵 (덮어쓰기 안 함).

## 에이전트 설치 플로우

```
1. 번들 에이전트 설치 상태 확인
   bash scripts/install_agents.sh --check

2. 미설치 에이전트 발견 시 사용자에게 안내:
   "cmux 오케스트레이션에 최적화된 서브에이전트를 설치합니다:
    - cmux-reviewer (코드리뷰, Sonnet, 5개 스킬)
    - cmux-git (커밋, Haiku, 2개 스킬)
    - cmux-security (보안감사, Sonnet, 4개 스킬)
    설치할까요? (예/아니오)"

3. 예 → bash scripts/install_agents.sh --install
   아니오 → 기본 subagent_type 사용 (스킬 없이 동작)
```

## 순차 파이프라인 (529 안전)

복합 작업 시 서브에이전트를 **순차 실행** (동시 1개만):

```
사용자 요청: "코드 구현 + 리뷰 + 보안 검사"

Phase 1: Main 구현 (또는 cmux send로 위임)
  ↓
Phase 2: cmuxreview (code-reviewer-pro + 11 skills)
  → Main이 결과 검증 → APPROVE/REJECT
  ↓
Phase 3: security-auditor (15 skills)
  → Main이 결과 검증 → 보안 이슈 수정
  ↓
Phase 4: test-automator
  → 테스트 자동 생성
  ↓
Phase 5: Main 커밋
```

**529 안전**: 각 Phase에서 서브에이전트 **1개만** 실행 → Main + Sub = 2개 (안전).

## 지속 스킬 최적화 프로토콜

```
매 서브에이전트 호출 시:
1. 결과에서 "사용한 스킬" 보고 요청 (프롬프트에 포함)
2. 실제 사용 스킬 기록
3. 3회 연속 미사용 스킬 → 제거 후보
4. 필요했으나 없던 스킬 → 추가 후보
5. 에이전트 정의 파일 업데이트
```

| 에이전트 | 스킬 | 테스트 방법 | 상태 |
|---------|------|-----------|------|
| cmux-reviewer | 5 | A/B 테스트 (11→5, 감지율 동일) | ✅ 최적화 완료 |
| cmux-git | 2 | A/B 테스트 (3→2, 핵심만) | ✅ 최적화 완료 |
| cmux-security | 4 | 번들 정의 (보안 전문 4개) | 실전 검증 필요 |
| debugger | 5 | 기존 정의 유지 | 실전 검증 필요 |
| test-automator | 7 | 기존 정의 유지 | 실전 검증 필요 |

## 메인 역할 분리 (v4.2 핵심)

```
┌─────────────────────────────────────────────────────────────┐
│                 Main Opus 전용 업무 (직접 수행)               │
│                                                              │
│  1. 오케스트레이션: 작업 큐 관리, cmux send 작업 분배        │
│  2. 계획 수립: 태스크 분해, 난이도 판정, surface 배정         │
│  3. 에러 대응: 529/장애 감지 → 복구 → 재위임                │
│  4. 커밋 판단: 리뷰 결과 보고 읽고 커밋/거부 결정            │
│  5. eagle 상태 읽기: cat /tmp/cmux-eagle-status.json         │
│                                                              │
│  ❌ Main이 하면 안 되는 것:                                   │
│  - 직접 코딩 (cmux send로 위임)                              │
│  - 직접 코드리뷰 (cmuxreview 서브에이전트에 위임)            │
│  - 수동 폴링 (eagle_watcher.sh가 자동)                       │
├─────────────────────────────────────────────────────────────┤
│                 서브에이전트 업무 (위임)                       │
│                                                              │
│  cmuxeagle (haiku): 상태 판단 + cmux send 작업 전달          │
│  cmuxreview (Sonnet): 코드 리뷰 ← ⚠️ Opus 금지 (529 방지)  │
│  cmuxgit (haiku): 커밋/푸시 실행                             │
│  cmuxplanner (sonnet): 대규모 작업 분해                      │
│  cmuxdiagnostic (haiku): 테스트 실행                         │
├─────────────────────────────────────────────────────────────┤
│                 cmux 외부 AI (0 API)                          │
│                                                              │
│  surface:1-5 팀원: 실제 코딩, 조사, 분析                     │
│  → cmux send로만 통신 (529 위험 0%)                          │
│  → 유일한 0-risk 작업 위임 방법                              │
└─────────────────────────────────────────────────────────────┘
```
