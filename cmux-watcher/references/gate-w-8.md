# GATE W-8 — 핵심 행동 사이클

> **이 사이클을 어기면 와쳐 존재 의미가 없다. `watcher-scan.py` 가 강제 실행.**

## 5-단계 사이클

```
┌─ 1. SCAN: 4계층 풀스캔 (eagle + OCR + VisionDiff + pipe-pane)
│
├─ 2. NOTIFY: Boss 에 cmux send + enter
│           (DONE 1개 확정될 때마다 즉시 개별 보고)
│
├─ 3. READ: Boss 화면 읽기 (3초 대기 후 read-surface)
│     → Boss WORKING?               → 감시 계속 (60초 간격)
│     → Boss IDLE (사용자 질문 중)?  → 느린 폴링 (120초)
│     → Boss IDLE + workers IDLE?   → 대기 모드 (120초)
│     → Boss WORKING + workers IDLE → 빠른 감시 (15초, 배정 시작 감지)
│
├─ 4. WAIT: adaptive interval 대기
│
└─ 5. LOOP: 1 번으로 돌아감
```

## Adaptive Polling 표 (v4.0)

| Boss 상태 | 팀원 상태 | 폴링 간격 | 이유 |
|-----------|----------|----------|------|
| WORKING | WORKING | 60s | 정상 감시 |
| IDLE | WORKING | 30s | 곧 완료 가능 |
| IDLE | ALL IDLE | 120s | 모두 대기 |
| WORKING | ALL IDLE | 15s | 배정 시작 감지 |

## 라운드 단계별 폴링 (Collaborative Intelligence)

| Boss PHASE | 폴링 | 감시 초점 |
|-----------|-----|----------|
| DISPATCH | 15s | QUEUED, STUCK |
| WORKING | 60s | STALLED, ERROR |
| COLLECTING | 30s | DONE 집중 |
| MERGING | 120s | Boss 건강 |

## 금지 행동

- SCAN 만 하고 NOTIFY 생략
- NOTIFY 만 하고 READ 생략 (Boss 반응 무시)
- READ 후 "대기 중" 보고만 하고 폴링 안 함

## 상태 기록

`/tmp/cmux-watcher-state.json` 에 `boss_state`, `interval`, `timestamp` 기록.

## 관련

- W-9 개입 금지 — 사이클 중 surface 에 직접 명령 금지
- W-10 IDLE 재배정 촉구 — DONE/IDLE 감지 시 Boss 에 재배정 요청 강제
