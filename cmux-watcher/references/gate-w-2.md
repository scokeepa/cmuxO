# GATE W-2 — Error / Rate-Limit Immediate Alert

`ERROR`, `RATE_LIMITED` 는 **쿨다운 무시하고 즉시 CRITICAL/HIGH 알림**.

## 감지 패턴 (eagle_watcher.sh)

| 패턴 | AI | 예시 |
|------|-----|------|
| `hit your limit` | Claude | "You've hit your limit · resets 3pm" |
| `rate limit` / `rate_limit` | 전체 | "RateLimitError: rate limit exceeded" |
| `429` | 전체 | "HTTP 429 Too Many Requests" |
| `quota exceeded`, `QuotaExceeded` | GLM/OpenAI | "Usage limit reached" |
| `too many requests` | 전체 | "Error: too many requests" |
| `insufficient balance` | OpenAI/GLM | 크레딧 부족 |
| `API Error 5\\d\\d` | 전체 | 529/500/503 등 |

## Watcher 행동 (Phase 1.4 이후)

1. `watcher-scan.py` 의 RATE_LIMITED 분기가 `rate_limit_pool.upsert_entry()` 호출
   → `/tmp/cmux-rate-limited-pool.json` 에 TTL 3600s entry 기록
2. CRITICAL/HIGH 알림 생성 + Boss `cmux notify`
3. reset 시간 추출 시도 (`reset in Xs`, `HH:MM:SS`)

## 쿨다운

| 상태 | 쿨다운 | 이유 |
|------|--------|------|
| ERROR | 2분 | 복구 소요 |
| RATE_LIMITED | 2분 | reset 대기 |
| BOSS_DEAD | 2분 | 복구 판정 재확인 |

## 관련 게이트

- Phase 1.4 rate_limit_pool — Watcher write + Boss dispatch precheck
- W-4 Cooldown Respect (쿨다운 내 중복 발송 금지)
