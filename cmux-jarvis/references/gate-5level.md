# GATE 5단계 판정 기준

| GATE | permissionDecision | 조건 | 동작 |
|------|--------------------|------|------|
| ALLOW | "allow" | 허용 경로 내 Write/Edit, 읽기 전용 Bash | 무조건 통과 |
| WARN | "allow" + stderr | /freeze 중 사용자 설정 변경 | 경고 표시 + 실행 |
| HOLD | "ask" | 근거 부족, CRITICAL 설정 변경 | Claude Code 승인 UI 표시 |
| BLOCK | "deny" | 금지 경로, /hooks 시도, out_of_scope, hooks 키 포함 | 즉시 거부 + 로그 |
| ESCALATE | "deny" + cmux notify | 반복 BLOCK, 보안 위협, 연속 실패 | 거부 + 사용자 알림 |

## HOLD 트리거 조건
- CURRENT_LOCK 없는데 settings.json 수정 시도 (진화 외 변경)
- evolution_type="mixed" 진화의 첫 실행
- 이전 진화에서 롤백된 동일 영역 재변경

## BLOCK 트리거 조건
- settings.json Write/Edit (LOCK 없음 또는 phase≠applying 또는 evidence 없음)
- .evolution-lock 직접 Write/Edit
- Bash로 settings.json 비읽기 명령
- proposed에 hooks 키 포함
- Worker가 evolutions/ 외부 Write
- 금지 경로 (/tmp/cmux-orch-enabled, cmux-start, cmux-pause 등)
