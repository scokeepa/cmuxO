# JARVIS Hook 등록 맵

> 정본(SSOT). hook 구성을 참조할 때 이 파일만 참조.

## HOOK_MAP (install.sh에 등록)

| # | 파일명 | 이벤트 | matcher | 타임아웃 | 역할 |
|---|--------|--------|---------|---------|------|
| 1 | cmux-jarvis-gate.sh | PreToolUse | Edit\|Write\|Bash | 3s | GATE J-1 + Worker 분기 + /freeze |
| 2 | cmux-settings-backup.sh | ConfigChange | (전체) | 10s | 3중 백업 + GATE exit 2 차단 |
| 3 | jarvis-session-start.sh | SessionStart | (전체) | 5s | 캐시 + initialUserMessage + watchPaths |
| 4 | jarvis-file-changed.sh | FileChanged | eagle-status\|watcher-alerts | 5s | 즉시 감지 + 디바운싱 60초 |
| 5 | jarvis-pre-compact.sh | PreCompact | (전체) | 5s | 진화 컨텍스트 보존 지시 |
| 6 | jarvis-post-compact.sh | PostCompact | (전체) | 5s | nav.md 재주입 |

## 제거된 hook
- ~~cmux-jarvis-worker-gate.sh~~ → gate.sh에 통합 (S4)
- ~~jarvis-prevent-idle.sh~~ → JARVIS ≠ teammate, 미적용 (CE-01)

## 기존 cmux hook과의 관계
- PreToolUse 기존: "Bash"(6 hooks), "Bash|Agent"(2), "Agent"(1)
- JARVIS 추가: "Edit|Write|Bash"(1) → **겹침 없음**
- ConfigChange, FileChanged, PreCompact: **기존 0개 → JARVIS 최초 등록**
- PostCompact: **기존 0개 → JARVIS 최초 등록**

## surface별 동작
| hook | JARVIS | Boss | Worker | Watcher |
|------|--------|------|--------|---------|
| gate.sh | GATE 전체 | 즉시 allow (~1ms) | Worker 분기 | 즉시 allow |
| session-start | additionalContext 전체 | 빈 context | - | 빈 context |
| file-changed | 임계 초과 시 주입 | - | - | - |
| pre-compact | 진화 컨텍스트 보존 | 무영향 | - | 무영향 |
