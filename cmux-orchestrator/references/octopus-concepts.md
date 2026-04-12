# Claude Octopus — Cherry-picked Concepts for cmux-orchestrator

> Source: github.com/nyldn/claude-octopus v9.6.0 (MIT, 1,584 stars)
> Date: 2026-03-19
> Integration: REFERENCE only (아키텍처 비호환으로 직접 설치 불가)

## 1. Consensus Gate (합의 게이트)

멀티AI 결과물의 품질을 보장하는 메커니즘.

**원리:**
- 3개 AI 프로바이더 중 75% 이상 동의해야 결과 확정
- 불일치 시 추가 토론 라운드 자동 진행
- 최종 합의 실패 시 사용자에게 에스컬레이션

**cmux 적용 방안:**
```
현재: Codex 보고서 + GLM팀 보고서 → Opus 수동 종합
개선: 2/3 합의 규칙 도입
  - 보고서 2개가 동일 이슈 지적 → 자동 확정
  - 1개만 지적 → Opus가 추가 검증 후 판단
  - 0개 지적 → PASS (단, 커버리지 확인)
```

## 2. Provider Routing Strategy (프로바이더 라우팅)

프로바이더를 자동 선택하는 3가지 전략.

**전략:**
| 모드 | 로직 | 사용 시점 |
|------|------|----------|
| round-robin | 순차 순환 | 기본 (균등 부하) |
| fastest | 레이턴시 기반 | 속도 우선 |
| cheapest | 비용 기반 | 예산 절약 |

**핵심 구현 (provider-router.sh):**
- metrics-session.json에서 프로바이더별 평균 레이턴시/비용 추적
- `select_fastest_provider()`: 후보 중 최저 레이턴시 선택
- 파일 기반 상태 관리 (크로스 프로세스 영속)

**cmux 적용 방안:**
```
현재: 난이도 기반 수동 배정 (상급→Codex, 중하급→GLM)
개선: surface별 응답 시간 메트릭 수집
  - cmux capture-pane 시간 기록
  - 동일 난이도 태스크 → 가장 빠른 surface에 배정
  - 에러율 높은 surface → 자동 회피
```

## 3. Context Awareness Hook (컨텍스트 인식)

워크플로우 중 컨텍스트 사용률을 모니터링하여 경고.

**임계값:**
| 사용률 | 심각도 | 행동 |
|--------|-------|------|
| 65% | WARNING | "현재 단계 마무리 후 /compact 권장" |
| 75% | CRITICAL | "즉시 /compact 필요. 현재 작업만 완료하세요" |
| 80% | AUTO_COMPACT | 자동 /compact 트리거 |

**구현 특징:**
- PostToolUse 이벤트에서 발동
- 5 tool call마다 디바운스 (플러딩 방지)
- 심각도 에스컬레이션은 디바운스 무시
- 워크플로우 단계별 맞춤 조언

**cmux 적용 방안:**
```
현재: 서브에이전트 /compact 불가, 작업량 조절만
개선: Boss Agent용 컨텍스트 모니터링
  - Wave 완료 시점에 컨텍스트 잔량 체크
  - 70%+ → 남은 태스크를 cmux 팀원에 더 위임
  - 80%+ → /compact 후 작업 재개
```

## 4. Double Diamond Workflow (4단계 워크플로우)

구조화된 4단계 문제 해결 프레임워크.

**단계:**
```
Discover(probe) → Define(grasp) → Develop(tangle) → Deliver(ink)
  발산→수렴         수렴→정의        발산→솔루션       수렴→배달
```

**각 단계별 에이전트 배정:**
| 단계 | Primary | Support |
|------|---------|---------|
| Discover | researcher | ai-engineer, business-analyst |
| Define | backend-architect | frontend, database, cloud |
| Develop | implementer | tdd-orchestrator, debugger |
| Deliver | code-reviewer | security-auditor, test-automator |

**cmux 적용 방안:**
```
대규모 프로젝트 시:
1. Discover: search-worker들로 병렬 조사
2. Define: Opus가 spec 작성 + Codex 리뷰
3. Develop: cmux surface들에 구현 분배
4. Deliver: Codex + GLM팀 품질검사
```

## 5. Dark Factory (자율 파이프라인)

스펙 → 소프트웨어 자율 생산 파이프라인.

**흐름:**
```
Spec Parse → Scenario Gen → Embrace(4단계) → Holdout Test → Score → Report
```

**핵심 개념 — Holdout Testing:**
- 전체 시나리오의 25%를 블라인드 테스트로 예약
- 구현 AI가 holdout 시나리오를 모른 상태에서 개발
- 완료 후 holdout으로 일반화 능력 검증
- 4차원 점수: 기능/품질/보안/성능

**cmux 적용 방안:**
```
auto-orchestrate에 holdout 개념 추가:
- TASKS.md에서 일부 태스크를 검증용으로 예약
- 구현 완료 후 예약 태스크로 회귀 테스트
- 합격률로 전체 품질 판단
```
