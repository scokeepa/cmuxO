# Inter-Peer Communication Protocol (v2.0)

> Boss(cmux-orchestrator)과 Watcher(cmux-watcher) 간의 공식 소통 규약.
> 사용자 프롬프트와 AI 간 소통을 100% 구분하기 위한 표준 형식.

## 핵심 원칙

```
사용자 → AI:    일반 텍스트 (접두사 없음)
AI ↔ AI:       [SENDER→RECEIVER] TYPE: content
```

**사용자가 보내는 메시지에는 `[X→Y]` 접두사가 없으므로, 이 패턴이 있으면 AI 간 소통임을 즉시 인식.**

---

## 메시지 형식

```
[{ROLE}→{ROLE}] {TYPE}: {content}
```

| 필드 | 값 | 설명 |
|------|-----|------|
| ROLE | `BOSS`, `WATCHER` | 발신/수신 역할 |
| TYPE | 아래 표 참조 | 메시지 유형 |
| content | 자유 텍스트 | 상세 내용 |

---

## Watcher → Boss 메시지 유형

| TYPE | 우선순위 | 의미 | 예시 |
|------|---------|------|------|
| **DONE** | HIGH | Surface 작업 완료 감지 | `[WATCHER→BOSS] DONE: surface:7 완료, DONE x2 확인됨` |
| **IDLE** | MEDIUM | Surface 유휴 (90초+) | `[WATCHER→BOSS] IDLE: surface:3,10,11 유휴 90초+` |
| **ERROR** | CRITICAL | 에러/크래시 감지 | `[WATCHER→BOSS] ERROR: surface:8 API 529 overloaded` |
| **STALLED** | HIGH | 화면 변화 없음 (Vision Diff) | `[WATCHER→BOSS] STALLED: surface:4 30초 변화 없음` |
| **RATE_LIMITED** | HIGH | Rate limit 감지 | `[WATCHER→BOSS] RATE_LIMITED: surface:7,8 GLM 429, reset 14:30` |
| **WAITING** | HIGH | 사용자 입력 대기 중 | `[WATCHER→BOSS] WAITING: surface:5 [Y/n] 프롬프트 감지` |
| **RECOVERED** | LOW | 에러 surface 복구 확인 | `[WATCHER→BOSS] RECOVERED: surface:8 정상 복귀` |
| **HEARTBEAT** | INFO | 주기 상태 요약 | `[WATCHER→BOSS] HEARTBEAT: 12 surfaces \| W:5 I:3 D:2 E:1 S:1` |
| **BOSS_DOWN** | CRITICAL | Boss 하트비트 실패 | `[WATCHER→BOSS] BOSS_DOWN: 하트비트 2분+ 없음, /compact 시도` |

### v2.0 추가 — Collaborative Intelligence 메시지

| TYPE | 우선순위 | 의미 | 예시 |
|------|---------|------|------|
| **DONE_VERIFIED** | HIGH | DONE x2 프로토콜 검증 완료 | `[WATCHER→BOSS] DONE_VERIFIED: surface:7 DONE x2 확인, summary 있음` |
| **DONE_PARTIAL** | HIGH | DONE 있지만 프로토콜 미충족 | `[WATCHER→BOSS] DONE_PARTIAL: surface:7 DONE 1회만` |
| **DONE_READY** | HIGH | DONE 검증 + /clear 완료 | `[WATCHER→BOSS] DONE_READY: surface:7 즉시 dispatch 가능` |
| **AUTO_RECOVERED** | MEDIUM | Watcher 직접 /new 복구 성공 | `[WATCHER→BOSS] AUTO_RECOVERED: surface:8 API 529 → /new 성공` |
| **RECOVERY_FAILED** | HIGH | Watcher 복구 실패 | `[WATCHER→BOSS] RECOVERY_FAILED: surface:8 /new 후 비정상` |
| **UNRELIABLE** | MEDIUM | 30분간 3회+ 에러 | `[WATCHER→BOSS] UNRELIABLE: surface:7 30분 3회 에러, 배정 회피 권장` |
| **RELIABLE_AGAIN** | LOW | 에러 없이 30분 경과 | `[WATCHER→BOSS] RELIABLE_AGAIN: surface:7 복귀` |
| **IDLE_WITH_QUEUE** | MEDIUM | IDLE + 대기 작업 있음 | `[WATCHER→BOSS] IDLE_WITH_QUEUE: surface:3, 2 tasks pending` |
| **IDLE_NO_QUEUE** | LOW | IDLE + 대기 작업 없음 | `[WATCHER→BOSS] IDLE_NO_QUEUE: surface:3, 라운드 종료 가능` |
| **SURFACE_PROFILE** | INFO | Surface 성능 상세 | `[WATCHER→BOSS] SURFACE_PROFILE: surface:2 avg:5.2min err:2.1% score:0.95` |

