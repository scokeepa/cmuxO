---
name: cmux-orchestrator
description: "Use when orchestrating multiple AI surfaces via cmux — cmux 멀티 AI 오케스트레이션 v7 — Main=지휘관(코드수정금지), 부하=직접구현(서브에이전트금지). DONE 2회 출력. 워크트리 병렬. 3-10분 작업단위. DONE확인→/new→재배정 프로토콜."
user-invocable: true
classification: workflow
allowed-tools: Bash, Read, Write, Grep, Glob, Agent, AskUserQuestion
---

# cmux Multi-AI Orchestrator v7.3

> v7.3 : DONE 2회 출력, 워크트리 병렬, Main 코드수정 금지, 부하 서브에이전트 금지, 3-10분 작업단위, DONE확인→/new 프로토콜

**경로 변수** (이식성):
- `${SKILL_DIR}` = 이 스킬의 루트 디렉토리 (예: `~/.claude/skills/cmux-orchestrator/`)
- `$CLAUDE_PLUGIN_ROOT` = 플러그인 루트 (있으면 사용, 없으면 프로젝트 루트)

**패키징 시 포함되는 파일:**
```
cmux-orchestrator/
├── SKILL.md                          # 오케스트레이션 지침 (이 파일)
├── agents/                           # 서브에이전트 정의
│   ├── cmux-reviewer.md              # 코드 리뷰어 (Sonnet, 0스킬)
│   ├── cmux-git.md                   # Git 작업 (haiku)
│   └── cmux-security.md              # 보안 검사 (Sonnet, 4스킬)
├── scripts/
│   ├── eagle_watcher.sh              # Surface 상태 감시 (WAITING 감지 포함)
│   ├── cmux-claude-bridge.sh         # Claude Code ↔ cmux 브릿지 훅
│   ├── cmux-idle-reminder.sh         # IDLE surface 알림 훅
│   ├── cmux-orchestra-enforcer.sh    # 세션 시작 시 자동 활성화 훅
│   ├── install_agents.sh             # 에이전트 설치 스크립트
│   └── detect_surfaces.py            # Surface 자동 감지
├── config/
│   └── orchestra-config.json         # AI 프리셋 (생존: 세션 재시작 유지)
└── references/
    ├── octopus-concepts.md           # Octopus 아키텍처 개념
    ├── circuit-breaker.md            # 529 에러 방지 및 Circuit Breaker
    ├── eagle-patterns.md             # Eagle Watcher 상세 패턴
    ├── dispatch-templates.md         # 디스패치 템플릿 및 ClawTeam DAG
    ├── error-recovery.md             # 에러 복구 프로토콜
    ├── cmux-commands-full.md         # cmux 명령어 전체 레퍼런스
    ├── onboarding-detail.md          # 온보딩 상세 절차
    └── subagent-definitions.md       # 서브에이전트 상세 정의 + 스킬 최적화
```

## 핵심 원칙 (MANDATORY — 모든 행동의 기반)

### 1. Main은 COO — 조직 운영만, 직접 작업 금지

```
User(CEO):   업무 지시 → Main에게 전달
Main(COO):   부서 편성 + 팀장 배치 + 결과 취합 + 커밋
Team Lead:   서브태스크 분해 + 팀원에게 직접 dispatch
Member:      실제 코딩/탐색/분석
Watcher:     모니터링 + 리소스 체크 + 보고만
```

**부서(Department) = 1 workspace**
- 팀장(Team Lead) = workspace의 첫 surface
- 팀원(Member) = 추가 surface (0~N명)
- 작업에 따라 동적 생성/해제

**✅ Main(COO)이 하는 것:**
- **부서 편성:** cmux new-workspace + rename-workspace + AI 시작
- **팀장 배치:** cmux rename-tab으로 역할 표시, 작업 지시 전송
- **팀원 생성:** 팀장 요청 시 cmux new-pane으로 추가
- **AI 선택:** 주제/난이도에 맞는 AI (ai-profile.json 기반, Claude 티어 fallback)
- **결과 취합:** 팀장 보고 → 리뷰 → git commit
- **부서 해제:** 완료 후 cmux close-workspace (컨트롤 타워 제외!)
- **컨트롤 타워 고정:** cmux reorder-workspace --index 0

**⛔ Main의 직접 금지 행동:**
- **Edit/Write 도구로 코드 파일 수정** — 팀장/팀원에게 위임
- **직접 코딩/탐색/조사** — 부서에 위임
- **서브에이전트로 작업 대체** — GATE 6 위반
- **컨트롤 타워 close-workspace** — 절대 금지

**⚠️ cmux 명령 필수 규칙:**
- 다른 workspace 접근 시 **--workspace 플래그 필수**
- 부서 해제 전 **컨트롤 타워 여부 확인** 필수

**서브에이전트 허용 범위:**
- **코드리뷰(Sonnet)** — GATE 2 필수
- **haiku 경량 도구 작업** — Git 작업, 간단 스크립트

### Traits 기반 dispatch 규칙 (MANDATORY)

dispatch 시 `/tmp/cmux-surface-map.json`의 traits 목록을 반드시 확인:

| Surface가 이 목록에 있으면 | 규칙 |
|---------------------------|------|
| `sandbox_surfaces` | cmux CLI 실행 불가 → cmux 관련 작업 배정 금지, 팀장 불가 |
| `short_prompt_surfaces` | 프롬프트 200자 이내로 축약하여 전송 |
| `two_phase_surfaces` | /clear와 작업을 분리 전송 (같은 cmux send에 합치지 마) |
| `no_init_surfaces` | /new 초기화 없이 바로 작업 전송 가능 |

