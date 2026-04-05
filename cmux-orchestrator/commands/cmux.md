# /cmux — cmux 멀티 AI 오케스트레이션 통합 명령어

입력: `$ARGUMENTS`

이 명령어는 cmux orchestrator의 **단일 진입점**입니다. 입력을 분석하여 적절한 cmux 기능을 자동 발동합니다.

---

## 라우팅 (입력 분석 → 자동 실행)

### 빈 입력 또는 `status`
```
cmux tree --all
bash ${SKILL_DIR:=$HOME/.claude/skills/cmux-orchestrator}/scripts/eagle_watcher.sh --once | python3 -m json.tool
```
→ 전 surface 상태 + 건강 확인

### `다음 라운드` / `next` / `round`
→ Skill("cmux-orchestrator") 활성화 + 다음 라운드 프로토콜 6-Step 자동 실행

### `조사` / `research` / `검색` + 주제
```
1. 전 surface 초기화 (/new, /clear)
2. AI별 능력 맞춤 번들 배정
3. 조사 디스패치:
   - search_executor.py 있으면 → py 스크립트로 멀티API 조사
   - 없으면 → 각 AI에 직접 "조사해줘" 프롬프트 전송 (WebSearch/내장 도구)
4. 결과 수집 GATE
```

### `배정` / `assign` / `작업` + 내용
```
1. speckit-tracker.py --init
2. AI별 태스크 분해 + 번들 배정
3. cmux send로 디스패치
4. speckit-tracker.py --add
```

### `수집` / `collect` / `결과`
```
1. eagle_watcher.sh --once (상태 확인)
2. 각 surface cmux read-screen --scrollback --lines 50
3. DONE 키워드 확인
4. speckit-tracker.py --done (완료 마킹)
5. GATE 5 검증: speckit-tracker.py --gate
```

### `리뷰` / `review`
```
→ Agent(subagent_type="code-reviewer", model="sonnet") 디스패치
→ Main 직접 리뷰 금지 (GATE 2)
```

### `커밋` / `commit`
```
1. GATE 1: eagle — WORKING surface 없는지
2. GATE 5: speckit-tracker --gate — 미완료 없는지
3. gate-blocker.sh가 PreToolUse에서 자동 검증
4. 통과 시 git commit
```

### `초기화` / `init` / `setup`
```
bash ${SKILL_DIR}/scripts/install_agents.sh --setup
cmux set-hook after-send-keys "bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once > /dev/null 2>&1 &"
cmux surface-health
cmux display-message "cmux orchestrator active"
```

### `감시` / `eagle` / `watch`
```
bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once | python3 -m json.tool
```

### `gate` / `검증`
```
python3 ${SKILL_DIR}/scripts/speckit-tracker.py --status
python3 ${SKILL_DIR}/scripts/speckit-tracker.py --gate
python3 ${SKILL_DIR}/scripts/gate-enforcer.py --check-all
```

### `surface` / `화면` + surface 번호
```
cmux read-screen --surface surface:N --scrollback --lines 50
```
→ 해당 surface 화면 직접 확인

### `에러` / `error` / `복구`
```
1. eagle에서 ERROR surface 탐지
2. cmux read-screen으로 에러 원인 확인
3. 에러 surface 작업을 다른 surface에 재배정
4. speckit-tracker.py --fail + --reassign
```

### `flash` / `알림`
```
cmux trigger-flash --surface surface:N
cmux notify --title "제목" --body "내용"
```

### `설정` / `config` / `프로파일` / `profile`
```bash
# 빈 입력 또는 list → 현재 AI 프로파일 표시
python3 ${SKILL_DIR}/scripts/manage-ai-profile.py --list

# config detect → 설치된 AI CLI 자동 감지
python3 ${SKILL_DIR}/scripts/manage-ai-profile.py --detect

# config add <이름> → AI 추가
python3 ${SKILL_DIR}/scripts/manage-ai-profile.py --add <이름>

# config remove <이름> → AI 제거
python3 ${SKILL_DIR}/scripts/manage-ai-profile.py --remove <이름>
```
→ AI 프로파일 관리 (traits 기반 surface 분류). 사용 가능: codex, minimax, glm, gemini, claude, opencode

### `프리셋` / `preset`
→ orchestra-config.json의 AI 프리셋 목록 출력

### 기타 (위 패턴 미매칭)
→ Skill("cmux-orchestrator") 활성화 후 입력 전달

---

## 강제 규칙 (모든 라우트에 적용)

1. **WORKING surface 있으면 커밋/종료 금지** (gate-blocker.sh가 물리적 차단)
2. **코드리뷰는 서브에이전트 필수** (Main 직접 금지)
3. **surface 확인은 cmux read-screen 직접** (재질문 금지)
4. **speckit 미완료 태스크 → 재배정 필수** (단순 스킵 금지)
5. **작업 전 /new /clear 초기화 필수**
6. **⛔ GATE 6: IDLE surface 있으면 Agent 도구로 탐색/구현/조사 서브에이전트 디스패치 금지** — 반드시 cmux send로 해당 surface에 위임. Agent 허용: 코드리뷰(Sonnet), cmux 전용 에이전트만.
6. **GATE 0 (수집 완료 GATE) — 조사 디스패치 후 결론/구현 진행 절대 금지** (**HARD BLOCK**)
7. **디스패치 후 10초 확인 (MANDATORY — 상태 확인만, 추가 메시지 금지)** — 작업 전송 후 10초 대기 → `cmux read-screen --lines 10`으로 상태만 확인
   - WORKING → 정상, 아무것도 안 함
   - IDLE → **"위 TASK 실행해" 같은 추가 메시지 보내기 절대 금지!** (프롬프트 엉킴 원인)
     → 대신: `Esc + /new + 원래 전체 프롬프트를 set-buffer+paste-buffer로 재전송`
   - ERROR → `Esc + /new + 원래 프롬프트 재전송`
