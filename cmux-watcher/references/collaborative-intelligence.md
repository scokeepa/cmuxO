# Collaborative Intelligence Protocol (v1.0)

> Main(Orchestrator)과 Watcher(Sentinel) 간의 고급 협력 프로토콜 8가지.
> inter-peer-protocol.md의 메시지 유형을 확장한다.

---

## Gap 1 : DONE x2 Verified (Watcher가 DONE 프로토콜 검증)

### 문제
Main이 매번 `read-screen --scrollback --lines 20`으로 DONE x2, 5 blank lines를 직접 확인해야 함.

### 해결
Watcher가 DONE 감지 시 **프로토콜 검증**까지 수행하고, 검증 완료된 것만 보고.

### Watcher 행동
```
eagle 감지: "DONE" 키워드 발견
  → Watcher 추가 검증:
    1. cmux read-screen --scrollback --lines 20
    2. "DONE" 2회 존재 확인
    3. summary 텍스트 존재 확인
  → 검증 성공: [WATCHER→MAIN] DONE_VERIFIED: surface:7 완료, DONE x2 확인, summary 있음
  → 검증 실패: [WATCHER→MAIN] DONE_PARTIAL: surface:7 DONE 1회만 (프로토콜 미준수), scrollback 필요
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **DONE_VERIFIED** | DONE x2 + summary 확인 완료. Main이 바로 merge-judge 진행 가능 |
| **DONE_PARTIAL** | DONE 키워드 있지만 프로토콜 미충족. Main이 직접 확인 필요 |

### Main 행동 변경
```
기존: DONE 감지 → Main이 read-screen으로 직접 확인 → merge-judge
개선: DONE_VERIFIED 수신 → Main이 바로 merge-judge (검증 스킵)
     DONE_PARTIAL 수신 → Main이 read-screen으로 추가 확인
```

---

## Gap 2 : Shared Rate Limit Pool

### 문제
Watcher가 RATE_LIMITED 감지 → Main에 알림 (비동기). 알림 전달 전에 Main이 해당 surface에 배정할 수 있음.

### 해결
`/tmp/cmux-rate-limited-pool.json` 공유 파일. Watcher가 즉시 기록, Main이 배정 전 즉시 체크.

### 공유 파일 형식
```json
{
  "last_updated": "2026-03-27T14:30:00Z",
  "surfaces": {
    "7": {"since": "2026-03-27T14:25:00Z", "reset_at": "2026-03-27T14:35:00Z", "reason": "GLM 429"},
    "8": {"since": "2026-03-27T14:28:00Z", "reset_at": null, "reason": "insufficient_balance"}
  }
}
```

### Watcher 행동
```python
# Rate Limit 감지 즉시 파일에 기록 (SendMessage보다 빠름)
import json
from pathlib import Path
from datetime import datetime, timezone

variable_pool_file = Path("/tmp/cmux-rate-limited-pool.json")

def function_update_rate_pool(variable_surface: str, variable_reason: str, variable_reset_at: str = None):
    variable_pool = json.loads(variable_pool_file.read_text()) if variable_pool_file.exists() else {"surfaces": {}}
    variable_pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    variable_pool["surfaces"][variable_surface] = {
        "since": datetime.now(timezone.utc).isoformat(),
        "reset_at": variable_reset_at,
        "reason": variable_reason
    }
    variable_pool_file.write_text(json.dumps(variable_pool, indent=2))

def function_remove_from_pool(variable_surface: str):
    if not variable_pool_file.exists():
        return
    variable_pool = json.loads(variable_pool_file.read_text())
    variable_pool["surfaces"].pop(variable_surface, None)
    variable_pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    variable_pool_file.write_text(json.dumps(variable_pool, indent=2))
```

### Main 행동 (배정 전 체크)
```python
def function_is_rate_limited(variable_surface: str) -> bool:
    variable_pool_file = Path("/tmp/cmux-rate-limited-pool.json")
    if not variable_pool_file.exists():
        return False
    variable_pool = json.loads(variable_pool_file.read_text())
    return variable_surface in variable_pool.get("surfaces", {})
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **RATE_POOL_UPDATE** | Pool 파일 갱신됨 (알림용, 긴급이 아닌 경우) |

---

## Gap 3 : Worker Auto-Recovery (Watcher 직접 복구)

