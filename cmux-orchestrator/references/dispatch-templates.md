# 디스패치 템플릿 및 ClawTeam DAG

## 태스크→큐 변환 프로토콜 (MANDATORY)

speckit-tasks가 생성한 태스크를 cmux 작업 큐로 변환하는 구체적 절차:

```
Step 1: 태스크 분류 — 난이도 + 파일 스코프 판정
  각 태스크에 대해:
  ├── 난이도: 상급/중상급 → Codex surface
  ├── 난이도: 중급/중하급 → GLM/Gemini surface (라운드로빈)
  └── 파일 스코프: 1 태스크 = 1 surface (파일 겹침 금지)

Step 2: 의존성 기반 Wave 분할
  ├── Wave 1: 독립 태스크들 (병렬 실행)
  ├── Wave 2: Wave 1 결과에 의존하는 태스크들
  └── Wave N: 통합/리뷰 태스크

Step 3: 컨텍스트 초기화 + cmux send 디스패치 (MANDATORY)
  각 surface에 작업 배정 전 반드시 초기화:
  1. cmux send --surface surface:N "{reset_cmd}"  # /new(Codex/GLM) 또는 /clear(Gemini)
  2. cmux send-key --surface surface:N enter
  3. sleep 3  # 초기화 대기
  4. cmux send --surface surface:N "다음 N가지 작업을 순서대로 수행해줘: (1) ... (2) ... 완료 후 DONE:"
  5. cmux send-key --surface surface:N enter
```

## MEMBER REQUEST 패턴 (팀장 → Main 팀원 요청)

팀장이 팀원을 요청할 때 출력하는 약속된 포맷:

```
MEMBER REQUEST: 팀원 N명 필요
- high: [작업 설명]
- medium: [작업 설명]
- low: [작업 설명]
```

예시:
```
MEMBER REQUEST: 팀원 2명 필요
- high: JWT 검증 로직 구현 (jsonwebtoken 사용)
- low: 환경 설정 파일 정리 (.env 템플릿)
```

Main이 팀장에게 업무 지시 시 반드시 포함:
> "팀원이 필요하면 'MEMBER REQUEST:' 로 시작하는 요청을 출력해. Main이 팀원을 생성해줄게."

Watcher가 eagle 스캔 시 각 팀장 surface 출력에서 `MEMBER REQUEST:` 패턴 감지 → Main에 보고.

---

## 공유 스킬 컨텍스트 주입 (MANDATORY)

Worker AI(MiniMax, Codex, GLM)는 Claude Code 스킬 시스템을 읽을 수 없다.
Main이 dispatch 시 **스킬 컨텍스트를 자연어로 프롬프트에 포함**하여 전송한다.

### 공통 스킬 블록 (모든 AI 공통)

모든 dispatch 프롬프트의 마지막에 아래 블록을 포함:

```
[SKILL CONTEXT — 공통 규칙]
- git worktree 사용: 충돌 방지를 위해 워크트리에서 작업
- 결과 보고: 절대 경로로 수정한 파일 목록 출력
- 완료 신호: 작업 끝나면 반드시 "DONE: 요약" 출력
- 에러 시: "DONE: ERROR — 에러 내용" 출력
- git commit 금지: 커밋은 Main만 수행
- 서브에이전트/하위 AI 호출 금지: 직접 작업만
- LSP/플러그인 설치 질문 → No 선택
```

### AI별 스킬 프리셋

dispatch 시 Worker AI 종류에 따라 추가 컨텍스트를 포함:

**MiniMax (difficulty: high)**
```
[SKILL — MiniMax]
- 장문 분석/구현 가능, 복합 작업 한 번에 전송 OK
- 코드 + 설명 함께 작성
- 파일 여러 개 동시 수정 가능
```

**Codex (difficulty: high)**
```
[SKILL — Codex]
- sandbox 모드: cmux CLI 직접 실행 불가
- cmux 관련 작업 배정 금지
- 코드 구현 + 분석 전문
- /quit으로 종료, /new로 초기화
```

**GLM (difficulty: low)**
```
[SKILL — GLM]
- 프롬프트 200자 이내 권장 (긴 입력 시 품질 저하)
- 단순/반복 작업에 적합
- 한 번에 1개 파일 작업 권장
- /quit으로 종료, /new로 초기화
```

### 디스패치 예시 (스킬 컨텍스트 포함)

