# cmuxO Hook JSON Schema Migration Plan

**작성일**: 2026-04-19
**작성자**: Claude (의뢰: cmux 사장)
**대상 저장소**: https://github.com/scokeepa/cmuxO (main 브랜치)
**상태**: DRAFT — 승인 대기

---

## 1. 문제 요약

Claude Code 세션 중 다음 에러가 다중 발생:

```
PreToolUse:Bash hook error
Hook JSON output validation failed — (root): Invalid input
```

한 턴에 5회까지 동시 발생 → 여러 훅이 동시에 스키마 위반 출력을 내고 있음.

---

## 2. 근거 (리서치 결과)

### 2.1 Claude Code 공식 훅 스키마 (출처: code.claude.com/docs/en/hooks.md)

**PreToolUse 이벤트의 올바른 출력 스키마**:

| 최상위 키 | 타입 | 비고 |
|-----------|------|------|
| `continue` | bool | 세션 계속 여부 |
| `stopReason` | string | 중단 사유 |
| `suppressOutput` | bool | stdout 숨김 |
| `decision` | `"approve"` \| `"block"` \| null | **레거시** (deprecated) |
| `reason` | string | `decision`에 대한 사유 |
| `hookSpecificOutput` | object | **현대 방식** |

**`hookSpecificOutput` 구조 (PreToolUse)**:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow" | "deny" | "ask" | "defer",
    "permissionDecisionReason": "...",
    "updatedInput": { ... }   // tool_input 치환 (선택)
  }
}
```

**핵심 제약**:
- 최상위 `decision`은 `"approve" | "block" | null`만 허용 — **`"allow"`는 INVALID**
- `"allow" / "deny" / "ask"`는 **오직** `hookSpecificOutput.permissionDecision` 안에서만 유효
- "그냥 통과"는 **exit 0 + 빈 stdout** 이 가장 안전 (스키마 검증 자체를 우회)
- `tool_input` 치환은 `hookSpecificOutput.updatedInput` 만 허용 — 최상위 `tool_input` 키는 무효

### 2.2 cmuxO 프로젝트 내 훅 감사 결과

전수 조사한 훅 스크립트 출력 패턴:

| 파일 | 이벤트 | 위반 위치 수 | 출력 내용 | 스키마 상태 |
|------|--------|------------|-----------|-----------|
| `cmux-read-guard.sh` | PreToolUse:Bash | 10 | `{"decision":"allow"}` | **INVALID → 에러 유발** |
| `cmux-gate6-agent-block.sh` | PreToolUse:Agent | 6 | `{"decision":"allow"}` | **INVALID → 에러 유발** |
| `cmux-control-tower-guard.py` | PreToolUse:Bash | 3 | `{"decision":"approve"}` | 레거시 (경고 없음) |
| `cmux-init-enforcer.py` | PreToolUse:Bash | 8 | `{"decision":"approve"}` | 레거시 |
| `cmux-watcher-msg-guard.py` | PreToolUse:Bash | 7 | `{"decision":"approve"}` | 레거시 |
| `cmux-completion-verifier.py` | PreToolUse:Bash | 5 | `{"decision":"approve"}` | 레거시 |
| `cmux-watcher-notify-enforcer.py` | PreToolUse:Bash | 12 | `{"decision":"approve"}` | 레거시 |
| `cmux-workflow-state-machine.py` | PreToolUse:Bash\|Agent | 6 | `{"decision":"approve"}` | 레거시 |
| `cmux-no-stall-enforcer.py` | PreToolUse:Bash\|Agent | 3 | `{"decision":"approve"}` | 레거시 |
| `cmux-plan-quality-gate.py` | PreToolUse:ExitPlanMode | 2 | `{"decision":"approve"}` | 레거시 |
| `cmux-gate7-main-delegate.py` | PreToolUse:Read\|... | 6 | `{"decision":"approve"}` | 레거시 |
| `cmux-dispatch-notify.sh` | PostToolUse:Bash | 1 | `{"decision":"approve"}` | PostToolUse에 불필요 |
| `cmux-memory-recorder.sh` | PostToolUse:Bash | 4 | 혼재 | 일부 불필요 |
| `cmux-idle-reuse-enforcer.py` | PostToolUse:Bash | 2 | `{"decision":"approve",...}` | PostToolUse에 불필요 |
| `cmux-setbuffer-fallback.py` | PostToolUse:Bash | 3 | 혼재 | 일부 불필요 |
| `cmux-enforcement-escalator.py` | PostToolUse | 5 | 혼재 | 일부 불필요 |

**이미 현대 스키마를 쓰는 참조 훅** (이것들을 레퍼런스 패턴으로 사용):
- `cmux-jarvis-gate.sh`: `hookSpecificOutput.permissionDecision` ✓
- `cmux-stop-guard.sh`: `{"continue": true/false, "stopReason": ...}` ✓
- `cmux-main-context.sh`: `hookSpecificOutput.additionalContext` ✓
- `cmux-hook-audit.sh` / `jarvis-session-start.sh`: SessionStart 현대 포맷 ✓

### 2.3 설치 플로우 확인

`cmuxO/install.sh:220-238`:
```bash
cp -r "$SCRIPT_DIR/$skill" "$SKILLS_DIR/"      # source → ~/.claude/skills/
chmod +x ...
```

→ **source 수정 + install.sh 재실행 = 모든 설치본 갱신**.
→ 단, 빠른 반영을 위해 직접 설치 경로도 함께 패치 권장.

---

## 3. 수정 전략

### 3.1 Tier 분류 (영향도 기준)

- **Tier A (에러 즉시 제거)**: `"decision":"allow"` 사용 2개 파일 (`cmux-read-guard.sh`, `cmux-gate6-agent-block.sh`) — **반드시 수정**
- **Tier B (레거시 deprecated 제거)**: `"decision":"approve"` 사용 13개 파일 — **현대 스키마로 마이그레이션 권장**
- **Tier C (PostToolUse 정리)**: PostToolUse에서 불필요한 `decision` 출력 — **빈 출력으로 단순화**

### 3.2 치환 규칙

| 기존 출력 | 이벤트 | 새 출력 |
|-----------|--------|---------|
| `{"decision":"allow"}` (pass-through) | PreToolUse | **exit 0 + 빈 stdout** |
| `{"decision":"approve"}` (pass-through) | PreToolUse | **exit 0 + 빈 stdout** |
| `{"decision":"block","reason":"..."}` | PreToolUse | `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}` |
| `{"decision":"allow","tool_input":{"command":...}}` (tool_input 수정) | PreToolUse | `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","updatedInput":{"command":...}}}` |
| `{"decision":"approve","systemMessage":"..."}` | PreToolUse | **두 개로 분리**: exit 0 + stderr에 메시지 (또는 `hookSpecificOutput.permissionDecisionReason`) |
| `{"decision":"approve"}` | PostToolUse | **exit 0 + 빈 stdout** (PostToolUse는 decision 불필요) |
| `{}` | 모든 이벤트 | **exit 0 + 빈 stdout** 으로 통일 |