### 문제
Worker 에러 시 Watcher→Main 보고→Main 복구→Main 재배정으로 4단계. 지연 발생.

### 해결
간단한 에러(크래시, 컨텍스트 초과)는 Watcher가 직접 `/new` 전송 후 결과 보고.

### Watcher 자동 복구 범위

| 에러 유형 | Watcher 직접 복구 | Main 에스컬레이션 |
|----------|------------------|-----------------|
| API 크래시 (529, 502) | ✅ `/new` 전송 | ❌ |
| 컨텍스트 초과 | ✅ `/new` 전송 | ❌ |
| 완전 멈춤 (STALLED 5min+) | ✅ `/clear` 전송 | ❌ |
| Rate Limit | ❌ (pool에만 기록) | ✅ 재배정 필요 |
| 인증 실패 | ❌ | ✅ 설정 변경 필요 |
| 미지 에러 | ❌ | ✅ 판단 필요 |

### Watcher 복구 흐름
```bash
# 자동 복구 가능한 에러 감지 시:
# 1. /new 전송
cmux send --workspace "$WS" --surface "$SF" "/new"
cmux send-key --workspace "$WS" --surface "$SF" enter
sleep 5

# 2. 복구 확인
variable_screen=$(cmux read-screen --workspace "$WS" --surface "$SF" --lines 5)

# 3. 보고
if echo "$variable_screen" | grep -qE "❯|Type your message"; then
    # [WATCHER→MAIN] AUTO_RECOVERED: surface:8 API 529 → /new 복구 성공. 재배정 대기.
else
    # [WATCHER→MAIN] RECOVERY_FAILED: surface:8 /new 후에도 비정상. Main 개입 필요.
fi
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **AUTO_RECOVERED** | Watcher가 직접 복구 성공. Main은 재배정만 하면 됨 |
| **RECOVERY_FAILED** | Watcher 복구 실패. Main 에스컬레이션 필요 |

### ⛔ Watcher 복구 경계
- ✅ `/new`, `/clear`, escape 키 전송 — 허용
- ⛔ 작업 배정 (TASK: ...) — 금지 (Monitoring-Only 원칙)
- ⛔ git 명령 — 금지

---

## Gap 4 : Error Frequency Tracking (에러 빈도 추적)

### 문제
개별 에러만 감지. "surface:7이 30분간 3회 에러" 패턴을 모름.

### 해결
`/tmp/cmux-error-history.jsonl`에 에러 이력 저장. 빈도 분석 후 UNRELIABLE 판정.

### 데이터 형식
```jsonl
{"timestamp": "2026-03-27T14:25:00Z", "surface": "7", "type": "API_529"}
{"timestamp": "2026-03-27T14:30:00Z", "surface": "7", "type": "API_529"}
{"timestamp": "2026-03-27T14:45:00Z", "surface": "7", "type": "context_exceeded"}
```

### Watcher 분석 로직
```python
def function_check_error_frequency(variable_surface: str, variable_window_minutes: int = 30) -> dict:
    """최근 N분간 에러 빈도 분석"""
    # /tmp/cmux-error-history.jsonl 읽기
    # 해당 surface의 에러 카운트
    # 3회+ → UNRELIABLE 판정
    pass
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **UNRELIABLE** | surface가 30분간 3회+ 에러. Main이 배정 회피 권장 |
| **RELIABLE_AGAIN** | 에러 없이 30분 경과. 다시 신뢰 가능 |

### Main 행동
```
UNRELIABLE 수신 → 해당 surface를 배정 우선순위 최하위로
RELIABLE_AGAIN 수신 → 정상 배정 풀에 복귀
```

---

## Gap 5 : Task Queue Awareness (태스크 큐 인식)

### 문제
Watcher가 IDLE 보고 시 대기 작업 수를 모름. "IDLE인데 할 일도 없다" vs "IDLE인데 5개 작업 대기중" 구분 불가.

### 해결
Watcher가 speckit-tracker 상태 파일을 읽어 대기 작업 수를 포함하여 보고.

### speckit-tracker 상태 파일
```bash
# speckit-tracker.py가 생성하는 상태 파일
variable_tracker="/tmp/cmux-speckit-status.json"
# 형식: {"total": 10, "completed": 6, "in_progress": 2, "pending": 2}
```

