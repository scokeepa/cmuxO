# Orchestrator Architecture

> 정본. Boss/Boss의 역할, 디스패치 프로토콜, 수집/리뷰/커밋 흐름을 정의한다.

## 역할

Boss는 컨트롤 타워의 중심이다.

- 작업 분석 + 부서 편성
- 팀장에게만 지시 (팀원 직접 배정 금지)
- DONE 취합 + 리뷰 Agent 위임
- 최종 커밋

## Department = Workspace 구조

```
Department (sidebar tab = workspace)
├── Team Lead (lead surface)
│   ├── Worker pane 1 (같은 workspace 내)
│   ├── Worker pane 2
│   └── Worker pane N
```

- Team Lead가 worker 생성, 로컬 AI/모델 선택, 난이도별 배정
- Boss는 Team Lead만 상대

## 디스패치 프로토콜

1. Boss가 작업을 분석하고 부서 수를 결정
2. `cmux new-workspace`로 department workspace 생성
3. `cmux send --surface {lead}` + `cmux send-key enter`로 팀장에게 지시
4. Team Lead가 `cmux split-pane`으로 worker 생성
5. Worker는 독립적으로 작업 실행

## 수집 프로토콜

1. Watcher가 worker DONE 감지 → Boss에 알림
2. Boss가 `cmux capture-pane`으로 결과 수집
3. 리뷰 Agent (Sonnet) 위임
4. LECEIPTS 5-섹션 보고서 작성
5. `git commit` (LECEIPTS gate 통과 필수)

## SRP

Boss는 다음을 하지 않는다:
- Worker pane 직접 작업 배정 (Team Lead 역할)
- Watcher 역할 수행 (감시/알림)
- JARVIS 진화 직접 구현 (Evolution Lane 역할)

## 참조

- 세부 프로토콜: `cmux-orchestrator/SKILL.md`
- 디스패치 패턴: `cmux-orchestrator/references/dispatch-templates.md`
- Gate: `cmux-orchestrator/references/gate-matrix.md`
