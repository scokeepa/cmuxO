# /cmux-config — AI 프로파일 관리

입력: `$ARGUMENTS`

cmux 오케스트레이션의 AI 프로파일을 관리합니다. 어떤 AI를 사용할지, 각 AI의 특성(traits)을 설정합니다.

---

## 라우팅

### 빈 입력 또는 `list`
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --list
```
→ 현재 AI 프로파일 표시 (이름, CLI, 감지 여부, traits)

### `detect`
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --detect
```
→ PATH에서 AI CLI 자동 감지하여 프로파일 갱신

### `add <이름>`
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --add <이름>
```
→ AI 프로파일에 추가 (codex, minimax, glm, gemini, claude, opencode)

### `remove <이름>`
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --remove <이름>
```
→ AI 프로파일에서 제거

---

## 사용 가능한 AI 이름

| 이름 | CLI | Traits |
|------|-----|--------|
| codex | `codex` | no_init_required, sandbox |
| opencode | `cco` | no_init_required, sandbox |
| minimax | `ccm` | (없음) |
| glm | `ccg2` | short_prompt |
| gemini | `gemini` | two_phase_send |
| claude | `claude` | (없음) |

## 예시

```
/cmux-config              → 현재 프로파일 확인
/cmux-config detect       → 설치된 AI 자동 감지
/cmux-config add codex    → Codex 추가
/cmux-config remove glm   → GLM 제거
```
