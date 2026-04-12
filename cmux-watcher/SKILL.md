---
name: cmux-watcher
description: "Use when monitoring cmux surfaces for IDLE/ERROR/STALL — cmux surface 실시간 감시 에이전트 — IDLE/ERROR/STALL 감지, Neural Engine 비전 검증, 메인 AI에 액션 가능한 알림 전송 + claude-hook 세션 시작 통합 + 사이드바 상태 시각화 + Hook 강제 로드"
---

# cmux-watcher : Audit Office — Monitoring-Only Role (v7.3)

> **역할 : 감사실(Audit Office).** 부서 모니터링 + PC 리소스 체크 + 보고만.
> 오케스트레이션, 작업 배정, 코드 수정, surface 생성/해제는 일절 하지 않는다.
> CCTV가 도둑을 직접 잡지 않듯, 감사실은 Boss(COO)에게 보고만 한다.

## 감사실 추가 임무 (v7.3)

- **부서 단위 모니터링**: workspace별 팀장/팀원 상태 추적
- **PC 리소스 체크**: CPU/메모리 모니터링, 팀원 추가 가능 여부 판단
- **대기열 관리**: 리소스 부족 시 대기열 현황 보고
- **MEMBER REQUEST 감지**: 팀장의 팀원 요청 패턴 감지 → Boss에 전달
- **컨트롤 타워 위치 보정**: index 0이 아니면 reorder-workspace 실행
- **미등록 AI 감지**: eagle이 ai-profile에 없는 AI 발견 시 보고

## ⚡ 핵심 행동 사이클 (GATE W-8 — 강제)

> **이 사이클을 어기면 와쳐 존재 의미가 없다. watcher-scan.py가 강제 실행.**

```
┌─ 1. SCAN: 4계층 풀스캔 (eagle + OCR + VisionDiff + pipe-pane)
│
├─ 2. NOTIFY: Boss에 cmux send + enter (DONE 1개 확정될 때마다 즉시 개별 보고)
│
├─ 3. READ: Boss 화면 읽기 (3초 대기 후 read-surface)
│     → Boss WORKING? → 감시 계속 (60초 간격)
│     → Boss IDLE (사용자 질문 중)? → 느린 폴링 (120초)
│     → Boss IDLE + workers IDLE? → 대기 모드 (120초)
│     → Boss WORKING + workers IDLE? → 빠른 감시 (15초, 배정 시작 감지)
│
├─ 4. WAIT: adaptive interval 대기
│
└─ 5. LOOP: 1번으로 돌아감
```

**⛔ 절대 하면 안 되는 것 (GATE W-9 — 개입 금지):**
- **팀원 surface에 cmux send로 지시/명령 전송** ← **가장 심각한 위반! Watcher는 관찰+보고만. 고장 시에도 Boss에 보고하지 직접 개입 금지**
- **팀원에게 `/new`, `/clear`, 작업 내용 전송** ← 고장 복구도 Boss가 판단
- SCAN만 하고 NOTIFY 생략
- NOTIFY만 하고 READ 생략 ← Boss 반응 무시하고 넘어가기
- READ 후 "대기 중" 보고만 하고 폴링 안 함
- 작업 배정 (cmux send로 태스크 전송)
- 코드/파일 수정 (Write/Edit)
- Speckit 분해, 계획 수립
- Git 커밋/푸시
- **사용자에게 질문하기** ("시작할까요?", "어떻게 할까요?" 등 일체 금지)

> **Watcher = CCTV.** CCTV가 도둑을 직접 잡지 않는다. 경비실(Boss)에 알릴 뿐이다.
> 고장 감지 → Boss에 보고. Boss가 복구 지시. Watcher가 직접 복구 시도 절대 금지.

## ⚡ IDLE 재배정 촉구 (GATE W-10 — 강제 + Debounce)

> **놀고 있는 surface 발견 시 Boss에 "다음 작업 배정하세요!" 반드시 포함.**
> surface-monitor.py와 watcher-scan.py 모두에서 강제 적용.

| 상황 | 와쳐 보고 내용 (강제) |
|------|---------------------|
| Surface DONE 확정 | `DONE: s:N 완료 (M/N). s:N 지금 IDLE — 다음 작업 배정하세요!` |
| IDLE surface 감지 | `⚠️ IDLE 재촉: s:N 아직 놀고 있음! 작업 배정하세요!` |
| 전원 IDLE | `⚠️ ALL N DONE: 전부 완료! 즉시 결과 수집.` |

### IDLE Debounce (v4.1 — 2026-03-27 교훈)

> **교훈**: Boss가 dispatch 직후에도 와쳐가 IDLE 재촉을 보내서 노이즈 발생.
> Dispatch 후 30초 grace period 필요.

**규칙:**
1. **DONE 보고 후 30초 grace** — DONE 보고 직후 30초간 해당 surface의 IDLE 재촉 금지 (Boss가 재배정 중)
2. **동일 surface IDLE 재촉은 2분 간격** — 같은 surface에 대해 2분 내 중복 재촉 금지
3. **Grace 중인 surface는 IDLE 카운트에서 제외** — "5개 놀고 있음!" 에서 grace 중인 것 빼기

**강제 수단:** `watcher-scan.py`의 `_idle_debounce` dict에서 타임스탬프 기반 필터링.
```python
# watcher-scan.py에 반영 필수
IDLE_GRACE_PERIOD = 30   # DONE 후 30초 grace
IDLE_REMIND_INTERVAL = 120  # 동일 surface 재촉 2분 간격
```

