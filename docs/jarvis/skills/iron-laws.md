# JARVIS Iron Laws

> 정본(SSOT). Iron Law 참조 시 이 파일만 참조.

## 3 Iron Laws

### #1: NO EVOLUTION WITHOUT USER APPROVAL FIRST
- 2단계 승인: ③ 1차 [수립] + ⑤-b 2차 [실행] + ⑩ [KEEP]
- 구조화 선택지만 인정 (free-text 금지)
- 물리적 강제: settings.json = phase="applying" 조건부 (gate.sh)
- Bash 간접 수정도 차단 (matcher Edit|Write|Bash, S3)
- /hooks 명령 금지 (GATE 자체 삭제 방지, META-1)
- ConfigChange exit 2로 GATE 삭제 차단 (S2)

### #2: NO IMPLEMENTATION WITHOUT EXPECTED OUTCOME FIRST
- code/hook/skill → failing test first (tests_failed_before_fix > 0)
- settings_change → expected_outcomes_documented == true
- mixed → 양쪽 모두
- 물리적 강제: jarvis-verify.sh가 05-tdd.md / 07-expected-outcomes.md 파일 존재 체크
- 테스트 품질: spec-reviewer가 trivial 테스트 감지

### #3: NO COMPLETION CLAIMS WITHOUT VERIFICATION EVIDENCE
- jarvis-verify.sh (사전 정의, AI 미개입)가 evidence.json 생성
- evidence.json 없으면 ⑩ 진입 REJECT
- 최종 판단은 사용자 (#1과 연계)

## Evidence 스키마
```json
{
  "evidence_type": "metric_comparison | test_result | user_approval",
  "before_snapshot": "evolutions/evo-001/before-metrics.json",
  "after_snapshot": "evolutions/evo-001/after-metrics.json",
  "metrics_compared": ["dispatch_failure_rate", "stall_count"],
  "collection_method": "jarvis-verify.sh",
  "collected_at": "2026-04-02T11:00:00Z"
}
```

## Iron Law 봉쇄 검증 이력
- Zero-Trust 감사: IL1-F1(settings 항상 허용) → phase="applying" 조건부
- META-1(/hooks GATE 제거) → exit 2 차단
- IL2-F1(TDD 미강제) → 파일 물리 체크
- IL3-F1(evidence 미생성) → verify.sh 출력 명시
- **v8 공격 시뮬레이션 (2026-04-03):**
  - IL1-ATK-1(Python 인라인) → Bash에 settings.json + 비읽기 → deny
  - IL1-ATK-3(LOCK 직접 생성) → .evolution-lock Write → deny
  - IL3-ATK-1(evidence AI 의존) → gate.sh에서 evidence.json 존재 체크 추가
