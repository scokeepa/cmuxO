# 온보딩 상세 절차 (Phase -1)

## Step 0: 기존 설정 확인

```bash
CONFIG_FILE="${SKILL_DIR}/config/orchestra-config.json"
if [ -f "$CONFIG_FILE" ]; then
  # 기존 설정 발견 → 사용자에게 재사용 여부 질문
fi
```

**기존 설정 있을 때:**
```
이전 cmux 오케스트레이션 설정이 남아있습니다:
- surface:1 = Claude Code (시작: claude, 종료: /exit)
- surface:3 = Codex (시작: codex, 종료: /quit)
- surface:5 = Gemini (시작: gemini, 종료: Ctrl+C)

이전 세팅대로 진행할까요? (예/아니오)
```

- **예** → Phase 0으로 바로 이동 (온보딩 스킵)
- **아니오** → Step 1부터 새로 진행

## Step 0.5: cmux 이벤트 훅 자동 등록

세션 시작 시 cmux set-hook으로 이벤트 기반 감시를 자동 등록합니다.

```bash
# 키 입력 후 상태 갱신 (작업 완료 즉시 감지)
cmux set-hook after-send-keys "bash ${SKILL_DIR}/scripts/eagle_watcher.sh --once > /dev/null 2>&1 &"

# 상태 바에 현재 오케스트레이션 상태 표시
cmux display-message -p "cmux orchestrator active"
```

> **참고**: `cmux set-hook --list`로 등록된 훅 확인, `--unset <event>`로 해제 가능.
> 세션 종료 시 훅은 자동 해제됨 (영속 X).

## Step 1: cmux 감지 + 활성화 질문

```bash
cmux tree --all  # surface 목록 확인
```

**surface가 2개 이상:**
```
cmux에 {N}개 창이 감지되었습니다. 멀티 AI 오케스트레이션을 활성화할까요?
(예/아니오)
```
- **예** → Step 1-1 (AI 확인) → Step 2
- **아니오** → 일반 모드

**surface가 1개 (Boss만 있음):**
```
cmux에 창이 1개뿐입니다. 다른 AI를 추가하면 병렬 작업이 가능합니다.
새 창을 만들까요? (예/아니오)
```
- **예** → Step 1-1 (AI 설치 지원)
- **아니오** → 일반 모드

## Step 1-1: AI 에이전트 확인 + 설치 지원

```bash
# 각 surface 화면 읽어서 AI 존재 여부 판별
for sid in $(cmux tree --all | grep -oE 'surface:[0-9]+' | sed 's/surface://'); do
  screen=$(cmux read-screen --surface surface:$sid --lines 5)
  # AI 프롬프트 감지: ❯, ›, *, Type your message 등
done
```

**빈 surface 발견 시 (AI 없음):**
```
surface:{N}에 AI가 없습니다. 아래 중 하나를 설치할 수 있습니다:

1. codex  — OpenAI Codex CLI (코드 구현에 탁월)
2. gemini — Google Gemini CLI (조사/분석에 탁월)
3. claude — Claude Code (범용)
4. 기타   — 직접 명령어 입력

어떤 AI를 설치할까요? (번호 또는 명령어)
```

## AI 명령어 프리셋

```json
{
  "codex":    { "start": "codex",    "quit": "/quit", "reset": "/new",   "model": "gpt-5.4",          "difficulty": "high" },
  "opencode": { "start": "cco",     "quit": "/quit", "reset": "/new",   "model": "gpt-5.4",          "difficulty": "high" },
  "gemini":   { "start": "gemini",  "quit": "/quit", "reset": "/clear", "model": "gemini-3.1-pro",   "difficulty": "low" },
  "glm":      { "start": "ccg2",    "quit": "/quit", "reset": "/new",   "model": "glm-4.7",          "difficulty": "low" },
  "claude":   { "start": "claude",  "quit": "/exit", "reset": "/clear", "model": "claude-opus",      "difficulty": "high" }
}
```

> **공통 종료**: `/quit` (모든 AI 동일)
> **컨텍스트 초기화**: Codex/OpenCode/GLM = `/new`, Gemini/Claude = `/clear`
> **반드시 초기화 후 작업 전송** — `/new` 또는 `/clear` → sleep 3 → 작업 send

## AI별 작업 배분 규칙 (MANDATORY)

| AI | 모델 | 번들 크기 | 작업 유형 | 특기 |
|----|------|----------|----------|------|
| **OpenCode** (oh-my-opencode) | GPT-5.4 | **3-5개** (가장 많이) | 고난이도 코드, 대규모 리팩토링, 복잡한 분석, 멀티파일 구현 | Sisyphus 에이전트 + 스킬 시스템으로 자율성 최고 |
| **MiniMax** | M2.5 | **2-3개** | 코드 구현, 분석, 데이터 정제 | GLM과 비슷한 분량 |
| **GLM** | glm-4.7 | **2-3개** | 코드 구현, 조사, 보조 분석 | 코딩플랜 무료 |
| **Gemini** | gemini-3.1-pro | **2개** (가벼운 것) | 가벼운 구현, **디자인 리뷰**, **UI/UX 평가**, 코드 스타일 리뷰 | 디자인 감각이 강점 |
| **Boss** (Opus) | claude-opus | 직접 처리 | 계획, speckit 분해, 리뷰 판정, 커밋, 취합 | 절대 코딩 직접 안 함 |

