# 529 에러 방지 및 Circuit Breaker 패턴

## 529 vs 429 차이

| 코드 | 의미 | 원인 | 해결 |
|------|------|------|------|
| **429** | Rate limit exceeded | 분당/일당 토큰 한도 초과 | 대기 후 재시도 (Retry-After 헤더) |
| **529** | Overloaded | Anthropic 서버 자체 과부하 | 동시 요청 줄이기 + 백오프 |

529는 **서버 과부하**이므로 단순 대기로 안 풀림. **동시 요청 수 자체를 줄여야** 함.

## 근본 원인

- 서브에이전트 3개+ 동시 → 메인 포함 4개+ Opus/Sonnet API 동시 요청
- 각 에이전트가 도구 호출할 때마다 API 요청 추가 발생
- cmux 팀원(외부 AI)도 동시에 Anthropic API 사용 가능 (다른 Claude Code 인스턴스)
- **숨겨진 요인**: cmux의 다른 Claude surface도 동시 API 사용 → 계정 전체 rate limit 공유

## 방지 규칙

| 규칙 | 상세 |
|------|------|
| **서브에이전트 총합 2개 이하** | Boss 포함 총 API 동시 3개 (계정 통합 제한) |
| **Haiku도 같은 풀** | Haiku가 별도 쿼터가 아님! 모든 모델 합산 |
| **cmux send는 무료** | 외부 AI(Codex/Gemini/GLM) 전송은 API 부하 0 |
| **cmux surface의 다른 Claude도 계산** | surface:1,2가 Claude면 그것도 Opus API 사용 중! |

## Exponential Backoff + Jitter

529 발생 시 고정 대기가 아닌 **지수 백오프 + 랜덤 지터** 사용:

```python
import random, time

def retry_with_backoff(func, max_retries=5):
    """529/429 발생 시 지수 백오프 + 지터로 재시도."""
    for attempt in range(max_retries):
        try:
            return func()
        except OverloadedError:  # 529
            if attempt == max_retries - 1:
                raise
            base_delay = min(2 ** attempt, 60)  # 1, 2, 4, 8, 16... max 60초
            jitter = random.uniform(0, base_delay * 0.5)  # 0~50% 랜덤
            delay = base_delay + jitter
            print(f"529 detected, retry {attempt+1}/{max_retries} after {delay:.1f}s")
            time.sleep(delay)
```

## Circuit Breaker 패턴 (Half-Open State 포함)

연속 529 발생 시 3-상태 Circuit Breaker:

```
상태 전이:

  CLOSED (정상) ──529 2회──→ OPEN (차단)
       ↑                        │
       │                    60초 대기
       │                        ↓
       └──성공──→ HALF-OPEN (회복 중)
                    │
                    └──실패──→ OPEN + 120초 대기
```

```python
CIRCUIT = {
    "state": "CLOSED",      # CLOSED / OPEN / HALF_OPEN
    "failures": 0,
    "max_concurrent": 2,    # Boss 제외
    "cooldown_until": 0,
    "half_open_test_sent": False,
}

def on_529_error():
    CIRCUIT["failures"] += 1
    if CIRCUIT["failures"] >= 2:
        CIRCUIT["state"] = "OPEN"
        CIRCUIT["max_concurrent"] = 0  # 서브에이전트 전면 중단
        CIRCUIT["cooldown_until"] = time.time() + 60
        print("🛑 OPEN: 서브에이전트 중단, cmux send만 사용 (60초)")

def check_circuit():
    if CIRCUIT["state"] == "OPEN":
        if time.time() > CIRCUIT["cooldown_until"]:
            CIRCUIT["state"] = "HALF_OPEN"
            CIRCUIT["half_open_test_sent"] = False
            print("🟡 HALF-OPEN: 테스트 요청 1개 허용")
    if CIRCUIT["state"] == "HALF_OPEN" and not CIRCUIT["half_open_test_sent"]:
        CIRCUIT["half_open_test_sent"] = True
        return True  # 1개 테스트 요청 허용
    return CIRCUIT["state"] == "CLOSED"

def on_success():
    if CIRCUIT["state"] == "HALF_OPEN":
        CIRCUIT["state"] = "CLOSED"
        CIRCUIT["failures"] = 0
        CIRCUIT["max_concurrent"] = 2
        print("✅ CLOSED: 정상 복구, 서브에이전트 2개 허용")
```

