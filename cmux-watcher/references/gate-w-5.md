# GATE W-5 — Action-Only Report

**액션이 필요한 알림만** Boss에 보고. WORKING 상태는 보고하지 않는다.

## 보고 대상

| 상태 | 우선순위 | 보고 시점 |
|------|---------|----------|
| BOSS_DEAD | CRITICAL | 즉시 |
| ERROR | CRITICAL | 즉시 |
| RATE_LIMITED | HIGH | 즉시 |
| STALLED | HIGH | 즉시 |
| STUCK_PROMPT | HIGH | 즉시 |
| WAITING | HIGH | 즉시 |
| DONE | HIGH | 즉시 (Boss가 즉시 재배정) |
| IDLE | MEDIUM | 90초 후 |
| WORKING | — | **보고 안 함** |

## 이유

- Boss가 노이즈로 흐려지지 않도록 action-required 만 전달
- WORKING 확인은 Boss가 read-surface 로 직접 조회 가능

## 구현

`watcher-scan.py::generate_alerts()` 가 상태별 priority 부여. `WORKING` 상태는 `alerts.append` 자체를 건너뛴다.