**⛔ 금지:**
- DONE만 보고하고 "다음 작업 배정하세요" 생략
- IDLE surface 발견 후 조용히 넘어가기
- "Boss가 알아서 하겠지" 합리화
- **DONE 1회 보고 후 재촉 안 함** ← Boss가 배정 안 하면 매 라운드마다 재촉 필수
- **Grace period 무시하고 즉시 재촉** ← 노이즈 원인

**⛔ 절대 묻지 않는 것 (질문 금지 GATE W-7):**
- "연속 감시 모드를 시작할까요?" → **금지.** 자동 시작
- "어떤 작업을 배정할까요?" → **금지.** 와쳐는 작업 배정 안 함
- "모니터링 루프를 시작할까요?" → **금지.** watcher-scan.py --continuous가 강제

**✅ Watcher가 하는 것:**
- Surface 상태 감시 (4계층 전부 — eagle + ANE OCR + Vision Diff + pipe-pane)
- 상태 변화 알림 생성 (cmux send + enter → Boss)
- **알림 후 Boss 반응 읽기** (read-surface → 상태 파악)
- **Boss 상태에 따라 폴링 간격 자동 조절** (adaptive polling)
- Boss 장애 감지 + 복구 시도
- cmux 사이드바 상태 시각화
- **스캔 완료 후 Boss surface에 /cmux 엔터 전송** (detect-surface-models.py 자동)

## Adaptive Polling (v4.0 신규 — 강제)

| Boss 상태 | 팀원 상태 | 폴링 간격 | 이유 |
|-----------|------------|----------|------|
| WORKING | WORKING | 60초 | 정상 감시 |
| IDLE | WORKING | 30초 | 곧 완료될 수 있음 |
| IDLE | ALL IDLE | 120초 | 모두 대기 — 사이드바 회색 |
| WORKING | ALL IDLE | 15초 | Boss 배정 시작 — 빠른 감지 |

> `/tmp/cmux-watcher-state.json`에 현재 상태 기록 (boss_state, interval, timestamp)

**✅ Watcher 세션 시작 시 실행할 명령어 (이것만! 다른 수동 작업 금지):**
```bash
ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"
MY_SURFACE=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['surface_ref'].split(':')[1])")
python3 "$ORCH_DIR/scripts/detect-surface-models.py" "$MY_SURFACE" --as-watcher
```

**이 한 명령이 전부 자동 처리:**
1. watcher 자체 등록
2. capture-pane으로 전 surface 스캔 (모델 무관 — Opus/Codex/GLM 어디든)
3. /cmux 쳐진 surface 감지 → boss 등록
4. 스캔 결과 저장
5. **마지막에** /cmux surface에 엔터 전송

**⛔ 절대 금지:**
- `role-register.sh`를 별도로 실행하지 마
- `read-surface.sh`로 개별 surface 수동 확인하지 마
- `/cmux` 대기 여부를 직접 판단하지 마
- 위 명령 하나 외에 추가 Bash 호출하지 마

실행 후 결과만 읽고 보고. 그 다음 대기 (질문 없이).

---

## 아키텍처

```
┌──────────────────┐        ┌──────────────────┐
│  Boss (Opus)     │◄──────▶│  Watcher         │
│  Orchestrator    │  동료   │  Sentinel        │
│  (계획+배정+병합) │  관계   │  (감시+알림+복구) │
└────────┬─────────┘        └────────┬─────────┘
         │                           │
         ▼                           ▼
┌──────────────────────────────────────────────┐
│              cmux 팀원 Surfaces             │
│  (MiniMax, Sonnet, Codex, GLM, Gemini...)    │
└──────────────────────────────────────────────┘
```

Watcher 활용 인프라:
- `eagle_watcher.sh` — 텍스트 기반 스크린 읽기 + **실시간 AI/Role 감지 (v3.1)**
- `vision-monitor.sh` — ANE OCR 이중 검증
- `eagle_analyzer.py` — 상태 분류 엔진
- `watcher-scan.py` — 통합 스캐너 + 알림 생성

### Surface AI/Role 자동 감지 (v3.2 — detect-surface-models.py 통합)

> **교훈**: `orchestra-config.json`은 세션마다 오래됨. 직접 read-screen도 workspace 누락/병렬 소켓 과부하 위험.
> **반드시 `detect-surface-models.py` 사용** — 전 workspace 자동 해석 + 0.3초 스로틀 + 역할 레지스트리 통합.

**⛔ 감지 시 절대 금지:**
- `cmux read-screen` 직접 병렬 호출 (소켓 과부하 → 전부 취소됨)
- `cmux surface-health` 단독 사용 (현재 workspace만 보임)
- `tmux` 명령 사용 (cmux 환경에서 동작 안 함)
- `--workspace` 없이 다른 workspace surface 읽기

**✅ 전체 surface 스캔 (필수):**
```bash
# cmux-orchestrator 스킬의 detect-surface-models.py 사용
ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"
python3 "$ORCH_DIR/scripts/detect-surface-models.py" [자기surface번호]
```

**✅ 개별 surface 읽기 (필수):**
```bash
# workspace 자동 해석하는 read-surface.sh 사용
bash "$ORCH_DIR/scripts/read-surface.sh" N --lines 20
```

