# cmux-orchestrator-watcher-pack

> **v8.0 — JARVIS 진화 엔진 + Department system + agent-memory + dynamic resources + one-command start + AI profile**

AI Multi-Agent Collaboration Platform.
User(CEO) -> Main(COO) -> Team Leads -> Members. Watcher monitors. **JARVIS evolves settings.**

## Skills (9)

| Skill | Purpose |
|-------|---------|
| **cmux-orchestrator** | Main(사장): 부서 편성 + 팀장 배치 + 결과 취합 |
| **cmux-watcher** | 와쳐(Watcher): 모니터링 + 리소스 관리 |
| **cmux-jarvis** | 자비스(JARVIS): 설정 진화 + 자동 감지 + 최적화 |
| **cmux-start** | 오케스트레이션 시작 (컨트롤 타워 구성 + 기존 세션 포함 질문) |
| **cmux-stop** | 오케스트레이션 종료 (부서 선택적 닫기) |
| **cmux-config** | AI 프로파일 관리 |
| **cmux-help** | 명령어 도움말 |
| **cmux-pause** | 일시 정지 + 재개 |
| **cmux-uninstall** | 완전 제거 + 롤백 |

## 설치

```bash
bash install.sh
```

한 줄이면 됩니다. 설치 스크립트가 자동으로:
1. cmux, python3 사전 검증
2. 기존 settings.json + skill 백업
3. 9개 skill 복사 + 실행 권한 설정
4. Hook symlink + settings.json 자동 등록
5. AI 프로파일 자동 감지

## AI 프로파일 관리

Claude Code 내에서 `/cmux-config` 슬래시 커맨드로 관리:

```
/cmux-config              # 현재 프로파일 확인
/cmux-config detect       # 설치된 AI 자동 감지
/cmux-config add codex    # AI 추가
/cmux-config remove glm   # AI 제거
```

또는 CLI에서 직접:
```bash
python3 ~/.claude/skills/cmux-orchestrator/scripts/manage-ai-profile.py --list
```

Traits 기반 surface 분류:
| Trait | 의미 | 해당 AI |
|-------|------|---------|
| `no_init_required` | /new 초기화 불필요 | Codex |
| `sandbox` | cmux CLI 직접 실행 불가 | Codex |
| `short_prompt` | 프롬프트 200자 이내 | GLM |
| `two_phase_send` | /clear와 작업 분리 전송 | Gemini |

## settings.json Hook 등록

**CRITICAL**: Claude Code hooks는 `{matcher, hooks: [...]}` 래퍼 구조 필수.

전체 JSON은 `INSTALLATION-PLAN.md` Step 7에 있습니다.

## cmux 레이아웃 생성

```bash
cmux new-workspace   # 필요한 만큼 반복
cmux rename-workspace --workspace workspace:N "이름"
```

> Surface ID 수동 편집 불필요 — Watcher가 자동 감지하여 `/tmp/cmux-surface-map.json` 생성.

## 슬래시 커맨드

| 커맨드 | 용도 | 어디서 |
|--------|------|--------|
| `/cmux-start` | 오케스트레이션 시작 | Main surface |
| `/cmux-config` | AI 프로파일 관리 | 아무 세션 |
| `/cmux-help` | 명령어 도움말 | 아무 세션 |
| `/cmux-pause` | 긴급 정지/재개 | Main surface |
| `/cmux-uninstall` | 완전 제거 + 롤백 | 아무 세션 |
| `/cmux-orchestrator` | Main 지휘관 모드 | Main surface |
| `/cmux-watcher` | Watcher 감시 모드 | Watcher surface |

## Usage

```
1. /cmux-start                   (one command - Main + Watcher + JARVIS)
2. Tell Main what to build       ("Add login feature")
3. Main forms departments        (automatic)
4. Watch progress                (Watcher reports)
5. JARVIS auto-evolves settings  (detect → analyze → propose → apply)
```

### Mode Gate

- Default = **individual mode** (no hook interference)
- After `/cmux-start` = **orchestration mode** (27 hooks active: 21 cmux + 6 JARVIS, dept management + evolution)
- Other sessions unaffected

## 전제 조건

| 요구사항 | 확인 방법 |
|---------|----------|
| cmux 0.62+ | `cmux --version` |
| Claude Code 2.1+ | `claude --version` |
| Python 3.9+ | `python3 --version` |

### 선택 (없어도 동작)

| 요구사항 | 용도 |
|---------|------|
| psutil | PC 리소스 모니터링 (없으면 기본값) |
| jq | 일부 bash hook (없으면 python3 fallback) |

## Key Features (v8.0)

- **JARVIS evolution engine**: auto-detect issues → analyze root cause → propose settings change → user approval → atomic apply → rollback-safe
  - 6 hooks (GATE, ConfigChange, FileChanged, SessionStart, PreCompact, PostCompact)
  - Iron Laws: no evolution without approval, no implementation without expected outcome, no completion without evidence
  - v8 attack defense: Python/Node indirect write blocked, LOCK forgery blocked, hooks array overwrite blocked
- **Department system**: workspace = dept (team lead + members), dynamic create/close
- **One-command start**: `/cmux-start` sets up Main + Watcher + JARVIS
- **AI profile + traits**: detect installed AIs, classify by behavior, inject to Main context
- **Agent memory**: auto-record orchestration events, drain to permanent storage, inject to Main decisions
- **21 enforcement hooks**: stdin protection (fail-closed/open), mode gate, deadlock prevention (300s timeout)
- **PC resource monitoring**: CPU/memory, queue when full (never skip)
- **Safe install**: backup + merge (never overwrite settings), one-command `install.sh`
- **Control tower protection**: never close Main/Watcher workspace
- **Security**: shlex.quote injection prevention, no shell=True in entire project

## Remove

```
/cmux-uninstall    (rollback from backup or remove only)
```

## Docs

- `install.sh` — One-command installer (backup + install + hook registration)
- `tests/` — Hook stdin protection + utility tests
- `cmux-orchestrator/references/` — 16 reference docs (dispatch templates, gate matrix, etc.)
- `cmux-jarvis/references/` — 7 reference docs (metric dictionary, iron laws, gate 5-level, etc.)
- `cmux-jarvis/scripts/` — Evolution CLI + verification + maintenance
- `docs/jarvis/` — JARVIS design docs (20+ files, architecture, pipeline, reviews, simulations)
