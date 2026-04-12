---
name: cmux-stop
description: "오케스트레이션 종료 — 컨트롤 타워 + 부서 선택적 종료. /cmux-stop으로 실행."
user-invocable: true
classification: workflow
allowed-tools: Bash, Read, AskUserQuestion
---

# /cmux-stop — 오케스트레이션 종료

입력: `$ARGUMENTS`

오케스트레이션을 종료합니다. 부서(workspace)는 선택적으로 닫을 수 있습니다.

> `/cmux-pause` = 일시 중지 (부서 유지)
> `/cmux-stop` = 종료 (부서 선택적 닫기)
> `/cmux-uninstall` = 완전 제거 (hook/스킬 삭제)

---

## 실행 절차

### Step 1: 오케스트레이션 상태 확인

```bash
# 오케스트레이션 모드 확인
if [ ! -f /tmp/cmux-orch-enabled ]; then
    echo "오케스트레이션이 실행 중이 아닙니다."
    # 종료
fi
```

### Step 2: 현재 상태 스캔 + 보고

eagle-status와 roles.json을 읽어 현재 상태를 보고합니다.

```bash
# eagle-status에서 surface 상태 집계
python3 -c "
import json
eagle = json.load(open('/tmp/cmux-eagle-status.json'))
roles = json.load(open('/tmp/cmux-roles.json'))
stats = eagle['stats']
surfaces = eagle['surfaces']

boss_ws = roles.get('boss',{}).get('workspace','')
jarvis_sid = roles.get('jarvis',{}).get('surface','')

# 컨트롤 타워 vs 부서 분리
ctrl_surfaces = []
dept_workspaces = {}
for sid, info in surfaces.items():
    ws = info.get('workspace','')
    if ws == boss_ws:
        ctrl_surfaces.append(f'surface:{sid} ({info[\"status\"]})')
    else:
        dept_workspaces.setdefault(ws, []).append({'sid':sid, 'status':info['status'], 'title':info.get('title','')})

print(f'컨트롤 타워: {len(ctrl_surfaces)}개 surface')
print(f'부서: {len(dept_workspaces)}개 workspace')
print(f'WORKING: {stats.get(\"working\",0)}개')
print(f'IDLE: {stats.get(\"idle\",0)}개')
print(f'ENDED: {stats.get(\"ended\",0) + stats.get(\"done\",0)}개')
" 2>/dev/null
```

### Step 3: WORKING surface 처리

WORKING surface가 있으면 (자비스/와쳐 제외) 사용자에게 질문합니다.

자비스(JARVIS)와 와쳐(Watcher)는 WORKING이어도 **즉시 종료 가능** (모니터링만 하므로).
실제 작업 중인 부서 surface만 "완료 대기" 대상입니다.

```
WORKING surface가 있습니다:
  surface:62 — electron-4layer (5분 경과)
  surface:63 — Research NL skill (3분 경과)

[완료 대기] — DONE 확인까지 2분 폴링으로 기다립니다.
[강제 종료] — 작업 중단하고 즉시 종료합니다.
[취소] — 종료를 취소합니다.
```

**[완료 대기] 선택 시:**
```bash
# 2분 간격 폴링
for round in 1 2 3 4 5; do
    sleep 120
    # 각 WORKING surface 확인
    for SID in $WORKING_SURFACES; do
        SCREEN=$(cmux read-screen --surface $SID --lines 5 2>/dev/null)
        if echo "$SCREEN" | grep -q "DONE"; then
            echo "✅ $SID 완료"
        fi
    done
    # 전부 완료 시 break
done
# 10분 초과 시 강제 진행
```

### Step 4: 종료 범위 선택

```
오케스트레이션을 어떻게 종료할까요?

[전부 닫기] — 컨트롤 타워 + 부서 N개 전부 종료.
[컨트롤 타워만] — 사장/와쳐/자비스만 종료. 부서는 독립 작업 계속.
[그대로 두기] — 취소. 아무것도 안 합니다.
```

### Step 5A: 전부 닫기

각 부서 workspace를 순서대로 종료합니다.