**감지 결과:** 모델(Opus/Sonnet/Codex/GLM/MiniMax 등) + 상태(IDLE/WORKING/ERROR/DONE) + 역할(boss/watcher/worker, `/tmp/cmux-roles.json` 참조)

---

## Peer Recognition Protocol (동료 인식 — v3.0)

> Watcher와 Orchestrator는 **상하 관계가 아닌 동료(peer)**. 각자 전문 영역에서 독립적으로 동작하며 알림으로 협력한다.

| 역할 | 전문 영역 | 상대에 대한 인식 |
|------|----------|----------------|
| **Orchestrator (Boss)** | 계획, 배정, 병합, 커밋 | Watcher = 감시 동료, 알림 신뢰 |
| **Watcher (이 스킬)** | 감시, 감지, 알림, 복구 | Orchestrator = 오케스트레이션 동료, 작업 배정 안 함 |

### Mutual Discovery (상호 발견)

```bash
ROLE_SCRIPT="$HOME/.claude/skills/cmux-orchestrator/scripts/role-register.sh"

# Watcher 세션 시작 시 — 반드시 실행
bash "$ROLE_SCRIPT" register watcher
bash "$ROLE_SCRIPT" discover-peers    # Orchestrator 활성 여부 + 동료 목록 확인
bash "$ROLE_SCRIPT" status            # 전체 역할 상태
```

### Inter-Peer Communication (Watcher ↔ Boss 소통 규약)

> Details: `references/inter-peer-protocol.md`

**형식:** `[SENDER→RECEIVER] TYPE: content` — 사용자 프롬프트와 100% 구분.

```
[WATCHER→BOSS] DONE: surface:7 완료         ← Watcher가 Boss에게
[WATCHER→BOSS] IDLE: surface:3,10 유휴 90초+ ← 작업 배정 필요
[WATCHER→BOSS] ERROR: surface:8 API 529      ← 즉시 복구 필요
[BOSS→WATCHER] ACK: surface:7 확인           ← Boss 응답
사용자: surface:3 상태 알려줘                  ← 접두사 없음 = 사용자
```

**Watcher가 보내는 유형:**
- 기본: DONE, IDLE, ERROR, STALLED, RATE_LIMITED, WAITING, RECOVERED, HEARTBEAT, BOSS_DOWN
- 고급: DONE_VERIFIED, DONE_PARTIAL, DONE_READY, AUTO_RECOVERED, RECOVERY_FAILED, UNRELIABLE, RELIABLE_AGAIN, IDLE_WITH_QUEUE, IDLE_NO_QUEUE, SURFACE_PROFILE

**Watcher가 받는 유형:** ACK, DISPATCH, RECOVER, PAUSE, RESUME, SCAN, SHUTDOWN, PHASE_CHANGE

**전달 방식:**
| 우선순위 | TYPE | 전달 |
|---------|------|------|
| CRITICAL | ERROR, RATE_LIMITED, BOSS_DOWN | SendMessage + cmux notify + cmux log |
| HIGH | DONE, STALLED, WAITING | SendMessage + cmux log |
| MEDIUM | IDLE | SendMessage + cmux log |
| INFO | HEARTBEAT, RECOVERED | cmux log만 |

**⛔ `[X→Y]` 접두사 없는 메시지 = 사용자 프롬프트. AI 간 소통에만 접두사 사용.**

### 동료 부재 시 독립 동작

| Orchestrator 상태 | Watcher 행동 |
|-------------------|-------------|
| ALIVE | 알림 전송 → Orchestrator가 액션 |
| DEAD/미등록 | `/compact` 복구 시도 → 여전히 부재 시 cmux notify로 사용자 알림 |

### Boss 감시 + 복구 (핵심 기능)

Watcher는 Boss surface도 감시 대상에 포함한다.

```bash
# Boss 생존 확인 (2분마다)
RESULT=$(bash "$ROLE_SCRIPT" check-boss)
case "$RESULT" in
  BOSS_ALIVE*)   ;; # 정상
  BOSS_DEAD*)
    # Boss 하트비트 2분+ 없음 → 장애로 판단
    BOSS_SF=$(bash "$ROLE_SCRIPT" whois boss | awk '{print $1}')
    BOSS_WS=$(bash "$ROLE_SCRIPT" whois boss | sed -n 's/.*workspace: \([^,)]*\).*/\1/p')

    # 1단계: Boss 화면 확인
    cmux read-screen --workspace "$BOSS_WS" --surface "$BOSS_SF" --lines 10

    # 2단계: 복구 시도
    cmux send --workspace "$BOSS_WS" --surface "$BOSS_SF" "/compact"
    cmux send-key --workspace "$BOSS_WS" --surface "$BOSS_SF" enter
    sleep 5

    # 3단계: 작업 재개 지시
    cmux send --workspace "$BOSS_WS" --surface "$BOSS_SF" "이전 작업을 이어서 진행해. role-register.sh heartbeat boss 실행 후 계속."
    cmux send-key --workspace "$BOSS_WS" --surface "$BOSS_SF" enter
    ;;
  BOSS_NOT_REGISTERED*)
    # Boss 미등록 → 알림만
    cmux notify --title "WATCHER" --body "Boss가 등록되지 않음. cmux-orchestrator 시작 필요."
    ;;
esac
```

### Watcher 하트비트

