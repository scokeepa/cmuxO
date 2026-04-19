# GATE W-7 — 질문 금지

Watcher 는 **사용자에게 질문하지 않는다**. 모든 판단은 자동.

## 절대 묻지 않는 것

- "연속 감시 모드를 시작할까요?" → **금지.** 자동 시작
- "어떤 작업을 배정할까요?" → **금지.** 와쳐는 작업 배정 안 함
- "모니터링 루프를 시작할까요?" → **금지.** `watcher-scan.py --continuous` 강제
- "DONE 감지했는데 clear 할까요?" → **금지.** Boss가 판단

## 허용되는 대화

- Boss 와 의 peer-to-peer 프로토콜 (`[WATCHER→BOSS] TYPE: ...`)
- cmux notify (passive notification)

## 구현 수단

- `cmux-send-guard.py` (Phase 1.2) — Watcher role 에 대해 `/new`·`/clear` 차단
- `activation-hook.sh` — 자동 실행, 사용자 prompt 없음
- SKILL.md 프론트매터 `trigger: watcher 세션 시작 / scan 주기`

## 관련

- W-9 개입 금지 — 질문뿐 아니라 명령 전송도 차단
- W-6 Boss Never Blocked — 사용자 interaction 자체를 배제
