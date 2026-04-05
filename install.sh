#!/bin/bash
# install.sh — cmux 멀티 AI 협업 플랫폼 설치
# 사용법: bash install.sh
#
# 전제 조건:
#   - cmux 0.62+  (cmux --version)
#   - Claude Code  (claude --version)
#   - python3 3.9+ (python3 --version)
#
# 설치 내용:
#   1. 기존 settings.json 백업
#   2. 7개 skill → ~/.claude/skills/
#   3. 실행 권한 설정
#   4. activation-hook.sh 실행 → symlink + settings.json 자동 등록
#   5. AI 프로파일 자동 감지

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
HOOKS_DIR="$HOME/.claude/hooks"
BACKUP_DIR="$HOME/.claude/backups/cmux-$(date +%Y%m%d_%H%M%S)"
SETTINGS="$HOME/.claude/settings.json"

echo ""
echo "  ===================================================="
echo "   cmux 멀티 AI 협업 플랫폼 설치 (v7.3)"
echo "  ===================================================="
echo ""

# ─── 사전 검증 ─────────────────────────────────────

echo "[1/6] 사전 검증..."

# cmux 확인
if ! command -v cmux >/dev/null 2>&1; then
  echo "  ✗ cmux가 설치되어 있지 않습니다."
  echo "    cmux를 먼저 설치해주세요."
  exit 1
fi
CMUX_VER=$(cmux --version 2>/dev/null | head -1)
echo "  ✓ cmux: $CMUX_VER"

# python3 확인
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✗ python3가 설치되어 있지 않습니다."
  exit 1
fi
PY_VER=$(python3 --version 2>/dev/null)
echo "  ✓ $PY_VER"

# Claude Code 확인 (경고만)
if ! command -v claude >/dev/null 2>&1; then
  echo "  ⚠ Claude Code CLI를 찾을 수 없습니다 (설치 후 사용 가능)"
else
  echo "  ✓ Claude Code: $(claude --version 2>/dev/null | head -1)"
fi

# 소스 디렉토리 확인
SKILLS=("cmux-orchestrator" "cmux-watcher" "cmux-jarvis" "cmux-config" "cmux-start" "cmux-stop" "cmux-help" "cmux-uninstall" "cmux-pause")
for skill in "${SKILLS[@]}"; do
  if [ ! -d "$SCRIPT_DIR/$skill" ]; then
    echo "  ✗ 소스 디렉토리 없음: $skill"
    exit 1
  fi
done
echo "  ✓ 소스 패키지: ${#SKILLS[@]}개 skill 확인"

echo ""

# ─── 백업 ──────────────────────────────────────────

echo "[2/6] 기존 설정 백업..."
mkdir -p "$BACKUP_DIR"

if [ -f "$SETTINGS" ]; then
  cp "$SETTINGS" "$BACKUP_DIR/settings.json"
  echo "  ✓ settings.json → $BACKUP_DIR/"
fi

# 기존 cmux skill이 있으면 백업
EXISTING=0
for skill in "${SKILLS[@]}"; do
  if [ -d "$SKILLS_DIR/$skill" ]; then
    cp -r "$SKILLS_DIR/$skill" "$BACKUP_DIR/"
    EXISTING=$((EXISTING+1))
  fi
done
if [ "$EXISTING" -gt 0 ]; then
  echo "  ✓ 기존 skill $EXISTING개 백업"
fi

# manifest 저장
cat > "$BACKUP_DIR/manifest.json" << MANIFEST
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "skills_backed_up": $EXISTING,
  "settings_backed_up": $([ -f "$SETTINGS" ] && echo "true" || echo "false"),
  "version": "7.3"
}
MANIFEST
echo "  ✓ manifest.json 생성"
echo ""

# ─── 복사 ──────────────────────────────────────────

echo "[3/6] Skill 설치..."
mkdir -p "$SKILLS_DIR" "$HOOKS_DIR"

for skill in "${SKILLS[@]}"; do
  # 기존 skill 제거 후 복사 (깨끗한 설치)
  rm -rf "$SKILLS_DIR/$skill"
  cp -r "$SCRIPT_DIR/$skill" "$SKILLS_DIR/"
  echo "  ✓ $skill"