```bash
# 예: surface:12가 short_prompt_surfaces에 있으면
cmux set-buffer --surface surface:12 "JWT 미들웨어 구현. auth.js에 verify 함수 추가."
# 200자 이내! 긴 설명 금지.

# 예: surface:15가 two_phase_surfaces에 있으면
cmux send --surface surface:15 "/clear"
cmux send-key --surface surface:15 Enter
sleep 2
cmux set-buffer --surface surface:15 "TASK: 세션 관리 모듈 구현..."
cmux paste-buffer --surface surface:15
cmux send-key --surface surface:15 Enter
# /clear와 작업을 분리!
```

**⛔ RED FLAG — 이런 행동이 나오면 즉시 STOP:**

| Main이 하려는 행동 | 올바른 행동 |
|-------------------|-----------|
| `Agent(subagent_type="Explore", ...)` | `cmux send --surface surface:N "이 파일/폴더 탐색해줘"` |
| `Agent(subagent_type="impl-worker", ...)` | `cmux send --surface surface:N "TASK: 이 코드 구현해줘"` |
| `Agent(subagent_type="search-worker", ...)` | `cmux send --surface surface:N "python3 search_executor.py --query '주제' --full"` |
| `Agent(subagent_type="general-purpose", ...)` | `cmux send --surface surface:N "이 작업 해줘"` |
| `Read(file_path=...)` 로 대량 파일 탐색 | cmux surface에 "이 파일들 읽고 분석해줘" 위임 |
| `Grep/Glob` 으로 코드베이스 탐색 | cmux surface에 "이 패턴 찾아줘" 위임 |
| 직접 코드 구현 (Edit/Write) | cmux surface에 구현 위임, 결과를 git diff로 확인 |

**예외 (Main 직접 허용):**
- 5줄 이하 간단 수정 (오타, 설정값 변경)
- git 명령어 (commit, push, status)
- cmux 명령어 자체 실행
- 서브에이전트 코드리뷰 결과 확인 후 APPROVE/REJECT
- GATE 검증 스크립트 실행

### 2. 절대 멈추지 않는다

| 금지 표현 | 해야 하는 것 |
|----------|------------|
| "별도 세션에서" | 즉시 다음 단계 진행 |
| "나중에 구현" | cmux AI에 위임하고 Main은 다른 작업 |
| "컨텍스트 부족" | /compact 후 계속 |
| "이 세션은 여기까지" | 사용자가 "멈춰" 하기 전까지 완주 |

### 3. 조사 완료 → 즉시 구현

```
조사 배포 (cmux send) → 결과 JSON 수집 → 계획 수립 → 코드 구현 → 테스트 → 커밋
                     ↑ 이 지점에서 멈추면 안 됨 ↓
```

### 4. 놀고 있는 AI = 0

매 UserPromptSubmit마다 cmux-idle-reminder.sh가 IDLE surface 알림.
IDLE surface 있으면 → 현재 작업에서 병렬 가능한 부분 즉시 위임.

### 5. DONE 프로토콜 (MANDATORY)

**작업 배정 시 Main이 보내는 프롬프트에 반드시 포함할 3가지:**

**① 절대경로 (MANDATORY — 생략 시 부하가 경로 못 찾음):**
```
프로젝트: /Users/YOU/project-root
sidecar: /Users/YOU/project-root/sidecar
```
⛔ "~/Ai/..." 또는 상대경로 금지. 반드시 /Users/YOU/... 절대경로.
⛔ 워크트리 사용 시: /tmp/wt-{surface}-{round}/System/10_Projects/... 절대경로.

**② 질문 절대 금지 (MANDATORY — 위반 시 DONE 미출력으로 멈춤):**
```
⛔ 어떤 상황에서도 질문하지 마. "~할까요?", "필요한가요?", "알려주시겠습니까?" 금지.
⛔ 경로를 모르면 직접 찾아. 판단이 필요하면 직접 판단해.
⛔ 작업 완료 후 "다음 작업 있을까?" 같은 질문도 금지. DONE만 출력.
```

**③ Footer Template:**
```
[지침] ⛔서브에이전트/git/pip금지. ⛔질문절대금지-직접판단. ⛔에러시 다른방법시도.
완료후 맨마지막: 요약→빈줄5개→DONE→빈줄2개→DONE. DONE이후 출력절대금지.
```

**DONE 출력 형식 (예시):**
```
요약: auth.ts에 JWT 미들웨어 추가, 3개 파일 수정, 테스트 통과.

DONE

DONE
```

**✅ 올바른 DONE:** 요약 후 DONE 2회 출력 (화면 짤림 방지)
**❌ 잘못된 DONE:** `DONE: 요약 내용`, `Done`, `done`, `DONE!!`, DONE 1회만

**DONE 확인 — dispatcher v6 스크립트 사용 (MANDATORY):**
```bash
bash ${SKILL_DIR}/scripts/surface-dispatcher.sh "39 32 41 42 43 44"
# 출력: S:39=DONE S:32=WORKING(3m) S:41=STUCK(12m) S:44=IDLE
# DONE: 39    IDLE: 44    STUCK: 41
```
- **DONE** → 즉시 커밋 + /new + 재배정
- **WORK(Xm)** → 대기
- **ENDED(Xm)** → 작업 끝났으나 DONE 미출력. /clear + 재배정
- **QUEUED** → "Press up to edit" 큐 멈춤. enter 전송 또는 /clear + 재전송
- **COMPACT!** → 컨텍스트 위험. 즉시 /clear + 재배정 (작업 유실 감수)
- **RATE_LIM** → API 제한. 해제까지 스킵
- **ACTIVE** → 글리프(✻✶✽) 보이지만 시간 미파싱. 대기
- **IDLE** → 프롬프트 미수신. 직접 재전송
- IDLE이지만 DONE 없으면 → **미완료로 간주** → scrollback 분석 후 판단
- 5분+ DONE 없이 IDLE → 화면 직접 분석해서 멈춘 건지 작업 중인지 파악

**Why:** 화면이 좁으면 마지막 줄이 잘림. DONE 2회 출력으로 1개라도 보이면 확인 가능.

