# Nudge/Escalation Policy

> 정본. 느린/멈춘/이탈한 세션에 대한 역할 기반 개입 정책을 정의한다.
> 원천: `referense/badclaude-main/`의 interrupt + follow-up prompt 패턴을 session-scoped 정책으로 재해석.

## 개요

cmux 오케스트레이션에서 Worker, Team Lead, Boss가 느리거나 지시를 이행하지 않을 때, 역할 권한 안에서 재촉/interrupt/재지시를 실행하는 정책이다.

badclaude의 Electron overlay/whip 상호작용은 직접 이식하지 않는다. cmux session ID 기반 메시지/interrupt API를 사용한다.

## 3단계 레벨

| 레벨 | 유형 | 설명 |
|------|------|------|
| L1 | 비중단 텍스트 재촉 | 존중형 문구로 상태 보고를 요청. workflow 중단 없음 |
| L2 | session-scoped interrupt + 재지시 | cmux session ID 기반으로 해당 pane에만 interrupt 전송 + 재지시 |
| L3 | 재분할/회수/재할당 제안 | Boss/JARVIS가 작업을 재분할하거나 다른 AI에 재할당을 제안 |

## 권한 매트릭스

| 대상 | 실행자 | 최대 레벨 | 조건 |
|------|--------|-----------|------|
| Worker | Team Lead | L2 | 같은 department workspace 안의 worker pane에만 |
| Team Lead | Boss | L2 | 해당 lead surface에만 |
| Boss | JARVIS | L2 | User/CEO 승인 또는 사전 정책에 따라. Boss surface에만 |
| Watcher | 없음 | - | evidence producer만. 실행 권한 없음 |

Watcher는 `STALLED`, `IDLE`, `instruction_drift`, `no_done_report`, `rate_limited` 근거를 생성할 수 있지만, nudge를 직접 실행하지 않는다.

> **구현 현황**: issuer 검증은 `ALLOWED_ISSUERS` set 기반 문자열 매칭 + `/tmp/cmux-roles.json` 기반 권한 매트릭스 검증 수행 (`jarvis_nudge.py:_validate_issuer_authority`). runtime role SSOT는 `roles["boss"]`이며 `roles["main"]`은 alias로 허용하지 않는다. 런타임 roles 파일이 있으면 미등록 issuer/target은 fail-closed, 파일이 없으면 ALLOWED_ISSUERS 검증만 적용한다.

## 트리거 조건

| 트리거 | 정의 | 기본 임계값 |
|--------|------|-------------|
| STALLED | 화면 고정 (Vision Diff 기준) | 8분 이상 |
| IDLE | DONE 후 재배정 없이 경과 | 5분 이상 |
| instruction_drift | 원래 작업과 현재 작업 불일치 | Watcher 또는 Boss 판정 |
| no_done_report | 예상 완료 시간 초과 | Boss 예측 대비 2배 |
| rate_limited | 외부 API rate limit으로 진행 불가 | Watcher 감지 |

## Cooldown/Throttle

| 레벨 | 같은 target cooldown | 동일 round 최대 |
|------|---------------------|----------------|
| L1 | 5분 | 제한 없음 |
| L2 | 15분 | 2회 |
| L3 | 30분 | 1회 |

cooldown 중 반복 요청은 `rate_limited` 이벤트로 기록되고 실행되지 않는다.

## Audit Event Schema

모든 nudge는 다음 필드를 가진 audit event를 남긴다:

```json
{
  "timestamp": "ISO-8601",
  "target_surface_id": "surface:N",
  "issuer_role": "team_lead|boss|jarvis",
  "reason_code": "STALLED|IDLE|instruction_drift|no_done_report|rate_limited",
  "evidence_span": "최근 N분간 관찰 요약",
  "level": "L1|L2|L3",
  "cooldown_until": "ISO-8601",
  "outcome": "sent|failed|rate_limited"
}
```

## 기본 문구

### L1 (비중단 재촉)

```
현재 {N}분간 진행 신호가 없습니다. 60초 안에 DONE, BLOCKED, NEEDS_INFO 중 하나로 보고하세요.
```

### L2 (interrupt + 재지시)

```
[INTERRUPT] 작업 "{task_description}"의 진행 상태를 즉시 보고하세요.
작업 컨텍스트: {context_summary}
현재까지 관찰된 상태: {observed_status}
```

### L3 (재할당 제안)

```
[ESCALATION] 작업 "{task_description}"이 {N}분간 진행되지 않았습니다.
제안: (1) 다른 AI에 재할당 (2) 작업 재분할 (3) 추가 대기
```

## Escalation Ladder

```
트리거 감지 → L1 재촉 → cooldown 경과 → L1 재시도
                                      → 응답 없음 → L2 interrupt
                                                  → cooldown 경과 → L3 제안
```

- L1 → L2 에스컬레이션: L1 후 지정 시간 안에 DONE/BLOCKED/NEEDS_INFO가 없을 때
- L2 → L3 에스컬레이션: L2 후 지정 시간 안에 응답이 없을 때
- L3은 Boss/JARVIS만 실행 가능

## 금지

- OS 전역 키 입력 (Cmd+C, Ctrl+C 매크로)
- focus stealing (다른 앱/윈도우 강제 포커스)
- 모욕적/위협적 문구
- 반복 spam (cooldown 무시)
- 감사 로그 없는 자동 개입
- 여러 pane/surface 동시 broadcast
- Watcher가 직접 실행

## Readiness Gate

| 레벨 | 상태 | 조건 |
|------|------|------|
| L1 | 즉시 가능 | 텍스트 메시지만 전송 |
| L2 | 조건부 | cmux session ID 기반 interrupt 경로 확인 후 |
| L3 | 보류 | Boss/JARVIS 재할당 workflow 구현 후 |

## SRP

Nudge/Escalation Policy는 **정책, 권한, throttle, audit event 정의만** 담당한다.

담당하지 않는 것:
- 작업 분해 → Boss/Team Lead
- 코드 수정 → Worker
- 멘토링 점수화 → Mentor Ontology
- 메모리 저장 → Palace Memory Adapter
- surface 상태 판정 → Watcher

## 참조

- Watcher 경계: `cmux-watcher/SKILL.md` GATE W-9
- 메트릭 임계값: `cmux-jarvis/references/metric-dictionary.json`
- 원천: `referense/badclaude-main/`
- Mentor Lane: [mentor-lane.md](mentor-lane.md)
