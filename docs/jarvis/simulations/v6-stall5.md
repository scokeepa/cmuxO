# 시뮬레이션 v6: STALL 5개 실측 (2026-04-03)

> 최신. 실제 cmux 런타임 데이터 기반.

## 실측 환경
```
surface:60 WORKING (Main)
surface:63 WORKING (Research)
surface:62 STALLED (electron-4layer)
surface:61 STALLED (system tools)
surface:58 STALLED (sns-reels)
surface:50 STALLED (law-chatbot)
surface:54 STALLED (법령 AI)
surface:55 STALLED (NotebookLM)
```

## 타임라인 (정상 경로)
```
T+0s   /cmux-start → JARVIS pane 생성 (workspace:10)
T+1s   session-start: SKILL 10줄 + additionalContext (JARVIS만)
T+2s   initialUserMessage → 자동 감지 (사용자 입력 불필요)
T+3s   STALL 5개 감지 → Lane B
T+7s   1차 승인 대기 중 사용자 "상태 보고" → Lane A 즉시 응답 (block 아님 ✓)
T+20s  [수립] → 백업 → 계획 → 2차 승인 → Worker
T+40s  Worker 완료 (플래그 파일) → verify → Outbound Gate
T+42s  Mermaid + ASCII 보고서 → [KEEP]
T+43s  JSON Patch(jq deep merge, 원자적) → 승격 + 문서 저장
T+350s STALL 3개 자동 정리 (timeout 효과)
T+600s STALL 0개 완전 정상화
```

## 5관점 검증 항목 전부 통과
- SR-03: SKILL 10줄 ✓
- CA-02: 디바운싱 60초 ✓
- CE-01: TeammateIdle 미사용 ✓
- CA-03: Bash 쓰기만 감지 ✓
- S1: permissionDecision 형식 ✓

## 발견: 신규 이슈 0건

---

# 시뮬레이션 v7: ERROR 2 + IDLE 1 + ENDED 1 (2026-04-03 11:28)

## 실측 환경
```
surface:60 WORKING (Main/이 세션)
surface:61 WORKING (system tools)
surface:63 WORKING (Research)
surface:62 WORKING (electron-4layer)
surface:58 ENDED   (sns-reels) ← 새 상태
surface:50 IDLE    (law-chatbot)
surface:54 ERROR   (법령 AI 챗봇) ← 새 상태
surface:55 ERROR   (NotebookLM) ← 새 상태
roles: main=surface:32, watcher=surface:57 (jarvis 미등록)
```

## 시나리오 A: 정상 경로 (ERROR 2개 감지)