**⛔ 작업 완료 전 새 프롬프트 전송 금지 (CRITICAL):**
- Surface에 DONE이 확인되기 **전에는** 해당 surface에 절대 새 프롬프트/명령 전송 금지
- /new도 DONE 확인 후에만 전송
- DONE 없이 /new 전송 → 이전 작업 결과 유실 + 작업 꼬임
- 확인 순서: `cmux read-screen --lines 3` → DONE 있으면 → `/new` → 새 작업

### 6. 작업 크기 규칙

- **최소 3분, 최대 10분 소요 작업** 배정 (이 범위를 벗어나면 분할 또는 병합)
- **함수 1개 추가 같은 초소형 작업 금지** — 최소 파일 3-5개 수정 + 테스트 실행 단위
- **단일 작업에 2-4개 하위 작업을 번들**로 묶어 배정

**✅ 좋은 예 (3-10분 분량):**
- "이 스크립트를 읽고 A, B, C 3가지 기능을 전부 추가해. 테스트도 작성하고 pytest 실행해."
- "services_features.py의 61개 함수를 도메인별 5개 파일로 분리해. 테스트도 작성해."
- "auth.rs에 JWT 검증 + 리프레시 토큰 + 로그아웃 구현. 테스트 5개. cargo test 통과까지."
- "src/components/ 아래 error-boundary, toast, sidebar 3파일의 접근성 개선. tsc 0에러 확인."

**❌ 나쁜 예:**
- "이 함수 하나만 추가해" — 30초 작업, 번들로 묶어야 함
- "__all__ 추가해" — 1줄 수정, 다른 작업과 합쳐서 배정
- "오타 3개 수정해" — 트라이비얼, AI 낭비
- "50개 함수를 전부 리팩토링해" — 10분 초과, 2-3개 작업으로 분할

**작업 배정 패턴:**
- Codex에게는 **중상급 로직 구현 + 테스트 + 검증**을 한 번에 (서브에이전트 금지 명시 필수)
- GLM에게는 **파일 3-5개 수정 + 테스트 실행**을 한 묶음으로
- MiniMax에게는 **UI/접근성/문서 3-4개 작업**을 한 묶음으로
- 각 AI가 **3-10분** 작업할 분량으로 배정

**DONE 확인 즉시 다음 작업 재배정** (surface가 놀면 안 됨)

### 7. 2분 폴링 + Self-Renewing Loop

> See references/polling-selfrenew.md for 상세 폴링 패턴 + Self-Renewing Loop

**핵심:**
- 2분 간격으로 전 surface 상태 확인 → DONE/WORKING/RATE_LIMIT/IDLE 분류
- Self-Renewing: 컨텍스트 50%+ + 모든 surface IDLE + 미커밋 없음 → pytest+tsc → git commit → /smart-handoff

### 9. Surface 재배정 프로토콜 (DONE 확인 필수)

**⛔ DONE 확인 없이 /new 금지. /new 없이 재배정 금지 (Compacting 유발).**

```bash
# Step 1: DONE 확인 (필수)
cmux read-screen --surface surface:N --lines 3
# → "DONE" 포함 확인. 없으면 STOP — 대기 또는 scrollback 분석

# Step 2: /new로 컨텍스트 초기화 (DONE 확인 후에만)
cmux send --surface surface:N "/new" && cmux send-key --surface surface:N enter && sleep 3

# Step 3: 새 작업 전송
cmux send --surface surface:N "$PROMPT" && cmux send-key --surface surface:N enter
```

**⛔ 위반 시나리오 (절대 금지):**
- WORKING 중인 surface에 /new 전송 → 작업 결과 유실
- DONE 미확인 상태에서 새 프롬프트 → 이전 작업과 혼재되어 꼬임
- 여러 surface 일괄 /new → 아직 작업 중인 surface가 초기화됨

### 10. 부하 AI 질문/멈춤 대응

> See references/worker-stuck-recovery.md for 상세 프로토콜

**핵심 규칙:**
- 부하 AI DONE 대신 질문/에러 시 → Main이 해결 방법 직접 전송
- 5분 후 미해결 → escape + /clear + 재배정
- Footer Template에 예방적 지시 필수 포함

### 10.5. Codex 제한사항

- **서브에이전트 사용 불가** (capacity 에러 발생)
- 프롬프트에 "서브에이전트 사용하지 마" 명시 필수
- tsc 검증은 main에서 직접 실행 (Codex 워크트리에 node_modules 없음)

### 11. 워크트리 기반 병렬 작업 (MANDATORY when 2+ surfaces)

**⛔ 2개+ surface에 동시 작업 배정 시 워크트리 사용 필수 (GATE 7)**

워크트리 없이 직접 수정하면 파일 충돌, 부분 덮어쓰기, 테스트 실패 위험.

**워크트리 생성 → 배정 → 병합 → 정리 전체 절차:**

> See references/worktree-workflow.md for 상세 예시 + 충돌 해결 + node_modules 공유

```bash
# 요약: 워크트리 생성 → /new → 절대경로 포함 프롬프트 1회 전송
ROUND="r$(date +%H%M)"
WT="/tmp/wt-codex-${ROUND}/System/10_Projects/PROJECT"
git worktree add "/tmp/wt-codex-${ROUND}" -b "codex-${ROUND}" HEAD

cmux send --surface surface:N "/new" && cmux send-key enter && sleep 3
cmux send --surface surface:N "TASK: ... [작업 경로] 프로젝트 루트: ${WT} ..."
cmux send-key --surface surface:N enter

# DONE 후: Main 커밋 → 병합 → 정리
cd "/tmp/wt-codex-${ROUND}" && git add -A && git commit -m "..."
cd "$PROJECT" && git merge "codex-${ROUND}" --no-edit
git worktree remove "/tmp/wt-codex-${ROUND}" && git branch -d "codex-${ROUND}"
```

**⛔ cd 명령 전송 금지 — AI 채팅에서 CWD 변경 불가. 절대경로를 프롬프트에 포함.**

