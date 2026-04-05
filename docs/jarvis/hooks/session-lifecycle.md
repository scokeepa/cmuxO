# Session Lifecycle Hooks

> 정본. session-start/file-changed/compact hook 참조 시 이 파일.

## jarvis-session-start.sh (SessionStart)
**역할 3가지:**
1. JARVIS surface에만 전체 지시 additionalContext 주입 (SR-03)
2. initialUserMessage로 자동 감지 시작 (S5)
3. watchPaths로 eagle-status/watcher-alerts 감시 등록 (S7)

**출력 (JARVIS surface):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[전체 JARVIS 지시사항 ~3000토큰]",
    "initialUserMessage": "JARVIS 초기화. eagle-status 확인 후 감지 시작.",
    "watchPaths": ["/tmp/cmux-eagle-status.json", "/tmp/cmux-watcher-alerts.json"]
  }
}
```

**폴백 (E1: roles.json 손상/삭제 시):**
```bash
if [ -z "$JARVIS_SID" ]; then
  # roles.json 없음 → 지시 주입 안 함 (안전 모드)
  # JARVIS는 빈 껍데기로 시작 → /cmux-start 재실행 필요
  echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":""}}'
  exit 0
fi
```

**출력 (다른 surface):** `additionalContext: ""` (빈 문자열)

## jarvis-file-changed.sh (FileChanged)
**트리거:** watchPaths에 등록된 파일 변경 시 자동 실행
**matcher:** `cmux-eagle-status.json|cmux-watcher-alerts.json`

**디바운싱 (CA-02):**
```bash
LAST_RUN="/tmp/jarvis-file-changed-last"
NOW=$(date +%s)
PREV=$(cat "$LAST_RUN" 2>/dev/null || echo 0)
[ $((NOW - PREV)) -lt 60 ] && exit 0
echo "$NOW" > "$LAST_RUN"
```

**임계값 체크 (SS-01 — metric-dictionary.json에서 읽기):**
```bash
STALL_WARN=$(jq -r '.metrics.stall_count.threshold.warning' \
  ~/.claude/cmux-jarvis/metric-dictionary.json)
STALL=$(jq '[.surfaces[] | select(.status=="STALLED")] | length' /tmp/cmux-eagle-status.json)
[ "$STALL" -ge "$STALL_WARN" ] && # → additionalContext 주입
```

## jarvis-pre-compact.sh (PreCompact, S9)
**역할:** compact 직전 진화 컨텍스트 보존 지시 주입
```bash
# stdout → compact 지시에 추가됨
if [ -f "$LOCK_FILE" ]; then
  echo "중요: 진화 $EVO_ID 진행 중. nav.md 내용을 요약에 포함:"
  cat "evolutions/$EVO_ID/nav.md"
fi
```

## jarvis-post-compact.sh (PostCompact)
**역할:** compact 후 현재 진화 nav.md 재주입
```json
{"hookSpecificOutput":{"hookEventName":"PostCompact","additionalContext":"[nav.md 내용]"}}
```