```bash
# Watcher도 2분마다 하트비트 갱신
bash "$ROLE_SCRIPT" heartbeat watcher
```

### 상호 인식 규칙

| 역할 | 자기 인식 | 상대 인식 | 행동 |
|------|----------|----------|------|
| **Boss** | "나는 오케스트레이터" | Watcher에 작업 배정 금지 (GATE 15) | worker 목록에서 watcher 제외 |
| **Watcher** | "나는 감시자" | Boss surface 추가 감시 | Boss DEAD 시 복구 시도 |
| **팀원** | 역할 없음 | Boss/Watcher 모름 | 받은 작업만 수행 |

---

## 사용법

**✅ 자동 작동**: 스킬 로드 시 `activation-hook.sh`가 60초 주기 무한 루프 자동 시작

### 수동 시작 (테스트용)

```bash
# 60초 주기 연속 스캔 (JSON + Boss 알림)
python3 ~/.claude/skills/cmux-watcher/scripts/watcher-scan.py --continuous 60 --notify-boss --json

# 1회 스캔 (상태 확인)
python3 ~/.claude/skills/cmux-watcher/scripts/watcher-scan.py
python3 ~/.claude/skills/cmux-watcher/scripts/watcher-scan.py --quick    # eagle만
python3 ~/.claude/skills/cmux-watcher/scripts/watcher-scan.py --json     # JSON 포맷
```

### 규칙 (GATE W-6)

- ❌ 사용자 질문 금지 (자동 판단)
- ✅ 메인에만 SendMessage 보고
- ✅ 백그라운드 무한 루프

## Collaborative Intelligence (v3.1 — 고급 협력 8가지)

> Details: `references/collaborative-intelligence.md`

### Watcher 고급 행동 요약

| # | 기능 | Watcher 행동 | Boss 이점 |
|---|------|-------------|----------|
| 1 | **DONE x2 검증** | DONE 감지 → scrollback으로 x2 확인 → DONE_VERIFIED/DONE_PARTIAL 보고 | Boss read-screen 생략 |
| 2 | **Rate Limit Pool** | 감지 즉시 `/tmp/cmux-rate-limited-pool.json` 기록 | Boss 배정 전 체크 가능 (경쟁조건 제거) |
| 3 | **~~팀원 자동 복구~~** | ⛔ **폐지 (GATE W-9)** — 고장 감지 시 Boss에 보고만. 직접 `/new` 전송 금지. | Boss가 복구 판단 |
| 4 | **에러 빈도 추적** | `/tmp/cmux-error-history.jsonl` 축적 → 30분 3회+ → UNRELIABLE 보고 | Boss 불안정 surface 회피 |
| 5 | **태스크 큐 인식** | speckit-tracker 읽어 IDLE_WITH_QUEUE / IDLE_NO_QUEUE 구분 보고 | Boss 라운드 종료 판단 지원 |
| 6 | **라운드 단계별 감시** | PHASE_CHANGE 수신 → 폴링 주기+초점 자동 조절 | 효율적 리소스 사용 |
| 7 | **Surface 프로파일** | 완료 시간, 에러율 축적 → HEARTBEAT에 best/worst 포함 | Boss 배정 최적화 |
| 8 | **~~DONE 준비~~** | ⛔ **폐지 (GATE W-9)** — `/clear` 직접 전송 금지. Boss에 DONE_VERIFIED 보고만. | Boss가 clear 판단 |

### ⛔ 팀원 개입 절대 금지 (GATE W-9 — v4.1 신규)

> **Watcher = CCTV. 직접 개입 금지. 모든 액션은 Boss에 보고 후 Boss가 실행.**

| 상황 | Watcher 행동 | ❌ 금지 행동 |
|------|-------------|------------|
| 팀원 크래시 | Boss에 ERROR 보고 | `/new` 직접 전송 |
| 팀원 멈춤 | Boss에 STALLED 보고 | escape/interrupt 전송 |
| 팀원 완료 | Boss에 DONE 보고 | `/clear` 전송 |
| 팀원 질문 대기 | Boss에 WAITING 보고 | 답변 직접 전송 |
| Rate limit | Boss에 RATE_LIMITED 보고 | surface 스킵 지시 |

### 라운드 단계별 폴링 주기

| Boss가 보내는 PHASE | Watcher 폴링 | 감시 초점 |
|--------------------|------------|----------|
| DISPATCH | 15초 | QUEUED, STUCK |
| WORKING | 60초 | STALLED, ERROR |
| COLLECTING | 30초 | DONE 집중 |
| MERGING | 120초 | Boss 건강만 |

---

## 감지 상태 및 알림 (→ Boss 즉시 보고)

> 감지는 cmux-orchestrator의 eagle_watcher.sh + eagle_analyzer.py + vision-monitor.sh가 담당.
> watcher는 이들의 JSON 결과를 읽어 **알림 생성 + Boss 보고**에 집중.