**워크트리 사용 기준 (GATE 7):**
| 상황 | 워크트리 | 직접 수정 |
|------|---------|----------|
| **2+ surface 동시 작업** | **⛔ 필수** | ❌ 금지 |
| 1개 surface만 작업 | 선택 | ✅ OK |
| surface 0개 (Main만) | ❌ 불필요 | ✅ OK |

**⛔ RED FLAG — 워크트리 없이 2+ surface 배정하려 할 때:**
"여러 surface가 같은 프로젝트를 동시에 수정하려 한다"
→ STOP → 워크트리부터 생성

**병합 시 Main 역할 (코드 수정 아님 — 판단만):**
1. 각 워크트리 diff 검토 (`git -C /tmp/wt-X diff HEAD`)
2. 병합 가치 판단 (APPROVE/REJECT)
3. APPROVE → git merge (충돌 시 Main 해결 허용 — 유일한 코드 수정 예외)
4. 최종 pytest + tsc 검증
5. 워크트리 + 브랜치 정리

#### MiniMax 워크트리 제한

**⚠️ MiniMax는 워크트리 경로를 무시하고 항상 기본 workspace를 사용합니다.**

MiniMax가 `/tmp/wt-minimax-r123456/...` 경로를 받아도 실제 파일 작업은 기본 workspace에서 수행됩니다. 이로 인해:

- 다른 surface의 워크트리와 파일 충돌 가능
- 병합 시 변경 사항이 정상 반영되지 않을 수 있음

**대응 방안:**
- MiniMax에는 직접 수정 (비워크트리) 방식 사용
- 또는 worktree를 사용하되, MiniMax 작업 완료 후 즉시 직접 확인 + 수동 병합 수행
- 가능하면 MiniMax에는 독립적인 폴더/파일을 할당하여 충돌 방지

### 12. 에러 발생 → Main이 즉시 대응

설정 파일의 프리셋으로 자동 복구:
- 컨텍스트 초과 → reset_cmd (/new 또는 /clear)
- 완전 멈춤 → quit_cmd (/quit) → start_cmd (codex 등)
- 529 → Circuit Breaker → cmux send만 사용

### 13. Rate Limit 대응

> See references/rate-limit-handling.md for 상세 프로토콜

**핵심 규칙:**
- GLM rate limit: 429 + "Usage limit reached" → CST 시간 확인 → KST 변환 (+1시간)
- 동일 API 키 공유 surface 전부 blocked (GLM-1+GLM-2)
- 리셋 시간까지 해당 surface에 작업 배정 금지

## ⛔ HARD GATE 시스템 — 위반 불가 강제 규칙

> See references/gate-enforcement.md for 4중 강제 체계 + L0~L3 상세

**핵심:**
- L0: `gate-blocker.sh` (PreToolUse) → WORKING 시 커밋 물리적 차단
- L1: `after-send-keys` 훅 → eagle 자동 갱신
- L2: `gate-enforcer.py` + `cmux-idle-reminder.sh`
- L3: SKILL.md GATE 체크리스트

### GATE 0.5: ZERO-PASTE (cmux send 강제)

**⛔ 절대 금지 표현:**

| 금지 표현 | 대신 해야 하는 것 |
|----------|-----------------|
| "이 프롬프트를 붙여넣어주세요" | `cmux send --surface surface:N "프롬프트"` |
| "surface:N에 입력해주세요" | `cmux send --surface surface:N "내용"` + `cmux send-key enter` |
| "다른 AI에게 전달해주세요" | `cmux send --surface surface:N "내용"` |
| "사용자가 직접 전달" | Main이 cmux send로 직접 전달 |

**200자+ 긴 프롬프트 전송:**
```bash
# 방법 1: cmux send (대부분 케이스)
cmux send --surface surface:N "긴 프롬프트 내용..."
cmux send-key --surface surface:N enter

# 방법 2: buffer (매우 긴 내용)
cmux set-buffer --name taskN -- "매우 긴 내용..."
cmux paste-buffer --name taskN --surface surface:N
cmux send-key --surface surface:N enter
```

**자가 교정**: Main이 "붙여넣", "전달해주", "입력해주", "복사해서" 표현을 생성하려 하면 → ⛔ STOP → cmux send로 교체.

### GATE 1: 과업 완료 GATE

```
⛔ WORKING surface가 1개라도 있으면 라운드 종료 금지.
⛔ IDLE이지만 "DONE" 키워드 미확인이면 완료 판정 금지. (IDLE ≠ 완료)
```

**IDLE 감지 시 확인 순서 (MANDATORY):**
```
1. cmux read-screen --surface surface:N --scrollback --lines 50
   → "DONE" 발견 → ✅ 완료

2. 미발견 → cmux read-screen --surface surface:N --lines 20
   → 진행 바(■), Working → ⏳ 대기
   → 에러 키워드 → ❌ 에러 → 재배정
   → 프롬프트만 보임 → scrollback 100줄로 확장

3. 그래도 없으면 → 그때만 재질문 (최후 수단)
```

**ERROR surface 재배정 (1단계 강제):**
1. `cmux read-screen --surface surface:{error} --lines 20` — 에러 원인 파악
2. 미완료 태스크 식별
3. `eagle.idle_surfaces` 확인
4. `cmux send --surface surface:{idle} "TASK: {에러 surface의 미완료 작업}"` — 재배정

⛔ "에러 surface 스킵하고 나머지로 진행" 금지

### GATE 2: 코드리뷰 위임 GATE

```
⛔ Main(Opus)이 직접 코드리뷰를 하면 안 된다.

→ Agent(subagent_type="code-reviewer", model="sonnet", run_in_background=true) 디스패치
→ Main은 결과만 읽고 APPROVE/REJECT 판단

예외: 서브에이전트가 3회 실패한 경우에만 Main 직접 리뷰 허용 (사유 기록 필수)
```