### 3.3 변경 방식

셸 스크립트 (예: `cmux-read-guard.sh`):
```bash
# BEFORE
[ -f /tmp/cmux-orch-enabled ] || { echo '{"decision":"allow"}'; exit 0; }

# AFTER
[ -f /tmp/cmux-orch-enabled ] || exit 0
```

Python 스크립트 (예: `cmux-control-tower-guard.py`):
```python
# BEFORE
print(json.dumps({"decision": "approve"}))
sys.exit(0)

# AFTER
sys.exit(0)
```

차단 케이스 (block)는 현대 스키마로:
```python
# BEFORE
print(json.dumps({"decision": "block", "reason": msg}))

# AFTER
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": msg
    }
}))
```

tool_input 수정 케이스 (`cmux-read-guard.sh`의 --workspace 주입):
```python
# BEFORE
result = {"decision": "allow", "tool_input": {"command": cmd}}

# AFTER
result = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "updatedInput": {"command": cmd}
    }
}
```

---

## 4. 5관점 순환검증

### 4.1 SSOT (Single Source of Truth)
- **관찰**: 같은 스키마를 여러 훅이 각자 하드코딩 중 → 중복
- **대응**: 공통 JSON 빌더 헬퍼(`hook_output.py`, `hook_output.sh`)를 `cmux-orchestrator/scripts/`에 신설할지 여부는 **본 플랜 범위 외** (CLAUDE.md: "3회 이상 반복 시에만 헬퍼 추출") — 위반 22개 파일이 넘으므로 헬퍼 도입 정당화됨
- **결론**: **Phase 2에서 헬퍼 도입**, Phase 1은 인라인 치환으로 긴급 해결

### 4.2 SRP (Single Responsibility)
- 훅 각각은 단일 책임(특정 가드/엔포스먼트) 유지됨
- 출력 포맷 로직이 각 훅에 흩어진 것이 SRP 위반이며, 4.1 헬퍼로 해소

