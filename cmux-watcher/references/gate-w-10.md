# GATE W-10 — IDLE 재배정 촉구 + Debounce

놀고 있는 surface 발견 시 Boss 에 **"다음 작업 배정하세요!"** 반드시 포함.
`surface-monitor.py` 와 `watcher-scan.py` 양쪽에서 강제.

## 보고 문구 (강제)

| 상황 | 문구 |
|------|------|
| Surface DONE 확정 | `DONE: s:N 완료 (M/N). s:N 지금 IDLE — 다음 작업 배정하세요!` |
| IDLE surface 감지 | `⚠️ IDLE 재촉: s:N 아직 놀고 있음! 작업 배정하세요!` |
| 전원 IDLE | `⚠️ ALL N DONE: 전부 완료! 즉시 결과 수집.` |

## Debounce (v4.1 — 2026-03-27 교훈)

Boss 가 dispatch 직후 와쳐가 재촉 → 노이즈 발생.

```python
IDLE_GRACE_PERIOD   = 30   # DONE 보고 후 30초 grace
IDLE_REMIND_INTERVAL = 120 # 동일 surface 재촉 최소 간격
```

규칙:
1. DONE 보고 직후 30초 해당 surface 재촉 금지 (Boss 재배정 중)
2. 동일 surface 는 2분 내 중복 재촉 금지
3. Grace 중인 surface 는 IDLE 카운트에서 제외

## 금지

- DONE 보고 후 "다음 작업 배정하세요" 생략
- IDLE 발견 후 조용히 넘어감
- "Boss 가 알아서 하겠지" 합리화
- DONE 1회 재촉 후 중단 (Boss 미응답 시 매 라운드 재촉 필수)
- Grace 무시하고 즉시 재촉

## 구현

`watcher-scan.py::_idle_debounce` dict + `append_alert_history` 타임스탬프 조합.

## 관련

- W-1 IDLE Zero Tolerance (90초 초과 시 알림)
- W-5 Action-Only Report — IDLE 재촉은 action 필수 알림