### GATE 3: 서브에이전트 사용 GATE

| 작업 | 필수 에이전트 | Main 직접 금지 |
|------|-------------|--------------|
| 코드리뷰 | Agent(code-reviewer, sonnet) | ⛔ |
| 코드리뷰 (보안) | Agent(code-reviewer, sonnet) | ⛔ |

### GATE 6: cmux 우선 위임 GATE (⛔ HARD — v7 신규)

```
⛔ cmux surface가 IDLE 상태이면, Agent 도구로 서브에이전트를 디스패치하는 것은 금지.
⛔ 반드시 cmux send로 해당 surface에 작업을 위임해야 한다.
```

**GATE 6 판정 로직:**
```python
# 매 작업 시작 전 자가 점검
idle_surfaces = [s for s in eagle_status if s["state"] == "IDLE"]
if len(idle_surfaces) > 0:
    # ⛔ 아래 Agent 호출 전부 금지:
    FORBIDDEN_AGENTS = [
        "Explore",           # → cmux send "탐색해줘"
        "general-purpose",   # → cmux send "작업해줘"
        "impl-worker",       # → cmux send "구현해줘"
        "search-worker",     # → cmux send "검색해줘"
        "debugger",          # → cmux send "디버깅해줘"
        "Plan",              # → cmux send "계획 세워줘"
        "frontend-engineer", # → cmux send "프론트엔드 구현해줘"
        "data-analyst",      # → cmux send "분석해줘"
    ]
    # ✅ 허용되는 Agent:
    ALLOWED_AGENTS = [
        "code-reviewer",     # 코드리뷰 (GATE 2 필수)
        "code-reviewer-pro", # 코드리뷰 (GATE 2 필수)
        "cmux-git",          # Git 작업 (haiku)
        "cmux-security",     # 보안 검사 (sonnet)
        "cmux-reviewer",     # cmux 전용 리뷰어
    ]
```

**GATE 6 위반 자가 교정:**
Main이 `Agent(subagent_type="Explore", ...)` 등을 호출하려 할 때:
1. ⛔ STOP — "GATE 6 위반: cmux surface에 위임해야 합니다"
2. IDLE surface 확인: `cat /tmp/cmux-eagle-status.json`
3. cmux send로 대체: 동일 작업을 cmux surface에 전송
4. Agent 호출 취소

**GATE 6 예외 (Agent 허용):**
- 모든 cmux surface가 WORKING 상태 (IDLE 0개)
- cmux 명령어 자체가 실패하는 경우 (cmux 미설치 등)
- 코드리뷰/보안검사 전용 에이전트 (ALLOWED_AGENTS)

### GATE 5: Speckit 태스크 완결성 GATE

```
⛔ speckit으로 분해한 태스크 중 1개라도 미완료이면 라운드 종료 금지.

MISSING = SPECKIT_TASKS - COMPLETED
if len(MISSING) > 0:
  → ⛔ BLOCKED — MISSING 태스크 재배정 필수
```

### GATE 7: 워크트리 강제 GATE

```
⛔ 2개+ surface에 동시 작업 배정 시, 워크트리 없이 cmux send로 작업 전송하면 GATE 위반.
```

**GATE 7 자가 점검 (매 배정 전):**
```python
active_surfaces = [s for s in surfaces if s.task == "pending"]
if len(active_surfaces) >= 2:
    worktrees = bash("git worktree list").count("/tmp/wt-")
    if worktrees < len(active_surfaces):
        # ⛔ BLOCKED — 워크트리 먼저 생성
        raise GateViolation("GATE 7: 워크트리 없이 2+ surface 배정 금지")
```

**강제 수단:**
- Phase 2 (초기 분배) 진입 전 `git worktree list` 실행 필수
- 워크트리 개수 < 배정 surface 수 → ⛔ 배정 차단
- 프롬프트에 `/tmp/wt-*` 경로 없으면 → ⛔ 배정 차단

### GATE 4: 라운드 종료 자가 점검 체크리스트

```
□ GATE 1: 모든 surface DONE 확인 (WORKING/미확인 없음)
□ GATE 2: 코드리뷰 서브에이전트 위임 (Main 직접 리뷰 0건)
□ GATE 3: 서브에이전트 사용 규칙 준수
□ GATE 5: speckit 태스크 전체 완료 (미완료 0개 — 재배정 포함)
□ GATE 6: Agent 도구 오용 0건 (탐색/구현/조사 서브에이전트 디스패치 0건, 전부 cmux send)
□ GATE 7: 2+ surface 배정 시 워크트리 사용 확인 (git worktree list)
□ GATE 7b: 병합 완료 + 워크트리 정리 완료 (git worktree list에 /tmp/wt-* 0개)
□ 서브에이전트 리뷰 결과 수신 + REJECT 항목 수정
□ 커밋 실행

하나라도 □(미체크)이면 → ⛔ 라운드 종료 금지.
```

## Quick Start — 세션 시작 절차

### Phase -1: 온보딩 (최초 1회 또는 설정 변경 시)

> See references/onboarding-detail.md for full onboarding procedure

```bash
# Step 0: 기존 설정 확인
cat ${SKILL_DIR}/config/orchestra-config.json  # 있으면 재사용 여부 질문

# Step 1: surface 감지
cmux tree --all
cmux identify

# Step 0.5: 이벤트 훅 등록
cmux set-hook after-send-keys "bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once > /dev/null 2>&1 &"
```

### Phase 0: Eagle Watcher 시작

```bash
pkill -f eagle_watcher.sh 2>/dev/null
bash ${SKILL_DIR}/scripts/eagle_watcher.sh &
bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once

# 상태 확인
cat /tmp/cmux-eagle-status.json
cmux surface-health
```

> See references/eagle-patterns.md for Eagle Watcher 상세 패턴

### Phase 1: 계획 수립 + 작업 큐 생성

