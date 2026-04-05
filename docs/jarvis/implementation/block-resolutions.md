# BLOCK 10건 해결 — 구현 준비 완료

> 시뮬레이션 v9에서 발견된 BLOCK 10건의 구체적 해결 내용.
> 구현 시 이 파일을 참조하여 즉시 코딩.

---

## B1: test-templates.md 내용 (LOW)

```markdown
# 진화 유형별 테스트 템플릿

## settings_change
1. JSON 유효성: `python3 -c "import json; json.load(open('settings.json'))"`
2. 변경 키 존재: `jq -e '.dispatch.timeout_seconds' settings.json`
3. surface 정상: `cmux surface-health` → ERROR 없음

## hook_change
1. 파일 존재 + 실행 권한: `[ -x "$HOOK_PATH" ]`
2. stdin 파이프 테스트: `echo '{}' | bash $HOOK_PATH`
3. JSON 출력 유효: `echo '{}' | bash $HOOK_PATH | python3 -c "import json,sys;json.load(sys.stdin)"`
4. 기존 hook 비간섭: 다른 hook 정상 실행 확인

## skill_change
1. YAML frontmatter: `head -10 SKILL.md | grep "^name:"`
2. 스킬 로드 확인: Claude Code가 스킬 인식하는지

## code_change
1. 구문 검사: `bash -n script.sh` / `python3 -c "compile(open('f').read(),'f','exec')"`
2. 실행 테스트: 예상 입력 → 예상 출력
```

---

## B2: is_worker_surface() 구현 (LOW)

```bash
is_worker_surface() {
  # 마커 파일 기반 (CV-02 확정)
  # Worker pane 생성 시 /tmp/cmux-jarvis-worker-{WORKER_PID} 생성
  # hook 프로세스에서는 PPID 체인이 불확실하므로 glob 패턴 사용
  ls /tmp/cmux-jarvis-worker-* >/dev/null 2>&1 || return 1

  # 현재 surface가 Worker인지 확인 (roles.json에 jarvis 등록된 surface가 아니면 Worker 가능)
  local MY_SID
  MY_SID=$(cmux identify 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin)['caller']['surface_ref'])" 2>/dev/null)
  local JARVIS_SID
  JARVIS_SID=$(jq -r '.jarvis.surface // ""' /tmp/cmux-roles.json 2>/dev/null)
  local MAIN_SID
  MAIN_SID=$(jq -r '.main.surface // ""' /tmp/cmux-roles.json 2>/dev/null)
  local WATCHER_SID
  WATCHER_SID=$(jq -r '.watcher.surface // ""' /tmp/cmux-roles.json 2>/dev/null)

  # Main/JARVIS/Watcher가 아니면 Worker (또는 일반 surface)
  [ "$MY_SID" != "$JARVIS_SID" ] && [ "$MY_SID" != "$MAIN_SID" ] && [ "$MY_SID" != "$WATCHER_SID" ]
}
```

**주의:** `cmux identify`가 hook 프로세스에서 동작하는지 확인 필요.
동작 안 하면 → 마커 파일 존재 여부만으로 판단 (모든 surface에서 Worker 제약 적용 = 안전 방향).

---

## B3: 3중 백업 → Phase 1 로컬 2중 (HIGH, 해결됨)

```bash
backup_settings() {
  local EVO_DIR="$HOME/.claude/cmux-jarvis/evolutions/$1/backup"
  mkdir -p "$EVO_DIR"

  # 이전 백업이 있으면 .prev로 이동 (2세대 유지)
  [ -f "$EVO_DIR/settings.json" ] && mv "$EVO_DIR/settings.json" "$EVO_DIR/settings.json.prev"

  # 원자적 복사
  cp "$HOME/.claude/settings.json" "/tmp/jarvis-backup-$$.json"
  mv "/tmp/jarvis-backup-$$.json" "$EVO_DIR/settings.json"
}

rollback_settings() {
  local EVO_DIR="$HOME/.claude/cmux-jarvis/evolutions/$1/backup"
  [ ! -f "$EVO_DIR/settings.json" ] && echo "백업 없음" && return 1

  # 원자적 복원
  cp "$EVO_DIR/settings.json" "/tmp/jarvis-restore-$$.json"
  mv "/tmp/jarvis-restore-$$.json" "$HOME/.claude/settings.json"
}
```

---

## B4: additionalContext 원본 (MED)

**해결:** `references/jarvis-instructions.md` 단일 파일 생성.
session-start.sh가 이 파일을 cat으로 읽어 additionalContext에 주입.

