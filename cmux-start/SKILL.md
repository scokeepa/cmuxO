---
name: cmux-start
description: "원커맨드 오케스트레이션 시작 — 컨트롤 타워(사장+와쳐+자비스) 구성 + 기존 세션 포함 여부 질문. /cmux-start로 실행."
user-invocable: true
classification: workflow
allowed-tools: Bash, Read, Write, Agent, AskUserQuestion
---

# /cmux-start — 오케스트레이션 시작

입력: `$ARGUMENTS`

이 커맨드 하나로 AI 다중 자동 협업 플랫폼을 시작합니다.

**결과물:**
- 사이드바에 **"컨트롤 타워"** workspace (맨 위 고정)
- 컨트롤 타워 안에 **사장(Main)**, **와쳐(Watcher)**, **자비스(JARVIS)** 3개 pane
- 사장 pane에 "작업을 지시해주세요" 출력
- 기존 세션이 있으면 오케스트레이션 포함 여부 질문

---

## 실행 절차 (MANDATORY — 순서대로)

### Step 0: 사전 검증

```bash
cmux identify > /dev/null 2>&1
# 실패 시: "cmux 환경이 아닙니다. cmux 터미널에서 실행해주세요." 출력 후 중단
```

### Step 0.5: 기존 세션 감지 + 포함 여부 질문

현재 cmux에 열려있는 workspace/surface를 스캔하고, 기존 세션이 있으면 사용자에게 질문합니다.

```bash
# 기존 surface 스캔
TREE=$(cmux tree --all 2>/dev/null)
SURFACE_COUNT=$(echo "$TREE" | grep -c "surface:" || echo "1")
```

**기존 세션이 2개 이상이면 AskUserQuestion:**

```
현재 cmux에 {N}개 세션이 열려있습니다:
{각 workspace: surface 목록}

이 세션들을 오케스트레이션에 포함할까요?
[포함] → 기존 세션을 팀원으로 등록. Main이 관리.
[새로 시작] → 기존 세션은 그대로 두고, 새 컨트롤 타워만 생성.
```

- **[포함]** → 기존 surface를 eagle-status에 등록, dispatch 대상에 추가
- **[새로 시작]** → 기존 세션 무시, 컨트롤 타워만 신규 생성

### Step 0.9: 크로스플랫폼 유틸리티 데먼 시작

```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/cmux_compat.py start 2>/dev/null
```

### Step 1: 컨트롤 타워 workspace 이름 변경

현재 workspace 이름을 **"컨트롤 타워"**로 변경합니다.

```bash
MAIN_WS=$(cmux identify 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('caller',{}).get('workspace_ref',''))" 2>/dev/null)
MAIN_SID=$(cmux identify 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('caller',{}).get('surface_ref',''))" 2>/dev/null)

# workspace 이름을 "컨트롤 타워"로
cmux rename-workspace --workspace $MAIN_WS "컨트롤 타워"

# 현재 pane(사장) 탭 이름 변경
cmux rename-tab --surface $MAIN_SID "사장(Main)"
```

### Step 2: Main(사장) 등록

```bash
python3 -c "
import json, os
from datetime import datetime, timezone
roles_file = '/tmp/cmux-roles.json'
roles = {}
if os.path.exists(roles_file):
    try:
        with open(roles_file) as f: roles = json.load(f)
    except: pass
roles['main'] = {
    'surface': '$MAIN_SID',
    'workspace': '$MAIN_WS',
    'started_at': datetime.now(timezone.utc).isoformat(),
    'last_heartbeat': datetime.now(timezone.utc).isoformat()
}
with open(roles_file, 'w') as f: json.dump(roles, f, indent=2)
"
```

### Step 3: 와쳐(Watcher) pane 생성

컨트롤 타워 workspace 안에 새 pane을 만들고 Claude Code + /cmux-watcher를 실행합니다.

```bash
# 기존 Watcher 확인
EXISTING_WATCHER=$(python3 -c "
import json
try:
    with open('/tmp/cmux-roles.json') as f: roles = json.load(f)
    print(roles.get('watcher',{}).get('surface',''))
except: print('')
" 2>/dev/null)

if [ -z "$EXISTING_WATCHER" ]; then
    RESULT=$(cmux new-pane --direction right)
    WATCHER_SID=$(echo "$RESULT" | awk '{for(i=1;i<=NF;i++) if($i ~ /surface:/) print $i}')

    # 탭 이름 변경
    cmux rename-tab --surface $WATCHER_SID "와쳐(Watcher)"

    # Claude Code 시작
    cmux send --surface $WATCHER_SID "claude"

    # 30초 폴링
    for i in $(seq 1 10); do
        sleep 3
        SCREEN=$(cmux read-screen --surface $WATCHER_SID --lines 5 2>/dev/null)
        if echo "$SCREEN" | grep -qE "❯|shortcuts|trust"; then break; fi
    done
    cmux send-key --surface $WATCHER_SID Enter
    sleep 2

    # /cmux-watcher 실행
    cmux send --surface $WATCHER_SID "/cmux-watcher"
    cmux send-key --surface $WATCHER_SID Enter

    # roles.json 등록
    python3 -c "
import json
from datetime import datetime, timezone
with open('/tmp/cmux-roles.json') as f: roles = json.load(f)
roles['watcher'] = {'surface':'$WATCHER_SID','workspace':'$MAIN_WS','started_at':datetime.now(timezone.utc).isoformat()}
with open('/tmp/cmux-roles.json','w') as f: json.dump(roles,f,indent=2)
"
else
    echo "⏭ 와쳐 이미 활성: $EXISTING_WATCHER"
fi
```

