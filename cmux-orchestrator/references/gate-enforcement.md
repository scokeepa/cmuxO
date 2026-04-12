# GATE 강제 체계 상세 레퍼런스

> SKILL.md HARD GATE 시스템 — 4중 강제 체계와 L0~L3 상세 설명

## 4중 강제 체계 개요

| 계층 | 수단 | 강제 대상 | 강제력 |
|------|------|----------|--------|
| **L0: PreToolUse block** | `gate-blocker.sh` → `git commit` 물리적 차단 | WORKING/미완료 시 커밋 차단 | ⛔ **AI 무시 불가** |
| **L1: cmux set-hook** | `after-send-keys` → eagle 자동 갱신 | surface 상태 실시간 감시 | 자동 |
| **L2: PostToolUse 경고** | `gate-enforcer.py` + `cmux-idle-reminder.sh` | WORKING/ERROR/WAITING 경고 주입 | 경고 |
| **L3: SKILL.md GATE** | 5-GATE 체크리스트 (이 문서) | Boss 행동 제한 | 텍스트 |

## L0: 물리적 차단 (PreToolUse Hook)

`gate-blocker.sh`가 PreToolUse 훅으로 등록됨.

### 차단 조건

```bash
# WORKING surface 있으면 → {"decision":"block"} → 커밋 물리적 불가
# speckit 미완료 태스크 있으면 → {"decision":"block"} → 커밋 물리적 불가
```

### 등록 위치

`settings.json` PreToolUse에 이미 등록 (영구)

### 동작 방식

```bash
# gate-blocker.sh 핵심 로직
if git_status_shows_working_surfaces; then
    echo '{"decision":"block","reason":"WORKING surface exists"}'
    exit 1
fi
if speckit_tracker_has_incomplete; then
    echo '{"decision":"block","reason":"speckit tasks incomplete"}'
    exit 1
fi
echo '{"decision":"allow"}'
exit 0
```

## L1: cmux 이벤트 훅

`after-send-keys` 이벤트 → eagle_watcher.sh 자동 실행

### 등록

```bash
cmux set-hook after-send-keys "bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once > /dev/null 2>&1 &"
```

### 역할

- surface 상태 실시간 감시
- IDLE/WORKING/ERROR 상태 자동 갱신
- `/tmp/cmux-eagle-status.json` 업데이트

## L2: PostToolUse 경고

### gate-enforcer.py

- git commit 실행 전 미완료 surface 감지
- WORKING/ERROR/WAITING 상태 경고 주입

### cmux-idle-reminder.sh

- UserPromptSubmit 훅으로 등록
- IDLE surface 자동 감지
- Boss에게 IDLE surface 알림

### speckit-tracker (태스크 추적)

```bash
# 초기화
python3 ${SKILL_DIR}/scripts/speckit-tracker.py --init "Round N"

# 태스크 추가
python3 ${SKILL_DIR}/scripts/speckit-tracker.py --add T1 S3 "epub_export"

# 완료 표시
python3 ${SKILL_DIR}/scripts/speckit-tracker.py --done T1

# 게이트 검증 (미완료 있으면 exit 1)
python3 ${SKILL_DIR}/scripts/speckit-tracker.py --gate
```

## L3: SKILL.md GATE 체크리스트

### GATE 0.5: ZERO-PASTE

**⛔ 절대 금지 표현:**

| 금지 표현 | 대신 해야 하는 것 |
|----------|-----------------|
| "이 프롬프트를 붙여넵어주세요" | `cmux send --surface surface:N "프롬프트"` |
| "surface:N에 입력해주세요" | `cmux send --surface surface:N "내용"` + `cmux send-key enter` |
| "다른 AI에게 전달해주세요" | `cmux send --surface surface:N "내용"` |
| "사용자가 직접 전달" | Boss가 cmux send로 직접 전달 |

### GATE 1: 과업 완료 GATE

```
⛔ WORKING surface가 1개라도 있으면 라운드 종료 금지.
⛔ IDLE이지만 "DONE" 키워드 미확인이면 완료 판정 금지. (IDLE ≠ 완료)
```

### GATE 2: 코드리뷰 위임 GATE

```
⛔ Boss(Opus)이 직접 코드리뷰를 하면 안 된다.
→ Agent(subagent_type="code-reviewer", model="sonnet", run_in_background=true) 디스패치
→ Boss는 결과만 읽고 APPROVE/REJECT 판단
예외: 서브에이전트가 3회 실패한 경우에만 Boss 직접 리뷰 허용 (사유 기록 필수)
```

### GATE 3: 서브에이전트 사용 GATE

| 작업 | 필수 에이전트 | Boss 직접 금지 |
|------|-------------|--------------|
| 코드리뷰 | Agent(code-reviewer, sonnet) | ⛔ |
| 코드리뷰 (보안) | Agent(code-reviewer, sonnet) | ⛔ |

### GATE 4: 라운드 종료 자가 점검 체크리스트

```
□ GATE 1: 모든 surface DONE 확인 (WORKING/미확인 없음)
□ GATE 2: 코드리뷰 서브에이전트 위임 (Boss 직접 리뷰 0건)
□ GATE 3: 서브에이전트 사용 규칙 준수
□ GATE 5: speckit 태스크 전체 완료 (미완료 0개 — 재배정 포함)
□ GATE 6: Agent 도구 오용 0건 (탐색/구현/조사 서브에이전트 디스패치 0건, 전부 cmux send)
□ GATE 7: 2+ surface 배정 시 워크트리 사용 확인 (git worktree list)
□ GATE 7b: 병합 완료 + 워크트리 정리 완료 (git worktree list에 /tmp/wt-* 0개)
□ 서브에이전트 리뷰 결과 수신 + REJECT 항목 수정
□ LECEIPTS: 5-섹션 보고서 작성 완료 (/tmp/cmux-leceipts-report.json)
□ LECEIPTS: verification 섹션에 실제 실행 결과 포함
□ 커밋 실행
하나라도 □(미체크)이면 → ⛔ 라운드 종료 금지.
```

## 세션 시작 시 자동 활성화 순서

```bash
# L0: gate-blocker.sh — settings.json PreToolUse에 이미 등록 (영구)
# L1: cmux 이벤트 훅 등록 (세션마다)
cmux set-hook after-send-keys "bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once > /dev/null 2>&1 &"
# L2: gate-enforcer.py — settings.json PostToolUse에 이미 등록 (영구)
# L3: SKILL.md — 스킬 활성화 시 자동 로드
```