```bash
# jarvis-session-start.sh 내부
INSTRUCTIONS="$HOME/.claude/skills/cmux-jarvis/references/jarvis-instructions.md"
if [ -f "$INSTRUCTIONS" ]; then
  CONTEXT=$(cat "$INSTRUCTIONS" | python3 -c "import sys;print(sys.stdin.read().replace('\"','\\\\\"').replace('\n','\\\\n'))")
  # JSON에 삽입
fi
```

**jarvis-instructions.md 내용 (~80줄):**
- Iron Laws 3개 요약
- GATE J-1 규칙
- Red Flags 참조
- 3레인 분류 기준
- 모니터링 메트릭 5개
- 진화 파이프라인 6단계 요약
- 피드백 5유형 처리
- 안전 제한 (MAX_CONSECUTIVE/DAILY)

---

## B5: evolution/SKILL.md 내용 (HIGH)

```markdown
---
name: cmux-jarvis-evolution
description: "JARVIS 진화 파이프라인 6단계 실행"
user-invocable: false
classification: workflow
---

# 진화 파이프라인 (Phase 1: 6단계)

이 스킬은 JARVIS 코어에서 Lane B(진화 실행) 시 호출됩니다.

## 실행 절차

### ① 감지 확인
- FileChanged/Watcher 알림으로 이미 감지된 상태
- metric-dictionary.json 임계값 기준 정량 확인
- North Star 설정: "이 진화의 성공 기준은?"
- Scope Lock: bounded / out_of_scope / followup

### ② 1차 승인
- AskUserQuestion: [수립][보류][폐기]
- AGENDA_LOG.md 기록
- 보류 시 deferred-issues.json 등록

### ③ 백업 + 계획
- `bash jarvis-evolution.sh backup evo-{N}`
- DAG 구조화 + evolution_type 결정
- 2차 승인: diff 표시 → [실행][수정][폐기]

### ④ Worker 실행
- `cmux new-workspace --command "claude"`
- `cmux set-buffer + paste-buffer` (계획 전달)
- Worker는 proposed-settings.json + STATUS 생성
- 완료 감지: 플래그 파일 ls 체크

### ⑤ 검증 + 반영 판단
- `bash jarvis-verify.sh evo-{N}`
- evidence.json 존재 확인
- Outbound Gate (hooks 키, Scope Lock, Red Flags)
- 시각화 보고서 생성 (Mermaid + ASCII)
- AskUserQuestion: [KEEP][DISCARD]

### ⑥ 반영 또는 롤백
- KEEP → `bash jarvis-evolution.sh apply evo-{N}`
- DISCARD → `bash jarvis-evolution.sh rollback evo-{N}`
- 사후: 옵티미스틱 승격 + AGENDA_LOG + counter 업데이트
```

---

## B6: visualization/SKILL.md 내용 (MED)

```markdown
---
name: cmux-jarvis-visualization
description: "JARVIS 진화 보고서 시각화"
user-invocable: false
classification: workflow
---

# 진화 보고서 시각화

## Before/After 보고서 (한국어)

### 형식
\```
═══════════════════════════════════════
JARVIS 진화 보고서: evo-{N}
═══════════════════════════════════════
■ 변경: {변경 내용 1줄}

■ Before/After
┌──────────┬──────────┬──────────────┐
│ 메트릭    │ Before   │ After (예상)  │
├──────────┼──────────┼──────────────┤
│ {metric} │ {value}  │ {expected}   │
└──────────┴──────────┴──────────────┘

■ 범위: {Scope Lock bounded}
═══════════════════════════════════════
\```

### Mermaid 상태 다이어그램
\```mermaid
stateDiagram-v2
  [*] --> 감지
  감지 --> 분석
  분석 --> 승인
  승인 --> 백업: 수립
  승인 --> [*]: 폐기
  백업 --> 구현
  구현 --> 검증
  검증 --> 반영: KEEP
  검증 --> 롤백: DISCARD
\```

### 메트릭 수집 (eagle-status.json 필드)
\```json
{
  "timestamp": "eagle.timestamp",
  "stall_count": "eagle.stats.stalled",
  "error_count": "eagle.stats.error",
  "idle_count": "eagle.stats.idle",
  "working_count": "eagle.stats.working",
  "ended_count": "eagle.stats.ended",
  "total_surfaces": "eagle.stats.total"
}
\```
```

---

## B7: jarvis-evolution.sh CLI 인터페이스 (HIGH)

