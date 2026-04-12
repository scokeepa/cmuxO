# JARVIS 피드백 루프

> 정본. 피드백 채널/처리 방식을 참조할 때 이 파일 링크.

## 4채널

### CH1: JARVIS → 사용자 (능동 보고)
| 방식 | cmux API | 언제 |
|------|----------|------|
| 사이드바 상태 | `cmux set-status` | 항상 |
| 즉시 알림 | `cmux notify` | 중요 이벤트 |
| 승인 요청 | AskUserQuestion | 진화 결정 |
| 시각화 보고 | Mermaid + ASCII | 진화 결과 |
| AGENDA_LOG | 파일 쓰기 | 모든 결정 |

### CH2: 사용자 → JARVIS (지시 + 피드백)
- 자연어 대화 (Lane A)
- 구조화 승인 ([수립][보류][폐기])
- 피드백 5유형 (아래 참조)
- 직접 지시 ("X를 Y로 바꿔")

### CH3: 오케스트레이션 → JARVIS (자동 수집)
- FileChanged hook (eagle-status/watcher-alerts)
- Watcher cmux send (STALL/ERROR)
- ConfigChange hook (설정 외부 변경)

### CH4: JARVIS → 오케스트레이션 (능동 제어)
- JSON Patch (⑪ 반영)
- Boss에 cmux send (하네스 추천, 재배정)
- cmux set-status (실시간)

## 피드백 5유형 처리

| 유형 | 키워드 | 처리 |
|------|--------|------|
| **긍정** | "좋았어" "잘했어" | importance +1 → 2회+ 시 승격 |
| **부정** | "별로야" "롤백해" | DISCARD + importance -2 → 2회+ 시 무효화 |
| **방향** | "이쪽으로" "더 해" | followup 큐 추가 + Scope Lock 업데이트 |
| **금지** | "하지 마" | Red Flags 영구 등록 + GATE 규칙 추가 |
| **질문** | "왜?" | Lane A → 진화 문서 참조 응답 |

## 옵티미스틱 승격
1. 감지 → short-term knowledge 기록
2. 사용자에게 cmux notify 알림
3. 사용자 개입 → 즉시 중지 + 롤백
4. 무개입 → 승격 완료
5. `{날짜}_{주제}.md` 문서 보존

## 보류 재감지 (deferred-issues.json)
- 재감지 시 단순 재제안 대신 **예측 A/B 보고서**
- [이번에 수립] [다시 보류] [영구 무시]
- deferred_count ≥ 3 → AGENDA_LOG만 기록