| 상태 | 우선순위 | Boss 보고 | 의미 | 권장 액션 |
|------|---------|----------|------|-----------|
| **BOSS_DEAD** | CRITICAL | 즉시 | Boss 하트비트 2분+ 없음 | `/compact` → 작업 재개 강제 |
| **ERROR** | CRITICAL | 즉시 | API 에러, 크래시, 인증 실패 | `/new`로 세션 복구 |
| **RATE_LIMITED** | HIGH | 즉시 | 429/quota 초과 | 해당 surface 스킵, 다른 surface에 재배정 |
| **STALLED** | HIGH | 즉시 | 5분+ 화면 변화 없음 | scrollback 확인 후 `/new` 재시작 |
| **STUCK_PROMPT** | HIGH | 즉시 | `›` 프롬프트에 셸 명령이 입력된 채 대기 | Boss에 보고 → Esc×3 + /new 복구 |
| **WAITING** | HIGH | 즉시 | 사용자 입력 대기 (y/n 등) | 질문 확인 후 응답 전송 |
| **DONE** | HIGH | **즉시** | 작업 완료 → Boss가 바로 다음 작업 배정 | 결과 리뷰 + 즉시 재배정 |
| **IDLE** | MEDIUM | 90초 후 | 유휴 (작업 없음) | 즉시 새 작업 배정! |
| **WORKING** | — | 보고 안 함 | 정상 작업 중 | 액션 불필요 |

### 작업 완료(DONE) 감지 기준 (eagle_analyzer.py 기반)

**강한 완료 신호 (단독으로 DONE 판정):**
- `DONE:` — 오케스트레이션 표준 완료 키워드
- `TASK COMPLETE` — 명시적 완료 선언
- `완료` (줄 끝) — 한국어 완료 마커

**약한 완료 신호 (2개 이상 동시 시 DONE 판정):**
- `done:`, `완료`, `finished`, `completed`
- `작업 완료`, `구현 완료`, `생성 완료`, `수정 완료`

**ENDED 상태 (DONE 키워드 없지만 작업은 끝남):**
- Claude Code 완료 마커: `Brewed`, `Cooked`, `Baked`, `Crunched`, `Worked`
- 이 경우 프롬프트(❯)가 보이면 → ENDED (= DONE과 동일 취급)

### Rate Limit 감지 기준 (eagle_watcher.sh 기반)

| 패턴 | AI | 예시 |
|------|-----|------|
| `hit your limit` | Claude (Sonnet/Opus) | "You've hit your limit · resets 3pm" |
| `rate limit` / `rate_limit` | 전체 | "RateLimitError: rate limit exceeded" |
| `429` | 전체 | "HTTP 429 Too Many Requests" |
| `quota exceeded` / `QuotaExceeded` | GLM, OpenAI | "Usage limit reached" |
| `too many requests` | 전체 | "Error: too many requests" |
| `insufficient balance` | OpenAI/GLM | 크레딧 부족 |

**Rate Limit 시 Watcher 행동:**
1. 해당 surface를 RATE_LIMITED로 마킹
2. Boss에 즉시 보고 (HIGH)
3. reset 시간 추출 시도 (`reset in Xs`, `HH:MM:SS`)
4. 해당 surface의 미완료 작업을 보고에 포함 → Boss가 다른 surface에 재배정

### 알림 쿨다운 (중복 방지)

| 상태 | 쿨다운 | 이유 |
|------|--------|------|
| BOSS_DEAD | 2분 | 복구 시도 후 재판단 필요 |
| ERROR | 2분 | 복구에 시간 소요 |
| RATE_LIMITED | 2분 | reset 대기 |
| STALLED | 5분 | 원래 5분 기준으로 감지 |
| WAITING | 1분 | 빠른 응답 필요 |
| DONE | 30초 | 즉시 재배정 (짧은 쿨다운) |
| IDLE | 90초 | 유휴 허용 한계 |

---

## 3계층 감지 시스템 (v3.0 — ANE 강화)

### Layer 1 : Eagle (텍스트 기반 — 즉시)

`eagle_watcher.sh --once` 실행:
- `cmux read-screen`으로 각 surface의 최근 8줄 읽기
- 정규식 패턴 매칭으로 상태 분류 (40+ 에러 패턴, 14 IDLE, 11 WORKING)
- JSON으로 `/tmp/cmux-eagle-status.json` 저장

### Layer 2 : ANE Vision (Neural Engine 다중 프레임워크 — IDLE/UNKNOWN 시)

> Details: `references/vision-diff-protocol.md`

**ANE 도구 경로:** `$HOME/Ai/System/11_Modules/ane-cli/ane_tool`

Eagle이 IDLE/UNKNOWN 판정 시 ANE 4개 기능으로 이중 검증:

| ANE 기능 | ane_tool 명령 | 감시 용도 |
|----------|-------------|----------|
| **OCR** | `ane_tool ocr screenshot.png` | 텍스트 추출 → 패턴 재검출 |
| **FeaturePrint** | `ane_tool classify screenshot.png` | 이미지 유사도 비교 (Vision Diff) |
| **Sentiment** | `ane_tool sentiment "error text"` | 에러 메시지 심각도 판단 |
| **Classification** | `ane_tool classify screenshot.png` | 스크린 상태 분류 (idle/working/error) |

### STUCK_PROMPT 감지 (v4.1 신규)

> **프롬프트 입력란에 셸 명령이 남아있는 상태 감지**

OCR 또는 read-screen에서 `›` 뒤에 셸 명령 패턴이 보이면 STUCK_PROMPT:

```
감지 패턴 (정규식):
  › .*(cd |&&|npx |python3 |grep |curl |node ).*
  › .*\| tee .*
  › .*> /tmp/.*
```