### Watcher IDLE 보고 강화
```
기존: [WATCHER→MAIN] IDLE: surface:3,10 유휴 90초+
개선: [WATCHER→MAIN] IDLE_WITH_QUEUE: surface:3,10 유휴 90초+, 2 tasks pending
  또는
      [WATCHER→MAIN] IDLE_NO_QUEUE: surface:3,10 유휴 90초+, 0 tasks pending (라운드 종료 가능)
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **IDLE_WITH_QUEUE** | IDLE + 대기 작업 있음 → 즉시 배정 필요 |
| **IDLE_NO_QUEUE** | IDLE + 대기 작업 없음 → 라운드 종료 검토 가능 |

---

## Gap 6 : Round Lifecycle Awareness (라운드 단계별 감시)

### 문제
Watcher가 모든 단계에서 같은 강도로 감시. 비효율적.

### 해결
Main이 라운드 단계를 Watcher에 알려주면, Watcher가 단계에 맞게 감시 강도 조절.

### 단계별 감시 전략

| 라운드 단계 | Watcher 감시 초점 | 폴링 주기 | 이유 |
|-----------|-----------------|----------|------|
| **DISPATCH** | QUEUED, STUCK 감지 | 15초 | 배정 직후 반응 없으면 즉시 감지 |
| **WORKING** | STALLED, ERROR 감지 | 60초 | 정상 작업 중, 과도한 감시 불필요 |
| **COLLECTING** | DONE 감지 집중 | 30초 | 빠른 완료 수집 중요 |
| **MERGING** | Main 건강 체크만 | 120초 | Worker 비활성, Main 집중 필요 |
| **IDLE** | 전체 상태 | 60초 | 라운드 사이 |

### 메시지 흐름
```
Main: [MAIN→WATCHER] PHASE_CHANGE: DISPATCH (4 surfaces dispatched)
Watcher: 폴링 15초로 전환, QUEUED/STUCK 집중 감시

Main: [MAIN→WATCHER] PHASE_CHANGE: WORKING
Watcher: 폴링 60초로 전환, STALLED/ERROR 집중

Main: [MAIN→WATCHER] PHASE_CHANGE: COLLECTING
Watcher: 폴링 30초로 전환, DONE 감지 집중

Main: [MAIN→WATCHER] PHASE_CHANGE: MERGING
Watcher: 폴링 120초로 전환, Main 건강만 체크
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **PHASE_CHANGE** | Main이 라운드 단계 변경 알림 |
| **PHASE_ACK** | Watcher가 단계 변경 수신 확인 + 감시 전략 조절 |

---

## Gap 7 : Surface Performance Profile (성능 프로파일)

### 문제
모든 surface를 동일하게 취급. 어떤 surface가 빠르고 안정적인지 데이터 없음.

### 해결
Watcher가 각 surface의 성능 데이터를 축적하고 HEARTBEAT에 포함.

### 프로파일 데이터
```json
{
  "surface:2": {
    "model": "Codex",
    "avg_completion_time_min": 5.2,
    "error_rate_pct": 2.1,
    "tasks_completed": 15,
    "last_error": "2026-03-27T13:00:00Z",
    "reliability_score": 0.95
  },
  "surface:7": {
    "model": "GLM",
    "avg_completion_time_min": 8.1,
    "error_rate_pct": 15.3,
    "tasks_completed": 8,
    "last_error": "2026-03-27T14:25:00Z",
    "reliability_score": 0.62
  }
}
```

### 저장 경로
`/tmp/cmux-surface-profiles.json`

### Watcher 데이터 수집 시점
- DONE 감지 → 완료 시간 기록
- ERROR 감지 → 에러 횟수 증가
- 매 HEARTBEAT → reliability_score 재계산

### HEARTBEAT 확장
```
기존: [WATCHER→MAIN] HEARTBEAT: 12 surfaces | W:5 I:3 D:2 E:1 S:1
개선: [WATCHER→MAIN] HEARTBEAT: 12 surfaces | W:5 I:3 D:2 E:1 S:1 | best:surface:2(0.95) worst:surface:7(0.62)
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **SURFACE_PROFILE** | 특정 surface 성능 상세 (Main 요청 시) |

---

## Gap 8 : DONE Ready Preparation (완료 후 준비)

### 문제
DONE 확인 후 Main이 수동으로 `/clear` → sleep 5 → dispatch. 매번 30초+ 소요.

### 해결
Watcher가 DONE_VERIFIED 후 `/clear`까지 수행하고 "준비 완료" 보고. Main은 바로 dispatch만.

### Watcher 행동 (DONE_VERIFIED 후 자동 준비)
```bash
# DONE x2 검증 완료 후:
# 1. /clear 전송
cmux send --workspace "$WS" --surface "$SF" "/clear"
cmux send-key --workspace "$WS" --surface "$SF" enter
sleep 5