## Boss → Watcher 메시지 유형

| TYPE | 의미 | 예시 |
|------|------|------|
| **ACK** | 알림 확인 + 처리 완료 | `[BOSS→WATCHER] ACK: surface:7 DONE 확인, 다음 작업 배정 완료` |
| **DISPATCH** | 새 작업 배정 알림 | `[BOSS→WATCHER] DISPATCH: surface:3에 JWT 구현 배정, 모니터링 시작` |
| **RECOVER** | 복구 조치 수행 알림 | `[BOSS→WATCHER] RECOVER: surface:8에 /new 전송, 복구 확인 요청` |
| **PAUSE** | 특정 surface 모니터링 중지 | `[BOSS→WATCHER] PAUSE: surface:7,8 rate limited, 모니터링 일시 중지` |
| **RESUME** | 모니터링 재개 | `[BOSS→WATCHER] RESUME: surface:7,8 reset 완료, 모니터링 재개` |
| **SCAN** | 즉시 스캔 요청 | `[BOSS→WATCHER] SCAN: 전체 surface 즉시 상태 확인 요청` |
| **SHUTDOWN** | Watcher 종료 요청 | `[BOSS→WATCHER] SHUTDOWN: 라운드 완료, 감시 종료` |
| **PHASE_CHANGE** | 라운드 단계 변경 | `[BOSS→WATCHER] PHASE_CHANGE: COLLECTING (4 surfaces dispatched)` |

---

## 전달 메커니즘

### 1. SendMessage (in-context — 기본)

AI 간 Agent 백그라운드 통신에 사용:

```python
# Watcher → Boss (SendMessage)
SendMessage(to="boss", message="[WATCHER→BOSS] DONE: surface:7 완료")

# Boss → Watcher (SendMessage)
SendMessage(to="watcher", message="[BOSS→WATCHER] ACK: surface:7 확인")
```

### 2. cmux notify (알림 패널 — CRITICAL만)

```bash
# CRITICAL 이벤트만 cmux notify 사용 (사용자도 볼 수 있음)
cmux notify --title "[WATCHER→BOSS]" --body "ERROR: surface:8 API 529" --workspace WS
```

### 3. cmux log (이력 기록 — 모든 메시지)

```bash
# 모든 메시지를 cmux log에 기록 (post-mortem 분석용)
cmux log --level info --source "watcher" --workspace WS "[WATCHER→BOSS] DONE: surface:7"
cmux log --level warn --source "watcher" --workspace WS "[WATCHER→BOSS] ERROR: surface:8 API 529"
cmux log --level info --source "boss" --workspace WS "[BOSS→WATCHER] ACK: surface:7 확인"
```

### 4. /tmp 파일 (비동기 — 폴링 기반)

```bash
# Watcher가 알림 파일에 기록
echo '[WATCHER→BOSS] DONE: surface:7' >> /tmp/cmux-peer-messages.log

# Boss가 폴링으로 읽기
tail -n 5 /tmp/cmux-peer-messages.log
```

---

## 메시지 우선순위 + 전달 방식

| 우선순위 | TYPE | 전달 방식 |
|---------|------|----------|
| **CRITICAL** | ERROR, RATE_LIMITED, BOSS_DOWN | SendMessage + cmux notify + cmux log |
| **HIGH** | DONE, STALLED, WAITING | SendMessage + cmux log |
| **MEDIUM** | IDLE | SendMessage + cmux log |
| **LOW** | RECOVERED, ACK | cmux log만 |
| **INFO** | HEARTBEAT, DISPATCH | cmux log만 |

---

## 수신 측 행동 규약

### Boss가 Watcher 메시지를 받았을 때