### Step 4: 자비스(JARVIS) pane 생성

컨트롤 타워 workspace 안에 JARVIS pane을 만듭니다.

```bash
EXISTING_JARVIS=$(python3 -c "
import json
try:
    with open('/tmp/cmux-roles.json') as f: roles = json.load(f)
    print(roles.get('jarvis',{}).get('surface',''))
except: print('')
" 2>/dev/null)

if [ -z "$EXISTING_JARVIS" ]; then
    RESULT=$(cmux new-pane --direction right)
    JARVIS_SID=$(echo "$RESULT" | awk '{for(i=1;i<=NF;i++) if($i ~ /surface:/) print $i}')

    # 탭 이름 변경
    cmux rename-tab --surface $JARVIS_SID "자비스(JARVIS)"

    # Claude Code 시작 (JARVIS는 모니터링 전용이므로 권한 프롬프트 스킵)
    cmux send --surface $JARVIS_SID "claude --dangerously-skip-permissions"

    for i in $(seq 1 10); do
        sleep 3
        SCREEN=$(cmux read-screen --surface $JARVIS_SID --lines 5 2>/dev/null)
        if echo "$SCREEN" | grep -qE "❯|shortcuts|bypass|trust"; then break; fi
    done
    cmux send-key --surface $JARVIS_SID Enter
    sleep 2

    # JARVIS 시작 명령 전달
    cmux send --surface $JARVIS_SID "당신은 JARVIS 시스템 관리자입니다. cmux-jarvis 스킬을 사용하여 오케스트레이션 상태를 모니터링하세요. /tmp/cmux-roles.json과 /tmp/cmux-eagle-status.json을 주기적으로 확인하고, 문제 발견 시 사장(Main) pane에 알려주세요."
    cmux send-key --surface $JARVIS_SID Enter

    # roles.json 등록
    python3 -c "
import json
from datetime import datetime, timezone
with open('/tmp/cmux-roles.json') as f: roles = json.load(f)
roles['jarvis'] = {'surface':'$JARVIS_SID','workspace':'$MAIN_WS','started_at':datetime.now(timezone.utc).isoformat()}
with open('/tmp/cmux-roles.json','w') as f: json.dump(roles,f,indent=2)
"
else
    echo "⏭ 자비스 이미 활성: $EXISTING_JARVIS"
fi
```

### Step 5: 컨트롤 타워 고정 + 오케스트레이션 모드 활성화

```bash
# 컨트롤 타워를 사이드바 맨 위에 고정
cmux reorder-workspace --workspace $MAIN_WS --index 0
touch /tmp/cmux-orch-enabled
```

### Step 5.5: JARVIS 복구 체크

```bash
LOCK_FILE="$HOME/.claude/cmux-jarvis/.evolution-lock"
if [ -f "$LOCK_FILE" ]; then
    EVO_ID=$(python3 -c "import json; print(json.load(open('$LOCK_FILE')).get('evo_id',''))" 2>/dev/null)
    echo "⚠️ 중단된 진화 발견: $EVO_ID. JARVIS가 자동 복구합니다."
fi
```

### Step 6: 사장 pane에 안내 출력

```
═══════════════════════════════════════════════════════
  cmux AI 다중 자동 협업 플랫폼 — 준비 완료!
═══════════════════════════════════════════════════════

  컨트롤 타워 구성:
  ─────────────────────────────────────────────────────
  🔵 사장(Main)   — 이 pane. 작업 지시 + 부서 편성
  🟢 와쳐(Watcher) — 모니터링 + 리소스 관리
  🟡 자비스(JARVIS) — User 직속 참모. 설정 진화 + 정책 변경 + 문제 즉각 해결

  이제 작업을 지시해주세요. 예:
  ─────────────────────────────────────────────────────
  "로그인 기능을 추가해줘"
  "프로젝트 리팩토링해줘"
  "보안 감사를 해줘"

  명령어:
  ─────────────────────────────────────────────────────
  /cmux-config         AI 프로파일 관리
  /cmux-stop           오케스트레이션 종료
  /cmux-watcher-mute   와쳐 알림 토글
  /cmux-pause          긴급 정지/재개
  /cmux-help           도움말
  /cmux-uninstall      제거 + 롤백

═══════════════════════════════════════════════════════
```

### Step 7: Orchestrator 스킬 활성화

Skill("cmux-orchestrator")를 활성화하여 Main(사장) 역할을 시작합니다.

---

## 주의사항

- cmux 환경이 아니면 실행 불가
- 이미 오케스트레이션 모드이면 중복 시작 방지 (roles.json 확인)
- 기존 세션 포함 여부는 사용자가 결정
- 컨트롤 타워 workspace가 항상 사이드바 맨 위
- 사장 pane에서만 작업 지시 (와쳐/자비스는 자동 동작)
