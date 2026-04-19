# cmuxO Upgrade Phase 1.2 — GATE W-9 Send-Guard Hook

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기
**선행 조건**: Tier A-E hook schema migration 완료 (PR #8/#9/#10 merged 2026-04-19)

---

## 1. 문제 요약

GATE W-9 ("팀원 개입 절대 금지")는 현재 **자연어 규칙(SKILL.md)로만 강제**된다.

- `cmux-watcher/SKILL.md:41,336` — Worker/Watcher가 `/new`, `/clear`를 팀원 surface에 직접 전송 금지 선언
- 하지만 실제로는 **아무 훅도 이를 차단하지 않음** → Worker 세션이 실수로/환각으로 `cmux send-keys ... /clear` 실행 가능
- 2026-04-14 ECO2G 세션에서 실제로 `/new` 재전송으로 팀원 context 파괴 사례 발견 (user 증언 인용)

**Iron Law**: "Worker는 Boss의 승인 없이 다른 surface에 개입할 수 없다."

## 2. 근거 (리서치 결과)

### 2.1 현재 GATE W-9 enforcement 범위

| 계층 | 수단 | 강제력 |
|------|------|--------|
| SKILL.md 자연어 | `cmux-watcher/SKILL.md:41,336,677-682` | 낮음 — LLM이 무시 가능 |
| `cmux-gate6-agent-block.sh` | PreToolUse:Agent | Agent tool 차단만 (send-keys 무관) |
| `cmux-read-guard.sh` | PreToolUse:Bash | Read-tier guard (send-keys 무관) |

→ **Bash의 `cmux send-keys` 자체를 검사하는 훅이 없음.**

### 2.2 탐지해야 할 패턴

```
tmux send-keys -t <target> '/new' Enter
tmux send-keys -t <target> '/clear' Enter
cmux send-keys ... /new
cmux send-keys ... /clear
```

Target surface가 "본인"이 아닌 다른 팀원이면 BLOCK.

### 2.3 role 식별 방법

- `~/.claude/.state/cmux-role.json` (cmux-start가 생성) → `{"role": "boss|worker|watcher"}`
- Boss만 허용, Worker/Watcher는 차단
- role 파일 부재 시 → "orchestration 미시작" 상태이므로 **PASS** (Iron Law: 스킬 로드만으로 훅 활성화 금지 — activation-hook.sh:180)

## 3. 설계

### 3.1 신규 훅

`cmux-orchestrator/hooks/cmux-send-guard.py` (PreToolUse:Bash, timeout 3s)

**로직**:
1. stdin의 `tool_input.command` 파싱
2. `tmux send-keys` 또는 `cmux send-keys` 패턴 감지
3. 명령 body에 `/new` 또는 `/clear` 포함 여부 확인 (quote-aware)
4. target pane이 본인 surface가 아니면 role 검사
5. role = worker/watcher → `hookSpecificOutput.permissionDecision: "deny"` + 사유
6. role = boss 또는 role 파일 없음 → exit 0 (PASS)

**출력 스키마**: Tier A-E migration으로 도입된 `hook_output.py` helper 사용 (SSOT).

### 3.2 settings.json 등록

`activation-hook.sh:81` HOOK_MAP에 추가:
```python
"cmux-send-guard.py": ("PreToolUse", "Bash", 3),
```

### 3.3 예외 처리

- Boss가 `/clear`를 자신 surface에 보내는 경우 → 허용 (self-target)
- `echo /new` 같은 false positive → send-keys 명령만 매칭 (quote/arg-aware regex)
- Surface target 추출 실패 → **fail-open** (PASS + stderr 경고 로그)
  - 이유: fail-closed면 Boss의 정상 dispatch까지 차단 위험

## 4. 5관점 순환검증

### SSOT
- role 정보 출처: `~/.claude/.state/cmux-role.json` (cmux-start가 유일 생성자) ✓
- 금지 패턴 목록: 훅 파일 내부 상수 — 중복 없음 ✓
- 훅 등록: `activation-hook.sh` HOOK_MAP (단일 진입점) ✓

### SRP
- 새 훅의 단일 책임: "Worker/Watcher의 `/new`·`/clear` send-keys 차단"
- 역할 판정은 기존 role 파일 재사용 (로직 중복 X)

### 엣지케이스
- `tmux send-keys -t 0 '/new' Enter` — quote 포함 (매칭 가능)
- `tmux send-keys -t 0 /new Enter` — 비인용 (매칭 가능)
- `tmux send-keys -t 0 $CMD Enter` — 변수 치환 (정적 불가능) → **pass-through + 경고 로그**
- Role 파일 오염 (JSON 손상) → JSON parse fail → PASS + 경고
- `cmux send-keys --help` — help 호출 (문자열 `/new` 없음) → PASS
- Self-target 판정: target = `$CMUX_SURFACE` 또는 `$TMUX_PANE` 기반
- orchestration 미시작 (role 파일 없음) → PASS

### 아키텍트
- 기존 훅과 matcher 충돌: `PreToolUse:Bash`에 이미 8개 훅 있음 → 순서 영향 없음 (parallel 실행)
- cmux-read-guard.sh와 역할 경합 없음 (read guard는 `cat/less` 계열, 본 훅은 send-keys)
- Timeout: 3초 — 정규식 매칭만 수행하므로 충분

### Iron Law
- **"스킬 로드만으로 훅이 활성화되면 안 된다"** (activation-hook.sh:180) — role 파일 부재 시 PASS로 준수 ✓
- **"Worker는 Boss 승인 없이 팀원 개입 불가"** (GATE W-9) — 본 훅이 기계적으로 강제 ✓
- **"fail-open for ambiguous"** (cmux 기본) — target 추출 실패 시 PASS ✓

## 5. 코드 시뮬레이션 (사전 검증)

### 5.1 테스트 케이스 (구현 전 시뮬레이션)

/tmp에 프로토타입 작성 후 실행 예정:

| # | stdin tool_input.command | role | expected | rationale |
|---|---|---|---|---|
| 1 | `tmux send-keys -t sess:0 '/new' Enter` | worker | DENY | GATE W-9 위반 |
| 2 | `tmux send-keys -t sess:0 '/clear' Enter` | watcher | DENY | 위반 |
| 3 | `tmux send-keys -t sess:0 '/new' Enter` | boss | PASS | Boss 권한 |
| 4 | `tmux send-keys -t sess:0 '/new' Enter` | (no role file) | PASS | 미시작 |
| 5 | `echo "/new test"` | worker | PASS | send-keys 아님 |
| 6 | `tmux send-keys -t self '/clear' Enter` | worker (self-target) | PASS | 본인 surface |
| 7 | `cmux send-keys $VAR Enter` | worker | PASS (경고) | 변수 치환 |
| 8 | malformed JSON stdin | worker | PASS (경고) | 파싱 실패 |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

프로토타입: `/tmp/cmux-send-guard-prototype.py`, 러너: `/tmp/test-cmux-send-guard.sh`.

```
[PASS] 1 worker /new other → deny
[PASS] 2 watcher /clear other → deny
[PASS] 3 boss /new → allow
[PASS] 4 no role file → allow
[PASS] 5 echo /new not send-keys → allow
[PASS] 6 self-target /clear → allow
[PASS] 7 variable substitution → allow
[PASS] 8 malformed JSON → allow

=== Phase 1.2 simulation: 8 pass / 0 fail ===
```

→ 8/8 PASS. 본 설계의 경계 조건(role 부재, self-target, 변수 치환, JSON 손상 모두 fail-open) 검증 완료.

## 6. 구현 절차

1. `/tmp/cmux-send-guard-prototype.py` 작성 + 8개 케이스 실행
2. 결과 본 문서 §5.2에 기록
3. `cmux-orchestrator/hooks/cmux-send-guard.py` 생성 (hook_output.py helper 사용)
4. `cmux-orchestrator/activation-hook.sh:81` HOOK_MAP 추가
5. `cmux-orchestrator/install.sh` HOOK_MAP 동기화
6. `cmux-orchestrator/hooks/test-hooks-negative.sh`에 W-9 케이스 추가
7. 로컬 smoke: `python3 cmux-send-guard.py < /tmp/fixtures/w9-*.json`
8. CHANGELOG.md 업데이트 (Phase 1.2 완료 기록)
9. PR 제출 (scokeepa/cmuxO)

## 7. DoD

- [ ] 프로토타입 8 케이스 PASS
- [ ] 훅 파일 생성, activation-hook.sh/install.sh 동기화
- [ ] settings.json에 자동 등록 확인 (로컬)
- [ ] test-hooks-negative.sh 신규 케이스 추가
- [ ] SKILL.md 갱신 — GATE W-9에 "훅으로 기계 강제" 문구
- [ ] PR merge 후 CHANGELOG 업데이트

## 8. 리스크

- **Regex false negative**: 복잡한 shell pipeline (e.g., `cmd | xargs cmux send-keys`) 미탐 가능 — pass-through + 경고 로그로 완화
- **Performance**: PreToolUse:Bash에 이미 8개 훅 → 9개로 증가. 훅당 3s timeout이므로 worst-case +3s. 정규식만 수행하므로 실측 <50ms 예상 (검증 필요)
- **Role 파일 경합**: cmux-start 실행 중 읽기 시 race — `fcntl.flock` 사용으로 완화
