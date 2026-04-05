# Evolution Worker 프로토콜

> 정본. Worker 통신/제약을 참조할 때 이 파일 링크.

## Worker 생성
```bash
cmux new-workspace --command "claude"  # 별도 workspace (컨트롤탭 보존)
WORKER_SID 획득
/tmp/cmux-jarvis-worker-{PID} 마커 파일 생성
```

## 지시 전달
```bash
cmux set-buffer --name evo-001 "[DAG + Scope Lock + expected outcomes]"
cmux paste-buffer --name evo-001 --surface $WORKER_SID
cmux send-key --surface $WORKER_SID enter
```

## Worker 제약 (E4: jq 배열 덮어쓰기 방지)
- proposed-settings.json에 **hooks 키 포함 금지** (기존 hooks 전부 삭제됨)
- proposed에 배열 키 포함 시 → Outbound Gate에서 REJECT
- 변경은 **스칼라/객체 키만** 허용 (배열은 Phase 2 재귀 merge 후)

## Worker 출력
```
evolutions/evo-XXX/
├── proposed-settings.json   # 변경 제안 (hooks 키 금지!)
├── file-mapping.json        # 제안→실제 경로 매핑
├── 05-tdd.md                # TDD 또는 expected outcomes
├── 07-expected-outcomes.md  # settings_change 시
└── STATUS                   # 완료 보고
```

## STATUS 파일 스키마
```json
{
  "evo_id": "evo-001",
  "evolution_type": "settings_change | hook_change | skill_change | code_change | mixed",
  "phase": "implementing | completed | failed",
  "status": "DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT",
  "tests_written": 0,
  "tests_passed": 0,
  "tests_failed_before_fix": 0,
  "expected_outcomes_documented": true,
  "test_file_paths": [],
  "proposed_changes_path": "evolutions/evo-001/proposed-settings.json"
}
```

## 완료 감지 (3중 — JARVIS block 안 됨)
1. **플래그 파일:** `/tmp/cmux-jarvis-evo-001-done` → JARVIS 다음 턴에서 ls 체크
2. **Watcher 중계:** STATUS.phase=completed → Watcher가 JARVIS에 cmux send
3. **claude-hook stop:** Worker pane 종료 → jarvis-worker-done.sh → STATUS 체크

## evolution_type별 검증
| 유형 | 필수 체크 |
|------|----------|
| settings_change | expected_outcomes_documented == true |
| hook/skill/code | tests_failed_before_fix > 0 |
| mixed | 양쪽 모두 |

## Circuit Breaker
- Worker PID 사망 + TTL 미초과 → respawn-pane 재시도 1회
- 2회 실패 → DISCARD + 롤백

## 정리
```bash
cmux close-workspace --workspace $WORKER_WS
rm /tmp/cmux-jarvis-worker-{PID}
rm /tmp/cmux-jarvis-evo-*-done
```
