# JARVIS 진화 파이프라인

> 정본. 파이프라인 단계를 참조할 때 이 파일 링크.

## 3가지 트리거
1. **FileChanged hook** — eagle-status/watcher-alerts 변경 즉시 (S7, 디바운싱 60초, 토큰 0)
2. **Watcher cmux send** — STALL 3회+ 시 JARVIS에 직접 알림
3. **initialUserMessage** — 세션 시작 시 자동 감지 (S5)

## 3레인 분류
- **Lane A:** 보고/질의 → 즉시 응답 (진화 안 함)
- **Lane B:** 진화 실행 → 파이프라인 진입
- **Lane C:** 피드백 → [feedback-loop.md](feedback-loop.md) 참조

## 11단계 파이프라인 (Phase 1: 6단계 실행, 나머지 수동)

```
① 감지 → Inbound Gate (데이터 무결성) → 3레인 분류
    ├ 무한 루프 체크 (MAX_CONSECUTIVE/DAILY/동일영역)
    ├ CURRENT_LOCK 확인 (있으면 큐 추가)
    ↓
② 분석 → 근본 원인 + 메트릭 사전 + North Star + Scope Lock
    ↓
③ 1차 승인 → [수립][보류][폐기] + AGENDA_LOG 기록
    ↓
④ 백업 → 원자적(tmp→rename) + 3중(로컬+git, 모드A:+Obsidian) + LOCK(TTL 60분) + /freeze
    ↓
⑤ 계획 → DAG + 위상 정렬 + evolution_type 결정
    ↓
⑤-b 2차 승인 → diff 표시 → [실행][수정][폐기] → TTL 리셋
    ↓ Execution Gate (GATE 5단계)
⑥ 검증 → 스펙 준수 → 품질 ("Do Not Trust the Report")
    ↓
⑦ TDD → code=failing test, settings=expected outcome
    ↓
⑧ 구현 → Worker pane (제안만, 적용 금지) → [worker-protocol.md](worker-protocol.md)
    ↓
⑨ E2E → jarvis-verify.sh (사전 정의, AI 미개입) → evidence.json 생성
    ↓ (실패 → ⑤ 순환, 진화당 최대 2회. 2회 → DISCARD)
⑩ Before/After → evidence.json 필수 → 사용자 [KEEP][DISCARD]
    ↓
⑪ 반영 → JSON Patch(jq deep merge, 원자적) → LOCK 해제 → Outbound Gate
    → 옵티미스틱 승격 + 문서 저장
```

## Watcher ↔ JARVIS 경계
- **Watcher(소방관):** 실시간 감시 + 즉시 대응 (escape/interrupt), 설정 안 건드림
- **JARVIS(건축가):** 패턴 분석 + 근본 해결 (설정 변경 진화)
- STALL 1회 → Watcher만. STALL 3회 → JARVIS 트리거
- ERROR → Watcher 즉시 대응 + JARVIS에 알림(학습용). JARVIS는 재발 방지 진화만
- ENDED/IDLE → JARVIS 진화 대상 (auto-cleanup 설정)
- Watcher 대응 상태 확인: watcher-alerts.json의 surface별 alerts 읽기 (V7-03)
