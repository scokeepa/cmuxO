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

# ─── OS 감지 ──────────────────────────────────────

OS_TYPE="unknown"
case "$(uname -s)" in
  Darwin) OS_TYPE="macos" ;;
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then
      OS_TYPE="wsl"
    else
      OS_TYPE="linux"
    fi
    ;;
esac

if [ "$OS_TYPE" = "wsl" ]; then
  echo "  ⚠  WSL 환경이 감지되었습니다."
  echo "     알려진 제약사항:"
  echo "     - tmux 클립보드 통합 제한 (win32yank 필요)"
  echo "     - /tmp 경로가 Windows와 분리됨"
  echo "     - systemd 미지원 시 데먼 자동 시작 수동 설정 필요"
  echo ""
  read -p "  설치를 계속하시겠습니까? [Y/n] " yn
  if [ "${yn:-Y}" != "Y" ] && [ "${yn:-y}" != "y" ]; then
    echo "  설치를 취소합니다."
    exit 0
  fi
fi

echo "  ✓ OS: $OS_TYPE ($(uname -m))"
echo ""

# ─── 사전 검증 ─────────────────────────────────────

echo "[1/6] 사전 검증..."

# cmux / tmux(psmux) 확인 + 자동 설치
CMUX_MODE=""
if command -v cmux >/dev/null 2>&1; then
  CMUX_VER=$(cmux --version 2>/dev/null | head -1)
  echo "  ✓ cmux: $CMUX_VER"
  CMUX_MODE="cmux"
elif command -v tmux >/dev/null 2>&1; then
  TMUX_VER=$(tmux -V 2>/dev/null)
  echo "  ✓ tmux: $TMUX_VER (cmux-shim으로 호환 모드 사용)"
  CMUX_MODE="shim"
else
  echo "  ✗ cmux 또는 tmux가 설치되어 있지 않습니다."
  echo ""
  case "$OS_TYPE" in
    macos)
      echo "  cmux 자동 설치를 시도합니다..."
      if command -v brew >/dev/null 2>&1; then
        brew tap manaflow-ai/cmux 2>/dev/null && brew install --cask cmux 2>/dev/null
        if command -v cmux >/dev/null 2>&1; then
          echo "  ✓ cmux 설치 완료"
          CMUX_MODE="cmux"
        else
          echo "  ⚠ cmux 설치 실패. tmux로 대체합니다..."
          brew install tmux 2>/dev/null
          CMUX_MODE="shim"
        fi
      else
        echo "  Homebrew가 없습니다. 수동 설치해주세요:"
        echo "    https://cmux.com 또는 brew install tmux"
        exit 1
      fi
      ;;
    linux)
      echo "  tmux 자동 설치를 시도합니다..."
      if command -v apt >/dev/null 2>&1; then
        sudo apt install -y tmux 2>/dev/null
      elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y tmux 2>/dev/null
      elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm tmux 2>/dev/null
      fi
      if command -v tmux >/dev/null 2>&1; then
        echo "  ✓ tmux 설치 완료"
        CMUX_MODE="shim"
      else
        echo "  ✗ tmux 자동 설치 실패. 수동 설치해주세요."
        exit 1
      fi
      ;;
    wsl)
      echo "  psmux 또는 tmux 자동 설치를 시도합니다..."
      if command -v winget.exe >/dev/null 2>&1; then
        winget.exe install psmux 2>/dev/null
      fi
      # WSL 내부에서는 tmux도 사용 가능
      if ! command -v tmux >/dev/null 2>&1; then
        sudo apt install -y tmux 2>/dev/null
      fi
      if command -v tmux >/dev/null 2>&1; then
        echo "  ✓ tmux 설치 완료 (WSL)"
        CMUX_MODE="shim"
      else
        echo "  ✗ 설치 실패. 수동으로 tmux를 설치해주세요."
        exit 1
      fi
      ;;
    *)
      echo "  지원되지 않는 OS입니다."
      exit 1
      ;;
  esac
fi

# python3 확인
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✗ python3가 설치되어 있지 않습니다."
  exit 1
fi
PY_VER=$(python3 --version 2>/dev/null)
echo "  ✓ $PY_VER"

# chromadb 설치 (Mentor Lane 필수)
if python3 -c "import chromadb" 2>/dev/null; then
  CHROMA_VER=$(python3 -c "import chromadb; print(chromadb.__version__)" 2>/dev/null)
  echo "  ✓ chromadb: $CHROMA_VER"
else
  echo "  chromadb 설치 중..."
  pip3 install chromadb --quiet 2>/dev/null
  if python3 -c "import chromadb" 2>/dev/null; then
    CHROMA_VER=$(python3 -c "import chromadb; print(chromadb.__version__)" 2>/dev/null)
    echo "  ✓ chromadb: $CHROMA_VER (설치 완료)"
  else
    echo "  ⚠ chromadb 설치 실패. Mentor Lane 기능 제한됨. 수동 설치: pip3 install chromadb"
  fi
fi

# ChromaDB telemetry 비활성화 (posthog warning 제거)
export ANONYMIZED_TELEMETRY=False

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
for f in "$SKILLS_DIR/cmux-jarvis/hooks/"*.sh "$SKILLS_DIR/cmux-jarvis/scripts/"*.sh "$SKILLS_DIR/cmux-jarvis/scripts/"*.py; do
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

# ─── cmux-shim 배포 (tmux 모드일 때) ─────────────────

if [ "$CMUX_MODE" = "shim" ]; then
  echo "[+] cmux-shim 설치 (tmux 호환 모드)..."
  SHIM_SRC="$SKILLS_DIR/cmux-orchestrator/scripts/cmux-shim.py"
  SHIM_DIR="$HOME/.local/bin"
  mkdir -p "$SHIM_DIR"
  if [ -f "$SHIM_SRC" ]; then
    chmod +x "$SHIM_SRC"
    # cmux 래퍼 스크립트 생성 (python3로 shim 호출)
    cat > "$SHIM_DIR/cmux" << SHIMEOF
#!/bin/sh
exec python3 "$SHIM_SRC" "\$@"
SHIMEOF
    chmod +x "$SHIM_DIR/cmux"
    echo "  ✓ cmux-shim → $SHIM_DIR/cmux"
    # PATH 확인
    if ! echo "$PATH" | tr ':' '\n' | grep -q "$SHIM_DIR"; then
      echo ""
      echo "  ⚠ $SHIM_DIR가 PATH에 없습니다. 셸 설정에 추가하세요:"
      echo "    export PATH=\"$SHIM_DIR:\$PATH\""
      echo ""
    fi
  else
    echo "  ⚠ cmux-shim.py를 찾을 수 없습니다."
  fi
  echo ""
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
