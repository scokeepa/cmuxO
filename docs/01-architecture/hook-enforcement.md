# Hook Enforcement Architecture

> 정본. 31개 hook의 4-tier 강제 체계와 gate matrix를 통합 정의한다.
> 원천: 기존 `hooks/hook-map.md` + `hooks/gate-logic.md` + `hooks/session-lifecycle.md` 통합.

## 설계 원칙

모든 31개 hook은 `/cmux-start` 전까지 **비활성**. 일반 Claude Code 사용에 간섭 없음.

## 이벤트별 분류

| Event | 수량 | 용도 | 강제 수준 |
|-------|------|------|-----------|
| PreToolUse | 15 | 도구 실행 전 차단 | L0 Physical Block |
| PostToolUse | 4 | 실행 후 모니터링 | L2 Warning |
| UserPromptSubmit | 3 | 프롬프트 전 context 주입 | L2 |
| SessionStart | 3 | 세션 초기화 | L1 |
| Stop | 1 | 종료 정리 | L1 |
| FileChanged | 1 | 파일 변경 감지 (JARVIS) | Trigger |
| ConfigChange | 1 | settings.json 보호 | L0 |
| Pre/PostCompact | 2 | context 압축 시 보존 | Info |

## 4-Tier 강제 체계

| Tier | 메커니즘 | 예시 |
|------|----------|------|
| **L0: Physical Block** | PreToolUse hook이 도구 실행 차단 | 미검증 `git commit` 차단 |
| **L1: Auto-execute** | 이벤트 시 자동 스크립트 실행 | Eagle status refresh |
| **L2: Warning** | systemMessage로 경고 주입 | 3+ IDLE surfaces 알림 |
| **L3: Self-check** | SKILL.md 체크리스트 | GATE 0-7 round 종료 전 |

## Gate Matrix (L0 Blocks)

| Gate | 규칙 | Hook |
|------|------|------|
| GATE 0 | 수집 완료 전 커밋 금지 | `cmux-completion-verifier.py` |
| GATE 6 | IDLE surface → Agent 금지 | `cmux-gate6-agent-block.sh` |
| GATE 7 | IDLE worker → Boss 직접 작업 금지 | `cmux-gate7-main-delegate.py` |
| CT | Control tower 종료 금지 | `cmux-control-tower-guard.py` |
| LECEIPTS | 5-섹션 보고서 필수 | `cmux-leceipts-gate.py` |
| PLAN-QG | 5관점 검증 + 시뮬레이션 | `cmux-plan-quality-gate.py` |
| WF | 워크플로 상태 머신 | `cmux-workflow-state-machine.py` |

## JARVIS GATE J-1

- settings.json: LOCK + phase=applying + evidence 3조건만 Write 허용
- Bash: 읽기 전용만 settings.json 접근 허용
- .evolution-lock: 직접 Write 금지 (jarvis-evolution.sh만)

## 세부 참조

- gate.sh 전체 로직: [gate-logic.md](gate-logic.md)
- hook 등록 맵: [hook-map.md](hook-map.md)
- 세션 라이프사이클: [session-lifecycle.md](session-lifecycle.md)