### 4.3 엣지케이스
- **E1**: pass-through 경로에서 stdout이 완전히 비어있어야 함 — trailing newline도 JSON 파서가 무시하는지? → Claude Code는 빈 stdout을 "출력 없음"으로 처리 (exit 0 조건부)
- **E2**: Python `sys.exit(0)` 직전 버퍼 플러시 필요 없음 (빈 출력이므로)
- **E3**: 셸 스크립트에서 `set -e`가 영향? → 현 파일들은 `set -e` 미사용 확인됨
- **E4**: `cmux-read-guard.sh`의 `tool_input` 수정 경로 — `updatedInput`으로 바꿨을 때 실제 명령어 치환이 Claude Code v2.1.x에서 동작하는지 확인 필요 → **시뮬레이션 필수**
- **E5**: `systemMessage` 키를 쓰던 `cmux-workflow-state-machine.py:168` — 이 키는 스키마에 없음. 대체 전략: `hookSpecificOutput.permissionDecisionReason` 사용 또는 stderr로 이동
- **E6**: `cmux-plan-quality-gate.py`의 ExitPlanMode 이벤트 — PreToolUse 하위인지 확인. hookEventName 값은 `"PreToolUse"` 유지(ExitPlanMode도 도구 호출이므로)

### 4.4 아키텍트 관점
- cmuxO는 install.sh로 `~/.claude/skills/` 에 복사되는 구조 — source-of-truth는 repo
- 설치본(installed)과 소스의 드리프트 방지: `install.sh`에 해시 검증 단계 추가 여부 고려 → **본 플랜 범위 외**
- 기존에 잘 작동하는 4개 훅(jarvis-gate, stop-guard, main-context, hook-audit)과 패턴 일치시키면 아키텍처 일관성 개선

### 4.5 Iron Law (프로젝트 고유 불변규칙)
- CLAUDE.md의 "요청 범위 외 수정 금지" — 본 수정은 "훅 에러 해결"이 범위. Tier B(approve→빈출력)는 같은 근본원인 해결 차원이라 범위 내.
- Tier C(PostToolUse 정리)는 에러를 직접 유발하진 않으나 같은 미그레이션 작업 — **사용자 승인 필요**
- 헬퍼 도입(Phase 2)은 별도 승인 필요

---

## 5. 코드 시뮬레이션 (승인 전 검증 대상)

### 5.1 빈 stdout + exit 0 동작 검증
```bash
echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | \
  bash -c 'exit 0'
# Expected: no output, exit 0, Claude Code proceeds
```

### 5.2 현대 deny 포맷 검증
```bash
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | \
  python3 -c '
import json, sys
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "test block"
  }
}))
'
# Expected: valid JSON, Claude Code blocks with reason
```

### 5.3 updatedInput 동작 검증
- Claude Code v2.1.89+ 버전에서 `hookSpecificOutput.updatedInput` 이 `tool_input`을 실제로 치환하는지 확인
- **검증 방법**: 테스트 훅 작성 → 실제 Bash 명령 주입 실험 → tool result에 치환된 명령이 실행되었는지 확인

**위 3개 시뮬레이션은 Phase 0 (승인 직후) 에 실제 실행하여 결과를 이 문서에 업데이트.**

---

## 6. 실행 계획 (Phase별)

### Phase 0 — 검증 (30분)
- [ ] 5.1, 5.2, 5.3 시뮬레이션 실제 실행
- [ ] 결과를 본 문서 §5에 기록
- [ ] `updatedInput` 미지원 시 Fallback 전략 결정 (`cmux-read-guard.sh` --workspace 주입을 bash 래퍼 스크립트로 이동)

### Phase 1 — Tier A 긴급 수정 (에러 즉시 제거)
- [ ] `cmux-orchestrator/hooks/cmux-read-guard.sh` 10곳 치환
- [ ] `cmux-orchestrator/hooks/cmux-gate6-agent-block.sh` 6곳 치환
- [ ] `~/.claude/skills/cmux-orchestrator/hooks/` 해당 2파일 동기화 (즉시 반영)
- [ ] Claude Code 세션에서 재현 테스트 — 에러 0건 확인

