# JARVIS Mentor Lane

> 정본. Mentor Lane의 역할, 입출력, SRP 경계를 정의한다.

## 역할

JARVIS Mentor Lane은 인간 사용자(CEO)의 **AI 협업 하네스 개선**을 돕는 조언 전용 레인이다.

기존 3레인 체계(Lane A 보고, Lane B 진화, Lane C 피드백)에 **Lane M(멘토)**을 추가한다.

| 레인 | 역할 | 실행 여부 |
|------|------|-----------|
| Lane A | 상태 보고, 질의 응답 | 즉시 응답 |
| Lane B | 시스템 설정 진화 | 6단계 파이프라인 |
| Lane C | 사용자 피드백 처리 | 즉시 반영 |
| **Lane M** | **사용자 지시 품질 개선 조언** | **soft intervention** |

## Evolution Lane과의 구분

| 기준 | Evolution Lane (B) | Mentor Lane (M) |
|------|-------------------|-----------------|
| 대상 | 시스템 config/hook/skill | 사용자의 지시 방식/검증 습관 |
| 실행 | 코드/설정 변경 | 조언 텍스트 생성 |
| 승인 | 2단계 구조화 승인 필수 | 승인 불필요 (무시 가능) |
| 산출물 | proposed-settings.json, evidence.json | coaching hint, weekly report |
| Iron Law | IL#1,#2,#3 전부 적용 | IL 적용 없음 (실행이 아님) |

## 원인 분류

반복 실패의 원인을 분류해서 적절한 레인으로 라우팅한다.

- **system config 원인** → Evolution Lane으로 전달
- **user instruction 원인** → Mentor Lane에서 조언 생성
- **복합 원인** → 사용자에게 "시스템 변경 vs 지시 방식 변경" 비교 제안

## 입력

- `user_instruction_submitted` 이벤트
- `boss_plan_created` 이벤트
- `lead_done_reported` 이벤트
- `review_failed`, `verification_failed` 이벤트
- `scope_changed`, `user_override` 이벤트

## 출력

- **coaching hint**: 매 orchestration round 최대 1~2개. 근거와 예상 효과를 함께 제시.
- **weekly report**: "AI 협업 하네스 개선 리포트" (사용자 등급표가 아님).
- **TIMELINE row**: 종단 추적용 행 업데이트.

## Context Injection 정책

`cmux-orchestrator/hooks/cmux-main-context.sh`를 통해 `/cmux` 입력 시 주입한다.

- L0(identity) + L1(essential story) 합산 **600~900 token** 이내
- 이번 round의 coaching hint **최대 1개**만 주입
- raw memory는 prompt에 직접 주입하지 않는다
- 사용자가 무시해도 workflow가 차단되지 않는다
- 같은 조언이 반복 spam되지 않도록 이전 round 조언을 비교한다

## 레인 분류 기준

1. 사용자의 메시지에 작업 지시가 포함되면 → Lane A 또는 B (기존)
2. Mentor signal이 생성되면 → Lane M이 다음 round hint를 준비
3. 사용자가 명시적으로 하네스 리포트를 요청하면 → Lane M이 report 생성
4. 5 orchestration rounds 또는 1주 중 먼저 도달하면 → Lane M이 정기 report 생성 (표본 부족 시 보류)

## SRP

Mentor Lane은 다음만 담당한다:

- 사용자 지시 품질 신호 분석 (Mentor Ontology 기반)
- 코칭 제안 텍스트 생성
- 학습 방향 제시
- reflection report 생성

Mentor Lane은 다음을 하지 않는다:

- 사용자의 승인권을 대체
- 심리/성격 진단
- 작업 중 일방적 차단
- config/hook/skill 변경 (Evolution Lane 영역)
- raw memory 저장/검색 (Palace Memory Adapter 영역)
- nudge/escalation 실행 (Nudge Controller 영역)
- scoring 정의 (Mentor Ontology 영역)

## 참조

- Evolution Lane: [evolution-pipeline.md](../pipeline/evolution-pipeline.md)
- Mentor Ontology: [mentor-ontology.md](mentor-ontology.md)
- Privacy Policy: [mentor-privacy-policy.md](mentor-privacy-policy.md)
- Context Injection: `cmux-orchestrator/hooks/cmux-main-context.sh`