```
T+0s  /cmux-start → JARVIS pane 생성 (surface:65 가정)
      [E5 중복 체크] roles.json jarvis 키 없음 → 생성 진행
      roles.json: jarvis=surface:65 등록

T+1s  jarvis-session-start.sh (SessionStart)
      [E1 roles.json 체크] jarvis.surface="surface:65" → 유효
      → additionalContext: 전체 JARVIS 지시 (~3000토큰, JARVIS만)
      → initialUserMessage: "JARVIS 초기화. eagle-status 확인."
      → watchPaths: ["/tmp/cmux-eagle-status.json", "/tmp/cmux-watcher-alerts.json"]
      ※ 다른 surface(60,61,62,63): SKILL.md 10줄만 로드 (SR-03 ✓)

T+2s  JARVIS 자동 시작 (initialUserMessage)
      eagle-status.json 읽기:
        WORKING: 4 (60,61,62,63)
        ENDED: 1 (58)
        IDLE: 1 (50)
        ERROR: 2 (54,55)

      [Inbound Gate]
      - JSON 유효 ✓, 타임스탬프 < 5분 ✓ → ALLOW

      [3레인 분류]
      ERROR 2 > metric-dictionary warning(0) → Lane B (진화 트리거)

T+3s  안전 체크:
      - .evolution-counter: 없음 → consecutive=0, daily=0 → PASS
      - .evolution-lock: 없음 → PASS

T+5s  ② 분석:
      ERROR surface 분석:
        surface:54 (법령 AI 챗봇) — ERROR 상태
        surface:55 (NotebookLM) — ERROR 상태
      Watcher ↔ JARVIS 경계 확인:
        ERROR → Watcher가 즉시 대응 (재시작/알림)
        JARVIS → "ERROR 재발 방지" 설정 변경이 가능한가?
      
      [핵심 판단] ERROR는 Watcher 영역. JARVIS는 패턴 분석만.
      → 진화 대상이 아닌 "관찰 + 학습" 결정

      BUT: ENDED(58) + IDLE(50) surface도 있음 → 정리 필요?
      → 이것은 settings 변경으로 해결 가능 (auto-cleanup)
      
      → North Star: "ENDED/IDLE surface 자동 정리"
      → Scope Lock:
        bounded: "surface 정리 관련 설정 (idle timeout)"
        out_of_scope: "ERROR 대응 (Watcher 영역)"

T+7s  ③ 1차 승인:
      AskUserQuestion:
        "ERROR 2개는 Watcher가 대응 중입니다.
         ENDED(sns-reels) + IDLE(law-chatbot) surface를
         자동 정리하는 idle timeout 설정을 제안합니다.
         [수립] [보류] [폐기]"

      → 사용자 [수립]

T+10s ④ 백업 + CURRENT_LOCK + /freeze

T+12s ⑤ 계획:
      evolution_type: "settings_change"
      proposed: dispatch.idle_timeout_seconds: 300
      [E4 배열 방어] proposed에 hooks 키 → 없음 ✓

T+13s ⑤-b 2차 승인 → [실행] → TTL 리셋

T+14s [Execution Gate]
      GATE 5단계: ALLOW (정상 진화 경로)

T+15s ⑧ Worker 생성
      cmux new-workspace --command "claude"
      set-buffer + paste-buffer (계획 전달)

T+25s Worker 완료:
      proposed-settings.json: {"dispatch":{"idle_timeout_seconds":300}}
      [E4 체크] hooks 키 → 없음 ✓
      file-mapping.json: {"proposed-settings.json":"~/.claude/settings.json"}
      07-expected-outcomes.md: "ENDED/IDLE surface 300초 후 자동 정리"
      STATUS: DONE, evolution_type=settings_change, expected_outcomes_documented=true

T+26s Worker 플래그 파일 생성: /tmp/cmux-jarvis-evo-001-done

T+27s JARVIS 다음 턴에서 감지:
      ls /tmp/cmux-jarvis-evo-*-done → 존재

      jarvis-verify.sh:
        - JSON 유효 ✓
        - expected-outcomes.md 존재 + 비어있지 않음 ✓
        - file-mapping.json 유효 ✓
        - evidence.json 생성

      [Outbound Gate]
        - idle_timeout_seconds: 300 → 유효 정수 ✓
        - hooks 키 없음 ✓ (E4 방어)
        - 새 최상위 키 아님 (dispatch 하위) ✓
        - Scope Lock 준수 ✓

T+28s ⑩ Before/After:
      시각화 보고서 (한국어):

      ```
      ═══════════════════════════════════════
      JARVIS 진화 보고서: evo-001
      ═══════════════════════════════════════
      ■ 변경: dispatch.idle_timeout_seconds = 300
      
      ■ Before/After
      ┌──────────┬──────────┬──────────────┐
      │ 메트릭    │ Before   │ After (예상)  │
      ├──────────┼──────────┼──────────────┤
      │ ENDED    │ 1        │ 0 (자동 정리) │
      │ IDLE     │ 1        │ 0 (자동 정리) │
      │ ERROR    │ 2        │ 2 (Watcher 대응)│
      │ timeout  │ 없음     │ 300초         │
      └──────────┴──────────┴──────────────┘
      
      ■ 범위: idle timeout만 (ERROR 대응은 Watcher)
      ═══════════════════════════════════════
      ```

      [KEEP] [DISCARD]
      → 사용자 [KEEP]

T+29s ⑪ 반영:
      LOCK phase="applying"
      jq -s '.[0] * .[1]' settings.json proposed → merged (원자적)
      LOCK 해제 + /freeze 해제

T+30s 사후 처리:
      옵티미스틱 승격: "idle-timeout-pattern" short-term
      cmux notify "evo-001: idle timeout 300초 적용"
      AGENDA_LOG 기록
      Worker workspace 종료
```

## 시나리오 B: 사용자가 진화 중 Lane A 질문

```
T+16s (Worker 구현 중) 사용자: "ERROR surface 상태 알려줘"

JARVIS 처리:
  [3레인] Lane A (보고)
  JARVIS block 아님 (wait-for 제거) ✓
  
  응답:
  "ERROR surface 2개:
   - surface:54 (법령 AI 챗봇) — Watcher가 대응 중
   - surface:55 (NotebookLM) — Watcher가 대응 중
   현재 진화(evo-001)는 IDLE/ENDED 정리에 집중 중입니다."
```

## 시나리오 C: FileChanged 디바운싱 테스트

