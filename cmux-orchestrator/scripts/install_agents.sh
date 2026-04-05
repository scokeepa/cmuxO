#!/bin/bash
# install_agents.sh — cmux 오케스트레이션 에이전트 설치
# 사용자 동의 후 ~/.claude/agents/에 에이전트 정의 복사
#
# Usage: bash install_agents.sh [--check|--install|--list|--install-hooks]

variable_skill_dir="$(cd "$(dirname "$0")/.." && pwd)"
variable_agents_src="${variable_skill_dir}/agents"
variable_agents_dst="$HOME/.claude/agents"
variable_scripts_dir="${variable_skill_dir}/scripts"
variable_settings_file="$HOME/.claude/settings.json"

case "${1:---check}" in
  --check)
    echo "=== cmux 에이전트 설치 상태 ==="
    for f in "${variable_agents_src}"/*.md; do
      [ -f "$f" ] || continue
      variable_name=$(basename "$f")
      if [ -f "${variable_agents_dst}/${variable_name}" ]; then
        echo "  ✅ ${variable_name} (설치됨)"
      else
        echo "  ❌ ${variable_name} (미설치)"
      fi
    done
    ;;
  --install)
    mkdir -p "$variable_agents_dst"
    variable_installed=0
    for f in "${variable_agents_src}"/*.md; do
      [ -f "$f" ] || continue
      variable_name=$(basename "$f")
      if [ -f "${variable_agents_dst}/${variable_name}" ]; then
        echo "  ⏭️  ${variable_name} (이미 존재, 스킵)"
      else
        cp "$f" "${variable_agents_dst}/${variable_name}"
        echo "  ✅ ${variable_name} 설치 완료"
        variable_installed=$((variable_installed + 1))
      fi
    done
    echo ""
    echo "${variable_installed}개 에이전트 설치 완료."
    ;;
  --list)
    echo "=== 번들된 에이전트 목록 ==="
    for f in "${variable_agents_src}"/*.md; do
      [ -f "$f" ] || continue
      variable_name=$(basename "$f" .md)
      variable_desc=$(grep "^description:" "$f" | head -1 | sed 's/description: //')
      variable_skills=$(grep -c "^  -" "$f" 2>/dev/null || echo 0)
      echo "  ${variable_name}: ${variable_skills}개 스킬 — ${variable_desc:0:60}"
    done
    ;;
  --install-hooks)
    echo "=== cmux 훅 스크립트 설치 상태 ==="
    echo ""

    # (1) scripts/ 폴더의 cmux-*.sh 파일 목록
    variable_hooks=()
    for hook in "${variable_scripts_dir}"/cmux-*.sh; do
      [ -f "$hook" ] || continue
      variable_hooks+=("$hook")
    done

    if [ ${#variable_hooks[@]} -eq 0 ]; then
      echo "  ⚠️  cmux-*.sh 훅 파일을 찾을 수 없습니다."
      exit 0
    fi

    echo "발견된 훅 파일 (${#variable_hooks[@]}개):"
    for hook in "${variable_hooks[@]}"; do
      variable_hook_name=$(basename "$hook")
      echo "  - ${variable_hook_name}"
    done
    echo ""

    # (2) settings.json에 훅 등록 여부 확인
    variable_missing_hooks=()
    variable_registered_hooks=()

    if [ ! -f "$variable_settings_file" ]; then
      echo "⚠️  settings.json 파일을 찾을 수 없습니다: ${variable_settings_file}"
      echo "    Claude Code를 최소 한 번 실행하여 settings.json을 생성해주세요."
      exit 0
    fi

    for hook in "${variable_hooks[@]}"; do
      variable_hook_path="$hook"
      variable_hook_name=$(basename "$hook")

      # settings.json에서 이 훅 파일명이 있는지 확인 (경로가 다를 수 있으므로 basename 매칭)
      if grep -q "$variable_hook_name" "$variable_settings_file" 2>/dev/null; then
        variable_registered_hooks+=("$variable_hook_name")
      else
        variable_missing_hooks+=("$variable_hook_name|$variable_hook_path")
      fi
    done

    echo "훅 등록 상태:"
    for hook_name in "${variable_registered_hooks[@]}"; do
      echo "  ✅ ${hook_name} (이미 등록됨)"
    done
    echo ""

    # (3) 미등록 훅이 있으면 등록 안내 출력
    if [ ${#variable_missing_hooks[@]} -gt 0 ]; then
      echo "⚠️  미등록 훅 (${#variable_missing_hooks[@]}개):"
      for entry in "${variable_missing_hooks[@]}"; do
        IFS='|' read -r hook_name hook_path <<< "$entry"
        echo "  ❌ ${hook_name}"
      done
      echo ""
      echo "📋 등록 방법:"
      echo "   Claude Code에서 ⌘Command + , 로 설정을 열고,"
      echo "   'User Hooks' 섹션에 다음 경로들을 추가하세요:"
      echo ""
      for entry in "${variable_missing_hooks[@]}"; do
        IFS='|' read -r hook_name hook_path <<< "$entry"
        echo "   \"${hook_path}\""
      done
      echo ""
      echo "   또는 settings.json의 'hooks' 배열에 수동으로 추가:"
      echo ""
      echo "   {"
      echo "     \"hooks\": ["
      for entry in "${variable_missing_hooks[@]}"; do
        IFS='|' read -r hook_name hook_path <<< "$entry"
        echo "       \"${hook_path}\","
      done
      echo "       ...기존 훅들"
      echo "     ]"
      echo "   }"
    else
      echo "✅ 모든 훅이 이미 등록되어 있습니다!"
    fi
    ;;
  --setup)
    echo "=== cmux orchestrator 원클릭 설치 ==="
    echo ""

    # 1. 에이전트 설치
    echo "[1/4] 에이전트 설치..."
    mkdir -p "$variable_agents_dst"
    for f in "${variable_agents_src}"/*.md; do
      [ -f "$f" ] || continue
      variable_name=$(basename "$f")
      cp "$f" "${variable_agents_dst}/${variable_name}" 2>/dev/null
      echo "  ✅ ${variable_name}"
    done

    # 2. 스크립트 실행 권한
    echo ""
    echo "[2/4] 스크립트 실행 권한 설정..."
    chmod +x "${variable_scripts_dir}"/*.sh 2>/dev/null
    echo "  ✅ scripts/*.sh chmod +x"

    # 3. settings.json에 훅 자동 등록
    echo ""
    echo "[3/4] Claude Code 훅 자동 등록..."
    python3 -c "
import json, sys
from pathlib import Path

settings_path = Path('$variable_settings_file')
if not settings_path.exists():
    print('  ⚠️ settings.json 미존재 — Claude Code를 먼저 실행해주세요')
    sys.exit(0)

s = json.loads(settings_path.read_text())
hooks = s.setdefault('hooks', {})
changed = False

# gate-blocker (PreToolUse — 커밋 차단)
pre = hooks.setdefault('PreToolUse', [])
if not any('gate-blocker' in json.dumps(e) for e in pre):
    pre.append({'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'bash ${variable_scripts_dir}/gate-blocker.sh', 'timeout': 5}]})
    changed = True
    print('  ✅ PreToolUse: gate-blocker.sh (커밋 차단)')

# gate-enforcer (PostToolUse — 상태 경고)
post = hooks.setdefault('PostToolUse', [])
if not any('gate-enforcer' in json.dumps(e) for e in post):
    post.append({'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'python3 ${variable_scripts_dir}/gate-enforcer.py --check-surfaces', 'timeout': 8}]})
    changed = True
    print('  ✅ PostToolUse: gate-enforcer.py (상태 경고)')

# cmux-claude-bridge (SessionStart/Stop/Notification)
ss = hooks.setdefault('SessionStart', [])
if not any('cmux-claude-bridge' in json.dumps(e) for e in ss):
    ss.append({'hooks': [{'type': 'command', 'command': 'bash ${variable_scripts_dir}/cmux-claude-bridge.sh session-start', 'timeout': 3}]})
    changed = True
    print('  ✅ SessionStart: cmux-claude-bridge.sh')

# cmux-idle-reminder (UserPromptSubmit)
ups = hooks.setdefault('UserPromptSubmit', [])
if not any('cmux-idle-reminder' in json.dumps(e) for e in ups):
    ups.append({'hooks': [{'type': 'command', 'command': 'bash ${variable_scripts_dir}/cmux-idle-reminder.sh', 'timeout': 5}]})
    changed = True
    print('  ✅ UserPromptSubmit: cmux-idle-reminder.sh')

if changed:
    settings_path.write_text(json.dumps(s, indent=2, ensure_ascii=False))
    print('  📝 settings.json 업데이트 완료')
else:
    print('  ✅ 모든 훅이 이미 등록됨')
" 2>&1

    # 4. 설치 확인
    echo ""
    echo "[4/4] 설치 확인..."
    echo "  에이전트: $(ls "${variable_agents_dst}"/cmux-*.md 2>/dev/null | wc -l | tr -d ' ')개"
    echo "  스크립트: $(ls "${variable_scripts_dir}"/*.sh "${variable_scripts_dir}"/*.py 2>/dev/null | wc -l | tr -d ' ')개"
    echo ""
    echo "✅ 설치 완료! cmux에서 AI 창을 열고 cmux-orchestrator 스킬을 활성화하세요."
    ;;
  *)
    echo "Usage: bash install_agents.sh [--check|--install|--list|--install-hooks|--setup]"
    echo ""
    echo "  --check          에이전트 설치 상태 확인"
    echo "  --install         에이전트만 설치"
    echo "  --list            번들된 에이전트 목록"
    echo "  --install-hooks   훅 등록 상태 확인"
    echo "  --setup           원클릭 전체 설치 (에이전트 + 훅 + 권한)"
    ;;
esac