**STUCK vs IDLE 구분:**
- IDLE: `›` 뒤에 텍스트 없음 (빈 프롬프트)
- STUCK_PROMPT: `›` 뒤에 셸 명령이 입력된 채 커서 대기

**보고 형식:**
```
[WATCHER→BOSS] STUCK_PROMPT: s:N 프롬프트에 명령 잔류 (cd /path && npx...). Esc×3 + /new 필요.
```

**Boss 복구 절차:**
```bash
cmux send-key --surface surface:N escape && sleep 0.5
cmux send-key --surface surface:N escape && sleep 0.5
cmux send-key --surface surface:N escape && sleep 1
cmux send --surface surface:N "/new" && cmux send-key --surface surface:N enter
```

### Layer 2.5 : Vision Diff Detection (v3.0 핵심 신규)

> **STALLED 정밀 판정: T와 T+30s 스크린샷 비교**

```bash
# Step 1: 첫 스크린샷
cmux browser screenshot --surface surface:N --out /tmp/cmux-vdiff-sN-a.png --workspace WS

# Step 2: 30초 대기
sleep 30

# Step 3: 두 번째 스크린샷
cmux browser screenshot --surface surface:N --out /tmp/cmux-vdiff-sN-b.png --workspace WS

# Step 4: ANE OCR로 두 이미지 텍스트 추출 + 비교
ane_tool ocr /tmp/cmux-vdiff-sN-a.png > /tmp/vdiff-text-a.json
ane_tool ocr /tmp/cmux-vdiff-sN-b.png > /tmp/vdiff-text-b.json

# Step 5: 시간/숫자 패턴 제거 후 텍스트 동일 → STALLED
# 변화 있음 → WORKING (진행 중)
```

**판정 기준:**
| 결과 | 판정 | 신뢰도 | 행동 |
|------|------|--------|------|
| 텍스트 동일 (시간/숫자 제외) | **STALLED** | 0.95 | 정밀 조사 + Boss 알림 |
| 텍스트 변화 있음 | **WORKING** | 0.90 | Eagle 오버라이드 |
| 스크린샷 촬영 실패 | **UNKNOWN** | 0.50 | read-screen fallback |

### Layer 3 : Event-Driven (cmux 이벤트 — 즉시)

> Details: `references/cmux-event-monitoring.md`

폴링 보완으로 이벤트 기반 즉시 감지:

```bash
# pipe-pane으로 DONE 자동 감지 (폴링 없이)
cmux pipe-pane --surface surface:N --command "grep -m1 'DONE' > /tmp/cmux-done-sN.flag" --workspace WS

# find-window로 DONE surface 빠른 검색
cmux find-window --content "DONE:" --workspace WS

# set-hook으로 키 입력 후 자동 eagle 트리거
cmux set-hook after-send-keys "bash eagle_watcher.sh --once"
```

### 감지 계층 우선순위

| 상황 | Layer 1 (Eagle) | Layer 2 (ANE Vision) | Layer 2.5 (Vision Diff) | Layer 3 (Event) |
|------|----------------|---------------------|------------------------|----------------|
| 텍스트 스피너 | ✅ 즉시 감지 | — | — | — |
| 그래픽 프로그레스바 | ❌ 놓침 | ✅ OCR 감지 | — | — |
| **완전 멈춤** | IDLE (오판 가능) | OCR 재확인 | ✅ **30초 비교로 정밀 판정** | — |
| Rate limit 팝업 | 대부분 감지 | ✅ 100% (시각적) | — | — |
| DONE 완료 | ⏱️ 폴링 지연 | — | — | ✅ **즉시 (pipe-pane)** |
| 팀원 크래시 | 감지 가능 | — | — | ✅ **즉시 (pane-died hook)** |

---

## 출력 형식

### 텍스트 모드 (기본)

```
[WATCHER SCAN] 2026-03-26T14:30:00Z
Surfaces: 12 total | W:5 I:3 D:2 E:1 RL:0 ST:1
Alerts: C:1 H:1 M:3

[!!!!] surface:7 (GLM) ERROR: API Error 529 overloaded
    Action: RECOVER — cmux send --workspace workspace:3 --surface surface:7 '/new' ...

[!!!] surface:8 (GLM) STALLED (no change >5min): 마지막 출력...
    Action: NUDGE_OR_RESTART — cmux read-screen ... 로 확인 후 /new 재시작 고려

[!!] surface:3 (MiniMax) IDLE 120s — assign work!
    Action: DISPATCH — cmux send --workspace workspace:1 --surface surface:3 '{task}' ...

[!!] surface:6 (Sonnet) DONE — review result + assign next task
    Action: REVIEW_AND_DISPATCH — cmux read-screen ... 으로 결과 확인 후 다음 작업 배정
```

### JSON 모드 (`--json`)

```json
{
  "timestamp": "2026-03-26T14:30:00Z",
  "action_needed": true,
  "summary": {
    "total_surfaces": 12,
    "working": 5,
    "idle": 3,
    "done": 2,
    "error": 1,
    "stalled": 1
  },
  "alerts": [...],
  "idle_surfaces": ["3", "10", "11"],
  "error_surfaces": ["7"]
}
```

---

## 메인 에이전트 통합 패턴

### 패턴 A : 작업 배정 후 감시 (권장)