```
T+5s   eagle-status 갱신 → jarvis-file-changed.sh 트리거
       디바운싱: LAST_RUN=/tmp/jarvis-file-changed-last
       T+2s에서 session-start가 watchPaths 등록
       첫 실행 → LAST_RUN 기록 (T+5s)
       임계값 체크: ERROR 2 > warning(0) → additionalContext 주입
       "⚠ ERROR:2 IDLE:1 ENDED:1 — 임계 초과"

T+10s  eagle-status 다시 갱신 → FileChanged 트리거
       디바운싱: T+10 - T+5 = 5초 < 60초 → **스킵** ✓ (CA-02)

T+65s  eagle-status 갱신 → FileChanged 트리거  
       디바운싱: T+65 - T+5 = 60초 ≥ 60초 → **실행**
       LAST_RUN 업데이트 (T+65s)
       임계값 체크: 진화 적용 후 ENDED/IDLE 정리 중 → ERROR 2만 남음
       ERROR 2 > warning → "⚠ ERROR:2 — Watcher 대응 중. JARVIS 개입 불필요."
```

## 시나리오 D: gate.sh Bash 쓰기 감지 테스트

```
T+20s  Worker가 Bash 실행: "cat ~/.claude/settings.json | jq '.model'"
       gate.sh 트리거:
         tool_name=Bash
         command="cat ~/.claude/settings.json | jq '.model'"
         쓰기 패턴 grep: (>|>>|cp|mv|tee|jq.*-w|sed -i).*settings.json
         → "cat ... | jq" → 쓰기 패턴 아님 → **allow** ✓ (CA-03)

T+22s  Worker가 Bash 실행: "cp proposed.json ~/.claude/settings.json"
       gate.sh 트리거:
         command="cp proposed.json ~/.claude/settings.json"
         쓰기 패턴: "cp.*settings.json" → **매칭!**
         → check_settings_gate()
         → LOCK phase="implementing" (아직 applying 아님)
         → **deny** "settings.json은 phase=applying만 허용" ✓
```

## 시나리오 E: E4 배열 덮어쓰기 방어 테스트

```
Worker가 실수로 proposed-settings.json에 hooks 포함:
  {"dispatch":{"idle_timeout":300},"hooks":{"PreToolUse":[{"type":"command","command":"echo hi"}]}}

Outbound Gate (jarvis-verify.sh 또는 gate-logic):
  jq -e '.hooks' proposed-settings.json → **존재!**
  → REJECT "proposed에 hooks 키 포함. 기존 hooks 덮어쓰기 위험."
  → Worker에게 수정 요청 (⑤ 순환 1회차)
```

## 시나리오 F: GATE exit 2 차단 테스트

```
JARVIS가 (혹시라도) /hooks 명령으로 settings.json 수정 시도:
  → Claude Code 내부에서 settings.json 변경
  → ConfigChange hook 트리거
  → cmux-settings-backup.sh 실행:
    → settings.json에서 cmux-jarvis-gate 검색
    → 삭제된 경우 → echo "GATE 삭제 감지" >&2 && exit 2
    → **exit 2 → Claude Code가 변경을 세션에 적용하지 않음** ✓
```

## v7 검증 결과

| 체크 | 결과 |
|------|------|
| ERROR → Watcher 영역, JARVIS는 학습만 | ✓ 경계 규칙 준수 |
| IDLE/ENDED → JARVIS 진화 대상 | ✓ 적절한 범위 |
| SR-03 SKILL 10줄 (다른 surface) | ✓ |
| CA-02 디바운싱 60초 | ✓ T+10s 스킵, T+65s 실행 |
| CA-03 Bash 읽기 통과 | ✓ cat/jq 읽기 → allow |
| S3 Bash 쓰기 차단 | ✓ cp → deny |
| E4 hooks 키 REJECT | ✓ Outbound Gate 방어 |
| S2 GATE exit 2 차단 | ✓ ConfigChange exit 2 |
| E5 JARVIS 중복 방지 | ✓ roles.json 체크 |
| E1 roles.json 폴백 | ✓ (시나리오에서는 정상) |
| 3레인 (Lane A 즉시 응답) | ✓ Worker 중 질문 처리 |

## 발견: 신규 이슈

| # | 발견 | 심각도 | 해결 |
|---|------|--------|------|
| **V7-01** | ERROR surface에 대해 JARVIS가 "관찰+학습"만 한다면, 어떤 학습을 하는지 미정의 | **LOW** | Phase 2: ERROR 패턴 → knowledge 자동 기록 |
| **V7-02** | ENDED 상태는 metric-dictionary에 정의 없음 (STALL/ERROR만) | **MED** | metric-dictionary에 ENDED 임계값 추가: warning≥1 |
| **V7-03** | Watcher가 ERROR 대응 중인지 JARVIS가 어떻게 아는가? 가정만 있음 | **MED** | watcher-alerts.json에서 surface별 대응 상태 확인. 없으면 Watcher에 cmux send 질의 |
