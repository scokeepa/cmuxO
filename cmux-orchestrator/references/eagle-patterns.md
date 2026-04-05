# Eagle Watcher 상세 패턴

## Persistent Eagle Watcher 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Opus (Main Orchestrator)                  │
│  역할: 코드리뷰, 설계판단, 작업큐관리, 커밋                 │
│  금지: 직접 코딩, 수동 폴링                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────┐                       │
│  │   eagle_watcher.sh (bash)        │ ← 20초 자동 폴링     │
│  │   API 비용: 0원 (순수 bash)      │   /tmp/cmux-eagle-    │
│  │   모든 surface 상태 → JSON 파일   │   status.json        │
│  └──────────────────────────────────┘                       │
│           ↓ 읽기                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │cmuxeagle │  │cmuxreview│  │ cmuxgit  │                  │
│  │ (haiku)  │  │(Opus상속)│  │ (haiku)  │                  │
│  │ 판단+전달│  │ 코드리뷰 │  │ 커밋/푸시│                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ surface:1│  │ surface:2│  │ surface:3│  │ surface:5│   │
│  │  Claude  │  │  Claude  │  │  Codex   │  │  Gemini  │   │
│  │  팀원    │  │  팀원    │  │  팀원    │  │  팀원    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Layer 1: eagle_watcher.sh 기본 사용

**역할**: 20초마다 모든 surface를 폴링, JSON 상태 파일에 기록.
**API 비용**: 0원 (순수 bash + cmux 명령)
**위치**: `skills/cmux-orchestrator/scripts/eagle_watcher.sh`

```bash
# 백그라운드 시작 (세션 시작 시 1회)
# ⚠️ nohup 금지 — cmux 세션 내부에서만 작동
pkill -f eagle_watcher.sh 2>/dev/null
bash ${SKILL_DIR}/scripts/eagle_watcher.sh &
bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once

# 상태 파일 위치
cat /tmp/cmux-eagle-status.json
# → {"timestamp":"...","surfaces":{"1":{"status":"IDLE",...},...},
#    "idle_surfaces":"1 3","error_surfaces":"","waiting_surfaces":"5",
#    "stats":{"total":4,"idle":2,"working":1,"waiting":1}}
```

## 상태 종류 및 대응

| 상태 | 의미 | 즉시 대응 |
|------|------|---------|
| **WORKING** | 작업 실행 중 | 전송 금지, 대기 |
| **IDLE** | 대기 중 (프롬프트) | DONE 확인 후 새 작업 배정 |
| **WAITING** | 질문/확인 대기 | Main이 즉시 cmux send로 답변 |
| **ERROR** | 오류 발생 | 복구 조치 즉시 실행 |
| **UNKNOWN** | 상태 판별 불가 | 수동 확인 |

## WAITING 감지 시 즉시 대응 (MANDATORY)

WAITING surface는 사용자 입력을 기다리는 중 — Main이 cmux send로 즉시 답변해야 함.
방치하면 해당 surface가 영원히 대기 → IDLE=0 원칙 위반.

```bash
# WAITING 대응 예시
cmux read-screen --surface surface:N --lines 10  # 무엇을 묻고 있는지 확인
cmux send --surface surface:N "yes"               # 또는 적절한 답변
cmux send-key --surface surface:N enter
```

## 능동적 확인 프로토콜 (MANDATORY — eagle만으로는 부족!)

eagle_watcher는 20초 폴링이므로 실시간이 아님. Main이 **능동적으로** 확인해야 함.

```bash
# 1. 작업 디스패치 전 surface 상태 확인 (MANDATORY)
cmux read-screen --surface surface:N --lines 5
# → 프롬프트가 보이면 OK, 질문이 보이면 먼저 답변

# 2. 작업 디스패치 후 10초 뒤 시작 확인 (MANDATORY — 생략 금지)
sleep 10
for sid in surface:1 surface:2 surface:3 surface:5; do
  screen=$(cmux read-screen --surface $sid --lines 10)
  # WORKING 감지 (프로그래스 바, spinner, interrupt)
  if echo "$screen" | grep -qE "interrupt|⠋|⠙|■|⬝|Working|Baking"; then
    echo "$sid: ✅ WORKING"
  # IDLE 감지 (프롬프트 대기 = 작업 수신 실패)
  elif echo "$screen" | grep -qE "❯|bypass permissions|Type your message"; then
    echo "$sid: ⚠️ IDLE — 즉시 재전송 필요!"
    cmux send --surface $sid "위에 보낸 작업 실행해줘"
    cmux send-key --surface $sid enter
  # 질문 대기 (이전 세션 잔여)
  elif echo "$screen" | grep -qE "select|y/n|confirm|스프레드시트"; then
    echo "$sid: ⚠️ 잔여 프롬프트 — Esc + /new 후 재전송!"
    cmux send-key --surface $sid escape
    sleep 1 && cmux send --surface $sid "/new" && cmux send-key --surface $sid enter
  fi
done
```

## 멈춤 감지 체크리스트

1. eagle_watcher JSON에서 `waiting_surfaces` 확인
2. IDLE 시간이 60초+ → `cmux read-screen`으로 원인 파악
3. 질문 대기 → 즉시 `cmux send`로 답변
4. 에러 → `cmux send --surface surface:N "{reset_cmd}"`로 복구
5. 정상 IDLE → 다음 작업 즉시 배정

