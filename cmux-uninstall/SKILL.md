---
name: cmux-uninstall
description: "cmux 오케스트레이션 완전 제거 + 설치 전 상태로 롤백. /cmux-uninstall로 실행."
user-invocable: true
classification: configuration
allowed-tools: Bash, Read, AskUserQuestion
---

# /cmux-uninstall — 제거 + 롤백

입력: `$ARGUMENTS`

cmux 오케스트레이션 플랫폼을 제거하고, 설치 전 상태로 복원합니다.

---

## 실행 절차

### Step 1: 백업 확인

```bash
ls -la ~/.claude/backups/cmux-*/manifest.json 2>/dev/null
```

백업이 있으면 사용자에게 선택지 제공:
1. **롤백** — 백업에서 settings.json 복원 (완전 원래 상태)
2. **제거만** — cmux 관련만 제거 (기존 설정 보존)
3. **취소**

### Step 2: 오케스트레이션 중지

```bash
pkill -f "watcher-scan.py" 2>/dev/null || true
rm -f /tmp/cmux-*
rm -rf /tmp/cmux-vdiff/
```

> 와일드카드로 모든 cmux 임시 파일을 한 번에 정리. 개별 나열보다 안전하고 누락 없음.

### Step 3-A: 롤백 (백업 있을 때)

```bash
BACKUP_DIR=$(ls -dt ~/.claude/backups/cmux-* | head -1)
cp "$BACKUP_DIR/settings.json" ~/.claude/settings.json
```
→ settings.json이 설치 전 상태로 완전 복원

### Step 3-B: 제거만 (백업 없거나 제거만 선택)

```bash
# settings.json에서 cmux hooks만 제거 (다른 설정 보존)
python3 -c "
import json
with open('$HOME/.claude/settings.json') as f: d=json.load(f)
hooks = d.get('hooks', {})
for event in list(hooks.keys()):
    hooks[event] = [g for g in hooks[event]
                    if not any('cmux' in h.get('command','') for h in g.get('hooks',[]))]
    if not hooks[event]: del hooks[event]
if not hooks: d.pop('hooks', None)
with open('$HOME/.claude/settings.json','w') as f: json.dump(d,f,indent=2,ensure_ascii=False)
"
```

### Step 4: 파일 제거

```bash
rm -f ~/.claude/hooks/cmux-*
rm -rf ~/.claude/skills/cmux-orchestrator
rm -rf ~/.claude/skills/cmux-watcher
rm -rf ~/.claude/skills/cmux-config
rm -rf ~/.claude/skills/cmux-start
rm -rf ~/.claude/skills/cmux-help
rm -rf ~/.claude/skills/cmux-uninstall
```

### Step 4-B: Lid Auto-Pause 훅 제거 (macOS)

`install.sh`가 심어둔 마커 블록만 제거합니다. 사용자가 직접 작성한 `~/.sleep`/`~/.wakeup` 내용은 보존됩니다. sleepwatcher 본체는 건드리지 않습니다 (다른 용도로 사용 중일 수 있음).

```bash
if [ "$(uname -s)" = "Darwin" ]; then
  for f in "$HOME/.sleep" "$HOME/.wakeup"; do
    [ -f "$f" ] || continue
    if grep -qF '# >>> cmuxO lid-watcher >>>' "$f"; then
      sed -i '' '/# >>> cmuxO lid-watcher >>>/,/# <<< cmuxO lid-watcher <<</d' "$f"
      # 파일이 shebang만 남고 사실상 비었으면 제거
      if [ "$(grep -cvE '^\s*(#!|$)' "$f")" = "0" ]; then
        rm -f "$f"
      fi
    fi
  done
  # 잔존 paused 플래그 정리
  rm -f /tmp/cmux-paused.flag
fi
```

### Step 4-C: 메모리 정리 (선택)

```bash
if [ -d ~/.claude/memory/cmux ]; then
  echo "cmux 학습 메모리가 존재합니다 (~/.claude/memory/cmux/)"
fi
```

사용자에게 선택지:
1. **삭제** — `rm -rf ~/.claude/memory/cmux`
2. **보존** — 재설치 시 학습 데이터 활용 가능

### Step 5: 완료 보고

```
제거 완료.
- cmux hooks: 삭제됨
- cmux skills: 삭제됨
- 임시 파일: 삭제됨
- settings.json: [롤백됨 / cmux만 제거됨]
- 기존 plugins/permissions: 보존됨
```
