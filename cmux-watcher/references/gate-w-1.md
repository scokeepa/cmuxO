# GATE W-1 — IDLE Zero Tolerance

IDLE 90초 초과 surface 발견 시 **반드시 Boss에 알림**.

## 판정 기준

- 마지막 화면 변화 이후 경과시간이 90초 초과
- `eagle_analyzer.py`가 IDLE로 분류 + `vision-monitor.sh` OCR에서도 IDLE 확인
- `›` 뒤에 입력 없음 (STUCK_PROMPT 제외)

## 보고 형식

```
[WATCHER→BOSS] IDLE: s:N 유휴 {seconds}초 — 즉시 작업 배정!
```

IDLE 쿨다운은 90초 (과잉 알림 방지, Phase 1.4 이후 rate-limit pool과 교차 검사).

## 관련 게이트

- W-5 Action-Only Report — WORKING은 보고하지 않음
- W-10 IDLE 재배정 촉구 debounce (DONE grace 30s, 재촉 2분 간격)