```bash
#!/bin/bash
# jarvis-evolution.sh — JARVIS 진화 CLI
# Usage: jarvis-evolution.sh <command> [evo-id]

set -euo pipefail
JARVIS_DIR="$HOME/.claude/cmux-jarvis"
LOCK_FILE="$JARVIS_DIR/.evolution-lock"
COUNTER_FILE="$JARVIS_DIR/.evolution-counter"
CONFIG="$JARVIS_DIR/config.json"

case "${1:-help}" in
  detect)
    # eagle-status 읽기 + metric-dictionary 임계값 비교
    # 출력: JSON {threshold_exceeded: bool, metrics: {...}}
    ;;
  backup)
    # $2 = evo-id
    # 1. evolutions/$EVO_ID/backup/ 생성
    # 2. settings.json 원자적 복사 (2세대)
    # 3. CURRENT_LOCK 생성 (TTL 60분)
    # 4. 안전 체크 (MAX_CONSECUTIVE/DAILY)
    ;;
  apply)
    # $2 = evo-id
    # 전제: LOCK phase="applying" + evidence.json 존재
    # 1. proposed-settings.json + settings.json → jq deep merge
    # 2. 원자적 쓰기 (tmp→rename)
    # 3. LOCK 해제
    # 4. counter 업데이트
    ;;
  rollback)
    # $2 = evo-id
    # 1. backup/settings.json → settings.json 복원 (원자적)
    # 2. LOCK 해제
    ;;
  status)
    # LOCK 상태, 큐, 카운터 표시
    # 출력: JSON
    ;;
  cleanup)
    # $2 = evo-id
    # Worker pane 종료 + 마커/플래그 파일 삭제
    ;;
  lock-phase)
    # $2 = evo-id, $3 = phase (planning|implementing|applying)
    # LOCK 파일의 phase 필드 업데이트
    ;;
  help|*)
    echo "Usage: jarvis-evolution.sh <detect|backup|apply|rollback|status|cleanup|lock-phase> [evo-id] [args]"
    ;;
esac
```

---

## B8: before-metrics.json 수집 (MED)

**소스:** eagle-status.json의 `stats` 필드가 이미 집계 정보를 제공.

```bash
# jarvis-verify.sh 내부 — before-metrics 수집
collect_metrics() {
  local EVO_DIR="$HOME/.claude/cmux-jarvis/evolutions/$1"
  local PHASE="$2"  # "before" 또는 "after"

  python3 -c "
import json, os
eagle = json.load(open('/tmp/cmux-eagle-status.json'))
metrics = {
    'timestamp': eagle['timestamp'],
    'stall_count': eagle['stats'].get('stalled', 0),
    'error_count': eagle['stats'].get('error', 0),
    'idle_count': eagle['stats'].get('idle', 0),
    'working_count': eagle['stats'].get('working', 0),
    'ended_count': eagle['stats'].get('ended', 0),
    'total_surfaces': eagle['stats'].get('total', 0),
    'stalled_surfaces': eagle.get('stalled_surfaces', ''),
    'error_surfaces': eagle.get('error_surfaces', ''),
}
with open('$EVO_DIR/${PHASE}-metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
"
}
```

**evidence.json 조립:**
```bash
assemble_evidence() {
  local EVO_DIR="$HOME/.claude/cmux-jarvis/evolutions/$1"
  python3 -c "
import json
before = json.load(open('$EVO_DIR/before-metrics.json'))
after = json.load(open('$EVO_DIR/after-metrics.json'))
evidence = {
    'evidence_type': 'metric_comparison',
    'before_snapshot': 'before-metrics.json',
    'after_snapshot': 'after-metrics.json',
    'metrics_compared': list(before.keys()),
    'collection_method': 'jarvis-verify.sh',
    'collected_at': after['timestamp'],
}
with open('$EVO_DIR/evidence.json', 'w') as f:
    json.dump(evidence, f, indent=2)
"
}
```

---

## B9: Worker 프롬프트 전문 (MED)

