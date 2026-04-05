# Claude Code 소스 검증 결과 (S1~S12)

> 소스 경로: /Users/csm/claude-code/source/src/

## 즉시 반영 (S1~S9)

| # | 발견 | 파일 | 반영 |
|---|------|------|------|
| S1 | GATE 출력 → permissionDecision | types/hooks.ts:73 | ✅ hookSpecificOutput 형식 |
| S2 | ConfigChange exit 2 차단 | hooksConfigManager.ts:214 | ✅ GATE 삭제 방지 |
| S3 | Bash 간접 수정 차단 | FileWriteTool.ts:56 (file_path) | ✅ matcher Edit\|Write\|Bash |
| S4 | worker-gate → gate.sh 통합 | - | ✅ hook 수 감소 |
| S5 | initialUserMessage 자동 시작 | types/hooks.ts:87 | ✅ session-start |
| S6 | HOLD = permissionDecision:"ask" | PermissionRule.ts:26 | ✅ GATE 5단계 매핑 |
| S7 | FileChanged + watchPaths | hooksConfigManager.ts:259 | ✅ eagle-status 즉시 감지 |
| S8 | ~~TeammateIdle~~ | stopHooks.ts:334 | ❌ JARVIS ≠ teammate (CE-01) |
| S9 | PreCompact stdout 주입 | hooksConfigManager.ts:136 | ✅ 진화 컨텍스트 보존 |

## Phase 2+ (S10~S12)

| # | 발견 | 활용 |
|---|------|------|
| S10 | InstructionsLoaded | SKILL.md 로드 모니터링 |
| S11 | PermissionRequest | Worker 권한 자동 처리 |
| S12 | CLAUDE_ENV_FILE | 동적 환경변수 |

## 핵심 소스 참조
- `coreSchemas.ts:414` — PreToolUseHookInputSchema (tool_name, tool_input)
- `coreTypes.ts:25` — HOOK_EVENTS 27종
- `hooks.ts:2133` — hookInput JSON.stringify → stdin
- `hooks.ts:2142` — 같은 matcher 병렬 실행
- `PermissionRule.ts:26` — allow/deny/ask 3가지
- `coreSchemas.ts:670` — ConfigChangeHookInputSchema (source, file_path)