**계획 파이프라인 자동 선택 (우선순위):**
1. speckit 라인 (specify→plan→tasks) — 가장 체계적
2. writing-plans + executing-plans — Superpowers 공식
3. brainstorming → writing-plans — Superpowers 기본
4. Main 직접 계획 — 스킬 없을 때 fallback

**작업 큐 형식:**
```python
WORK_QUEUE = [
    {"id": 1, "task": "...", "target": "surface:1", "status": "pending"},
    {"id": 2, "task": "...", "target": "surface:2", "status": "pending"},
    ...
]
```

**작업 크기 최소 기준 (CRITICAL):**
- 함수 1개 같은 초소형 작업 금지 → **최소 파일 1개 전체 또는 기능 1개 완성**
- 각 AI에 **3-10분 분량** 배정
- OpenCode/Codex: 파일 분석 + 여러 함수 + 테스트를 한 묶음으로
- Gemini: 조사 + 레퍼런스 + 분석 보고서를 한 묶음으로
- GLM: 독립 파일 생성 (레퍼런스, 설정, 스크립트) 한 묶음으로

> See references/dispatch-templates.md for 태스크→큐 변환 프로토콜 + ClawTeam DAG

### Phase 2: 초기 분배

**⚠️ CRITICAL 3단계: GATE 7 워크트리 → DONE 확인 → /new → 새 작업.**

```bash
# 0. GATE 7 워크트리 사전 점검 (2+ surface 배정 시 MANDATORY)
ACTIVE_COUNT=$(echo "$WORK_QUEUE" | grep -c "pending")
if [ "$ACTIVE_COUNT" -ge 2 ]; then
    ROUND="r$(date +%H%M)"
    PROJECT="프로젝트 절대경로"
    for SURFACE in codex glm1 glm2 minimax; do
        git -C "$PROJECT" worktree add "/tmp/wt-${SURFACE}-${ROUND}" -b "${SURFACE}-${ROUND}" HEAD 2>/dev/null
    done
    git worktree list  # 확인
    # 프롬프트에 반드시 /tmp/wt-${SURFACE}-${ROUND} 경로 포함
fi

# 1. DONE 확인 (이전 작업 완료 여부)
cmux read-screen --workspace "workspace:N" --surface surface:N --lines 3
# → "DONE" 포함 확인. 없으면 STOP.

# 2. 컨텍스트 초기화 + 워크트리 cd + 작업 전송
cmux send --workspace "workspace:N" --surface surface:N "/new"  # Codex/GLM: /new, Gemini: /clear
cmux send-key --workspace "workspace:N" --surface surface:N enter
sleep 3
# 2b. 워크트리 절대경로를 프롬프트에 포함 (GATE 7 — cd는 작동 안 함!)
# ⛔ cmux send "cd /path" 금지 — AI 채팅에서 CWD 변경 불가
# ✅ 프롬프트에 절대경로 명시 + /new 후 단일 메시지로 전체 지시사항 전송
WT="/tmp/wt-SURFACE-ROUND/System/10_Projects/PROJECT"
cmux send --workspace "workspace:N" --surface surface:N "TASK: {작업 설명}

[작업 경로] 프로젝트 루트: ${WT}. 모든 파일은 ${WT}/ 하위에서만读写.
⛔ ~/Ai/System/ 직접 수정 금지. ⛔ 서브에이전트/Agent 금지. ⛔ git 금지.
완료 후: 요약 → 빈줄5개 → DONE → 빈줄2개 → DONE"
cmux send-key --workspace "workspace:N" --surface surface:N enter

# 3. 10초 후 시작 확인 (MANDATORY)
sleep 10
cmux read-screen --workspace "workspace:N" --surface surface:N --lines 5
```

**멈춤/에러 복구:**
```bash
# surface가 멈춘 경우 (5분+ 변화 없음)
cmux send-key --workspace "workspace:N" --surface surface:N escape   # 현재 작업 취소
sleep 2
cmux send --workspace "workspace:N" --surface surface:N "/clear"     # 컨텍스트 초기화
cmux send-key --workspace "workspace:N" --surface surface:N enter
sleep 3
# 재배정 (기존 작업 내용은 이미 파일에 저장되어 있으므로 유실 없음)
cmux send --workspace "workspace:N" --surface surface:N "TASK: {재배정 프롬프트}" && cmux send-key --workspace "workspace:N" --surface surface:N enter
```

### Phase 3: Watch + 병합 + 재위임 루프

> See references/worktree-workflow.md for 상세 병합 + 충돌 해결

```
2분 폴링 루프:
1. 전 surface read-screen --lines 3 → DONE/WORKING/RATE_LIMITED 분류
2. DONE surface → 워크트리 검증(pytest+tsc) → Main이 diff 판단 → merge 또는 reject
3. 병합 후 메인에서 최종 pytest+tsc
4. DONE surface 워크트리 정리 → 새 워크트리 생성 → 다음 작업 재배정
5. 멈춘 surface → 섹션 10 패턴으로 개입
6. Main은 대기 X — 코드리뷰/계획 병행
```

### Phase 4: 장애 대응

> See references/error-recovery.md for 에러 복구 프로토콜

**빠른 복구:**
```bash
# 컨텍스트 초과
cmux send --workspace "workspace:N" --surface surface:N "/new" && cmux send-key --workspace "workspace:N" --surface surface:N enter
# 완전 장애
cmux send --workspace "workspace:N" --surface surface:N "/quit" && cmux send-key --workspace "workspace:N" --surface surface:N enter && sleep 3
cmux send --workspace "workspace:N" --surface surface:N "codex" && cmux send-key --workspace "workspace:N" --surface surface:N enter
```

## ⛔ GATE 8: --workspace 필수 GATE

> See references/workspace-gate.md for 상세 설명 + 예시

**핵심 3줄:**
```
⛔ 다른 workspace surface 접근 시 --workspace 필수.
⛔ workspace:1만 --workspace 생략 가능 (현재 workspace).
✅ cmux send/read-screen/send-key/paste-buffer 전부 --workspace 명시.
```