```bash
cmux set-buffer --surface surface:3 "TASK: src/api/auth.ts에 JWT 검증 미들웨어 구현
- access token 검증
- refresh token 갱신
- 에러 핸들링 (401, 403)

[SKILL CONTEXT — 공통 규칙]
- git worktree 사용: 충돌 방지를 위해 워크트리에서 작업
- 결과 보고: 절대 경로로 수정한 파일 목록 출력
- 완료 신호: 작업 끝나면 반드시 DONE: 요약 출력
- git commit 금지: 커밋은 Main만 수행

[SKILL — MiniMax]
- 파일 여러 개 동시 수정 가능"

cmux paste-buffer --surface surface:3
cmux send-key --surface surface:3 Enter
```

> **원칙**: 스킬 컨텍스트는 자연어이므로 어떤 AI든 이해할 수 있다.
> Main의 SKILL.md에 있는 규칙 중 Worker에게 공유해야 할 것만 추출하여 전달.

---

## AI별 특수 사항

### Gemini 2-Phase 전송 (필수)
Gemini는 /clear와 작업을 **같은 cmux send로 보내면 안 됨** (한 줄로 합쳐져서 실패)

```bash
# Phase 1: 초기화
cmux send --surface surface:N "/clear"
cmux send-key --surface surface:N enter
sleep 4

# Phase 2: 작업 전송
cmux send --surface surface:N "작업 내용"
sleep 1
cmux send-key --surface surface:N enter
```

### Codex 제약사항
- Codex sandbox 모드에서는 cmux CLI 직접 실행 불가 (소켓 접근 차단)
- cmux 관련 작업은 Codex에 배정 금지 → Claude Code 또는 Gemini surface에 배정
- Codex는 코드 구현 + 분析만 담당

## 과업 완료 수집 체크리스트 (MANDATORY — Step 4)

### 4-1. 과업 체크리스트 생성 (디스패치 시점에 작성)

```
TASK_CHECKLIST:
  S1:  [ ] 2개 번들 — cmux 검증 + hook 확인
  S3:  [ ] 4개 번들 — orchestrator + embedding + qa + 검증
  S5:  [ ] 2개 번들 — 디자인 리뷰 + 스타일 분석
  S10: [ ] 2개 번들 — publish_utils + 에러 핸들링
```

### 4-2. 주기적 수집 루프

```bash
# 30초마다 전 surface 스캔
for sid in $(registered surface IDs); do
  STATUS=$(eagle_watcher → surface status)
  if STATUS == "IDLE" and CHECKLIST[$sid] == unchecked:
    RESULT=$(cmux read-screen --surface surface:$sid --lines 30)
    if RESULT contains "DONE:":
      CHECKLIST[$sid] = ✅ (성공)
    elif RESULT contains "error|Error|ERROR|timeout|1008|429|529":
      CHECKLIST[$sid] = ❌ (에러) → 에러 분류 후 재배정 또는 스킵
    else:
      CHECKLIST[$sid] = ⚠️ (확인 필요)
    fi
  fi
done
```

### 4-3. 에러 감지 시 즉시 대응

| 에러 유형 | 감지 키워드 | 대응 |
|----------|-----------|------|
| API 타임아웃 | `timeout`, `TIMEOUT`, `API_TIMEOUT_MS` | 작업 축소 후 재배정 |
| 잔액 부족 | `1008`, `insufficient_balance` | 해당 AI 스킵, 다른 surface에 재배정 |
| 권한 거부 | `Operation not permitted`, `sandbox` | Main 직접 처리 |
| 컨텍스트 초과 | `context`, `exceed`, `too long` | /new 또는 /clear → 작업 분할 재배정 |
| 완전 멈춤 | 60초+ IDLE but no DONE | read-screen → 원인 파악 → 재배정 |

### 4-4. HARD GATE 0 — 전체 수집 완료 확인

```
dispatched = [surface:1, surface:2, ...]  # 디스패치한 surface 목록
CHECKLIST = {}
for attempt in range(5):  # 최대 5회 polling (60초 간격)
    for sid in dispatched:
        screen = cmux read-screen --surface {sid} --scrollback --lines 80
        if "DONE:" in screen:
            CHECKLIST[sid] = "✅"
        elif ERROR_PATTERN in screen:
            CHECKLIST[sid] = "❌-error"
            → 다른 surface에 재배정 또는 Main 직접 처리
        else:
            CHECKLIST[sid] = "⏳-waiting"

    ALL_DONE = all(v != "⏳-waiting" for v in CHECKLIST.values())
    if ALL_DONE: break

    pending = [sid for sid, v in CHECKLIST.items() if v == "⏳-waiting"]
    log(f"⏳ {len(pending)}개 surface 대기 중: {pending}")
    sleep(60)

# 최종 검증
assert all(v in ["✅", "❌-handled"] for v in CHECKLIST.values()), \
    "HARD GATE 0 위반: 미수집 surface 존재"
```

