# Mentor Ontology

> 정본. AI 협업 하네스 개선 신호의 측정 기준을 정의한다.
> 원천: `referense/vibe-sunsang-main/agents/growth-analyst.md` 6축 모델을 cmux 오케스트레이션 용어로 변환.

## 6축 기술 차원

cmux 오케스트레이션에서 사용자의 AI 협업 하네스 품질을 6개 독립 축으로 관찰한다.

| 코드 | 차원 | cmux 정의 | 관찰 대상 |
|------|------|-----------|-----------|
| DECOMP | 작업 분해 | 요구사항을 부서/팀장/작업 단위로 분해할 수 있을 만큼 명확한가 | Boss plan의 부서 수, 작업 단위 크기, 모호함 |
| VERIFY | 검증 전략 | 테스트, 리뷰, 근거, 재현 조건, 완료 기준을 요구하는가 | review_failed, verification_failed 빈도, 완료 기준 유무 |
| ORCH | 오케스트레이션 | 단일 AI, 부서 분할, 병렬 worker, JARVIS 진화 중 적절한 것을 구분하는가 | 불필요한 부서 생성, 단일 AI로 충분한 작업의 과분할 |
| FAIL | 실패 대응 | 오류 원인 분석, 대안 탐색, 재시도 조건, rollback 판단이 있는가 | 같은 오류 반복, "고쳐줘" 패턴, rollback 없이 반복 시도 |
| CTX | 맥락 관리 | 파일 경로, 제약 조건, 배경, acceptance criteria가 있는가 | 컨텍스트 누락 빈도, Boss가 보충 질문하는 횟수 |
| META | 메타인지 | 사용자가 자기 지시 방식과 하네스를 점검하고 개선하려 하는가 | 하네스 리포트 요청, 피드백 수용, 지시 방식 변경 |

6축은 독립적이다. 사용자가 DECOMP L5, VERIFY L2일 수 있다.

## Workspace Type

cmux 오케스트레이션 프로젝트의 기본 workspace type은 **Builder + Operator 혼합**이다.

| 차원 | Builder 가중치 | Operator 가중치 | cmux 기본 (혼합) |
|------|---------------|----------------|-----------------|
| DECOMP | 25% | 15% | 20% |
| VERIFY | 25% | 20% | 22% |
| ORCH | 15% | 25% | 20% |
| FAIL | 15% | 20% | 18% |
| CTX | 10% | 10% | 10% |
| META | 10% | 10% | 10% |

ORCH/VERIFY/FAIL 가중치를 일반 코딩보다 높인다. AGI 오케스트레이션에서는 도구 조합, 검증, 실패 대응이 핵심이기 때문이다.

## Harness Level

user-facing 명칭은 **Harness Level**이다. vibe-sunsang의 레벨명(Observer, Tinkerer 등)은 내부 alias로만 유지하고 공식 노출하지 않는다.

| 레벨 | 단계 | 설명 |
|------|------|------|
| L1.0~L1.5 | 수동 | AI에게 결과만 요청. 검증/분해 없음 |
| L2.0~L2.5 | 능동 | 기본적인 분해와 맥락 제공 시작 |
| L3.0~L3.5 | 전환 | 파일/함수 수준 구체성. 검증 행동 시작 |
| L4.0~L4.5 | 주도 | 검증 필수. 실패 시 원인 분석. 전략적 분해 |
| L5.0~L5.5 | 설계 | 도구/에이전트 전략적 조합. AI의 80% 한계 인식 |
| L6.0~L6.5 | 통합 | 멀티에이전트 경험. 시스템 수준 하네스 설계 |
| L7.0 | 확장 | 커뮤니티/산업 기여. 외부 확산 |

레벨 표시는 0.5 단위로 반올림한다. 내부 추적은 소수점 2자리까지 허용한다.

## Gate 조건 (승급 필수 조건)

| 레벨 | 조건 | 근거 |
|------|------|------|
| L3 진입 | context_specificity > 0.5 | 파일/함수 수준 구체성 필수 |
| L4 진입 | verification > 0.15 AND correction > 0.05 | 검증 행동 필수 |
| L5 진입 | (tool_diversity > 8 OR orchestration) AND strategic > 0.05 | 도구 + 전략적 사고 필수 |
| L6 진입 | multi_agent_experience OR orch_count > 10 | 멀티에이전트 경험 필수 |
| L7 진입 | L6 통과 + 외부 기여 증거 | 커뮤니티/산업 기여 필수 |

상위 레벨 판정은 **최근 5개 세션 중 3개 이상**에서 반복 관찰될 때만 허용한다.

## Fit Score 공식

```
F_L = SUM(w_i * S_i)  for i in {DECOMP, VERIFY, ORCH, FAIL, CTX, META}
```

- `w_i`: workspace type별 가중치
- `S_i`: 차원 i의 fit score (0.0~1.0)
- 반올림: x.00~x.24 → x.0, x.25~x.74 → x.5, x.75~x.99 → (x+1).0

## 안티패턴 (cmux 변환)

| 안티패턴 | 약한 축 | cmux 맥락 |
|----------|---------|-----------|
| "고쳐줘" 반복 | FAIL | 오류 메시지를 읽지 않고 "고쳐줘"만 반복 |
| 컨텍스트 생략 | CTX | 파일 경로, 제약 조건 없이 작업 지시 |
| 검증 생략 | VERIFY | AI 결과를 리뷰 없이 수용 |
| 과분할 | ORCH | 단일 AI로 충분한 작업을 불필요하게 부서 분할 |
| 범위 확장 | META | 작업 중간에 범위를 계속 넓힘 |
| 단일 소스 의존 | VERIFY | AI 답변만 신뢰, 교차 검증 없음 |
| 이해 없는 수용 | META | 코드가 작동하지만 이유를 모름 |

## 분석 방식

- **window**: 최근 5~10개 user instruction 또는 최근 1~3개 orchestration round
- **detrend**: 전체 평균 대비 최근 window의 방향성
- **lag**: 사용자 지시 변화가 다음 1~3 round의 재작업률에 미치는 영향
- **predicted-vs-actual**: Boss plan 예측 vs 실제 DONE/rework/error
- **confidence**: 표본 수, 관찰 기간, 이벤트 누락 여부를 함께 기록
- **calibration**: 실제 outcome이 예상과 어긋나면 다음 advice confidence를 낮춤

## 금지

- 사용자의 성격, 정신상태, 능력을 단정하지 않는다
- 단일 메시지로 장기 패턴을 결론내리지 않는다
- raw conversation을 대량으로 prompt에 주입하지 않는다
- 표본 부족 시 레벨/패턴을 확정하지 않고 "insufficient evidence"를 표시한다

## SRP

Mentor Ontology는 **scoring 기준 정의만** 담당한다.

담당하지 않는 것:
- raw log 저장 → Palace Memory Adapter
- 검색 → Palace Memory Adapter
- hook injection → cmux-main-context.sh
- JARVIS 진화 적용 → Evolution Lane
- report 렌더링 → Mentor Report Pipeline
- nudge 실행 → Nudge/Escalation Controller

## 참조

- Mentor Lane: [mentor-lane.md](mentor-lane.md)
- 원천: `referense/vibe-sunsang-main/agents/growth-analyst.md`
