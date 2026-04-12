# Security Architecture

> 정본. cmux orchestrator의 8대 보안 메커니즘을 정의한다.

## 보안 매트릭스

| 메커니즘 | 구현 | 방어 대상 |
|----------|------|-----------|
| Injection 방지 | `shlex.quote()`, `shell=True` 금지 | Shell metachar 공격 |
| 원자적 백업 | backup-then-copy (덮어쓰기 금지) | settings.json 손상 |
| 이중 강제 | SKILL.md 규칙 + PreToolUse hook | 비인가 config 변경 |
| ConfigChange 차단 | `exit 2`로 수정 차단 | GATE hook 삭제 |
| LOCK 3-조건 | LOCK + phase=applying + evidence | 위조된 진화 시도 |
| CT guard | shlex 토큰 분석, `close-workspace`만 대상 | Boss/Watcher 종료 |
| 역할 필터링 | `cmux identify` + roles.json | 세션 간 간섭 |
| 모드 게이트 | `/cmux-start` 전 31 hooks 비활성 | 비-오케스트레이션 간섭 |

## Mentor Lane 보안

| 메커니즘 | 구현 | 방어 대상 |
|----------|------|-----------|
| 자동 redaction | `mentor_redactor.py` 5패턴 | API key/password/token 유출 |
| raw 저장 OFF | `mentor.raw_capture_enabled` opt-in 전용 | 무단 대화 기록 |
| 토큰 예산 | L0+L1 합산 3600 chars 제한 | Context 과부하 |
| Watcher 실행 차단 | `jarvis_nudge.py` issuer 검사 | 권한 없는 nudge |
| Cooldown | target별 5분 rate limit | Nudge spam |
| Audit trail | `nudge-audit.jsonl` 전 건 기록 | 추적 불가 개입 |