```markdown
# Evolution Worker 프롬프트 템플릿

당신은 JARVIS Evolution Worker입니다.
아래 진화 계획을 실행하세요.

## 진화 ID: {evo_id}
## 유형: {evolution_type}

## 범위 (Scope Lock)
- bounded: {bounded_scope}
- out_of_scope: {out_of_scope}

## 작업
{DAG 태스크 목록}

## 예상 결과
{expected_outcomes}

## 제약 (반드시 준수)
1. settings.json, ai-profile.json 직접 수정 **금지**
2. 모든 변경은 `~/.claude/cmux-jarvis/evolutions/{evo_id}/` 내부에만 파일 생성
3. 완료 시 아래 파일을 반드시 생성:
   - `proposed-settings.json` (변경할 키-값만 포함, hooks 키 금지!)
   - `file-mapping.json` (제안→실제 경로 매핑)
   - `STATUS` (JSON: evo_id, evolution_type, phase, status, expected_outcomes_documented)
4. settings_change 유형이면 `07-expected-outcomes.md` 필수 (3줄 이상)
5. code/hook/skill 유형이면 `05-tdd.md` 필수 (실패 테스트 먼저)
6. 완료 후: `touch /tmp/cmux-jarvis-{evo_id}-done`

## 보고 형식
- DONE: 모든 단계 성공
- DONE_WITH_CONCERNS: 완료했으나 우려사항 있음 (목록 첨부)
- BLOCKED: 진행 불가 (사유 + 시도한 방법)
- NEEDS_CONTEXT: 정보 부족 (필요한 정보 명시)
```

---

## B10: JARVIS activation-hook.sh (LOW)

```bash
#!/bin/bash
# cmux-jarvis activation hook
# 설치 시 hook 심링크 + settings.json 등록

set -e
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_SOURCE="$SKILL_DIR/hooks"
HOOKS_TARGET="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"

# 초기 디렉토리 생성
mkdir -p "$HOME/.claude/cmux-jarvis/evolutions"
mkdir -p "$HOOKS_TARGET"

# Hook 심링크 (기존 패턴)
for f in "$HOOKS_SOURCE"/*.sh; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  link="$HOOKS_TARGET/$fname"
  if [ ! -L "$link" ] && [ ! -f "$link" ]; then
    ln -s "$f" "$link"
    chmod +x "$f"
  fi
done

# settings.json Hook 등록 (Python — 기존 cmux-orchestrator 패턴)
python3 << 'PYEOF'
import json, os

settings_path = os.path.expanduser("~/.claude/settings.json")
if not os.path.exists(settings_path):
    exit(0)

with open(settings_path) as f:
    data = json.load(f)

if "hooks" not in data:
    data["hooks"] = {}

HOOK_MAP = {
    "cmux-jarvis-gate.sh": ("PreToolUse", "Edit|Write|Bash", 3),
    "cmux-settings-backup.sh": ("ConfigChange", None, 10),
    "jarvis-session-start.sh": ("SessionStart", None, 5),
    "jarvis-file-changed.sh": ("FileChanged", "cmux-eagle-status.json|cmux-watcher-alerts.json", 5),
    "jarvis-pre-compact.sh": ("PreCompact", None, 5),
    "jarvis-post-compact.sh": ("PostCompact", None, 5),
}

added = 0
for filename, (event, matcher, timeout) in HOOK_MAP.items():
    if event not in data["hooks"]:
        data["hooks"][event] = []

    # 중복 체크
    all_hooks = []
    for group in data["hooks"][event]:
        all_hooks.extend(group.get("hooks", []) if isinstance(group, dict) and "hooks" in group else [group])
    if any(filename in h.get("command", "") for h in all_hooks):
        continue

    entry = {
        "type": "command",
        "command": f"bash ~/.claude/hooks/{filename}",
        "timeout": timeout,
    }

    # matcher가 있으면 그룹으로, 없으면 기존 빈 matcher 그룹에 추가
    if matcher:
        data["hooks"][event].append({"matcher": matcher, "hooks": [entry]})
    else:
        # 빈 matcher 그룹 찾기
        found = False
        for group in data["hooks"][event]:
            if isinstance(group, dict) and group.get("matcher", "") == "":
                group.setdefault("hooks", []).append(entry)
                found = True
                break
        if not found:
            data["hooks"][event].append({"matcher": "", "hooks": [entry]})
    added += 1

with open(settings_path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"  JARVIS hooks: {added}개 등록")
PYEOF

# config.json 초기화 (없으면 생성)
CONFIG="$HOME/.claude/cmux-jarvis/config.json"
if [ ! -f "$CONFIG" ]; then
  cat > "$CONFIG" << 'JSON'
{
  "obsidian_vault_path": null,
  "poll_interval_seconds": 300,
  "max_consecutive_evolutions": 3,
  "max_daily_evolutions": 10,
  "queue_max_size": 5,
  "approval_timeout_minutes": 30,
  "lock_ttl_minutes": 60,
  "debounce_seconds": 60
}
JSON
fi
```