```
1. 메인: 5개 surface에 작업 배정 (cmux send)
2. 메인: watcher 백그라운드 실행
3. 메인: 다른 작업 진행 (결과 리뷰 등)
4. watcher: 스캔 완료 → 알림 반환
5. 메인: 알림 확인 → IDLE surface에 추가 작업 배정
6. 반복
```

### 패턴 B : 라운드 종료 전 최종 확인

```
1. 메인: 라운드 종료 판단 전
2. 메인: watcher --quick 실행 (포그라운드)
3. WORKING surface 남아있으면 → 대기
4. 모든 surface DONE/IDLE → 라운드 종료
```

### 패턴 C : 에러 자동 복구

```
watcher 알림: surface:7 ERROR
메인 자동 대응:
  1. cmux send --surface surface:7 '/new'
  2. sleep 5
  3. cmux send-key --surface surface:7 enter
  4. 해당 surface의 미완료 작업을 다른 surface에 재배정
```

---

## 메인 부팅 지원 (v3.3 — 와쳐가 메인 활성화)

> 사용자가 메인 surface에 `/cmux` 타이핑만 해두면 와쳐가 나머지 처리.

### 와쳐 세션 시작 시 자동 수행

```
1. detect-surface-models.py로 전 surface 스캔 (순차 + 스로틀)
2. 스캔 결과를 /tmp/cmux-surface-scan.json에 저장
3. /tmp/cmux-roles.json에 watcher 역할 등록
4. 메인 surface 화면에서 "/cmux" 또는 "❯" 대기 상태 감지
5. 감지되면:
   a. cmux send-key으로 Enter 쳐줌 (메인의 /cmux 발동)
   b. 메인 enforcer가 /tmp/cmux-surface-scan.json 읽음 → 재스캔 불필요
```

### 스캔 결과 공유 (MANDATORY)

```bash
ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"

# 1. 전 surface 스캔
SCAN=$(python3 "$ORCH_DIR/scripts/detect-surface-models.py" [자기surface번호])

# 2. 공유 파일에 저장 (메인이 읽을 수 있게)
python3 -c "
import json, sys
from datetime import datetime, timezone
surfaces = json.loads('''$SCAN''')
data = {
    'surfaces': surfaces,
    'scanned_by': 'watcher (surface:자기번호)',
    'scanned_at': datetime.now(timezone.utc).isoformat(),
}
open('/tmp/cmux-surface-scan.json','w').write(json.dumps(data, indent=2))
"
```

### Boss `/cmux` 감지 + 엔터

```bash
# Boss surface(role-register에서 boss로 등록된 surface)의 화면 확인
BOSS_SF=$(python3 -c "import json; r=json.load(open('/tmp/cmux-roles.json')); print(r.get('boss',{}).get('surface',''))" 2>/dev/null)

if [ -n "$BOSS_SF" ]; then
    BOSS_SCREEN=$(bash "$ORCH_DIR/scripts/read-surface.sh" "${BOSS_SF#surface:}" --lines 5)
    # "/cmux" 입력 대기 중이면 엔터 쳐줌
    if echo "$BOSS_SCREEN" | grep -q "/cmux"; then
        BOSS_WS=$(python3 -c "import json; r=json.load(open('/tmp/cmux-roles.json')); print(r.get('boss',{}).get('workspace',''))" 2>/dev/null)
        cmux send-key --workspace "$BOSS_WS" --surface "$BOSS_SF" enter
        sleep 3
        # Boss에게 스캔 결과 알림
        cmux notify --title "Watcher Ready" --body "스캔 완료. /tmp/cmux-surface-scan.json 참조." --workspace "$BOSS_WS"
    fi
fi
```

> 메인 enforcer(v8)는 `/tmp/cmux-surface-scan.json`이 2분 이내면 재스캔 생략 → 즉시 사용

## 핵심 규칙 (GATE)

| GATE | 규칙 | 설명 |
|------|------|------|
| W-1 | **IDLE Zero Tolerance** | IDLE 90초 초과 surface 발견 시 반드시 알림 |
| W-2 | **Error Immediate Alert** | ERROR/RATE_LIMITED 즉시 CRITICAL 알림 |
| W-3 | **Vision Verify IDLE** | IDLE 판정 시 ANE OCR로 이중 확인 (가능한 경우) |
| W-4 | **Cooldown Respect** | 동일 알림 쿨다운 기간 내 중복 발송 금지 |
| W-5 | **Action-Only Report** | 액션이 필요한 알림만 보고 (WORKING은 보고 안 함) |
| W-6 | **Boss Never Blocked** | watcher는 항상 백그라운드, 메인 작업 차단 금지 |

---

## 세션 시작 자동 로드 (Hook 통합)

> cmux-watcher는 세션 시작 시(대화 압축 후 재시작 포함) 자동으로 맥락을 주입한다.

### SessionStart Hook

`~/.claude/hooks/cmux-watcher-session.sh` 가 SessionStart 이벤트에서:
1. cmux 환경 감지 (`cmux identify` 성공 여부)
2. 감지되면 eagle 스캔 1회 실행 → 현재 상태 수집
3. additionalContext로 다음 정보 주입:
   - 활성 surface 수 + 각 상태 (W/I/D/E)
   - IDLE surface 목록 (즉시 작업 배정 필요)
   - ERROR surface 목록 (즉시 복구 필요)
   - cmux-watcher 스킬 사용 지침 리마인더

### 대화 압축 후에도 맥락 유지