## 핵심 cmux 명령어 (Quick Reference)

```bash
# 환경 파악
cmux tree --all
cmux identify
cmux surface-health

# 작업 전송 (--workspace 필수!)
cmux send --workspace "workspace:N" --surface "surface:N" "내용"
cmux send-key --workspace "workspace:N" --surface "surface:N" enter

# 화면 확인 (--workspace 필수!)
cmux read-screen --workspace "workspace:N" --surface "surface:N" --lines 20
cmux read-screen --workspace "workspace:N" --surface "surface:N" --scrollback --lines 80

# 상태 확인
cat /tmp/cmux-eagle-status.json

# 알림
cmux notify --title "완료" --body "내용"

# 버퍼 (200자+ 전송 시, --workspace 필수!)
cmux set-buffer --name task1 -- "긴 내용..."
cmux paste-buffer --name task1 --workspace "workspace:N" --surface "surface:N"
cmux send-key --workspace "workspace:N" --surface "surface:N" enter
```

> See references/cmux-commands-full.md for 전체 85개 명령어 레퍼런스

## "다음 라운드" 프로토콜 (MANDATORY)

```
Step 0: cmux 공식 기능 자동 활성화 (라운드 시작 시 1회)
  ├── cmux set-hook after-send-keys "bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once > /dev/null 2>&1 &"
  ├── cmux surface-health
  └── python3 ${SKILL_DIR}/scripts/speckit-tracker.py --init "Round N"

Step 1: 조사 — 각 AI surface에 조사 주제 배포
  방법 A (search_executor.py 있는 경우):
    cmux send --surface surface:N "python3 search_executor.py --query '주제' --full --outdir /tmp/rN_topic"
  방법 B (범용):
    cmux send --surface surface:N "다음 주제를 조사해줘: {주제}. [Footer Template 붙여서 전송]"

Step 1.5: speckit 태스크 분해 — Skill("speckit-tasks") 호출 (MANDATORY)

Step 2: A/B 테스트 — 현재 구성 vs 개선안

Step 3: 채택 — 더 나은 결과를 채택

Step 4: 리뷰 — 코드 완료 즉시 서브에이전트 코드리뷰 (MANDATORY)
  ├── Agent(subagent_type="code-reviewer", model="sonnet") 백그라운드 디스패치

Step 5: 커밋 — Main이 판단 후 실행 (MANDATORY — 생략 금지!)

Step 6: 자가개선 — 리뷰 이슈 수정 + SKILL.md 업데이트
```

**핵심 규칙:**
1. 조사는 **반드시 cmux surface에 위임** (Main 직접 안 함)
2. **speckit 스킬을 실제로 호출**하여 태스크 분해 (수동 분해 금지)
3. **코드 완료 즉시** 서브에이전트 코드리뷰 디스패치
4. **리뷰 통과 후 반드시 커밋** — 커밋 없이 라운드 종료 금지

## 529 API 안전 규칙

> See references/circuit-breaker.md for 상세 Circuit Breaker 패턴

**핵심 규칙:**
- **서브에이전트 총합 2개 이하** (Main 포함 총 3개)
- **cmux send는 API 0원** — 가장 안전한 위임 방법
- 529 발생 시: 5초 → 15초 → 60초 대기 + 에이전트 수 감소
- Circuit Breaker: 2회 실패 → OPEN (60초) → HALF-OPEN (테스트 1개) → CLOSED

```
✅ 최안전: cmux send 4개 (0 API) + Main(Opus) = Opus 1개만
✅ 안전:   cmuxeagle(haiku) + Main(Opus) = API 2개
⚠️ 주의:   cmuxreview(Sonnet) + Main(Opus) = 2개
❌ 금지:   3개+ Opus/Sonnet 서브에이전트 동시
```

## 전용 에이전트 요약

| 컴포넌트 | 모델/비용 | 역할 |
|---------|----------|------|
| **eagle_watcher.sh** | **API 0원** | 20초 자동 폴링 → JSON 상태 파일 |
| **cmuxeagle** | haiku | 상태 판단 + cmux send 작업 전달 |
| **cmuxreview** | **Sonnet** | 코드 리뷰 (code-reviewer-pro) |
| **cmuxgit** | haiku | 커밋/푸시 (git-workflow-manager) |
| **cmuxplanner** | sonnet | 작업 큐 생성 (태스크 분해) |
| **cmuxdiagnostic** | haiku | 사전 검증 (테스트 실행) |

> See references/subagent-definitions.md for 상세 에이전트 정의 + 스킬 최적화

## Hook 시스템 — 6개 자동 연동

| Hook | 이벤트 | 스크립트 | 역할 |
|------|--------|---------|------|
| **SessionStart** | 세션 시작 | cmux-orchestra-enforcer.sh | 설정 파일 확인 → 온보딩 질문 |
| **SessionStart** | 세션 시작 | cmux-claude-bridge.sh session-start | cmux 사이드바 "Running" 표시 |
| **UserPromptSubmit** | 매 메시지 | cmux-idle-reminder.sh | IDLE surface 자동 알림 |
| **Stop** | 세션 종료 | cmux-claude-bridge.sh stop | cmux 사이드바 "Idle" 표시 |
| **PostToolUse** | 도구 사용 후 | cmux-claude-bridge.sh post-tool | Agent 완료 시 cmux 알림 |
| **Notification** | 알림 | cmux-claude-bridge.sh notification | cmux 알림 패널 전달 |

## 완주 보장 사이클

