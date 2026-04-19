# GATE W-4 — Cooldown Respect

동일 alert_key 가 쿨다운 내이면 **중복 발송 금지**.

## 쿨다운 표

| 상태 | 쿨다운 | 이유 |
|------|--------|------|
| BOSS_DEAD | 2분 | 복구 시도 후 재판단 |
| ERROR | 2분 | 복구에 시간 소요 |
| RATE_LIMITED | 2분 | reset 대기 |
| STALLED | 5분 | 원래 5분 기준 |
| WAITING | 1분 | 빠른 응답 필요 |
| DONE | 30초 | 즉시 재배정 (짧게) |
| IDLE | 90초 | 유휴 허용 한계 |

## 구현

`cmux-watcher/scripts/watcher-scan.py::is_cooldown_active(alert_key, history, seconds)` + `append_alert_history()`.
히스토리 파일: `/tmp/cmux-watcher-history.jsonl`.

## 예외

RATE_LIMITED 은 쿨다운 활성 시에도 `rate_limit_pool` upsert 는 수행 (Phase 1.4).
pool 기록은 dispatch 차단용 데이터이므로 alert 쿨다운과 무관.