done
echo ""

# ─── 실행 권한 ─────────────────────────────────────

echo "[4/6] 실행 권한 설정..."

# orchestrator hooks + scripts
for f in "$SKILLS_DIR/cmux-orchestrator/hooks/"*.sh "$SKILLS_DIR/cmux-orchestrator/hooks/"*.py; do
  [ -f "$f" ] && chmod +x "$f"
done
for f in "$SKILLS_DIR/cmux-orchestrator/scripts/"*.sh "$SKILLS_DIR/cmux-orchestrator/scripts/"*.py; do
  [ -f "$f" ] && chmod +x "$f"
done
chmod +x "$SKILLS_DIR/cmux-orchestrator/activation-hook.sh" 2>/dev/null

# watcher hooks + scripts
for f in "$SKILLS_DIR/cmux-watcher/hooks/"*.sh "$SKILLS_DIR/cmux-watcher/scripts/"*.sh "$SKILLS_DIR/cmux-watcher/scripts/"*.py; do
  [ -f "$f" ] && chmod +x "$f"
done

# jarvis hooks + scripts
for f in "$SKILLS_DIR/cmux-jarvis/hooks/"*.sh "$SKILLS_DIR/cmux-jarvis/scripts/"*.sh; do
  [ -f "$f" ] && chmod +x "$f"
done
for f in "$SKILLS_DIR/cmux-jarvis/scripts/verify-plugins/"*.sh; do
  [ -f "$f" ] && chmod +x "$f"
done
chmod +x "$SKILLS_DIR/cmux-jarvis/activation-hook.sh" 2>/dev/null

echo "  ✓ hooks + scripts 실행 권한 설정"
echo ""

# ─── activation-hook 실행 ──────────────────────────

echo "[5/6] Hook 등록 (symlink + settings.json)..."

# install flag 초기화 (강제 재등록)
rm -f "$HOME/.claude/.state/cmux-orch-hooks-installed.flag" 2>/dev/null

# activation-hook 실행 (orchestrator + jarvis)
bash "$SKILLS_DIR/cmux-orchestrator/activation-hook.sh" 2>/dev/null
bash "$SKILLS_DIR/cmux-jarvis/activation-hook.sh" 2>/dev/null

# 등록 결과 확인
SYMLINKS=$(ls "$HOOKS_DIR"/cmux-*.sh "$HOOKS_DIR"/cmux-*.py 2>/dev/null | wc -l | tr -d ' ')
echo "  ✓ symlinks: ${SYMLINKS}개"

if [ -f "$SETTINGS" ]; then
  HOOK_COUNT=$(python3 -c "
import json
with open('$SETTINGS') as f: d=json.load(f)
count=0
for ev, groups in d.get('hooks',{}).items():
    for g in groups:
        for h in g.get('hooks',[]):
            if 'cmux' in h.get('command',''): count+=1
print(count)
" 2>/dev/null || echo "?")
  echo "  ✓ settings.json: ${HOOK_COUNT}개 hook 등록"
fi
echo ""

# ─── AI 프로파일 감지 ──────────────────────────────

echo "[6/6] AI 프로파일 자동 감지..."
PROFILE_SCRIPT="$SKILLS_DIR/cmux-orchestrator/scripts/manage-ai-profile.py"
if [ -f "$PROFILE_SCRIPT" ]; then
  python3 "$PROFILE_SCRIPT" --detect 2>/dev/null && echo "  ✓ AI 감지 완료" || echo "  ⚠ AI 감지 스킵 (수동: /cmux-config detect)"
else
  echo "  ⚠ manage-ai-profile.py 없음 (수동 설정 필요)"
fi

echo ""
echo "  ===================================================="
echo "   설치 완료!"
echo "  ===================================================="
echo ""
echo "   시작:     Claude Code에서 /cmux-start"
echo "   설정:     /cmux-config"
echo "   도움말:   /cmux-help"
echo "   제거:     /cmux-uninstall (백업에서 롤백 가능)"
echo ""
echo "   백업 위치: $BACKUP_DIR"
echo ""
echo "  ===================================================="
echo ""