# 2. 프롬프트 표시 확인
variable_screen=$(cmux read-screen --workspace "$WS" --surface "$SF" --lines 3)
if echo "$variable_screen" | grep -qE "❯|Type your message"; then
    # [WATCHER→MAIN] DONE_READY: surface:7 완료 검증 + /clear 완료. 즉시 dispatch 가능.
else
    # [WATCHER→MAIN] DONE_VERIFIED: surface:7 완료 검증. /clear 실패 — Main 직접 처리.
fi
```

### 신규 메시지 유형

| TYPE | 의미 |
|------|------|
| **DONE_READY** | DONE 검증 + /clear 완료. Main은 바로 dispatch만 하면 됨 |

### Main 행동 변경
```
기존: DONE 감지 → read-screen → DONE 확인 → /clear → sleep 5 → dispatch (30초+)
개선: DONE_READY 수신 → 즉시 dispatch (0초)
```

### ⛔ 경계
- Watcher는 `/clear`만 전송 (surface 초기화)
- ⛔ 작업 프롬프트 전송 금지 (Monitoring-Only)
- DONE_READY 전송 후 Main이 배정하지 않으면 → 90초 후 IDLE로 재보고

---

## 전체 신규 메시지 유형 요약

### Watcher → Main (추가)

| TYPE | Gap | 의미 |
|------|-----|------|
| DONE_VERIFIED | 1 | DONE x2 프로토콜 검증 완료 |
| DONE_PARTIAL | 1 | DONE 있지만 프로토콜 미충족 |
| DONE_READY | 8 | DONE 검증 + /clear 완료, 즉시 dispatch 가능 |
| AUTO_RECOVERED | 3 | Watcher 직접 /new 복구 성공 |
| RECOVERY_FAILED | 3 | Watcher 복구 실패, Main 개입 필요 |
| UNRELIABLE | 4 | 30분간 3회+ 에러, 배정 회피 권장 |
| RELIABLE_AGAIN | 4 | 에러 없이 30분 경과, 복귀 |
| IDLE_WITH_QUEUE | 5 | IDLE + 대기 작업 있음 |
| IDLE_NO_QUEUE | 5 | IDLE + 대기 작업 없음 |
| SURFACE_PROFILE | 7 | Surface 성능 상세 |

### Main → Watcher (추가)

| TYPE | Gap | 의미 |
|------|-----|------|
| PHASE_CHANGE | 6 | 라운드 단계 변경 (DISPATCH/WORKING/COLLECTING/MERGING) |

### Watcher → Main (기존, 유지)
DONE, IDLE, ERROR, STALLED, RATE_LIMITED, WAITING, RECOVERED, HEARTBEAT, MAIN_DOWN

### Main → Watcher (기존, 유지)
ACK, DISPATCH, RECOVER, PAUSE, RESUME, SCAN, SHUTDOWN

---

## 공유 파일 요약

| 파일 | 관리자 | 소비자 | 용도 |
|------|--------|--------|------|
| `/tmp/cmux-roles.json` | role-register.sh | Both | 역할 등록 + 하트비트 |
| `/tmp/cmux-rate-limited-pool.json` | Watcher | Main (읽기) | Rate limit 즉시 동기화 |
| `/tmp/cmux-error-history.jsonl` | Watcher | Watcher (분석) | 에러 빈도 추적 |
| `/tmp/cmux-surface-profiles.json` | Watcher | Main (읽기) | Surface 성능 프로파일 |
| `/tmp/cmux-speckit-status.json` | speckit-tracker | Watcher (읽기) | 대기 작업 수 |
| `/tmp/cmux-eagle-status.json` | eagle_watcher | Both | Surface 상태 |
| `/tmp/cmux-peer-messages.log` | Both | Both | 메시지 이력 |