## 안전한 동시 실행 조합

```
✅ 최안전: cmux send 4개 (0 API) + 메인(Opus) = Opus 1개만
✅ 안전:   cmuxeagle(haiku) + 메인(Opus) = API 2개 (별도 model rate limit)
✅ 안전:   cmuxeagle(haiku) + cmuxgit(haiku) + 메인(Opus) = 3개 (haiku 별도)
⚠️ 주의:   cmuxreview(Sonnet) + 메인(Opus) = 2개 — surface Claude 수에 따라 주의
❌ 위험:   cmuxreview(Sonnet) + cmuxplanner(sonnet) + cmuxeagle(haiku) + 메인 = 4개
❌ 금지:   3개+ Opus/Sonnet 서브에이전트 동시
```

## 529 발생 시 행동 프로토콜

```
1. 첫 529 → 5초 대기 → 재시도
2. 두번째 529 → 15초 대기 + 서브에이전트 1개로 축소 → 재시도
3. 세번째 529 → 60초 대기 + 서브에이전트 전면 중단 → cmux send만 사용
4. 5분 후 → 서브에이전트 1개 허용으로 복귀
5. 10분 후 → 정상 복귀 (최대 2개)
```

## 모델별 동시성 (계정 단위 통합)

> **딥 리서치 결과 (2026-03-18, 신뢰도 95%)**:
> Haiku/Sonnet/Opus 모두 **계정 단위 통합 제한** 사용.
> 모델별 독립 쿼터 없음 (GitHub #32254, #33154 확인).

| 상황 | 총 동시 API | 529 위험 |
|------|-----------|---------|
| Boss(Opus) 단독 | 1 | 없음 |
| Boss + Haiku 1 | 2 | 낮음 |
| Boss + Haiku 2 | 3 | **중간** |
| Boss + Haiku 2 + cmux Claude 2 | **5** | **높음** |
| Boss + Sonnet 1 + Haiku 1 | 3 | **중간** |

## 프로덕션 재시도 설정 (OpenClaw #24321 기반)

```python
RETRY_CONFIG = {
    "max_attempts": 3,       # 최대 재시도
    "min_delay_ms": 2000,    # 초기 대기 2초
    "max_delay_ms": 30000,   # 최대 대기 30초
    "jitter": 0.1,           # 10% 지터 (thundering herd 방지)
    "timeout_ms": 60000,     # 전체 타임아웃 60초
}
```

## 커뮤니티 검증 인사이트 (2026-03 조사)

**출처**: GitHub Issues #661, #29099 / Reddit r/ClaudeAI / Anthropic 공식 문서

1. **529 ≠ 429**: 429는 quota 초과(대기하면 풀림), 529는 서버 과부하(동시 요청 줄여야 함)
2. **Claude Code 자동 재시도 버그**: 일부 버전에서 529 자동 재시도가 깨짐 → 수동 재시도 필수
3. **피크 시간 회피**: 09:00-17:00 PST (한국 시간 02:00-10:00) 회피
4. **529 클러스터**: 5-30분간 지속 → 첫 529 후 바로 재시도하면 악화
5. **지터 필수**: 고정 간격 재시도는 동시 재시도 충돌(thundering herd) → 랜덤 지터 추가
6. **컨텍스트 팽창 주의**: PDF/큰 파일이 보이지 않게 컨텍스트 소비 → 사용률 6%에서도 limit 발생 가능
7. **최대 재시도 10회, 최대 대기 60초**: Perplexity/Reddit 합의

**핵심 교훈:**
1. cmux send(외부 AI)는 0 API — 이것이 가장 안전한 작업 위임 방법
2. **Haiku도 Opus와 같은 계정 풀 공유** — 별도 쿼터 아님
3. 서브에이전트 총합 2개 이하 (Boss 포함 3개) — 이것이 안전 한계
4. **Claude Code 자동 재시도 신뢰 금지** — Issue #661 미해결, 수동 구현 필수
