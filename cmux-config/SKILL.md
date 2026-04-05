---
name: cmux-config
description: "cmux AI 프로파일 관리 — 사용할 AI 선택, 자동 감지, 추가/제거. /cmux-config로 실행."
user-invocable: true
classification: configuration
allowed-tools: Bash, Read
---

# /cmux-config — AI 프로파일 관리

입력: `$ARGUMENTS`

cmux 오케스트레이션에서 사용할 AI를 관리합니다.

---

## 라우팅

### 빈 입력 또는 `list`
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --list
```
→ 현재 AI 프로파일 표시 (이름, CLI, 감지 여부, traits)

### `detect` / `감지` / `스캔`
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --detect
```
→ PATH에서 AI CLI 자동 감지하여 프로파일 갱신

### `add` / `추가` + AI 이름
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --add <이름>
```
→ AI 프로파일에 추가

### `remove` / `제거` + AI 이름
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --remove <이름>
```
→ AI 프로파일에서 제거

---

## 사용 가능한 AI

| 이름 | CLI | Traits |
|------|-----|--------|
| codex | `codex` | no_init_required, sandbox |
| opencode | `cco` | no_init_required, sandbox |
| minimax | `ccm` | (없음) |
| glm | `ccg2` | short_prompt |
| gemini | `gemini` | two_phase_send |
| claude | `claude` | (없음) |

## Traits 설명

| Trait | 의미 |
|-------|------|
| `no_init_required` | /new 초기화 없이 바로 작업 전송 가능 |
| `sandbox` | cmux CLI 직접 실행 불가 (Codex sandbox 모드) |
| `short_prompt` | 프롬프트 200자 이내 권장 |
| `two_phase_send` | /clear와 작업을 분리하여 전송 필요 |

## 예시

```
/cmux-config              → 현재 프로파일 확인
/cmux-config detect       → 설치된 AI 자동 감지
/cmux-config add codex    → Codex 추가
/cmux-config remove glm   → GLM 제거
```
