# Rate Limit 대응 레퍼런스

> SKILL.md Section 13 — GLM (ZhipuAI), Codex (OpenAI), MiniMax, Claude 등 AI 모델별 Rate Limit 감지 및 대응 프로토콜

## Rate Limit 감지

### GLM (ZhipuAI) — 429 에러

```
429 {"error":{"code":"1308","message":"Usage limit reached for 5 hour. Your limit will reset at YYYY-MM-DD HH:MM:SS"}}
```

### 其他 모델 공통

| 모델 | 에러 코드 | 증상 |
|------|----------|------|
| GLM-4.7 (ZhipuAI) | 429 / 1308 | "Usage limit reached for 5 hour" |
| Codex (OpenAI) | 429 | "Rate limit exceeded" |
| MiniMax | 429 | "Rate limit exceeded" |
| Claude (Anthropic) | 529 | "Too many requests" |

## 시간대 변환 (MANDATORY)

**리셋 시간은 CST (UTC+8, 중국 표준시) 기준.**

```bash
# CST → KST 변환 (CST + 1시간)
# 예: CST 19:27 → KST 20:27

# Python으로 리셋 시간 계산
python3 -c "
from datetime import datetime, timezone, timedelta

# CST 시간대 (UTC+8)
cst_tz = timezone(timedelta(hours=8))

# 리셋 시간 (CST)
reset_cst_str = '2026-03-25 19:27:00'
reset_cst = datetime.strptime(reset_cst_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=cst_tz)

# KST 변환 (UTC+9)
kst_tz = timezone(timedelta(hours=9))
reset_kst = reset_cst.astimezone(kst_tz)
now_kst = datetime.now(kst_tz)

diff = reset_kst - now_kst
print(f'리셋 KST: {reset_kst.strftime(\"%H:%M\")} (남은: {int(diff.total_seconds()//60)}분)')
"
```

## 대응 프로토콜

### 1단계: Rate Limit 감지

```bash
# 화면에서 rate limit 확인
cmux read-screen --surface surface:N --lines 20
# → "429" 또는 "rate limit" 또는 "Usage limit" 포함 확인
```

### 2단계: 리셋 시간 계산

```bash
# request_id 앞 14자리가 CST 타임스탬프
# 예: 20260325174809 = CST 2026-03-25 17:48:09

# KST 변환 (MANDATORY)
python3 -c "
from datetime import datetime, timezone, timedelta
reset_cst = datetime(2026, 3, 25, 19, 27, 0, tzinfo=timezone(timedelta(hours=8)))
reset_kst = reset_cst.astimezone(timezone(timedelta(hours=9)))
now_kst = datetime.now(timezone(timedelta(hours=9)))
diff = reset_kst - now_kst
print(f'리셋 KST: {reset_kst.strftime(\"%H:%M\")} (남은: {int(diff.total_seconds()//60)}분)')
"
```

### 3단계: 작업 재배정

```bash
# 해당 surface에 새 작업 배정 금지 (리셋까지)
# 미완료 작업이 있으면 → 다른 IDLE surface에 재배정

# 예: GLM-1이 rate limit → GLM-2에 미완료 작업 재배정
cmux send --surface surface:M "TASK: {rate limit surface의 미완료 작업}"
```

## 동일 API 키 공유 주의

| Surface 쌍 | 공유 키 | 주의사항 |
|------------|--------|----------|
| GLM-1 + GLM-2 | ZhipuAI 키 | 하나가 rate limit이면 둘 다 blocked |

**대응:**
- 한쪽 rate limit 발생 시 → 다른 GLM surface에도 즉시 작업 배정 중단
- 미완료 작업은 Claude 또는 다른 비차단 surface로 재배정

## 각 모델별 Rate Limit 특성

| 모델 | 시간대 | 리셋 주기 | 비고 |
|------|--------|----------|------|
| GLM-4.7 (ZhipuAI) | CST (UTC+8) | 5시간 | 중국 API — request_id 타임스탬프 |
| Codex (OpenAI) | UTC | 다양 | OpenAI API |
| MiniMax | CST (UTC+8) | 다양 | 중국 API |
| Claude (Anthropic) | UTC | 다양 | 529 에러 |

## Circuit Breaker 패턴

```python
# 529 에러 발생 시
circuit_breaker_state = "CLOSED"

if api_error == 529:
    if failure_count < 3:
        # 지수 백오프: 5s → 15s → 60s
        wait_time = 5 * (3 ** failure_count)
        sleep(wait_time)
        failure_count += 1
    else:
        circuit_breaker_state = "OPEN"
        # 60초 후 HALF-OPEN
        sleep(60)
        # 테스트 요청 1개
        if test_success:
            circuit_breaker_state = "CLOSED"
            failure_count = 0
```

## 차단 해제 후 복구

```bash
# rate limit 해제 확인
cmux read-screen --surface surface:N --lines 5
# → rate limit 메시지 없음 확인

# 복구 확인 후 해당 surface에 새 작업 배정
cmux send --surface surface:N "TASK: {작업}"
cmux send-key --surface surface:N enter
```

## 관련 레퍼런스

- `references/error-recovery.md` — 일반 에러 복구 프로토콜
- `references/circuit-breaker.md` — Circuit Breaker 상세 패턴