```
사용자 요청 수신
  ↓
Phase -1: 온보딩 (설정 파일 확인)
  ↓
Phase 0: eagle 부트 + surface 확인
  ↓
Phase 1: 작업 분해 + 작업 큐 생성
  ↓
Phase 2: cmux send로 각 surface에 배포
  ↓ (eagle로 완료 감지)
Phase 3: 결과 수집 + Main이 결과 취합 + 구현 계획
  ↓
Phase 4: 구현 (Main 직접 + 병렬 가능한 것은 cmux 위임)
  ↓
Phase 5: 테스트 + 코드리뷰 (cmuxreview Sonnet)
  ↓
Phase 6: 커밋
  ↓
사용자에게 완료 보고
```

## 금지사항

### 절대 금지 (위반 시 사용자 화남)
❌ **"별도 세션에서 진행"** — cmux가 있으므로 이유 없음. 즉시 완주.
❌ **"나중에 구현"** — 조사 결과 있으면 바로 구현.
❌ **놀고 있는 AI 방치** — eagle이 IDLE 감지하면 즉시 작업 전달.
❌ **"붙여넣어주세요"** — cmux send로 직접 전송.

### 기술적 금지
❌ Codex MCP 직접 호출 — cmux send로 Codex 창에 전송
❌ cmuxreview에 Opus 사용 — Sonnet만 (529 방지)
❌ 서브에이전트 3개+ 동시 — Circuit Breaker 발동
❌ 조사 요청 시 raw search-worker 직접 디스패치 — Skill("search-orchestration") 경유
❌ 장애 AI 방치 — 설정 파일의 quit_cmd/start_cmd로 즉시 복구

### ⛔ GATE 6 위반 금지 (v7 신규 — 가장 심각한 오류)
❌ **IDLE cmux surface가 있는데 Agent(Explore) 디스패치** — cmux send로 탐색 위임
❌ **IDLE cmux surface가 있는데 Agent(impl-worker) 디스패치** — cmux send로 구현 위임
❌ **IDLE cmux surface가 있는데 Agent(search-worker) 디스패치** — cmux send로 조사 위임
❌ **IDLE cmux surface가 있는데 Agent(general-purpose) 디스패치** — cmux send로 범용 작업 위임
❌ **Main이 직접 Read/Grep/Glob으로 대량 파일 탐색** — cmux surface에 탐색 위임
❌ **Main이 직접 Edit/Write로 100줄+ 코드 작성** — cmux surface에 구현 위임
❌ **speckit으로 분해 후 서브에이전트에 구현 위임** — cmux surface에 구현 위임

**핵심**: cmux surface = API 0원 + 별도 컨텍스트. 서브에이전트 = API 비용 + 529 위험 + Main 컨텍스트 소모.
cmux surface가 있으면 **항상** cmux send가 더 나은 선택.

## 자동 트리거

1. `$CMUX_WORKSPACE_ID` 존재 + surface 2개+
2. 사용자가 "병렬", "동시에", "부하", "cmux" 키워드
3. Agent Team Forge 트리거 시 cmux도 동시 활용
4. SessionStart hook이 additionalContext 주입


---

## Failure Recovery & Self-Improvement

> **참조**: `System/11_Modules/enforcement-mechanisms/README.md` (강제력 4단계)
> **패턴**: Karpathy autoresearch (modify → verify → keep/discard → repeat)

### 실패 시 자동 행동

| 실패 유형 | 자동 행동 |
|-----------|-----------|
| 스크립트 실행 에러 | 에러 메시지 분석 → 의존성 확인 → 재시도 (최대 2회) |
| 품질 기준 미달 | autoresearch 루프: 수정→검증→채택/폐기 (최대 3 iteration) |
| MCP/외부 도구 미연결 | fallback 경로 시도 → 실패 시 사용자 보고 |
| 파이프라인 단계 중단 | `/tmp/sdd-failure-stats.jsonl`에 기록 → 2회+ 시 [AUTO-HEAL] 트리거 |

### 강제력 수준

| 규칙 | 레벨 | 메커니즘 |
|------|------|---------|
| 필수 출력 형식 | L2 (경고) | PostToolUse systemMessage |
| 품질 점수 미달 | L3 (프롬프트) | SKILL.md 지침 |
| 파괴적 명령 보호 | L0 (차단) | defense-in-depth.py |

### Autoresearch 자가개선 루프

이 스킬이 2회+ 실패하면 `skill-pipeline-healer.sh`가 `[AUTO-HEAL]`을 주입한다.
메인 AI는 현재 작업 완료 후 1F2 Mode C를 자동 실행하여:
1. 실패 로그 분석 (`/tmp/sdd-failure-stats.jsonl`)
2. 이 SKILL.md의 누락된 가이드/패턴 보강
3. 필요 시 L0-L2 Hook 생성 (enforcement-mechanisms 템플릿 사용)
4. `diagnose.py --json`으로 수정 검증

---

## Agent Memory (자동 학습)

오케스트레이션 중 발생하는 이벤트를 자동 기록하여 축적. Main이 의사결정 시 참조.

### 자동 기록 (cmux-memory-recorder.sh)
- dispatch (cmux send/set-buffer/paste-buffer), 부서 생성/해제, 제어탑 재정렬 이벤트
- `~/.claude/memory/cmux/journal.jsonl`에 JSONL 형식으로 저장
- 5MB 초과 시 기록 스킵 (drain으로 rotation)

### CLI (agent-memory.sh)
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/agent-memory.sh drain       # 저널 → memories.json
bash ~/.claude/skills/cmux-orchestrator/scripts/agent-memory.sh query <kw>  # 메모리 검색
bash ~/.claude/skills/cmux-orchestrator/scripts/agent-memory.sh stats       # 통계
bash ~/.claude/skills/cmux-orchestrator/scripts/agent-memory.sh --self-test # 내장 테스트
```

### /cmux 시 자동 inject
Main이 `/cmux` 입력 시 cmux-main-context.sh가 자동으로:
1. 와쳐 캐시 (surface 상태)
2. AI traits (sandbox, short_prompt, two_phase_send)
3. 최근 학습 메모리 (최대 10건 요약)

을 context에 주입하여 Main의 의사결정을 보조.