## cmux 공식 모니터링 명령어

| 명령어 | 용도 | 사용 시점 |
|--------|------|----------|
| `cmux surface-health` | surface 건강 상태 | 세션 시작 시, 주기적 |
| `cmux read-screen --lines N` | 화면 내용 직접 확인 | 작업 전후, 멈춤 의심 시 |
| `cmux set-hook <event> <cmd>` | 이벤트 기반 훅 등록 | 세션 시작 시 1회 |
| `cmux claude-hook idle` | surface IDLE 신호 | Claude Code 연동 시 |
| `cmux claude-hook active` | surface 활성 신호 | Claude Code 연동 시 |
| `cmux trigger-flash` | 시각적 플래시 알림 | 주의 필요 시 |
| `cmux notify` | 알림 전송 | 작업 완료/에러 시 |

## Layer 2: cmuxeagle (haiku) — 판단 + 작업 전달

```
Agent(subagent_type="general-purpose", model="haiku", name="cmuxeagle",
  run_in_background=true, prompt="""
  You are cmuxeagle — task dispatcher for IDLE surfaces.

  INPUT: work_queue (JSON), status_file path

  PROCEDURE:
  1. Read /tmp/cmux-eagle-status.json
  2. Find IDLE surfaces
  3. For each IDLE surface with pending work:
     a. cmux send --surface surface:N "TASK: {work_item}"
     b. cmux send-key --surface surface:N enter
     c. sleep 3 (cooldown between sends)
  4. Report dispatched tasks to main

  RULES:
  - NEVER send to WORKING surface (overwrites previous task)
  - NEVER send to ERROR surface (fix first)
  - 3 second gap between sends
  - Report: {"dispatched":[{"surface":"N","task_id":X}],"skipped_working":["N"]}
""")
```

## 529 안전 분석 — Eagle가 안전한 이유

```
Haiku eagle 감시자 = bash(cmux read-screen) + Haiku 1회 판단
  ├── cmux read-screen × 4 surfaces = bash 명령 4회 (API 0원)
  ├── Haiku 에이전트 = Anthropic API 1회 (Haiku, 별도 rate limit)
  ├── Main Opus = API 1회 (eagle 결과 처리)
  └── 총: Haiku 1 + Opus 1 = 동시 API 2개 (529 임계치 이하)
```

| 컴포넌트 | API 종류 | 동시 수 | 529 위험 |
|---------|---------|---------|---------|
| eagle_watcher.sh | 없음 (bash) | 1 | 없음 |
| cmuxeagle | Haiku API | 1 | 없음 (별도 rate limit) |
| cmuxreview | Opus API | 1 | 낮음 (Main과 동시 최대 2) |
| Main | Opus API | 1 | 기본 |
| cmux send 대상 | 외부 AI | 4 | 없음 (Anthropic 아님) |
| **총 동시 API** | | **최대 3** | **안전** |

## Persistent Watcher 운영 플로우

```
1. 세션 시작 → eagle_watcher.sh 백그라운드 실행
2. Main이 작업 큐 생성 (WORK_QUEUE JSON)
3. Main이 cmuxeagle(haiku) 디스패치:
   - "이 작업 큐를 IDLE surface들에 분배해"
   - eagle는 상태 파일 읽고 → cmux send로 전달
4. Main은 코드리뷰/설계 작업에 집중
5. 20초 후: eagle_watcher.sh가 상태 갱신
6. Main이 cat /tmp/cmux-eagle-status.json 읽기 (bash 1회)
7. IDLE surface 발견 → 새 cmuxeagle 디스패치 (작업 큐의 다음 항목)
8. 반복
```

## Phase 3: Persistent Watch + 즉시 재위임 루프

```python
# 메인이 반복하는 루프 (20초 간격)
while work_queue_has_items:
    # 1. 상태 확인 (bash 1회, API 0원)
    status = bash("cat /tmp/cmux-eagle-status.json")

    # 2. IDLE surface 발견?
    idle_surfaces = status["idle_surfaces"]

    if idle_surfaces:
        # 3. git diff 확인 (이전 작업 결과물 있는지)
        for surface in idle_surfaces:
            diff = bash("git diff HEAD")
            if diff:
                # 4. cmuxreview에 리뷰 요청 (Opus 1회)
                review = Agent("code-reviewer-pro", "review git diff")
                if review == "APPROVE":
                    commit()
                else:
                    fix_issues()

        # 5. cmuxeagle(haiku)로 다음 작업 전달
        Agent(model="haiku", name="cmuxeagle", prompt=f"""
          Read /tmp/cmux-eagle-status.json.
          IDLE surfaces: {idle_surfaces}
          Send these tasks via cmux send:
          {next_tasks_from_queue}
        """)

    # 6. 메인은 코드리뷰/설계 작업 진행 (대기 X)
    do_code_review_or_planning()

    # 7. 20초 후 다시 상태 확인 (eagle_watcher.sh가 자동 갱신)
```

**핵심: 메인이 절대 "가만히 대기"하지 않음. 상태 확인 → 리뷰 → 전달 → 다른 작업 → 반복.**
