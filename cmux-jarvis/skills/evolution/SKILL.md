---
name: cmux-jarvis-evolution
description: "JARVIS 진화 파이프라인 6단계 실행"
user-invocable: false
classification: workflow
---

# 진화 파이프라인 (Phase 1: 6단계)

이 스킬은 JARVIS 코어에서 Lane B(진화 실행) 시 호출됩니다.

## ① 감지 확인
- FileChanged/Watcher 알림으로 이미 감지된 상태
- `bash jarvis-evolution.sh detect` → 임계값 초과 확인
- North Star: "이 진화의 성공 기준"을 1문장으로
- Scope Lock: bounded / out_of_scope / followup (references/scope-lock-template.md)

## ② 승인
- AskUserQuestion: [수립][보류][폐기] (한국어, 구조화 선택지만)
- AGENDA_LOG.md에 기록
- [보류] → deferred-issues.json 등록. 재감지 시 예측 A/B 보고서

## ③ 백업 + 계획
- `bash jarvis-evolution.sh backup evo-{N}`
- DAG 구조화 + evolution_type 결정 (settings_change|hook_change|skill_change|code_change|mixed)
- 2차 승인: 변경 diff 표시 → [실행][수정][폐기]

## ④ Worker 실행
```bash
WORKER_RESULT=$(cmux new-workspace --command "claude")
WORKER_SID=$(echo "$WORKER_RESULT" | awk '{for(i=1;i<=NF;i++) if($i ~ /surface:/) print $i}')
touch /tmp/cmux-jarvis-worker-$$
cmux set-buffer --name evo-plan "[계획 + Scope Lock + Worker 제약]"
cmux paste-buffer --name evo-plan --surface $WORKER_SID
cmux send-key --surface $WORKER_SID enter
```
- Worker 완료 감지: `ls /tmp/cmux-jarvis-evo-*-done` 체크
- 타임아웃 30분

## ⑤ 검증 + 반영 판단
- `bash jarvis-verify.sh evo-{N}`
- evidence.json 존재 확인
- Outbound Gate: proposed에 hooks 키 → REJECT, Scope Lock 일탈 → REJECT
- 시각화 보고서 (Skill("cmux-jarvis-visualization") 호출)
- AskUserQuestion: [KEEP][DISCARD]

## ⑥ 반영 또는 롤백
- KEEP → `bash jarvis-evolution.sh apply evo-{N}`
- DISCARD → `bash jarvis-evolution.sh rollback evo-{N}`
- 사후: 옵티미스틱 승격 + AGENDA_LOG + counter 업데이트
- `bash jarvis-evolution.sh cleanup evo-{N}`