### Phase 2 — Tier B 마이그레이션 (approve → 빈 출력 또는 현대 스키마)
- [ ] 13개 파일 순차 치환 (PreToolUse pass-through → exit 0)
- [ ] block 케이스는 `hookSpecificOutput.permissionDecision:"deny"` 로 현대화
- [ ] `systemMessage` 키 사용 1건(`cmux-workflow-state-machine.py:168`) 재설계
- [ ] `cmux-plan-quality-gate.py` ExitPlanMode 분기 확인

### Phase 3 — Tier C PostToolUse 정리
- [ ] 5개 PostToolUse 훅에서 불필요한 `decision` 출력 제거
- [ ] 빈 `{}` 출력도 exit 0으로 통일

### Phase 4 — (선택) 헬퍼 도입
- [ ] `cmux-orchestrator/scripts/hook_output.py` 생성 (`allow()`, `deny(reason)`, `allow_with_input(updated)` 등)
- [ ] `cmux-orchestrator/scripts/hook_output.sh` 생성
- [ ] 전체 훅을 헬퍼 사용으로 리팩터링
- [ ] **별도 승인 필요**

### Phase 5 — 배포
- [ ] `install.sh` 재실행 또는 설치본 수동 동기화
- [ ] 테스트: 새 Claude Code 세션 열어 실 훅 에러 0건 확인
- [ ] 회귀 테스트: `cmux-orchestrator/hooks/test-hooks-negative.sh` 가 있으면 실행

### Phase 6 — 커밋 & 푸시
- [ ] Git 커밋 메시지 (5-섹션 포맷 준수):
  ```
  fix(hooks): migrate hook JSON output to modern Claude Code schema

  Root cause: Legacy `{"decision":"allow"}` output violated Claude Code
  hook schema validation (only "approve"|"block" valid at top-level
  decision; "allow" belongs in hookSpecificOutput.permissionDecision).

  Change: Migrated 22 hook scripts across Tier A (error-causing) and
  Tier B (deprecated). Pass-through cases now exit 0 silently; block
  cases use hookSpecificOutput.permissionDecision="deny".

  Recurrence prevention: (Phase 4 헬퍼 도입 시) 중앙화된 hook_output
  헬퍼로 포맷 일탈 방지.

  Verification: Simulation §5.1-5.3 실행 결과 기록. 실 세션에서 에러
  5→0 감소 확인.

  Remaining risk: updatedInput Claude Code 버전 호환성 (Phase 0에서
  확인).
  ```
- [ ] `git push origin main` → https://github.com/scokeepa/cmuxO

---

## 7. 비범위 (명시적 제외)

- cmuxO의 다른 버그 수정 (이번 작업과 무관한 것)
- 설치 스크립트 전체 리팩터링
- 문서 번역 업데이트
- Tier C, Phase 4 는 사용자 별도 승인 시에만 진행

---

## 8. 승인 요청 항목

사용자 결정 필요:

1. **범위 결정**:
   - (a) Tier A만 긴급 (최소) — 에러 즉시 제거
   - (b) Tier A+B (권장) — 레거시 스키마 전체 현대화
   - (c) Tier A+B+C (완전) — PostToolUse까지 정리
   - (d) A+B+C+Phase 4 헬퍼 (이상적) — 재발 방지 구조화

2. **tool_input 수정 전략** (Phase 0 결과 의존):
   - `updatedInput` 동작 시: 스키마 치환
   - 미동작 시: `cmux-read-guard.sh`의 --workspace 주입을 사전 래퍼로 이동 (별도 설계 필요)

3. **커밋 방식**:
   - Single 대형 커밋 vs Phase별 N개 커밋 (권장: Tier별 3개 커밋)

---

## 9. 위험 & 롤백

- **위험 1**: 일부 훅이 stdout 출력으로 Claude 에이전트에 정보 전달 중이었다면, 빈 출력으로 바꿀 때 정보 손실
  - 완화: 각 훅의 `print(...)` 호출이 **정보 전달용** 인지 **스키마 응답용** 인지 grep으로 분리 확인
- **위험 2**: `install.sh` 재실행이 settings.json을 덮어써 다른 설정 손실
  - 완화: settings.json 백업 → 설치 → diff 확인
- **롤백**: `git revert <commit>` + `install.sh` 재실행

---

## 10. 참조

- Claude Code Hooks 공식 문서: https://code.claude.com/docs/en/hooks.md
- 감사 보고서: 본 작업 세션 내 Explore 에이전트 결과
- cmuxO 내부 참조 훅: `cmux-jarvis-gate.sh`, `cmux-stop-guard.sh` (이미 현대 스키마 사용)