**배분 원칙:**
1. **OpenCode에 가장 많은 양 + 가장 어려운 작업** — GPT-5.4 + oh-my-opencode 플러그인으로 자율적 완수 가능
2. **디자인/UI 관련은 Gemini 우선** — 디자인 코드 리뷰, CSS/스타일링, UI 컴포넌트 평가
3. **GLM/MiniMax는 중간 분량** — 조사, 보조 구현, 데이터 처리
4. **Boss는 코딩 금지** — 계획 + 판단 + 취합 + 커밋만

## Step 2: 각 창에 AI 로그인 요청

```
각 창에 사용할 AI를 로그인해주세요.
현재 빈 창 목록:
  - surface:1 (pane:2)
  - surface:3 (pane:4)
  - surface:5 (pane:5)

로그인 후 스크린샷을 보내주시거나
"surface:1은 Codex, surface:3은 Gemini" 형태로 알려주세요.
(시작/종료 명령어는 프리셋으로 자동 적용됩니다)
```

## Step 3: 사용자 응답 파싱 + 설정 저장

사용자가 "surface:1은 Claude, surface:3은 Codex, surface:5는 Gemini"라고 하면:
→ 프리셋에서 자동으로 start/quit/reset 명령어 매칭

```json
// ${SKILL_DIR}/config/orchestra-config.json (자동 생성)
{
  "created_at": "2026-03-18T12:00:00Z",
  "surfaces": {
    "1": {
      "ai": "Claude Code",
      "start_cmd": "claude", "quit_cmd": "/exit", "reset_cmd": "/clear",
      "model": "claude-opus",
      "capabilities": ["coding", "review"]
    },
    "3": {
      "ai": "Codex",
      "start_cmd": "codex", "quit_cmd": "/quit", "reset_cmd": "/new",
      "model": "gpt-5.4",
      "capabilities": ["coding", "implementation"]
    },
    "5": {
      "ai": "Gemini",
      "start_cmd": "gemini", "quit_cmd": "/quit", "reset_cmd": "/clear",
      "model": "gemini-3.1-pro",
      "capabilities": ["research", "analysis"]
    }
  },
  "boss_surface": "4",
  "boss_ai": "Opus"
}
```

## Step 4: 설정 확인 + 온보딩 완료

```
오케스트레이션 설정 완료:
┌─────────┬──────────┬──────────┬──────────┐
│ Surface │ AI       │ 시작     │ 종료     │
├─────────┼──────────┼──────────┼──────────┤
│ 1       │ Claude   │ claude   │ /exit    │
│ 3       │ Codex    │ codex    │ /quit    │
│ 5       │ Gemini   │ gemini   │ Ctrl+C   │
│ 4 (Me)  │ Opus     │ -        │ -        │
└─────────┴──────────┴──────────┴──────────┘

이제부터 IDLE surface에 자동으로 작업을 분배합니다.
에러 발생 시 해당 AI의 종료→재시작 명령으로 자동 복구합니다.
```

## 새 창 동적 감지 + 자동 등록 (MANDATORY)

사용자가 세션 중 새 창을 켜면 Boss가 자동으로 인지하고 작업 창으로 추가해야 함.

```bash
# eagle_watcher가 새 surface를 자동 감지 (기존 config에 없는 surface 발견)
# 현재 등록: config/orchestra-config.json의 surfaces 키 목록
# eagle 스캔: cmux tree --all에서 감지된 surface 목록
# 차이 = 새 창

# Boss가 확인:
cmux tree --all  # 전체 surface 확인
cat ${SKILL_DIR}/config/orchestra-config.json  # 기존 등록 목록
# → 새 surface 발견 시 아래 절차 실행
```

**새 창 등록 절차:**
1. `cmux read-screen --surface surface:N --lines 5`로 어떤 AI인지 판별
2. 프리셋 매칭 (codex/opencode/gemini/glm/claude/minimax)
3. `orchestra-config.json`에 해당 surface 추가
4. 즉시 작업 배정 (IDLE=0 원칙)

**AI 판별 키워드:**

| 화면 키워드 | AI | 프리셋 |
|------------|-----|--------|
| `gpt-5` / `codex` / `Implement` | Codex | codex |
| `Sisyphus` / `opencode` / `OpenAI` | OpenCode | opencode |
| `gemini` / `sandbox` | Gemini | gemini |
| `glm` / `z.ai` | GLM | glm |
| `claude` / `opus` / `sonnet` | Claude | claude |
| `MiniMax` / `minimax` | MiniMax | minimax (codex 프리셋 + 난이도 high) |