```
[WATCHER→BOSS] DONE: surface:7
→ Boss 행동:
  1. cmux read-screen으로 결과 확인
  2. Merge-Judge (Sonnet 서브에이전트) 트리거
  3. [BOSS→WATCHER] ACK: surface:7 확인, merge-judge 진행 중

[WATCHER→BOSS] IDLE: surface:3,10
→ Boss 행동:
  1. 태스크 큐에서 다음 작업 추출
  2. cmux send로 배정
  3. [BOSS→WATCHER] DISPATCH: surface:3에 새 작업 배정

[WATCHER→BOSS] ERROR: surface:8 API 529
→ Boss 행동:
  1. cmux send surface:8 "/new" + enter
  2. 해당 surface 미완료 작업을 다른 IDLE surface에 재배정
  3. [BOSS→WATCHER] RECOVER: surface:8에 /new 전송, 복구 확인 요청

[WATCHER→BOSS] STALLED: surface:4
→ Boss 행동:
  1. cmux read-screen --scrollback --lines 50으로 정밀 조사
  2. 원인 파악 → /clear 또는 재배정
  3. [BOSS→WATCHER] RECOVER: surface:4 정밀 조사 후 /clear + 재배정
```

### Watcher가 Boss 메시지를 받았을 때

```
[BOSS→WATCHER] DISPATCH: surface:3에 새 작업 배정
→ Watcher 행동:
  1. surface:3 모니터링 활성화 (IDLE → WORKING 전환 확인)
  2. 10초 내 WORKING 전환 안 되면 → [WATCHER→BOSS] STALLED: surface:3 배정 후 반응 없음

[BOSS→WATCHER] PAUSE: surface:7,8
→ Watcher 행동:
  1. surface:7,8을 PAUSED 상태로 마킹
  2. 해당 surface 알림 생성 중지

[BOSS→WATCHER] RESUME: surface:7,8
→ Watcher 행동:
  1. surface:7,8 PAUSED 해제
  2. 정상 모니터링 재개 + 즉시 1회 스캔

[BOSS→WATCHER] SCAN: 즉시 스캔
→ Watcher 행동:
  1. watcher-scan.py --quick 즉시 실행
  2. 결과를 [WATCHER→BOSS] HEARTBEAT로 전달

[BOSS→WATCHER] SHUTDOWN:
→ Watcher 행동:
  1. 모니터링 루프 정상 종료
  2. 최종 상태 보고 후 종료
```

---

## 메시지 파싱 (Python)

```python
import re

variable_peer_pattern = re.compile(
    r'^\[(?P<sender>BOSS|WATCHER)→(?P<receiver>BOSS|WATCHER)\]\s+'
    r'(?P<type>[A-Z_]+):\s*(?P<content>.*)$'
)

def function_parse_peer_message(variable_text: str) -> dict | None:
    """AI 간 소통 메시지 파싱. 사용자 메시지는 None 반환."""
    variable_match = variable_peer_pattern.match(variable_text.strip())
    if not variable_match:
        return None  # 사용자 메시지 (접두사 없음)
    return {
        "sender": variable_match.group("sender"),
        "receiver": variable_match.group("receiver"),
        "type": variable_match.group("type"),
        "content": variable_match.group("content"),
        "is_peer_message": True
    }

# 사용 예시
msg1 = "[WATCHER→BOSS] DONE: surface:7 완료"
msg2 = "이 파일을 수정해줘"

result1 = function_parse_peer_message(msg1)
# → {"sender": "WATCHER", "receiver": "BOSS", "type": "DONE", "content": "surface:7 완료", "is_peer_message": True}

result2 = function_parse_peer_message(msg2)
# → None (사용자 메시지)
```

---

## 사용자 구분 규칙

| 메시지 출처 | 형식 | 예시 |
|-----------|------|------|
| 사용자 → Boss | 접두사 없음 | "이 파일 수정해줘" |
| 사용자 → Watcher | 접두사 없음 | "surface:3 상태 알려줘" |
| **Watcher → Boss** | `[WATCHER→BOSS]` | `[WATCHER→BOSS] DONE: surface:7` |
| **Boss → Watcher** | `[BOSS→WATCHER]` | `[BOSS→WATCHER] ACK: surface:7` |

**⛔ 사용자는 `[X→Y]` 접두사를 사용하지 않으므로, 이 패턴이 감지되면 100% AI 간 소통.**
**⛔ AI는 사용자에게 응답할 때 `[X→Y]` 접두사를 사용하지 않는다.**