8. **메시지 전송 패턴 (MANDATORY)** — surface에 작업 전송 시 **반드시 이 순서**:
   ```bash
   # 1. clear (이전 잔여 제거)
   cmux send --surface surface:N "/clear" && cmux send-key --surface surface:N enter && sleep 2
   # 2. 전체 메시지를 한 번에 전송 (set-buffer → paste-buffer → enter 연속)
   cmux set-buffer --surface surface:N "전체 프롬프트 내용"
   cmux paste-buffer --surface surface:N && cmux send-key --surface surface:N enter
   # 3. 10초 후 확인
   sleep 10 && cmux read-screen --surface surface:N --lines 8
   ```
   - **여러 번 나눠 보내기 금지** — surface가 중간 메시지를 다른 작업으로 해석
   - **sleep 없이 연속 전송 금지** — 각 단계 사이 최소 1초 대기
9. **멈춘 surface 복구 절차 (MANDATORY)** — surface가 IDLE/ERROR/컨텍스트초과 상태이면:
   ```bash
   cmux send-key --surface surface:N escape   # 현재 상태 중단
   sleep 1
   cmux send --surface surface:N "/new"       # 세션 초기화 (/clear도 가능)
   cmux send-key --surface surface:N enter
   sleep 2
   cmux read-screen --surface surface:N --lines 5  # 복구 확인
   # 그 후 작업 재전송
   ```
   - 멈춘 상태에서 메시지만 보내면 **무시됨** — 반드시 Esc + /new 먼저
   - "Hide the context summary", "context_length_exceeded", API Error 등 보이면 즉시 복구
10. **매 작업 전후 전 surface 상태 확인 (MANDATORY)** — 작업 디스패치/결과 수집/라운드 시작 시:
    ```bash
    for s in 1 2 3 5 10; do cmux read-screen --surface surface:$s --lines 5; done
    ```
    - ERROR 보이면 → 즉시 Esc + /new 복구
    - IDLE인데 작업 미완료면 → 재전송
    - 이전 메시지 중복/잔류 보이면 → /clear + 재전송
    - **자주 확인할수록 좋음** — 5분 이상 확인 안 하면 surface 상태 유실
11. **"완료/결론" 발언 전 dispatch 검증 (MANDATORY)** — "달성", "완료", "0개", "전부 통과" 등 완료성 발언 전 반드시:
   - `gate-enforcer.py --check-dispatch` 실행하여 `all_collected: true` 확인
   - `all_collected: false`이면 **완료 선언 금지** — 남은 surface 처리 먼저
   - 이 규칙 위반 = GATE 0 위반과 동급 (심각한 오류)
   - WORKING 상태 (프로그래스 바, interrupt, ■⬝) → 정상
   - IDLE 상태 (❯, bypass permissions, Type your message) → **즉시 재전송**
   - 질문/프롬프트 대기 (select, y/n, 스프레드시트) → **Esc + /new + 재전송**
   - 이 확인을 생략하면 surface가 멈춰있는 것을 한참 뒤에야 발견하는 심각한 오류 반복
   - 모든 디스패치된 surface에서 `DONE:` 키워드가 확인되기 전까지 다음 단계 진행 불가
   - 수집 절차:
     1. 디스패치한 surface 목록을 메모리에 유지 (예: `dispatched = [surface:1, surface:2, surface:3, surface:5, surface:10]`)
     2. 각 surface에 대해 `cmux read-screen --surface surface:N --scrollback --lines 80`으로 DONE: 확인
     3. DONE: 미확인 surface가 있으면 → 60초 대기 후 재확인 (최대 5회 polling)
     4. 5회 후에도 DONE 없으면 → **해당 surface를 STALLED로 마킹** → 다른 surface에 재배정 또는 사용자에게 보고
     5. **모든 surface DONE 확인 후에만** 종합/결론/구현 단계 진행 허용
   - 위반 시: "아직 N개 surface에서 결과를 받지 못했습니다. 수집 완료 후 진행합니다." 메시지 출력 후 polling 재개
   - **예외 없음**: "이미 충분한 데이터" 합리화 금지. 모든 surface 결과가 필요함

## cmux 공식 기능 자동 활용

| 기능 | 자동 발동 시점 |
|------|--------------|
| `set-hook after-send-keys` | /cmux init |
| `surface-health` | /cmux status, eagle |
| `trigger-flash` | ERROR/WAITING 감지 시 |
| `rename-tab` | eagle 상태 갱신 시 |
| `display-message` | 라운드 시작/상태 변경 |
| `set-progress` | eagle 진행률 |
| `read-screen --scrollback` | 결과 수집 시 |
| `set-buffer + paste-buffer` | 200자+ 프롬프트 |
| `wait-for` | 동기화 토큰 |