대화가 압축(compact)되면 이전 맥락이 손실될 수 있다. Hook이 매 세션 시작마다 재주입하므로:
- 압축 후에도 cmux surface 상태를 즉시 인지
- IDLE surface 방치 없이 즉시 활용
- watcher 스킬 사용 강제 (잊어버림 방지)

### 메인 AI에 주입되는 메시지 형식

```
[CMUX-WATCHER] 세션 시작 상태:
- 전체: {N}개 surface | W:{n} I:{n} D:{n} E:{n}
- IDLE surfaces: {list} → 즉시 작업 배정 필요!
- ERROR surfaces: {list} → 즉시 복구 필요!
- 감시: python3 watcher-scan.py 또는 Agent(name="watcher") 백그라운드 실행 권장
- 스킬: Skill("cmux-watcher") 또는 Skill("cmux-orchestrator") 활용
```

---

## Active cmux Native Commands (v3.0 — 적극 활용)

Watcher는 감시에 cmux 고유 명령어를 적극적으로 사용한다.

### 감시용 명령어 (매 스캔 사용)

```bash
ORCH_DIR="$HOME/.claude/skills/cmux-orchestrator"

# ✅ 전체 surface 스캔 (필수 — 전 workspace + 스로틀 내장)
python3 "$ORCH_DIR/scripts/detect-surface-models.py" [자기surface번호]

# ✅ 개별 surface 읽기 (workspace 자동 해석)
bash "$ORCH_DIR/scripts/read-surface.sh" N --lines 8
bash "$ORCH_DIR/scripts/read-surface.sh" N --scrollback --lines 50

# 전체 구조 확인
cmux tree --all
cmux identify
```

**⛔ 금지:** `cmux read-screen` 직접 병렬 호출, `cmux surface-health` 단독, `tmux` 명령

### 사이드바 시각화 (상태 업데이트)

```bash
cmux set-status "watcher" "W:5 I:2 D:1 E:0" --icon "eye" --color "#00ff00" --workspace WS
cmux set-progress 0.7 --label "7/10 done" --workspace WS
cmux log --level warn --source "watcher" --workspace WS "surface:7 ERROR detected"
```

### 알림 (동료에게 전달)

```bash
cmux notify --title "WATCHER" --body "surface:7 DONE — ready for merge-judge" --workspace WS
cmux trigger-flash --workspace WS --surface SF                    # 시각적 깜빡임
cmux claude-hook notification --workspace WS --surface SF         # Hook 알림
```

### 복구용 명령어 (Boss 장애 시)

```bash
cmux send --workspace WS --surface SF "/compact"                  # Boss 복구
cmux send-key --workspace WS --surface SF enter                   # 키 전송
```

⛔ Watcher는 **감시/알림/복구 명령만** 사용. `cmux send "TASK: ..."` 형태의 작업 배정은 금지.

---

## 데이터 파일

| 파일 | 용도 | 생명주기 |
|------|------|---------|
| `/tmp/cmux-eagle-status.json` | Eagle 스캔 결과 | 매 스캔 갱신 |
| `/tmp/cmux-watcher-alerts.json` | 최신 알림 보고서 | 매 스캔 갱신 |
| `/tmp/cmux-watcher-history.jsonl` | 알림 이력 (쿨다운용) | 200줄 자동 트림 |
| `/tmp/cmux-vision-monitor-prev.json` | Vision 이전 상태 | 매 Vision 스캔 갱신 |
| cmux claude-hook session-start | 세션 시작 시 상태 주입 | SessionStart Hook 연동 |

---

## 사이드바 시각화 (v2.0 신규)

watcher 스캔 결과를 cmux 사이드바에 실시간 표시.

### 상태 표시

```bash
# 전체 상태 요약
cmux set-status "watcher" "W:5 I:2 D:1 E:0" --icon "eye" --color "#00ff00" --workspace WS

# 에러 발생 시 빨간색
cmux set-status "watcher" "E:2 ALERT" --icon "warning" --color "#ff0000" --workspace WS

# 진행률
cmux set-progress 0.7 --label "7/10 done" --workspace WS
```

### 이벤트 로깅

```bash
# 이벤트 기록
cmux log --level warn --source "watcher" --workspace WS "surface:7 ERROR detected"
cmux log --level info --source "watcher" --workspace WS "surface:3 DONE — ready for next task"

# 로그 확인
cmux list-log --limit 20 --workspace WS
```

### 알림

```bash
# CRITICAL 알림 (ERROR, RATE_LIMITED)
cmux notify --title "WATCHER ALERT" --body "surface:7 ERROR: API 529" --workspace WS
cmux trigger-flash --workspace WS --surface SF    # 시각적 깜빡임
```

---

## 스크립트 경로

```
~/.claude/skills/cmux-watcher/
├── SKILL.md                    # 이 파일
└── scripts/
    └── watcher-scan.py         # 통합 스캐너 (메인 실행 파일)

Hook (세션 자동 로드):
└── ~/.claude/hooks/cmux-watcher-session.sh  # SessionStart Hook

의존 (cmux-orchestrator 스킬):
├── eagle_watcher.sh            # 텍스트 기반 전체 스캔
├── eagle_analyzer.py           # 상태 분류 엔진
├── vision-monitor.sh           # ANE OCR 이중 검증
├── workspace-resolver.sh       # workspace 자동 해석
└── read-surface.sh             # 단일 surface 조회
```
