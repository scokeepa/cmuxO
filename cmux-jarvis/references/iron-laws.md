# JARVIS Iron Laws

## #1: NO EVOLUTION WITHOUT USER APPROVAL FIRST
- 2단계 승인: 1차 [수립] + 2차 [실행] + 최종 [KEEP]
- 구조화 선택지만 인정 (free-text 금지)
- 물리적 강제: gate.sh → LOCK+phase+evidence 3조건

## #2: NO IMPLEMENTATION WITHOUT EXPECTED OUTCOME FIRST
- code/hook/skill → tests_failed_before_fix > 0 + 05-tdd.md 존재
- settings_change → expected_outcomes_documented + 07-expected-outcomes.md 존재
- mixed → 양쪽 모두

## #3: NO COMPLETION CLAIMS WITHOUT VERIFICATION EVIDENCE
- jarvis-verify.sh가 evidence.json 생성 (AI 미개입)
- evidence.json 없으면 반영 거부 (gate.sh 물리 체크)
- 최종 판단은 사용자 (Iron Law #1)