## ClawTeam 하이브리드 모드 — Task DAG Autopilot (v7)

> **설치 경로**: `~/bin/clawteam` → `~/.venv/bin/clawteam`
> 미설치 시: `pip install clawteam`
> **핵심**: ClawTeam의 **spawn/inbox는 사용하지 않는다**. task board(의존성 DAG + 자동 unblock)만 사용.

### 왜 필요한가

| 기존 (Phase 1~3) | 하이브리드 (Task DAG) |
|---|---|
| Opus가 수동으로 Wave 순서 관리 | ClawTeam이 `--blocked-by` 기반 자동 unblock |
| IDLE 감지 → Opus가 직접 다음 작업 판단 | unblock된 태스크를 idle surface에 자동 매칭 |
| CHECKLIST를 세션 메모리로 유지 | `.clawteam/` 파일로 영속 (세션 종료 후에도 유지) |
| Wave 단위 배치 (전부 끝나야 다음) | **태스크 단위 즉시 진행** (T1 끝나면 T2 바로 시작) |

### Phase 1: speckit → ClawTeam DAG 변환

```bash
# 0. ClawTeam 사용 가능 여부 확인
if ! command -v clawteam &>/dev/null; then
  echo "ClawTeam 미설치 → 기존 WORK_QUEUE 방식 사용"
fi

# 1. 프로젝트 보드 생성
clawteam team spawn-team proj-$(date +%H%M)
PROJ="proj-$(date +%H%M)"

# 2. 태스크 등록 (speckit-tasks 결과 기반)
T1_OUT=$(clawteam task create $PROJ "아키텍처 설계 + 데이터 모델" -o opus 2>&1)
T1_ID=$(echo "$T1_OUT" | grep "Task created:" | awk '{print $NF}')

T2_OUT=$(clawteam task create $PROJ "백엔드 API 구현 (JWT, CRUD)" -o surface:2 --blocked-by "$T1_ID" 2>&1)
T2_ID=$(echo "$T2_OUT" | grep "Task created:" | awk '{print $NF}')

T3_OUT=$(clawteam task create $PROJ "프론트엔드 UI 구현" -o surface:3 --blocked-by "$T1_ID" 2>&1)
T3_ID=$(echo "$T3_OUT" | grep "Task created:" | awk '{print $NF}')

T5_OUT=$(clawteam task create $PROJ "통합 테스트 작성" -o surface:2 --blocked-by "$T2_ID,$T3_ID" 2>&1)
T5_ID=$(echo "$T5_OUT" | grep "Task created:" | awk '{print $NF}')

# 3. 보드 확인
clawteam board show $PROJ
```

### Phase 2: 자동 디스패치 시작

```bash
# Opus가 T1(아키텍처 설계) 직접 수행 → 완료 시:
clawteam task update $PROJ $T1_ID --status completed
# → T2, T3, T4 자동 unblock!

# unblock된 태스크 확인
clawteam --json task list $PROJ

# cmux send로 기존 AI 세션에 전달 (ClawTeam spawn 아님!)
cmux send --surface surface:2 "/new"
cmux send-key --surface surface:2 enter
sleep 3
cmux send --surface surface:2 "TASK $T2_ID: 백엔드 API 구현 (JWT, CRUD)
파일: src/api/auth.ts, src/api/routes.ts
완료 후 반드시 실행: clawteam task update $PROJ $T2_ID --status completed
그리고 마지막에 DONE: 요약 작성"
cmux send-key --surface surface:2 enter
```

**⚠️ 팀원이 `clawteam task update` 실행 불가능한 경우 (Codex sandbox 등):**
Eagle Watcher가 DONE 감지하면 Opus가 대신 update 실행:
```bash
cmux read-screen --surface surface:2 --lines 20
# "DONE:" 확인 → Opus가 대신 실행:
clawteam task update $PROJ $T2_ID --status completed
```

### Autopilot Watch Loop