```bash
# 각 부서 workspace
for WS in $DEPT_WORKSPACES; do
    # 해당 ws에 WORKING surface가 있는지 확인 (S4 방어)
    WS_WORKING=$(python3 -c "
import json
eagle = json.load(open('/tmp/cmux-eagle-status.json'))
working = [sid for sid,info in eagle['surfaces'].items() 
           if info.get('workspace')=='$WS' and info.get('status')=='WORKING']
print(' '.join(working))
" 2>/dev/null)
    
    if [ -n "$WS_WORKING" ]; then
        # WORKING surface에 종료 알림
        for SID in $WS_WORKING; do
            cmux send --workspace $WS --surface surface:$SID "작업을 중단하고 현재 상태를 저장하세요."
            cmux send-key --workspace $WS --surface surface:$SID Enter
        done
        sleep 5
    fi
    
    # workspace 종료 (S2: --workspace 명시로 guard 통과)
    cmux close-workspace --workspace $WS 2>/dev/null
    echo "  ✅ $WS 종료"
done
```

이후 Step 5B로 진행.

### Step 5B: 컨트롤 타워 종료

```bash
JARVIS_SID=$(python3 -c "import json;print(json.load(open('/tmp/cmux-roles.json')).get('jarvis',{}).get('surface',''))" 2>/dev/null)
WATCHER_SID=$(python3 -c "import json;print(json.load(open('/tmp/cmux-roles.json')).get('watcher',{}).get('surface',''))" 2>/dev/null)

# 자비스 종료
if [ -n "$JARVIS_SID" ]; then
    cmux send --surface $JARVIS_SID "/quit"
    cmux send-key --surface $JARVIS_SID Enter
    sleep 3
    echo "  ✅ 자비스 종료"
fi

# 와쳐 종료
pkill -f "watcher-scan.py" 2>/dev/null || true
if [ -n "$WATCHER_SID" ]; then
    cmux send --surface $WATCHER_SID "/quit"
    cmux send-key --surface $WATCHER_SID Enter
    sleep 3
    echo "  ✅ 와쳐 종료"
fi

# 사장 pane은 닫지 않음 (사용자 세션)
```

### Step 6: 정리

```bash
# 오케스트레이션 모드 OFF
rm -f /tmp/cmux-orch-enabled

# 역할 초기화
rm -f /tmp/cmux-roles.json

# JARVIS 임시 파일
rm -f /tmp/cmux-jarvis-*
rm -f /tmp/cmux-jarvis-freeze-mode

# 크로스플랫폼 유틸리티 데먼 종료
python3 ~/.claude/skills/cmux-orchestrator/scripts/cmux_compat.py stop 2>/dev/null

# pause 플래그
rm -f /tmp/cmux-paused.flag

# 컨트롤 타워 workspace 이름 복원
BOSS_WS=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['workspace_ref'])" 2>/dev/null)
cmux rename-workspace --workspace $BOSS_WS "$(basename $HOME)"
cmux rename-tab --surface $(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['surface_ref'])" 2>/dev/null) "Claude Code"
```

### Step 7: 완료 보고

```
═══════════════════════════════════════════════════════
  오케스트레이션 종료 완료
═══════════════════════════════════════════════════════

  종료된 항목:
  ─────────────────────────────────────────────────────
  🟡 자비스(JARVIS) — 종료
  🟢 와쳐(Watcher) — 종료
  📁 부서 N개 — 종료 (전부 선택 시)

  유지된 항목:
  ─────────────────────────────────────────────────────
  🔵 이 세션 — 일반 모드로 계속 사용
  ⚙️  Hook — 유지 (재시작 가능)
  📦 스킬 — 유지 (재시작 가능)

  /cmux-start     오케스트레이션 재시작
  /cmux-uninstall 완전 제거 + Hook/스킬 삭제

═══════════════════════════════════════════════════════
```

---

## 주의사항

- 사장 pane(이 세션)은 절대 닫지 않음
- WORKING surface 강제 종료 시 작업 유실 가능 → "저장하세요" 알림 후 5초 대기
- 같은 workspace에 WORKING + ENDED가 섞여있으면 workspace 전체를 닫기 전 확인
- Hook은 유지됨 → /cmux-start로 즉시 재시작 가능
- 완전 제거는 /cmux-uninstall 사용