```python
# Autopilot Dispatch Loop (기존 Phase 3 + ClawTeam DAG)
while True:
    # Step 1: Eagle 상태 읽기 (API 0원)
    eagle = read("/tmp/cmux-eagle-status.json")

    # Step 2: DONE surface 처리 → ClawTeam board 업데이트
    for sid in eagle.idle_surfaces:
        screen = cmux_read_screen(sid, lines=30)
        task_id = get_current_task_for(sid)

        if "DONE:" in screen and task_id:
            bash(f"clawteam task update {PROJ} {task_id} --status completed")
            # → ClawTeam이 의존 태스크 자동 unblock!

        elif "error" in screen.lower():
            bash(f"clawteam task update {PROJ} {task_id} --status failed")

    # Step 3: 새로 unblock된 태스크 → idle surface 자동 매칭
    pending_tasks = bash(f"clawteam --json task list {PROJ}")
    idle_surfaces = eagle.idle_surfaces

    for task in pending_tasks:
        target_surface = task.owner
        if target_surface in idle_surfaces:
            cmux_send(target_surface, f"TASK {task.id}: {task.description}")
            bash(f"clawteam task update {PROJ} {task.id} --status in_progress")

    # Step 4: 대시보드 체크
    bash(f"clawteam board show {PROJ}")

    sleep(20)
```

### ClawTeam vs cmux 명령어 매핑

| 목적 | cmux 명령 | ClawTeam 명령 |
|------|----------|--------------|
| 작업 지시 | `cmux send --surface` | 사용 안 함 (cmux가 채널) |
| 상태 확인 | `cmux read-screen` | `clawteam --json task list $PROJ` |
| 전체 현황 | Eagle JSON | `clawteam board show $PROJ` |
| 실시간 현황 | — | `clawteam board live $PROJ` |
| 완료 보고 | `DONE:` 키워드 감지 | `clawteam task update $PROJ $ID --status completed` |
| 완료 대기 | 수동 폴링 | `clawteam task wait $PROJ` |
| 의존성 관리 | 수동 Wave 분할 | `--blocked-by` 자동 해소 |

## 실전 패턴 (테스트 검증 완료)

### 병렬 검색 배포 (search_executor.py)

```bash
# ⚠️ 병렬 실행 시 --outdir로 출력 경로를 분리해야 함!
# 같은 outdir 사용 시 마지막 surface의 결과만 남음

# surface:1 → 도서 출판 조사
cmux send --surface surface:1 "python3 50_AutomationCode/search/search_executor.py --query 'AI book authoring' --full --outdir /tmp/search-s1 2>&1 | tail -5"
cmux send-key --surface surface:1 enter

# surface:3 → 한국어 NLP 조사 (다른 출력 경로)
cmux send --surface surface:3 "python3 50_AutomationCode/search/search_executor.py --query 'Korean NLP spell check' --full --outdir /tmp/search-s3 2>&1 | tail -5"
cmux send-key --surface surface:3 enter

# 결과 수집: 각각 /tmp/search-s1/refined.json, /tmp/search-s3/refined.json
```

> **주의**: `--output` 플래그는 존재하지 않음. 반드시 `--outdir`을 사용.
> 상대 경로 `50_AutomationCode/search/search_executor.py` 사용 (작업 디렉토리가 $AI_ROOT/System 기준).

### 긴 프롬프트 전송 (200자+)

```bash
# send는 200자+ 시 불안정 → set-buffer + paste-buffer 사용
cmux set-buffer --name task1 -- "TASK: 이 파일을 읽고 함수 3개 추가해. ..."
cmux paste-buffer --name task1 --surface surface:N
cmux send-key --surface surface:N enter
```

### 자동 완료 감지 (pipe-pane)

```bash
# surface 출력에서 DONE: 패턴 감시 → 파일로 저장
cmux pipe-pane --surface surface:1 --command "grep -m1 DONE: > /tmp/surface1_done.txt"
# 나중에 확인
[ -s /tmp/surface1_done.txt ] && echo "완료!" || echo "진행중"
```

### 동적 팀원 추가/제거

```bash
# 새 팀원 추가
cmux new-split right
# → surface:N, pane:M 반환
# 새 Claude Code 실행
cmux send --surface surface:N "claude --name worker-1"
cmux send-key --surface surface:N enter
# 작업 완료 후 제거
cmux close-surface --surface surface:N
```

## 프롬프트 규칙 (cmux send 시)

1. **경로는 `~`로 시작** 또는 상대경로 (`/`는 슬래시 커맨드로 인식됨)
2. **GLM은 짧게** (200자 이내, 긴 파일 읽기 피하기)
3. **Codex/Gemini는 길어도 OK** (복합 작업 한 번에)
4. **`git commit 금지`** 항상 포함
5. **결과물 범위 명확히** (함수 추가, 파일 생성 등)
6. **LSP/플러그인 질문 방지**: 프롬프트 마지막에 "LSP 설치 질문 나오면 No 선택해" 추가
7. **스킬 컨텍스트 포함**: 모든 dispatch에 `[SKILL CONTEXT]` 공통 블록 + AI별 프리셋 포함 (위 "공유 스킬 컨텍스트 주입" 섹션 참조)
