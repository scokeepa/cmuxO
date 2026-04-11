# CMUX AGI Mentor Integrated Plan

작성일: 2026-04-11
상태: 프로젝트 핵심 계획 문서
판정: Conditional Go. P0 차단 항목을 먼저 정리한 뒤 Mentor Lane 구현을 시작한다.

## 0. 이 문서의 역할

이 문서는 cmux-orchestrator-watcher-pack의 AGI 지향 오케스트레이션 계획과 인간 사용자 멘토링 계획을 하나의 실행 계획으로 통합한 SSOT다.

목표는 Gemini CLI 같은 단일 CLI 도구 경쟁이 아니다. 목표는 다음이다.

- cmux IDE 안에서 부서별 사이드탭을 만들고, 각 부서의 팀장이 같은 사이드탭 안에서 팀원 pane을 할당한다.
- Boss(Main)는 부서 편성, 팀장 지시, 결과 취합, 리뷰 위임, 커밋을 담당한다.
- Watcher는 감시와 알림만 담당한다.
- JARVIS는 User(CEO)의 직속 참모로서 시스템 진화와 인간 사용자 지시 품질 개선을 돕는다.
- 인간 사용자의 문제 인식, 지시 품질, 검증 습관이 전체 AGI 하네스의 최상위 변수라는 전제를 시스템에 반영한다.

## 1. 로컬 근거

전수조사 기준으로 현재 repo는 `README.md`, `cmux-orchestrator`, `cmux-watcher`, `cmux-jarvis`, `cmux-start`, `tests`, `docs/jarvis` 중심으로 구성되어 있다. 현재 작업 전부터 `cmux-orchestrator/config/orchestra-config.json`은 수정 상태였고, 외부 참고자료 SSOT는 사용자가 추가한 `referense/` 디렉터리다.

핵심 근거:

- `/cmux-start`는 Boss, Watcher, JARVIS를 구성하고, Boss가 작업을 분해하며, Watcher가 감시하고, JARVIS가 반복 실패 기반 config 개선을 담당한다고 설명한다. 근거: `README.md:42`, `README.md:43`, `README.md:45`, `README.md:47`.
- 계층은 CEO Staff/JARVIS, Control Tower/Boss+Watcher, Departments/Lead+Workers로 정의되어 있다. 근거: `README.md:95`, `README.md:96`, `README.md:97`.
- Department는 workspace(side tab), Team Lead는 lead surface, Workers는 같은 workspace 안 pane이라는 최신 구조가 문서화되어 있다. 근거: `README.md:431`, `README.md:432`, `cmux-orchestrator/SKILL.md:18`, `cmux-orchestrator/SKILL.md:20`, `cmux-orchestrator/SKILL.md:23`.
- Boss는 작업 분석, 부서 편성, 팀장 지시, DONE 취합, 리뷰 위임, 커밋을 담당한다. 근거: `cmux-orchestrator/SKILL.md:26`, `cmux-orchestrator/SKILL.md:29`, `cmux-orchestrator/SKILL.md:31`, `cmux-orchestrator/SKILL.md:32`, `cmux-orchestrator/SKILL.md:33`.
- Boss는 팀장에게만 지시하고, 팀원 생성/AI 선택/작업 분배는 팀장이 수행한다. 근거: `cmux-orchestrator/SKILL.md:128`, `cmux-orchestrator/SKILL.md:162`, `cmux-orchestrator/SKILL.md:166`, `cmux-orchestrator/SKILL.md:167`.
- Watcher는 오케스트레이션, 작업 배정, 코드 수정, surface 생성/해제를 하지 않는다. 근거: `cmux-watcher/SKILL.md:9`, `cmux-watcher/SKILL.md:42`, `cmux-watcher/SKILL.md:53`, `cmux-watcher/SKILL.md:338`, `cmux-watcher/SKILL.md:767`.
- Watcher와 Orchestrator는 상하 관계가 아닌 peer다. 근거: `cmux-watcher/SKILL.md:192`, `cmux-watcher/SKILL.md:196`, `cmux-watcher/SKILL.md:197`.
- JARVIS는 User(CEO)의 직속 참모이자 오케스트레이션 설정 진화 엔진이다. 근거: `cmux-jarvis/SKILL.md:11`, `cmux-jarvis/SKILL.md:17`, `cmux-jarvis/SKILL.md:20`, `cmux-jarvis/SKILL.md:21`.
- JARVIS Evolution Lane은 감지, 승인, 백업, worker 위임, 검증, KEEP/DISCARD, rollback을 가진다. 근거: `cmux-jarvis/skills/evolution/SKILL.md:14`, `cmux-jarvis/skills/evolution/SKILL.md:24`, `cmux-jarvis/skills/evolution/SKILL.md:33`, `cmux-jarvis/skills/evolution/SKILL.md:41`, `cmux-jarvis/skills/evolution/SKILL.md:48`, `cmux-jarvis/skills/evolution/SKILL.md:49`.
- `cmux-main-context.sh`는 `/cmux` 입력 시 watcher cache, roles, AI profile, 최근 memory를 additionalContext로 주입한다. 근거: `cmux-orchestrator/hooks/cmux-main-context.sh:3`, `cmux-orchestrator/hooks/cmux-main-context.sh:20`, `cmux-orchestrator/hooks/cmux-main-context.sh:21`, `cmux-orchestrator/hooks/cmux-main-context.sh:48`, `cmux-orchestrator/hooks/cmux-main-context.sh:64`, `cmux-orchestrator/hooks/cmux-main-context.sh:80`.
- `agent-memory.sh`는 `~/.claude/memory/cmux/journal.jsonl`과 `memories.json`을 사용하는 운영 메모리 계층이다. 근거: `cmux-orchestrator/scripts/agent-memory.sh:5`, `cmux-orchestrator/scripts/agent-memory.sh:10`, `cmux-orchestrator/scripts/agent-memory.sh:17`, `cmux-orchestrator/scripts/agent-memory.sh:18`, `cmux-orchestrator/scripts/agent-memory.sh:74`.
- `jarvis_telemetry.py`는 JARVIS 이벤트 JSONL, ring buffer, window query, summary를 제공한다. 근거: `cmux-jarvis/scripts/jarvis_telemetry.py:32`, `cmux-jarvis/scripts/jarvis_telemetry.py:55`, `cmux-jarvis/scripts/jarvis_telemetry.py:69`, `cmux-jarvis/scripts/jarvis_telemetry.py:90`, `cmux-jarvis/scripts/jarvis_telemetry.py:116`, `cmux-jarvis/scripts/jarvis_telemetry.py:125`.
- 과거 JARVIS 리뷰는 JARVIS가 7개 역할을 한 surface에서 수행하면 SRP와 context가 무너진다고 지적했고, Phase 1은 진화와 모니터링으로 한정하라고 결론냈다. 근거: `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:337`, `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:348`, `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:351`, `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:354`, `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:358`.
- 같은 리뷰는 설정 변경 A/B를 Phase 1에서 과신하지 말고 Before/After 스냅샷, 관찰 기간, 사용자 판단으로 제한하라고 한다. 근거: `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:362`, `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:375`, `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:376`, `docs/jarvis/knowledge/raw/2026-04-02_critical-review-round2.md:377`.
- `orchestra-config.json`은 `_note`에서 runtime workspaces/surfaces는 동적이고 presets만 정본이라고 하지만, 실제로 `surfaces`, `main_surface`, `watcher_surface`, `auto_synced`가 남아 있다. 근거: `cmux-orchestrator/config/orchestra-config.json:4`, `cmux-orchestrator/config/orchestra-config.json:50`, `cmux-orchestrator/config/orchestra-config.json:81`, `cmux-orchestrator/config/orchestra-config.json:82`, `cmux-orchestrator/config/orchestra-config.json:84`.
- `validate-config.sh`는 현재 `os.path.isfile`을 사용하지만 `os`를 import하지 않는다. 근거: `cmux-orchestrator/scripts/validate-config.sh:104`, `cmux-orchestrator/scripts/validate-config.sh:143`. 실제 실행도 `NameError: name 'os' is not defined`로 실패했다.

외부 흡수 대상:

- `referense/vibe-sunsang-main`: 인간 사용자의 AI 활용 능력을 6축(DECOMP/VERIFY/ORCH/FAIL/CTX/META), workspace type(Builder/Explorer/Designer/Operator), 7단계 레벨, 성장 리포트, TIMELINE으로 추적하는 멘토링 패턴을 흡수한다. 이전 원격 조사 기준 commit은 `7376fa429bbb56b80f69d5aedabfff6399be5add`였지만, 이후 검증의 우선 근거는 로컬 `referense` 스냅샷이다.
- `referense/mempalace-main`: raw verbatim storage, wing/room/hall/tunnel/closet/drawer palace model, L0~L3 memory stack, ChromaDB/SQLite KG/MCP 검색, auto-save hook 패턴을 흡수한다. 이전 원격 조사 기준 commit은 `1056018b521824a590400e36ccb540588f065895`였지만, 이후 검증의 우선 근거는 로컬 `referense` 스냅샷이다.
- `referense/badclaude-main`: Electron tray/overlay, whip canvas interaction, crack sound, interrupt plus follow-up prompt 패턴을 "통제된 세션 개입 UX" 참고자료로만 흡수한다. OS 전역 키 입력, 모욕적 문구, 자동 처벌형 인터럽트는 흡수하지 않는다.

흡수 원칙:

- 외부 레포를 그대로 vendoring하지 않는다. cmux의 SSOT, SRP, 권한 경계에 맞춰 adapter와 schema로 재해석한다.
- vibe-sunsang은 Mentor Scoring Ontology로 흡수한다.
- mempalace는 Mentor Memory Substrate로 흡수한다.
- badclaude는 Nudge/Escalation Interaction Reference로 흡수한다.
- 외부 의존성은 P0/P1/P2에서 문서와 schema를 먼저 고정한 뒤, P3 이후 opt-in adapter로만 붙인다.

로컬 이미지 근거:

- `referense/1.jpeg`는 "모델의 원리 및 작동 방식"으로 헌법 기반 정렬(Constitutional AI), 적응형 사고(Adaptive Thinking), 에이전트적 설계(Agentic Scaffolding), 합성 데이터/고도화 학습을 요약한다.
- `referense/2.jpeg`는 "모델의 뛰어난 점"으로 강한 사이버 보안 능력, 고도화된 소프트웨어 엔지니어링, 높은 alignment, calibration, 시각적 추론 능력을 요약한다.
- 따라서 이미지 기반 반영은 신호 분석이 아니라 JARVIS 운영 원칙으로 흡수한다. 즉 JARVIS는 constitutional rules, adaptive problem decomposition, agentic scaffolding, evidence calibration, visual reasoning loop를 Mentor/Evolution Lane 공통 원칙으로 가져간다.

## 2. 통합 아키텍처

```text
User / CEO
  |
  | 지시, 승인, KEEP/DISCARD, 학습 목표
  v
JARVIS Mentor Lane
  - 사용자 지시 품질 관찰
  - 바이브코딩 패턴 분석
  - 주기적 코칭, 방향성 제안, 학습 도움
  - 진단/통제 금지, 조언과 근거 제시만 허용
  |
  v
Boss / Main / COO
  - 부서 편성
  - 팀장에게만 지시
  - DONE 취합
  - 리뷰 Agent 위임
  - 최종 커밋
  |
  v
Department Workspace / Sidebar Tab
  |
  +-- Team Lead Surface
        - 난이도 판단
        - 같은 workspace 안 worker pane 생성
        - 로컬 AI 및 모델 선택
        - worker 결과 검증
        - Boss에게 DONE 보고
        |
        +-- Worker Pane(s)

Watcher / Audit Office
  - runtime scan
  - IDLE/ERROR/STALLED/RATE_LIMITED/DONE 알림
  - 직접 작업 배정 금지

Controlled Nudge / Escalation Layer
  - slow, stalled, instruction-drift 세션에 대한 재촉/개입
  - Worker 대상: 해당 Team Lead만 실행
  - Team Lead 대상: Boss만 실행
  - Boss 대상: JARVIS가 근거를 제시하고 User/CEO 승인 또는 사전 정책에 따라 실행
  - Watcher는 trigger evidence만 제공하고 실행하지 않음
  - session-scoped interrupt, follow-up prompt, audit log, throttle을 필수로 적용

JARVIS Evolution Lane
  - 반복 실패 감지
  - 승인 기반 config/skill/hook 진화
  - 백업, 검증, KEEP/DISCARD, rollback

Memory and Signal Layer
  - 운영 메모리: orchestration events
  - 멘토 메모리: 사용자 지시/결정/피드백 패턴
  - 진화 텔레메트리: JARVIS 이벤트
  - mempalace-style palace memory: wing/room/drawer raw store + L0~L3 recall
  - vibe-sunsang-style mentor signal: DECOMP/VERIFY/ORCH/FAIL/CTX/META
  - signal engine: window, trend, lag, predicted-vs-actual, calibration 비교
```

## 3. 두 플랜의 통합

### Plan A. AGI 오케스트레이션 + 자기 진화

현재 코드와 문서는 이미 Plan A의 골격을 갖고 있다.

- `/cmux-start`가 Boss, Watcher, JARVIS control tower를 만든다.
- Boss는 department workspace를 생성하고 team lead만 상대한다.
- Team Lead는 같은 workspace 안에 worker pane을 만들고, 로컬 AI와 모델을 난이도별로 선택한다.
- Watcher는 감시와 알림만 맡는다.
- JARVIS Evolution Lane은 반복 문제를 감지해 승인, 백업, worker 위임, 검증, 반영/롤백을 수행한다.

Plan A의 미완성 지점:

- runtime surface SSOT가 `orchestra-config.json`, `/tmp/cmux-roles.json`, `/tmp/cmux-surface-scan.json`, `/tmp/cmux-surface-map.json`, cmux tree 사이에 아직 완전히 정리되지 않았다.
- `validate-config.sh`가 현재 실패하므로 SSOT 검증 자동화가 차단되어 있다.
- JARVIS의 역할이 커질수록 기존 리뷰의 SRP/context explosion 리스크가 재발한다.

### Plan B. 인간 사용자 멘토 + 메모리 + 신호 분석

Plan B는 Plan A보다 상위 하네스에 위치한다. 이유는 인간 사용자의 지시 방식이 Boss, Team Lead, Worker의 출력 품질을 제한하기 때문이다.

Plan B의 핵심:

- 사용자 대화 내역과 업무 지시는 기본적으로 derived event/signal만 저장하고, raw log/drawer는 명시 opt-in 후에만 저장한다.
- raw log를 직접 orchestration memory와 섞지 않고 mentor signal로 파생한다.
- JARVIS는 사용자의 판단 프레임, 지시 품질, 검증 압력, 범위 안정성, 피드백 습관을 주기적으로 분석한다.
- JARVIS는 사용자를 대체하거나 통제하지 않고, "더 좋은 지시와 더 좋은 의사결정 하네스"를 제안한다.
- 피드백은 작업 중단을 유발하지 않는 soft intervention으로 시작한다.

사용자 제공 이미지 1/2 반영:

- `referense/1.jpeg`는 JARVIS가 따라야 할 작동 원칙으로 흡수한다. 헌법 기반 정렬은 Iron Law/SSOT/SRP 규칙, 적응형 사고는 task decomposition과 failure recovery, 에이전트적 설계는 Boss-TeamLead-Worker scaffold, 합성 데이터/고도화 학습은 simulation fixture와 self-play review로 대응한다.
- `referense/2.jpeg`는 JARVIS가 목표로 삼을 능력 품질로 흡수한다. 사이버 보안은 secret/path/permission gate, 소프트웨어 엔지니어링은 tests/typecheck/build 기반 evidence, alignment는 사용자 승인과 scope lock, calibration은 confidence와 "검증 불가" 표기, visual reasoning은 Watcher/Eagle/OCR/스크린샷 기반 surface 상태 판정으로 대응한다.
- 이미지 자체는 외부 논문/출처가 아니므로 사실 근거가 아니라 제품 원칙 레퍼런스로만 사용한다.

## 3.1 흡수 플랜 청크

Chunk A. Mentor Ontology (vibe-sunsang 흡수)

- SSOT: `docs/jarvis/architecture/mentor-ontology.md`.
- 코드 후보: `cmux-jarvis/scripts/jarvis_mentor_signal.py`.
- 흡수 항목: DECOMP, VERIFY, ORCH, FAIL, CTX, META 6축; Builder/Explorer/Designer/Operator workspace type; 7단계 레벨; 요청 품질 A~D; 안티패턴; TIMELINE.
- cmux 변환: cmux의 기본 workspace type은 `Builder + Operator` 혼합으로 둔다. AGI 오케스트레이션 프로젝트이므로 ORCH/VERIFY/FAIL 가중치를 높이고, 일반 코딩 요청에는 Builder weight를 적용한다.
- SRP: scoring ontology만 담당한다. raw 저장, 검색, hook injection, JARVIS 진화 적용을 하지 않는다.

Chunk B. Palace Memory Substrate (mempalace 흡수)

- SSOT: `docs/jarvis/architecture/palace-memory-ssot.md`.
- 코드 후보: `cmux-jarvis/scripts/jarvis_palace_memory.py`.
- 흡수 항목: raw verbatim drawer, wing/room/hall/tunnel/closet 구조, L0 identity, L1 essential story, L2 on-demand room recall, L3 deep search, SQLite KG triple/attribute schema, MCP adapter 후보.
- cmux 변환:
  - wing = person/project/department.
  - room = topic, feature, failure class, mentoring axis.
  - hall = relation type inside a wing.
  - tunnel = same room across different wings.
  - closet = derived summary pointer.
  - drawer = raw verbatim source.
- SRP: 저장/검색/계층 로딩만 담당한다. 사용자 평가나 진화 판단을 하지 않는다.

Chunk C. JARVIS Constitution Layer (referense/1.jpeg 흡수)

- SSOT: `docs/jarvis/architecture/jarvis-constitution.md`.
- 코드 후보: 기존 `cmux-jarvis/references/iron-laws.md` 확장.
- 흡수 항목: constitutional rules, adaptive thinking, agentic scaffolding, synthetic/self-play simulation.
- cmux 변환: Iron Laws를 JARVIS Mentor/Evolution 공통 constitutional policy로 두고, 모든 advice/evolution/report는 `scope`, `evidence`, `confidence`, `verification`, `rollback` 필드를 가진다.
- SRP: 정책만 담당한다. 실행은 Evolution Lane과 Mentor Lane이 한다.

Chunk D. JARVIS Superiority Capability Targets (referense/2.jpeg 흡수)

- SSOT: `docs/jarvis/architecture/jarvis-capability-targets.md`.
- 코드 후보: gate/test/checklist.
- 흡수 항목: security, software engineering, alignment, calibration, visual reasoning.
- cmux 변환: secret/path guard, independent verification, user approval, uncertainty reporting, Watcher visual/OCR signal을 capability target으로 둔다.
- SRP: 품질 목표와 acceptance criteria만 담당한다.

Chunk E. Mentor Report Pipeline

- SSOT: `docs/jarvis/pipeline/mentor-report-pipeline.md`.
- 코드 후보: `cmux-jarvis/scripts/jarvis_mentor_report.py`.
- 흡수 항목: vibe-sunsang의 weekly/monthly report와 TIMELINE 업데이트.
- cmux 변환: report는 JARVIS가 직접 사용자를 평가하는 문서가 아니라 "AI 협업 하네스 개선 리포트"로 이름 붙인다.
- SRP: reporting만 담당한다. scoring은 Chunk A, storage는 Chunk B에서 받는다.

Chunk F. Context Injection Adapter

- SSOT: `docs/jarvis/architecture/context-injection-policy.md`.
- 코드 후보: `cmux-orchestrator/hooks/cmux-main-context.sh`의 얇은 adapter.
- 흡수 항목: mempalace L0/L1 wake-up, vibe-sunsang 약한 축 next action.
- cmux 변환: `/cmux` 입력 때 raw memory가 아니라 L0/L1 summary와 이번 round의 1개 coaching hint만 주입한다.
- SRP: injection만 담당한다. 분석/저장/검색을 직접 하지 않는다.

Chunk G. Opt-in/Privacy/Retention Gate

- SSOT: `docs/jarvis/architecture/mentor-privacy-policy.md`.
- 코드 후보: config + redaction utility.
- 흡수 항목: raw verbatim store의 강력함과 위험을 함께 반영한다.
- cmux 변환: 기본은 derived signal만 저장하고, raw drawer 저장은 사용자 opt-in 후 활성화한다.
- SRP: 동의, 보존 기간, redaction, export/delete 정책만 담당한다.

Chunk H. Controlled Nudge/Escalation Weapon (badclaude 흡수)

- SSOT: `docs/jarvis/architecture/nudge-escalation-policy.md`.
- 코드 후보: `cmux-orchestrator/scripts/session-nudge.sh`, `cmux-jarvis/scripts/jarvis_escalation_policy.py`, 또는 cmux API 기반 equivalent. P0/P1에서는 문서와 이벤트 schema만 정의한다.
- 흡수 항목: `referense/badclaude-main`의 tray click -> overlay -> whip crack -> interrupt -> follow-up prompt interaction pattern.
- cmux 변환:
  - "무기"는 실제 공격/처벌이 아니라 `nudge`, `interrupt`, `refocus`, `rescope`, `reassign`으로 구성된 역할 기반 개입 장치다.
  - Worker가 느리거나 지시를 이행하지 않으면 Team Lead가 같은 department side tab 안의 해당 worker pane에만 실행한다.
  - Team Lead가 느리거나 drift하면 Boss가 해당 lead surface에만 실행한다.
  - Boss가 느리거나 사용자 지시를 이행하지 않으면 JARVIS가 evidence bundle을 만들고 User/CEO 승인 또는 명시 정책에 따라 Boss surface에만 실행한다.
  - Watcher는 `STALLED`, `IDLE`, `instruction_drift`, `no_done_report`, `rate_limited` 근거를 만들 수 있지만 실행 권한은 없다.
  - L1은 비중단 텍스트 재촉, L2는 세션 스코프 interrupt + 재지시, L3는 Boss/JARVIS가 재분할/회수/재할당을 제안하는 단계로 둔다.
- SRP: 개입 정책, 권한, throttle, audit event만 담당한다. 작업 분해, 코드 수정, 메모리 저장, 사용자 멘토링 점수화는 담당하지 않는다.
- 금지: OS 전역 `Cmd+C`/`Ctrl+C` 키 주입, focus stealing, 모욕/위협 문구, 반복 spam, 감사 로그 없는 자동 개입, 여러 pane 동시 broadcast.

## 4. SSOT 결정

| 영역 | SSOT | 보조/캐시 | 금지 |
|---|---|---|---|
| 로컬 AI preset | `cmux-orchestrator/config/orchestra-config.json`의 `presets` | `ai-profile.json` | runtime surface를 preset config에 영구 저장 |
| runtime surface 상태 | `cmux tree --all` + `/tmp/cmux-surface-map.json` | `/tmp/cmux-surface-scan.json`, `/tmp/cmux-roles.json` | stale config surfaces를 dispatch 근거로 사용 |
| control tower role | `/tmp/cmux-roles.json` | tab name, surface title | title만 보고 role 확정 |
| 부서 구조 | `/tmp/cmux-surface-map.json`의 departments | Watcher scan cache | Boss가 worker pane을 직접 팀원처럼 배정 |
| 운영 메모리 | `~/.claude/memory/cmux/journal.jsonl`, `~/.claude/memory/cmux/memories.json` | `cmux-main-context.sh` recent inject | 사용자 raw conversation과 혼합 |
| JARVIS 진화 텔레메트리 | `~/.claude/cmux-jarvis/telemetry/events-YYYY-MM-DD.jsonl` | in-memory ring buffer | 검증 없는 성공률 주장 |
| 멘토 raw memory | `~/.claude/cmux-jarvis/mentor/palace/drawers/` | mempalace adapter cache | raw를 바로 prompt에 대량 주입 |
| 멘토 palace index | `~/.claude/cmux-jarvis/mentor/palace/index.sqlite` | optional ChromaDB/MCP adapter | 검색 인덱스를 원문 정본으로 취급 |
| 멘토 L0/L1 context | `~/.claude/cmux-jarvis/mentor/context/L0.md`, `L1.md` | L2/L3 on-demand retrieval | 매 턴 전체 raw를 주입 |
| 멘토 파생 신호 | `~/.claude/cmux-jarvis/mentor/signals.jsonl` | weekly report markdown | 심리 진단, 성격 단정 |
| 멘토 온톨로지 | `docs/jarvis/architecture/mentor-ontology.md` | vibe-sunsang adapter | 코드 안 하드코딩 |
| JARVIS constitution | `docs/jarvis/architecture/jarvis-constitution.md` | `cmux-jarvis/references/iron-laws.md` | role별 prompt에 중복 복붙 |
| 개입/재촉 정책 | `docs/jarvis/architecture/nudge-escalation-policy.md` | `referense/badclaude-main` | OS 전역 키 주입, 처벌형 자동화, Watcher 직접 실행 |
| 외부 참고자료 | `referense/` | 이전 `/tmp` clone, GitHub URL | 네트워크 최신본을 로컬 검증 없이 SSOT로 사용 |
| 이미지 레퍼런스 | `docs/jarvis/architecture/jarvis-capability-targets.md` | `referense/1.jpeg`, `referense/2.jpeg` | 이미지 문구를 검증된 외부 사실로 주장 |
| 핵심 계획 | 이 문서 | `docs/jarvis/*` 세부 문서 | 여러 계획 문서가 서로 다른 우선순위 주장 |

P0 결정: `orchestra-config.json`의 `surfaces`, `main_surface`, `watcher_surface`, `main_ai`, `auto_synced`는 최종적으로 제거한다. 단, 현재 `read-surface.sh`, `workspace-resolver.sh`, `idle-auto-dispatch.sh`, `eagle_watcher.sh`, `validate-config.sh`가 아직 config `surfaces`를 읽으므로 즉시 삭제하지 않는다. 먼저 resolver 계층을 `/tmp/cmux-surface-map.json` + `cmux tree --all` 우선으로 이관하고, `orchestra-config.json`의 runtime field는 `_legacy_runtime_surfaces` 같은 명시적 compat 경로로 격하시킨 뒤 제거한다.

## 5. SRP 경계

Boss/Main:

- 한다: task decomposition, department workspace 생성, team lead 지시, DONE 취합, 리뷰 Agent 위임, 최종 커밋.
- 하지 않는다: worker pane 직접 작업 배정, Watcher 역할 수행, JARVIS 진화 직접 구현.

Team Lead:

- 한다: 자기 department workspace 안 worker pane 생성, 로컬 AI와 모델 선택, worker 작업 검증, Boss에게 DONE 보고.
- 한다: 자기 department workspace 안 worker가 느리거나 지시를 이탈할 때 nudge/escalation policy에 따라 해당 pane에만 재촉/interrupt를 실행.
- 하지 않는다: 다른 department workspace 관리, 최종 커밋, JARVIS config 진화.

Watcher:

- 한다: scan, status classification, alert, Main에 보고.
- 하지 않는다: task dispatch, code edit, department 생성/삭제, worker 직접 복구 지시.

JARVIS Evolution Lane:

- 한다: 반복 문제 감지, root cause 분석, 승인, 백업, evolution worker 위임, 사전 정의 검증, KEEP/DISCARD/rollback.
- 한다: Boss가 느리거나 사용자 지시를 이행하지 않는 근거가 충분할 때 User/CEO에게 개입안을 제시하고, 승인 또는 사전 정책이 있으면 Boss surface에만 session-scoped nudge를 실행.
- 하지 않는다: 모든 지식 관리/멘토링/시각화/예산을 한 세션에서 동시에 처리.

JARVIS Mentor Lane:

- 한다: 사용자 지시 품질 신호 분석, 코칭 제안, 학습 방향 제시, reflection report 생성.
- 하지 않는다: 사용자의 승인권을 대체, 심리/성격 진단, 작업 중 일방적 차단.

Memory Adapter:

- 한다: raw conversation, derived signals, operational memory, telemetry를 분리하고 필요한 최소 컨텍스트만 제공.
- 하지 않는다: 모든 memory store를 하나의 `memories.json`에 합치기.

Palace Memory Adapter:

- 한다: mempalace의 wing/room/drawer/L0~L3 패턴을 cmux mentor memory에 맞춰 저장/검색/계층 로딩으로 제한한다.
- 하지 않는다: 사용자 점수화, JARVIS 진화 결정, Boss dispatch에 직접 개입.

Signal Engine:

- 한다: rolling window, detrending, lagged comparison, predicted-vs-actual, confidence, evidence span 계산.
- 하지 않는다: 낮은 표본으로 자동 결론 확정, 사용자에게 단정적 라벨 부여.

Nudge/Escalation Controller:

- 한다: slow/stalled/instruction-drift 세션에 대한 역할 기반 재촉 이벤트 생성, session-scoped interrupt, follow-up prompt, throttle, audit log 기록.
- 하지 않는다: 작업을 직접 수행, Watcher 권한으로 실행, OS 전역 키 입력, 모욕/위협 문구 전송, 여러 세션 broadcast.

Mentor Ontology:

- 한다: vibe-sunsang의 6축, workspace type, 레벨, 안티패턴, 요청 품질 기준을 cmux 용어로 정의한다.
- 하지 않는다: raw log 저장, report 렌더링, hook injection, JARVIS config 변경.

## 6. Mentor Signal 모델

초기 signal은 점수화보다 "증거 있는 경향"을 우선한다. vibe-sunsang의 6축을 기본 온톨로지로 삼되, cmux 오케스트레이션에 맞춰 ORCH/VERIFY/FAIL을 핵심 축으로 올린다.

기본 이벤트:

- `user_instruction_submitted`
- `boss_plan_created`
- `department_created`
- `lead_done_reported`
- `review_failed`
- `verification_failed`
- `scope_changed`
- `user_override`
- `jarvis_mentor_advice_shown`
- `user_feedback_on_advice`
- `nudge_requested`
- `nudge_applied`
- `nudge_ignored`
- `nudge_escalated`
- `nudge_rate_limited`

초기 파생 신호:

- `DECOMP`: 요구사항을 부서/팀장/작업 단위로 분해할 수 있을 만큼 명확한가.
- `VERIFY`: 테스트, 리뷰, 근거, 재현 조건, 완료 기준을 요구하는가.
- `ORCH`: 단일 에이전트, 부서 분할, 병렬 worker, JARVIS 진화 중 무엇이 맞는지 구분하는가.
- `FAIL`: 오류 원인 분석, 대안 탐색, 재시도 조건, rollback 판단이 있는가.
- `CTX`: 파일 경로, 제약 조건, 배경, 사용자 목표, acceptance criteria가 있는가.
- `META`: 사용자가 자기 지시 방식과 하네스를 점검하고 개선하려 하는가.
- `intent_clarity`: 요구사항, 산출물, 제약, 완료 조건이 명확한가.
- `scope_stability`: 중간에 범위가 얼마나 자주 바뀌는가.
- `decision_latency`: 승인/보류/중단 판단이 얼마나 지연되는가.
- `rework_rate_after_instruction`: 초기 지시 후 재작업 비율.
- `mentor_receptivity`: JARVIS 제안 후 사용자가 지시를 개선했는가.
- `nudge_effectiveness`: nudge 후 지정 시간 안에 DONE, blocker report, clarification request 중 하나가 나왔는가.
- `instruction_drift_recovery`: 재촉/재지시 후 원래 목표로 복귀했는가.

분석 방식:

- window: 최근 5~10개 user instruction 또는 최근 1~3개 orchestration round.
- detrend: 전체 평균보다 최근 window가 좋아졌는지/나빠졌는지 본다.
- lag: 사용자 지시 변화가 다음 1~3 round의 재작업률, 검증 실패, 완료 시간에 미치는 영향을 본다.
- predicted-vs-actual: Boss plan이 예측한 난이도/부서 수/리스크와 실제 DONE/rework/error를 비교한다.
- confidence: 표본 수, 관찰 기간, 이벤트 누락 여부를 함께 기록한다.
- calibration: 실제 outcome이 JARVIS/Boss 예상과 어긋났을 때 다음 advice confidence를 낮춘다.
- level: 공식 노출은 0.5 단위까지만, 내부 추적은 소수점 2자리까지 허용한다.
- gate: 상위 레벨 판정은 최근 window에서 반복 관찰될 때만 허용한다.

금지:

- 사용자의 성격, 정신상태, 능력을 단정하지 않는다.
- 단일 메시지로 장기 패턴을 결론내리지 않는다.
- raw conversation을 대량으로 prompt에 주입하지 않는다.
- 사용자가 opt-out한 데이터를 저장하지 않는다.
- 느린 에이전트에게 모욕적/위협적 문구를 보내지 않는다.
- 감사 로그와 throttle 없이 반복 interrupt를 보내지 않는다.

## 7. 실행 계획

### P0. 차단 리스크 정리

목표: Plan A의 검증 가능한 기반을 먼저 복구한다.

작업:

- `validate-config.sh`의 `os` import 누락을 수정하고 테스트한다.
- `orchestra-config.json`의 runtime surface 필드와 `_note` 충돌을 정리한다. 사실 확인 결과 `read-surface.sh`, `workspace-resolver.sh`, `idle-auto-dispatch.sh`, `eagle_watcher.sh`, `validate-config.sh`가 아직 config `surfaces`를 읽으므로, 먼저 resolver를 `/tmp/cmux-surface-map.json` + `cmux tree --all` 우선으로 바꾼 뒤 runtime field를 제거한다.
- runtime department SSOT를 `/tmp/cmux-surface-map.json`으로 고정하고 schema를 문서화한다.
- `cmux-start` 중복 실행 시 Main/Watcher/JARVIS idempotency를 실제 검증한다.
- `referense/1.jpeg`, `referense/2.jpeg`는 문구를 외부 사실로 주장하지 않고 JARVIS 원칙/capability target 레퍼런스로만 문서화한다. 사실 확인 결과 둘 다 `referense/` 아래 JPEG이고 docs asset 디렉터리는 없으므로, P1 전까지 `referense` reference로 유지한다.

검증:

- `bash cmux-orchestrator/scripts/validate-config.sh`
- `bash -n` for changed shell scripts
- 관련 Python `py_compile`
- `/cmux-start` 수동 시뮬레이션 또는 cmux socket 기반 dry run

### P1. Chunk A/C/D/H 문서화

목표: vibe-sunsang, 이미지 1/2, badclaude nudge reference를 코드보다 먼저 SSOT 문서로 흡수한다.

작업:

- `docs/jarvis/architecture/mentor-lane.md` 작성.
- `docs/jarvis/architecture/mentor-ontology.md` 작성: DECOMP/VERIFY/ORCH/FAIL/CTX/META, workspace type, 레벨, 안티패턴.
- `docs/jarvis/architecture/jarvis-constitution.md` 작성: Iron Law + `referense/1.jpeg`의 constitutional/adaptive/agentic/self-play 원칙.
- `docs/jarvis/architecture/jarvis-capability-targets.md` 작성: `referense/2.jpeg`의 security/software/alignment/calibration/visual reasoning target.
- `docs/jarvis/architecture/nudge-escalation-policy.md` 작성: badclaude의 interrupt/overlay 패턴을 session-scoped nudge 정책으로 재해석하고, Worker/Lead/Boss별 권한, throttle, audit log를 정의.
- raw, signal, report schema 초안 정의.

검증:

- 문서 간 중복 권위가 없는지 SSOT review.
- JARVIS Evolution Lane과 Mentor Lane의 책임 분리 review.
- 이미지 레퍼런스가 검증된 외부 사실처럼 표현되지 않았는지 red-team review.

### P2. Chunk B/G Palace Memory 설계

목표: mempalace를 그대로 가져오지 않고 cmux용 palace memory substrate로 설계한다.

작업:

- `docs/jarvis/architecture/palace-memory-ssot.md` 작성.
- `docs/jarvis/architecture/mentor-privacy-policy.md` 작성.
- `wing/room/hall/tunnel/closet/drawer`를 cmux 용어로 mapping한다.
- L0/L1/L2/L3 loading policy를 정의한다.
- raw drawer 저장은 opt-in으로 둔다.
- `~/.claude/cmux-jarvis/mentor/palace/drawers/` writer 후보를 설계한다.
- `~/.claude/cmux-jarvis/mentor/signals.jsonl` writer 후보를 설계한다.
- 기존 `agent-memory.sh`는 orchestration event memory로 유지한다.
- `cmux-main-context.sh`에는 raw memory가 아니라 요약된 mentor signal만 제한적으로 주입한다.

검증:

- raw 저장 opt-in/off 설계 review.
- 민감 정보 필터링 정책 review.
- memory file locking/atomic append 테스트 계획.
- prompt inject가 L0/L1 + coaching hint 1개만 넣는지 policy review.

### P3. Chunk A/B 최소 코드 구현

목표: 인간 사용자의 지시 품질을 vibe-sunsang 6축 기반으로 관찰하고, mempalace-style raw/derived store를 분리한다.

작업:

- `cmux-jarvis/scripts/jarvis_mentor_signal.py` 또는 동등한 script 추가.
- `cmux-jarvis/scripts/jarvis_palace_memory.py` 또는 동등한 script 추가.
- window/trend/lag/predicted-vs-actual/calibration 계산.
- DECOMP/VERIFY/ORCH/FAIL/CTX/META 기본 score를 산출한다.
- confidence와 evidence span을 반드시 포함한다.
- JARVIS telemetry에 `mentor_signal_generated` 이벤트를 emit한다.

검증:

- `/tmp` fixture 기반 단위 테스트.
- 작은 sample에서 표본 부족 시 "insufficient evidence"가 나오는지 확인.
- user-facing report에서 단정적 표현이 없는지 red flag test.
- raw drawer와 derived signal이 서로 다른 저장소에 기록되는지 확인.

### P4. Chunk F Soft Intervention

목표: JARVIS가 사용자의 흐름을 끊지 않고 지시 개선을 돕는다.

작업:

- `/cmux` context에 다음 round에만 적용되는 짧은 조언을 주입한다.
- 예: "이번 요청은 완료 조건이 빠져 있어 팀장이 과분할할 수 있습니다. 완료 조건 1줄을 추가하면 재작업률을 낮출 수 있습니다."
- 조언은 최대 1~2개, 근거와 예상 효과를 함께 제시한다.
- L0/L1 wake-up은 600~900 token 이내 목표로 제한한다.
- L2/L3 deep search는 사용자가 요청하거나 Boss/JARVIS가 evidence 부족을 선언한 경우에만 실행한다.

검증:

- additionalContext 길이 제한.
- 사용자가 무시해도 workflow가 막히지 않음.
- 같은 조언 반복 spam 방지.

### P4.1 Chunk H Controlled Nudge/Escalation

목표: 팀원, 팀장, Boss가 느리거나 지시를 이행하지 않을 때 역할 권한 안에서 재촉/interrupt/재지시를 실행한다.

작업:

- `nudge-escalation-policy.md`의 L1/L2/L3 단계를 코드 contract로 옮긴다.
- Worker 대상 nudge는 해당 Team Lead만 같은 department side tab의 worker pane에 실행한다.
- Team Lead 대상 nudge는 Boss만 해당 lead surface에 실행한다.
- Boss 대상 nudge는 JARVIS가 근거를 묶어 User/CEO에게 제시한 뒤 승인 또는 명시 정책에 따라 실행한다.
- badclaude의 visual whip/interrupt 아이디어는 옵션 UX로만 두고, 핵심 동작은 cmux session ID를 대상으로 하는 메시지/interrupt API를 우선한다.
- 모든 nudge는 `target_surface_id`, `issuer_role`, `reason_code`, `evidence_span`, `level`, `cooldown_until`, `outcome`을 audit event로 남긴다.
- 기본 문구는 존중형이어야 한다. 예: "현재 8분간 진행 신호가 없습니다. 60초 안에 DONE, BLOCKED, NEEDS_INFO 중 하나로 보고하세요."

검증:

- Watcher가 직접 실행하지 않는지 권한 테스트.
- 다른 side tab/pane으로 broadcast되지 않는지 session ID 테스트.
- cooldown 안에서 반복 nudge가 rate-limited 되는지 테스트.
- L2 interrupt 후 기존 task context가 follow-up prompt에 보존되는지 fixture 테스트.
- macOS/Windows OS 전역 키 입력 없이 cmux 세션 경로로만 동작하는지 review.

### P5. Chunk E Mentor Report

목표: JARVIS가 사용자를 주기적으로 코칭한다.

작업:

- 최근 round 요약.
- DECOMP/VERIFY/ORCH/FAIL/CTX/META 6축 변화.
- 좋아진 점과 악화된 점을 증거 기반으로 표시.
- TIMELINE row 업데이트.
- 다음 1주일의 연습 목표 1~3개 제안.
- 사용자가 KEEP/DISCARD/IGNORE로 피드백할 수 있게 한다.

검증:

- raw quote 최소화.
- 표본 부족 시 보고서 생성 보류.
- JARVIS Evolution Lane의 config 변경 승인 flow와 섞이지 않음.
- 리포트는 사용자를 평가하는 문서가 아니라 AI 협업 하네스를 개선하는 문서로 표현.

### P6. Evolution과 Mentor의 결합

목표: 인간 하네스 개선과 시스템 하네스 개선을 함께 학습한다.

작업:

- 반복 실패의 원인을 system config, team decomposition, user instruction 중 하나 이상으로 분류한다.
- system 원인이면 Evolution Lane으로 보낸다.
- user instruction 원인이면 Mentor Lane에서 soft advice로 처리한다.
- 둘 다 원인이면 JARVIS가 사용자에게 "시스템 변경 vs 지시 방식 변경"을 비교 제안한다.

검증:

- JARVIS가 사용자 지시 개선을 빌미로 승인 없는 config 변경을 하지 않음.
- system evolution은 기존 Iron Law, 2단계 승인, rollback을 통과해야 함.

## 8. 레드팀 리뷰

1. JARVIS 역할 폭발
   - 문제: Evolution, monitoring, mentor, memory, visualization, budget을 한 pane에 넣으면 SRP가 깨진다.
   - 대응: Evolution Lane과 Mentor Lane을 명시적으로 분리한다. Phase 1에서는 Mentor Lane도 설계와 signal v0까지만 간다.

2. SSOT 붕괴
   - 문제: `orchestra-config.json`의 `_note`와 runtime fields가 충돌한다.
   - 대응: P0에서 preset config와 runtime map을 분리하고 validate-config를 고친다.

3. Watcher 권한 오염
   - 문제: Watcher 문서 일부에는 복구 명령 예시가 있고, 강한 금지 규칙도 같이 있어 해석이 흔들릴 수 있다.
   - 대응: Watcher는 Main에 알림만 보낸다는 상위 규칙을 gate로 강제한다. 실제 복구 지시는 Main이 실행한다.

4. 인간 멘토링의 오버리치
   - 문제: JARVIS가 사용자를 평가하거나 통제하는 시스템이 되면 신뢰를 잃는다.
   - 대응: 조언은 작업 품질 신호에 한정하고, 성격/심리 진단을 금지한다. opt-out과 report discard를 제공한다.

5. 메모리 프라이버시
   - 문제: raw conversation 저장은 민감하다.
   - 대응: raw는 opt-in, retention, redaction, local-only 원칙을 둔다. prompt에는 derived signal만 주입한다.

6. 통계 환상
   - 문제: 적은 표본으로 "사용자 패턴"을 단정할 수 있다.
   - 대응: confidence, insufficient evidence, lag window를 필수 필드로 둔다.

7. GitHub star 1위급 제품성
   - 문제: 많은 기능보다 "항상 정확히 작동하는 핵심 loop"가 중요하다.
   - 대응: P0/P1/P2를 제품 핵심으로 보고, 외부 메모리/AGI 확장은 adapter로 둔다.

8. 외부 레포 과흡수
   - 문제: vibe-sunsang과 mempalace를 그대로 합치면 Claude Code 멘토 플러그인, memory DB, cmux orchestration이 한 덩어리가 된다.
   - 대응: vibe-sunsang은 ontology, mempalace는 memory substrate로만 흡수한다. 실행 주체와 저장소는 cmux 쪽에서 재정의한다.

9. Raw memory 검색 결과의 권위 오해
   - 문제: mempalace-style raw drawer 검색 결과를 JARVIS가 사실로 오해할 수 있다.
   - 대응: raw drawer는 "기억된 발화/자료"일 뿐이고, system fact는 별도 검증을 거친다.

10. 재촉 무기의 권한 오염
   - 문제: badclaude식 OS 전역 키 입력을 그대로 흡수하면 잘못된 pane에 interrupt가 들어가거나, Watcher가 실행 권한을 갖거나, 모욕적 자동화가 제품 신뢰를 무너뜨릴 수 있다.
   - 대응: 세션 ID 기반 nudge만 허용하고, Worker는 Team Lead, Lead는 Boss, Boss는 JARVIS/User 경로로만 개입한다. Watcher는 evidence producer로 제한한다.

## 9. 블루팀 리뷰

현재 코드베이스의 강점:

- Department = workspace, Team Lead = lead surface, Worker = same workspace pane 구조가 이미 문서화되어 있다.
- Watcher의 금지 행위와 peer 경계가 강하게 작성되어 있다.
- JARVIS는 approval, backup, verification, rollback 개념을 이미 갖고 있다.
- `agent-memory.sh`와 `jarvis_telemetry.py`가 있어 memory/signal layer를 새로 처음부터 만들 필요가 없다.
- `/cmux` additionalContext 주입 지점이 이미 있어 Mentor Lane의 soft intervention을 작게 시작할 수 있다.
- vibe-sunsang은 6축/레벨/안티패턴/TIMELINE을 이미 잘게 나눈 멘토링 모델로 제공한다.
- mempalace는 raw verbatim, palace graph, L0~L3 loading, MCP/search를 memory substrate로 삼을 만한 구조를 제공한다.
- 1.jpeg/2.jpeg는 JARVIS 헌법과 capability target을 제품 언어로 정리하는 기준점이 된다.
- badclaude는 느린 AI 세션에 대한 attention UX와 interrupt+follow-up prompt 패턴을 보여주므로, cmux의 세션 스코프 nudge/escalation 기능으로 재해석할 수 있다.

따라서 방향은 "새 시스템 추가"가 아니라 "기존 구조의 SSOT와 경계를 보존하면서 Mentor Lane을 얇게 붙이는 것"이다.

## 10. FSD/아키텍처 경계 리뷰

이 프로젝트는 Feature-Sliced Design을 사용하지 않는다. 대체 기준은 role/domain/module boundary다.

Domain boundary:

- `cmux-orchestrator`: Boss/Main orchestration.
- `cmux-watcher`: runtime monitoring.
- `cmux-jarvis`: system evolution and future mentor intelligence.
- `cmux-start`: control tower bootstrap.
- `docs/jarvis`: architecture, pipeline, review records.
- `tests`: Python/hook unit tests.

Mentor Lane 도입 시 파일 배치 원칙:

- 문서: `docs/jarvis/architecture/mentor-lane.md`, `mentor-ontology.md`, `palace-memory-ssot.md`, `jarvis-constitution.md`, `jarvis-capability-targets.md`, `mentor-privacy-policy.md`.
- 파이프라인 문서: `docs/jarvis/pipeline/mentor-report-pipeline.md`.
- 코드: JARVIS 내부 script로 시작한다. 예: `cmux-jarvis/scripts/jarvis_mentor_signal.py`, `cmux-jarvis/scripts/jarvis_palace_memory.py`.
- hook: 기존 `cmux-main-context.sh`는 signal inject만 담당하고, 분석 로직을 직접 넣지 않는다.
- storage: `~/.claude/cmux-jarvis/mentor/` 아래에 두며, raw drawer, derived signal, L0/L1 context, reports를 분리한다.
- intervention: `cmux-orchestrator`는 Team Lead/Boss의 세션 개입 명령을 담당하고, `cmux-jarvis`는 Boss 대상 개입 정책과 User 승인 경로를 담당한다. Watcher는 trigger evidence만 제공한다.

## 11. 시뮬레이션

### 시뮬레이션 A. `/cmux-start` 이후 구조

예상 흐름:

1. User가 `/cmux-start` 실행.
2. control tower workspace가 Main, Watcher, JARVIS pane을 갖는다.
3. User가 작업을 지시.
4. Boss가 department workspace를 만든다.
5. 각 department workspace에 Team Lead surface가 생긴다.
6. Team Lead가 같은 workspace 안에 worker pane을 split하고 로컬 AI/model을 고른다.
7. Watcher는 상태만 Main에 보고한다.
8. Boss가 Team Lead DONE을 취합하고 review Agent를 위임한 뒤 commit한다.

근거상 성립한다. 다만 P0의 validate-config 실패와 runtime map SSOT 충돌 때문에 "정확히 항상 작동"한다고 말할 수는 없다.

### 시뮬레이션 B. Mentor Lane soft intervention

예상 흐름:

1. UserPromptSubmit hook에서 `/cmux` context injection이 실행된다.
2. 기존 watcher cache, roles, AI profile, memory recent를 읽는다.
3. 새 Mentor Signal summary가 있으면 최근 1~2개만 additionalContext에 넣는다.
4. Boss는 사용자의 지시를 바꾸지 않고, 조언을 참고해 질문하거나 plan을 더 명확히 만든다.

근거상 `cmux-main-context.sh`가 이미 injection point를 제공하므로 작은 구현으로 가능하다. 다만 raw memory capture와 signal generation은 아직 없다.

### 시뮬레이션 C. 반복 실패 분류

예상 흐름:

1. Watcher 또는 telemetry에서 반복 실패를 감지한다.
2. JARVIS가 failure evidence를 수집한다.
3. 원인이 system config이면 Evolution Lane으로 보낸다.
4. 원인이 user instruction ambiguity이면 Mentor Lane에서 advice를 생성한다.
5. 원인이 복합이면 사용자에게 두 경로를 비교해서 승인받는다.

이 흐름은 현재 JARVIS evolution pipeline과 telemetry 구조 위에 얹을 수 있다. 단, 분류기가 없으므로 P3 전에는 수동/규칙 기반으로 제한한다.

### 시뮬레이션 D. vibe-sunsang 6축 흡수

예상 흐름:

1. User instruction이 들어오면 JARVIS Mentor Lane은 raw text를 직접 평가하지 않고 event를 만든다.
2. Mentor Ontology가 DECOMP/VERIFY/ORCH/FAIL/CTX/META 신호를 산출한다.
3. workspace type이 cmux orchestration이면 Builder+Operator weight를 적용한다.
4. 단일 round로 레벨을 올리지 않고 최근 window에서 반복 관찰될 때만 레벨/약한 축을 제안한다.
5. report는 "사용자 등급표"가 아니라 "다음 orchestration round에서 개선할 하네스"로 출력한다.

리스크: vibe-sunsang의 멘토링 언어를 그대로 쓰면 사용자를 평가하는 느낌이 강해질 수 있다. cmux에서는 "AI 협업 하네스 개선"으로 표현을 바꿔야 한다.

### 시뮬레이션 E. mempalace memory 흡수

예상 흐름:

1. opt-in이 켜진 경우에만 raw conversation을 drawer로 저장한다.
2. wing은 user/project/department, room은 topic/failure/mentor-axis로 매핑한다.
3. L0/L1은 항상 로드 가능한 짧은 context로 유지한다.
4. L2/L3 deep search는 evidence 부족 시에만 실행한다.
5. 검색 결과는 raw memory evidence로만 표시하고, system fact로 승격하려면 별도 검증을 요구한다.

리스크: ChromaDB/MCP를 즉시 의존성으로 넣으면 설치/운영 복잡도가 커진다. Phase 1은 JSONL/SQLite schema와 adapter interface까지만 둔다.

### 시뮬레이션 F. 이미지 원칙 흡수

예상 흐름:

1. `referense/1.jpeg`의 constitutional/adaptive/agentic/self-play 원칙을 JARVIS constitution 문서로 옮긴다.
2. `referense/2.jpeg`의 security/software/alignment/calibration/visual reasoning을 capability target으로 옮긴다.
3. Mentor advice와 Evolution proposal은 항상 evidence/confidence/scope/verification 필드를 가진다.
4. Watcher visual/OCR 신호는 "surface 상태 판단 보조"로만 쓰고, 코드 진실성 판단은 tests/review/build로 검증한다.

리스크: 이미지 문구는 외부 fact가 아니므로 "Claude Mythos Preview 성능" 같은 주장을 cmux 문서의 사실 근거로 쓰지 않는다.

### 시뮬레이션 G. badclaude식 재촉 무기 흡수

예상 흐름:

1. Watcher가 worker pane에서 `STALLED` 또는 `instruction_drift` 증거를 만든다.
2. Team Lead가 해당 worker surface ID만 대상으로 L1 nudge를 보낸다.
3. 지정 시간 안에 DONE/BLOCKED/NEEDS_INFO가 없으면 Team Lead가 L2 session-scoped interrupt와 재지시를 보낸다.
4. Team Lead 자체가 멈추면 Boss가 동일한 정책으로 lead surface에만 nudge를 보낸다.
5. Boss가 사용자 지시를 이행하지 않거나 장시간 정지하면 JARVIS가 evidence bundle을 만들고 User/CEO 승인 또는 사전 정책에 따라 Boss surface에만 nudge를 보낸다.
6. 모든 nudge는 audit event로 남고, cooldown 중 반복 요청은 `nudge_rate_limited`로 기록된다.

근거상 badclaude는 Electron overlay, canvas whip physics, sound, `whip-crack` IPC, macOS/Windows 키 입력 매크로로 interrupt+문구 전송을 구현한다. cmux에는 그대로 이식하지 않고, interaction metaphor와 interrupt+follow-up prompt 패턴만 가져온다.

리스크: OS 전역 키 입력은 잘못된 앱/세션으로 전송될 수 있다. 따라서 P4.1 구현 전까지는 cmux session ID 기반 메시지/interrupt API가 확인되지 않으면 L2는 No-Go다.

## 12. Readiness Gate

Conditional Go:

- P0만 즉시 착수 가능.
- P1 문서화는 P0와 병행 가능하지만, P1 내용을 hook/code에 연결하는 것은 validate-config 복구 후만 허용한다.
- P2 palace memory 설계는 가능하지만 raw drawer 저장 구현은 privacy/retention/opt-out 결정 전에는 No-Go.
- P3 최소 코드는 raw off 기본값, fixture 테스트, insufficient evidence 동작이 있어야 Conditional Go.
- external memory adapter, ChromaDB, MCP는 local-only schema와 import/export contract가 생긴 뒤 검토한다.
- P4.1 nudge/escalation은 session ID 기반 interrupt 경로, 권한 matrix, audit log, cooldown이 정의되기 전까지 L1 텍스트 재촉만 허용한다. OS 전역 키 입력 기반 구현은 No-Go다.

## 12.1 확인 항목 종결 결정

1. Raw conversation 저장
   - 확인 사실: `~/.claude/cmux-jarvis/config.json`에는 mentor/raw/opt-in/privacy 설정이 없다. `~/.claude/cmux-jarvis/mentor/` 디렉터리도 없다. 현재 운영 메모리는 `~/.claude/memory/cmux/journal.jsonl` 170라인뿐이다.
   - 결정: 기본값은 raw 저장 OFF다. P2 구현 전까지 derived signal만 허용하고, raw drawer는 `mentor.raw_capture_enabled: true` 같은 명시 config와 retention/redaction 정책이 생긴 뒤에만 구현한다.

2. `referense/1.jpeg`, `referense/2.jpeg`
   - 확인 사실: 둘 다 `referense/` 아래 JPEG다. `file` 기준 `referense/1.jpeg`는 1080x2679, `referense/2.jpeg`는 1079x2697이며 Android EXIF가 있다. 현재 `docs` 아래 asset/image 전용 디렉터리는 없다.
   - 결정: P1 전까지 이동하지 않고 `referense` reference로 유지한다. 문서에서는 이미지 문구를 외부 검증 사실로 쓰지 않고 JARVIS constitution/capability target의 제품 원칙 근거로만 사용한다. asset 편입은 P1에서 `docs/jarvis/assets/` 생성 여부까지 같이 결정한다.

3. `orchestra-config.json` runtime fields
   - 확인 사실: `_note`는 runtime workspaces/surfaces가 동적이고 presets만 정본이라고 하지만, config에는 `surfaces`, `main_surface`, `watcher_surface`, `main_ai`, `auto_synced`가 남아 있다. 또한 `read-surface.sh`, `workspace-resolver.sh`, `idle-auto-dispatch.sh`, `eagle_watcher.sh`, `validate-config.sh`가 아직 config `surfaces`를 읽는다.
   - 결정: 즉시 삭제가 아니라 2단계 제거다. P0-1에서 resolver를 `/tmp/cmux-surface-map.json` + `cmux tree --all` 우선으로 바꾼다. P0-2에서 config runtime fields를 legacy compat로 격하한다. P0-3에서 해당 compat read path가 사라진 뒤 제거한다.

4. Mentor report 주기
   - 확인 사실: vibe-sunsang은 weekly/monthly routine과 TIMELINE을 제공하지만, cmux에는 아직 mentor report pipeline이 없다. cmux 작업은 orchestration round 기반으로 진행된다.
   - 결정: 기본 주기는 "weekly + 5 orchestration rounds 중 먼저 도달한 조건"이다. 단, report 생성은 표본 부족 시 보류한다. soft intervention은 매 round 최대 1개 hint로 제한한다.

5. vibe-sunsang 레벨명
   - 확인 사실: vibe-sunsang은 Builder/Explorer/Designer/Operator별 레벨명을 제공한다. cmux의 목적은 사용자 평가가 아니라 AI 협업 하네스 개선이다.
   - 결정: user-facing 이름은 `Harness Level`로 바꾼다. vibe-sunsang 레벨명은 내부 ontology alias로만 유지한다.

6. mempalace adapter 방식
   - 확인 사실: mempalace 원격 `main` HEAD는 조사한 `1056018b521824a590400e36ccb540588f065895`와 일치한다. repo는 ChromaDB/MCP/raw verbatim 중심이며, cmux에는 아직 mentor palace storage가 없다.
   - 결정: Phase 1/2는 독립 JSONL/SQLite substrate로 간다. ChromaDB/MCP 호환 adapter는 Phase 3 이후 optional로 둔다. raw drawer 검색 결과는 system fact가 아니라 memory evidence로만 취급한다.

7. vibe-sunsang 외부 근거 최신성
   - 확인 사실: vibe-sunsang 원격 `main` HEAD는 조사한 `7376fa429bbb56b80f69d5aedabfff6399be5add`와 일치한다.
   - 결정: 현재 문서의 vibe-sunsang 흡수 근거는 최신 `main` 기준으로 유지한다. 단, 구현 전에는 다시 `git ls-remote`로 HEAD를 확인한다.

8. validate-config 차단 항목
   - 확인 사실: 실제 cmux socket 접근으로 `bash cmux-orchestrator/scripts/validate-config.sh`를 재실행하면 `NameError: name 'os' is not defined`로 실패한다.
   - 결정: P0의 첫 구현 항목은 `validate-config.sh` Python block에 `import os`를 추가하고, no-cmux/sandbox/cmux-socket 세 경우의 JSON report 동작을 고정하는 것이다.

9. `referense/` 로컬 참고자료 SSOT
   - 확인 사실: `referense/`에는 `mempalace-main`, `vibe-sunsang-main`, `badclaude-main`, `1.jpeg`, `2.jpeg`가 저장되어 있다. `.git` 디렉터리는 없으므로 commit 기반 최신성보다 로컬 스냅샷 파일 내용이 우선 근거다.
   - 결정: 이후 플랜 검증은 `referense/`를 외부 참고자료 SSOT로 삼는다. 네트워크 원격과 `/tmp` clone은 보조 확인 수단이며, 로컬 `referense`와 다르면 `referense` 기준으로 문서를 수정한다.

10. badclaude 흡수 방식
   - 확인 사실: `referense/badclaude-main`은 Electron tray/overlay 앱이고, macOS/Windows에서 키 입력 매크로로 interrupt와 문구 입력을 보낸다. package는 `electron`과 `koffi`를 의존하고 OS는 `darwin`, `win32`로 제한되어 있다.
   - 결정: cmux는 badclaude를 runtime dependency로 vendoring하지 않는다. visual attention과 interrupt+follow-up prompt 패턴만 흡수하고, 실제 개입은 cmux session ID 기반 nudge/escalation 정책으로 설계한다.

## 13. 성공 기준

P0 성공:

- validate-config가 실제 cmux tree 또는 no-cmux 상태에서 명확한 JSON report를 낸다.
- runtime surface의 SSOT가 하나로 정리된다.
- 기존 tests와 shell syntax check가 통과한다.

P1 성공:

- Mentor Lane, Mentor Ontology, JARVIS Constitution, Capability Target이 서로 충돌하지 않는 문서 구조로 정착한다.
- vibe-sunsang은 ontology로, mempalace는 memory substrate로 분리되어 있다.
- `referense/1.jpeg`, `referense/2.jpeg`는 사실 근거가 아니라 제품 원칙으로만 반영되어 있다.

P2/P3 성공:

- 사용자 instruction signal이 raw quote 없이 derived evidence로 생성된다.
- DECOMP/VERIFY/ORCH/FAIL/CTX/META가 최소 fixture에서 계산된다.
- raw, derived, operational, telemetry memory가 분리되어 있다.
- 표본 부족 시 조언을 보류한다.
- prompt injection은 짧고 삭제 가능하다.

P4/P5 성공:

- JARVIS 조언이 사용자 workflow를 막지 않는다.
- 조언 수용/무시/폐기가 signal로 다시 학습된다.
- system evolution과 human coaching이 서로 다른 승인 경로를 갖는다.
- Worker/Lead/Boss nudge가 역할 권한, session ID, audit log, cooldown을 통과한다.
- badclaude식 UX는 옵션 reference일 뿐 OS 전역 키 입력이 핵심 경로가 되지 않는다.

## 14. 다음 작업 제안

1. P0 구현: `validate-config.sh` 복구와 `orchestra-config.json` SSOT 정리.
2. P1 문서 분리: Mentor Ontology, Palace Memory SSOT, JARVIS Constitution, Capability Target, Privacy Policy 작성.
3. P2 설계 검증: raw drawer opt-in, L0/L1/L2/L3 loading, vibe 6축 scoring schema 검토.
4. P3 최소 코드: `jarvis_mentor_signal.py`, `jarvis_palace_memory.py` fixture 기반 구현.
5. P4 hook 연결: `cmux-main-context.sh`에는 L0/L1 summary와 coaching hint 1개만 추가.
6. P4.1 nudge/escalation 설계: Worker/Lead/Boss 권한 matrix와 audit event schema를 먼저 문서화하고, cmux session ID 기반 interrupt 경로가 확인될 때만 L2를 구현.

가장 중요한 원칙은 "JARVIS가 더 똑똑해지는 것"이 아니라 "인간 사용자, Boss, Team Lead, Watcher, JARVIS가 각자의 책임을 잃지 않는 것"이다. AGI 지향 확장은 이 경계가 유지될 때만 제품으로 성장한다.

## 15. 플랜 검증 시스템 재검증

검증일: 2026-04-11
검증 방식: `research` + `simulate` 흐름. 외부 2개 레포는 원격 `main` HEAD 확인, tracked file 전수 목록화, README/스킬/에이전트/스크립트/핵심 모듈 키워드 검증, Python/shell 문법 검증을 수행했다.
주의: 이 장은 `referense/` 도입 전의 이전 검증 기록이다. `referense/` 도입 이후 외부 근거 SSOT와 최종 gate는 16장을 우선한다.

### 15.1 검증 입력

로컬 플랜:

- 파일: `docs/CMUX-AGI-MENTOR-INTEGRATED-PLAN.md`
- 검증 시점 라인 수: 694

외부 레포 1: MemPalace

- URL: `https://github.com/milla-jovovich/mempalace`
- 원격 `main` HEAD: `1056018b521824a590400e36ccb540588f065895`
- 로컬 조사 경로: `/tmp/cmux-research-mempalace`
- tracked files: 134
- tracked Python files: 76
- tracked Markdown files: 34
- 전수 표면: `.agents/`, `.claude-plugin/`, `.codex-plugin/`, `.github/`, `benchmarks/`, `docs/`, `examples/`, `hooks/`, `integrations/openclaw/`, `mempalace/`, `tests/`, `pyproject.toml`, `uv.lock`, `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `LICENSE`.

외부 레포 2: vibe-sunsang

- URL: `https://github.com/fivetaku/vibe-sunsang`
- 원격 `main` HEAD: `7376fa429bbb56b80f69d5aedabfff6399be5add`
- 로컬 조사 경로: `/tmp/cmux-research-vibe-sunsang`
- tracked files: 30
- tracked Python files: 1
- tracked Markdown files: 25
- 전수 표면: `.claude-plugin/`, `agents/`, `assets/`, `commands/`, `references/`, `scripts/`, `skills/`, `CHANGELOG.md`, `README.md`.

### 15.2 외부 레포 근거 검증

MemPalace 검증 결과:

- 플랜의 "raw verbatim drawer" 흡수는 사실과 맞다. README가 raw verbatim storage와 ChromaDB 기반 저장을 핵심으로 설명하고, `mempalace/searcher.py`, `mempalace/miner.py`, `mempalace/convo_miner.py`, `mempalace/repair.py`가 `mempalace_drawers` collection을 사용한다.
- 플랜의 "wing/room/hall/tunnel/closet/drawer" 흡수는 사실과 맞다. README와 `mempalace/palace_graph.py`가 wing/room/hall/tunnel graph 구조를 설명하고 구현한다.
- 플랜의 "L0/L1/L2/L3 계층 로딩" 흡수는 사실과 맞다. `mempalace/layers.py`가 L0 identity, L1 essential story, L2 on-demand recall, L3 deep search를 구현한다.
- 플랜의 "ChromaDB/MCP는 optional adapter" 결정은 안전하다. MemPalace는 ChromaDB/MCP를 적극 사용하지만, cmux에는 아직 mentor palace storage가 없고 P0/P1/P2는 SSOT/schema 단계이므로 즉시 의존성으로 넣으면 설치/운영 복잡도가 커진다.
- 플랜의 "AAAK는 기본 저장 포맷으로 흡수하지 않음"은 안전하다. README와 `mempalace/dialect.py`가 AAAK를 lossy/experimental로 분명히 다룬다.
- 플랜의 "raw drawer 검색 결과를 system fact로 승격하지 않음"은 안전하다. MemPalace 자체도 raw memory와 knowledge graph/contradiction detection 사이의 배선이 완전한 자동 사실 판정으로 닫혀 있지 않음을 문서화한다.

vibe-sunsang 검증 결과:

- 플랜의 "6축 Mentor Ontology" 흡수는 사실과 맞다. README, `skills/vibe-sunsang-mentor/SKILL.md`, `skills/vibe-sunsang-growth/SKILL.md`, `agents/growth-analyst.md`, 각 `growth-metrics.md`가 DECOMP/VERIFY/ORCH/FAIL/CTX/META를 반복적으로 정의한다.
- 플랜의 "Builder/Explorer/Designer/Operator workspace type" 흡수는 사실과 맞다. README, onboard skill, mentor skill, growth analyst가 네 workspace type을 기준으로 가중치와 안티패턴을 분기한다.
- 플랜의 "7단계 + 0.5 단위 + Fit Score" 흡수는 사실과 맞다. `agents/growth-analyst.md`와 `growth-metrics.md`들이 내부 소수점 추적, 공식 0.5 단위 반올림, Fit Score, gate 조건을 다룬다.
- 플랜의 "TIMELINE/weekly report" 흡수는 사실과 맞다. growth skill과 growth analyst가 `growth-log/TIMELINE.md` 업데이트를 명시한다.
- 플랜의 "Harness Level로 user-facing 용어 변경"은 외부 레포의 직접 구현은 아니며 cmux 제품 판단이다. 다만 vibe-sunsang이 사용자 성장/레벨 언어를 쓰기 때문에, cmux가 사용자를 평가하는 느낌을 줄이기 위해 Harness Level로 재명명하는 것은 SRP/UX 관점의 정당한 변환이다.

### 15.3 문법 검증

실행한 외부 코드 검증:

- `/tmp/cmux-research-mempalace`: `git ls-files '*.py' | xargs python3 -m py_compile` 통과.
- `/tmp/cmux-research-vibe-sunsang`: `git ls-files '*.py' | xargs python3 -m py_compile` 통과.
- `/tmp/cmux-research-mempalace`: `git ls-files '*.sh' | xargs bash -n` 통과.

실행하지 않은 검증:

- 외부 레포 전체 test suite는 실행하지 않았다. 이유: 이번 작업의 목적은 cmux 플랜 검증이며, 외부 레포의 dependency 설치와 테스트 환경 구성은 cmux 플랜의 직접 검증 범위를 넘는다. 따라서 외부 프로젝트의 런타임 품질은 검증 불가다.

### 15.4 Cyclic Review

SSOT:

- 판정: Conditional Pass.
- 근거: 플랜은 `orchestra-config.json` runtime field, mentor raw memory, palace index, L0/L1, mentor ontology, constitution, capability target을 별도 SSOT로 나눈다.
- 차단: 로컬 코드가 아직 `orchestra-config.json`의 `surfaces`를 읽는다. 따라서 P0 resolver 이관 전에는 SSOT가 완전히 닫히지 않는다.

SRP:

- 판정: Pass.
- 근거: vibe-sunsang은 scoring ontology, mempalace는 memory substrate, JARVIS constitution은 policy, capability target은 acceptance criteria, context injection은 injection만 담당하도록 청크가 나뉘어 있다.
- 주의: P3에서 `jarvis_mentor_signal.py`와 `jarvis_palace_memory.py`를 합치면 SRP가 깨진다. 파일을 분리해야 한다.

FSD/도메인 경계:

- 판정: Pass.
- 근거: 이 프로젝트는 FSD를 쓰지 않으므로 role/domain/module boundary로 대체한다. `cmux-orchestrator`, `cmux-watcher`, `cmux-jarvis`, `cmux-start`, `docs/jarvis`, `tests` 경계가 문서에 반영되어 있다.

Architect:

- 판정: Conditional Pass.
- 근거: Mentor Lane은 JARVIS 내부 문서/스크립트에서 시작하고, `cmux-main-context.sh`는 얇은 adapter로만 쓰기로 했다.
- 차단: P4 hook 연결은 `validate-config.sh`와 runtime surface SSOT가 복구된 뒤 진행해야 한다.

Edge Cases:

- 판정: Pass with P0/P2 gates.
- 반영된 edge: raw opt-in/off, raw prompt 대량 주입 금지, ChromaDB/MCP optional, image fact overclaim 금지, 표본 부족 시 report 보류, `validate-config.sh` NameError, config surfaces legacy dependency.

Coverage:

- 판정: Pass.
- 근거: 두 외부 레포의 실제 핵심 구조가 플랜의 Chunk A~G에 매핑되어 있다. 이미지 1/2도 constitution/capability target으로 분리되어 있다.

Execution:

- 판정: Conditional Pass.
- 근거: P0 -> P1 -> P2 -> P3 -> P4/P5 -> P6 순서는 현실적이다.
- 차단: P0 첫 작업은 반드시 `validate-config.sh` 복구와 resolver 이관이다. Mentor 코드 구현을 먼저 하면 runtime SSOT 충돌이 남는다.

Risk:

- 판정: Conditional Pass.
- 주요 리스크: 외부 레포 기능을 그대로 vendoring하려는 유혹, raw conversation privacy, ChromaDB/MCP dependency creep, 사용자 평가 UX, runtime surface SSOT 충돌.
- 완화: ontology/substrate/adapter 분리와 raw OFF 기본값이 계획에 들어가 있다.

Readiness:

- 판정: Conditional Go.
- 구현 가능: P0 코드 수정, P1 문서 분리.
- 구현 보류: raw drawer 저장, ChromaDB/MCP adapter, prompt injection, Mentor report 자동화.

### 15.5 최종 Gate

최종 판정: Conditional Go.

Go가 아닌 이유:

- `bash cmux-orchestrator/scripts/validate-config.sh`가 실제 cmux socket 접근 시 `NameError: name 'os' is not defined`로 실패한다.
- `orchestra-config.json`은 presets만 SSOT라고 말하지만, 여러 스크립트가 아직 config `surfaces`를 읽는다.
- raw mentor memory의 privacy/retention/opt-in config가 아직 없다.

No-Go가 아닌 이유:

- 외부 레포 2개 전수 표면과 핵심 코드가 플랜의 흡수 방향을 지지한다.
- 플랜이 외부 레포를 그대로 합치지 않고 ontology/substrate/adapter로 분리한다.
- raw memory, ChromaDB/MCP, prompt injection을 후순위 gate로 묶어 리스크를 차단한다.

Fix-before-build checklist:

1. `validate-config.sh` Python block에 `import os` 추가.
2. `read-surface.sh`, `workspace-resolver.sh`, `idle-auto-dispatch.sh`, `eagle_watcher.sh`, `validate-config.sh`의 runtime surface read path를 `/tmp/cmux-surface-map.json` + `cmux tree --all` 우선으로 이관.
3. `orchestra-config.json` runtime field를 legacy compat로 격하한 뒤 제거 계획 실행.
4. P1 문서 6개 생성: `mentor-ontology.md`, `palace-memory-ssot.md`, `jarvis-constitution.md`, `jarvis-capability-targets.md`, `mentor-privacy-policy.md`, `nudge-escalation-policy.md`. 이 항목은 16장의 `referense` 재검증 결과로 업데이트되었다.
5. raw drawer 저장은 opt-in config, retention, redaction, export/delete 정책 전까지 구현하지 않음.

## 16. referense 로컬 SSOT 재검증 및 nudge 통합

검증일: 2026-04-11
검증 방식: 사용자가 저장한 `referense/` 디렉터리를 외부 참고자료의 새 SSOT로 삼아 파일 표면, 핵심 문서/코드, 이미지 메타데이터, 문법 검증, Cyclic Review를 다시 수행했다.

### 16.1 검증 입력

로컬 참고자료 SSOT:

- 경로: `referense/`
- 전체 파일 수: 184
- code/doc 후보 파일 수: 155
- `.git` 디렉터리: 없음. 따라서 commit 최신성보다 저장된 로컬 스냅샷 파일 내용이 우선 근거다.
- 불필요 파일: `referense/.DS_Store` 1개. 계획 근거로 사용하지 않는다.

참고자료별 표면:

- `referense/mempalace-main`: 134 files. `.agents/`, `.claude-plugin/`, `.codex-plugin/`, `.github/`, `benchmarks/`, `docs/`, `examples/`, `hooks/`, `integrations/`, `mempalace/`, `tests/`, `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `pyproject.toml`, `uv.lock`.
- `referense/vibe-sunsang-main`: 30 files. `.claude-plugin/`, `agents/`, `assets/`, `commands/`, `references/`, `scripts/`, `skills/`, `README.md`, `CHANGELOG.md`.
- `referense/badclaude-main`: 17 files. `README.md`, `main.js`, `preload.js`, `overlay.html`, `bin/badclaude.js`, `package.json`, `package-lock.json`, `assets/`, `icon/`, `sounds/`.
- `referense/1.jpeg`: JPEG 1080x2679, Android EXIF.
- `referense/2.jpeg`: JPEG 1079x2697, Android EXIF.

### 16.2 badclaude 흡수 근거

확인 사실:

- `README.md`는 tray icon click으로 whip overlay를 띄우고, crack 시 interrupt와 follow-up message를 보내는 UX를 설명한다.
- `package.json`은 `electron`과 `koffi`를 dependency로 두며, 지원 OS를 `darwin`, `win32`로 제한한다.
- `main.js`는 Electron `Tray`, `BrowserWindow`, `ipcMain`을 사용해 투명 always-on-top overlay를 만들고, `whip-crack` IPC에서 `sendMacro()`를 호출한다.
- `main.js`는 Windows에서는 `koffi`로 `user32.dll` keyboard event를 호출하고, macOS에서는 `osascript`로 `Cmd+C`, text 입력, Enter를 보낸다.
- `overlay.html`은 canvas 기반 whip physics와 sound playback을 구현하고, tip velocity threshold를 넘으면 `window.bridge.whipCrack()`를 호출한다.
- `preload.js`는 `whipCrack`, `hideOverlay`, `onSpawnWhip`, `onDropWhip` IPC bridge만 노출한다.

흡수 결정:

- 흡수한다: attention UX, interrupt + follow-up prompt, crack/event metaphor, explicit user-triggered intervention.
- 흡수하지 않는다: OS 전역 키 입력, focus stealing, 모욕/위협 문구, 자동 처벌형 반복 interrupt, Electron/koffi runtime dependency.
- cmux 변환: Team Lead -> Worker, Boss -> Team Lead, JARVIS/User -> Boss의 권한 matrix를 가진 session-scoped nudge/escalation 정책으로 전환한다.

### 16.3 실행 검증

실행한 검증:

- `find referense/mempalace-main referense/vibe-sunsang-main -name '*.py' -print0 | xargs -0 python3 -m py_compile`: 통과.
- `find referense/mempalace-main referense/vibe-sunsang-main -name '*.sh' -print0 | xargs -0 bash -n`: 통과.
- `node --check referense/badclaude-main/main.js`: 통과.
- `node --check referense/badclaude-main/preload.js`: 통과.
- `node --check referense/badclaude-main/bin/badclaude.js`: 통과.
- `file referense/1.jpeg referense/2.jpeg`: JPEG 크기와 EXIF 확인.

실행하지 않은 검증:

- MemPalace, vibe-sunsang, badclaude의 전체 test suite와 Electron runtime 실행은 하지 않았다. 이유: 이번 작업은 cmux 플랜 문서 검증이며, 외부 프로젝트 dependency 설치와 GUI 권한 실행은 범위를 넘는다. 따라서 외부 프로젝트의 런타임 품질은 검증 불가다.
- cmux session ID 기반 interrupt API의 실제 존재와 동작은 아직 확인하지 않았다. 따라서 P4.1의 L2 session interrupt 구현 가능성은 검증 불가이며, 해당 API 확인 전까지 L2는 No-Go다.

### 16.4 Cyclic Review 업데이트

SSOT:

- 판정: Conditional Pass.
- 업데이트: 외부 근거의 우선 SSOT는 `referense/`다. 이전 `/tmp` clone과 GitHub URL은 보조 근거로 격하한다.
- 차단: `referense/`는 `.git` 없는 스냅샷이라 원격 최신성은 자체로 증명하지 못한다. 최신성 재확인은 별도 네트워크 검증이 필요하다.

SRP:

- 판정: Pass.
- 업데이트: Chunk H를 nudge/escalation policy로 분리했다. 작업 분해, Watcher scan, mentor scoring, memory storage와 섞지 않는다.

FSD/도메인 경계:

- 판정: Pass.
- 업데이트: 이 프로젝트는 FSD가 아니라 role/domain/module boundary를 사용한다. 개입 명령은 `cmux-orchestrator`, Boss 대상 정책과 승인 경로는 `cmux-jarvis`, 감지 근거는 `cmux-watcher`로 분리한다.

Architect:

- 판정: Conditional Pass.
- 업데이트: badclaude의 OS macro architecture는 cmux 핵심 구조와 맞지 않으므로 도입하지 않는다. cmux는 session ID를 대상으로 한 메시지/interrupt API가 확인될 때만 L2를 구현한다.

Edge Cases:

- 판정: Conditional Pass.
- 반영: 잘못된 pane interrupt, multi-pane broadcast, focus stealing, Watcher 권한 오염, 반복 spam, 모욕적 문구, cooldown 누락, audit log 누락, Boss 대상 개입 승인 누락을 Chunk H gate에 추가했다.

Coverage:

- 판정: Pass.
- 업데이트: 사용자 요청의 "팀원, 팀장, 사장이 느리거나 지시를 이행하지 않을 때 재촉하는 무기"를 Worker/Lead/Boss별 권한 matrix, L1/L2/L3 escalation, audit event, cooldown으로 반영했다.

Execution:

- 판정: Conditional Pass.
- 업데이트: P1에서 `nudge-escalation-policy.md`를 먼저 문서화하고, P4.1에서 L1 텍스트 재촉부터 구현한다. L2 interrupt는 session ID 기반 API 확인 후로 둔다.

Risk:

- 판정: Conditional Pass.
- 주요 리스크: badclaude식 OS 전역 키 입력의 오작동, 사용자가 느끼는 폭력적/모욕적 UX, Watcher 권한 오염, 세션 선택 오류, audit 누락.
- 완화: session-scoped API, 존중형 문구, 명시 권한 matrix, cooldown, audit log, Watcher 실행 금지.

Readiness:

- 판정: Conditional Go.
- 구현 가능: P1 문서화, L1 텍스트 nudge contract, audit event schema.
- 구현 보류: L2 interrupt, visual whip overlay, sound, Electron/koffi adapter, OS macro.

### 16.5 최종 Gate 업데이트

최종 판정: Conditional Go.

즉시 반영할 플랜 변경:

1. `referense/`를 외부 참고자료 SSOT로 유지한다.
2. badclaude는 runtime dependency가 아니라 `nudge-escalation-policy.md`의 UX/interaction reference로만 사용한다.
3. Worker nudge는 Team Lead, Lead nudge는 Boss, Boss nudge는 JARVIS/User 경로로 제한한다.
4. L1은 비중단 텍스트 재촉으로 허용한다.
5. L2 session interrupt는 cmux session ID 기반 interrupt API가 확인되기 전까지 No-Go다.
6. OS 전역 `Cmd+C`/`Ctrl+C` 키 주입은 No-Go다.

업데이트된 fix-before-build checklist:

1. `validate-config.sh` Python block에 `import os` 추가.
2. runtime surface read path를 `/tmp/cmux-surface-map.json` + `cmux tree --all` 우선으로 이관.
3. P1 문서 6개 생성: `mentor-ontology.md`, `palace-memory-ssot.md`, `jarvis-constitution.md`, `jarvis-capability-targets.md`, `mentor-privacy-policy.md`, `nudge-escalation-policy.md`.
4. `nudge-escalation-policy.md`에는 role matrix, L1/L2/L3, cooldown, audit event, 금지 문구, Watcher 실행 금지, Boss 대상 승인 경로를 반드시 포함한다.
5. L2 interrupt는 cmux session ID 기반 API 검증 전까지 구현하지 않는다.

## 17. 원본 코드/문서 + 2개 레포 + 이미지 1/2 전수 재검증

검증일: 2026-04-11
검증 범위: 원본 프로젝트 코드/문서, `referense/mempalace-main`, `referense/vibe-sunsang-main`, `referense/1.jpeg`, `referense/2.jpeg`.
범위 제외: `referense/badclaude-main`은 16장의 nudge reference로 유지하지만, 사용자가 이번에 지정한 "2가지 레포" 재검증 범위에는 포함하지 않는다.

### 17.1 전수 표면

원본 프로젝트:

- `referense/`와 `.git`을 제외한 전체 파일: 194.
- 원본 code/doc 후보 파일: 183.
- 핵심 표면: `README.md`, `cmux-start/SKILL.md`, `cmux-orchestrator/`, `cmux-watcher/`, `cmux-jarvis/`, `docs/jarvis/`, `tests/`.

2개 참고 레포:

- `referense/mempalace-main`: 134 files.
- `referense/vibe-sunsang-main`: 30 files.
- 두 레포 code/doc 후보 파일: 151.
- 두 레포에는 `.git` 디렉터리가 없으므로 commit 기반 최신성보다 로컬 스냅샷 파일 내용이 우선 근거다.

이미지:

- `referense/1.jpeg`: JPEG 1080x2679, Android EXIF. 시각적으로 "모델의 원리 및 작동 방식"을 다루며 constitutional AI, adaptive thinking, agentic scaffolding, synthetic data/고도화 학습을 설명한다.
- `referense/2.jpeg`: JPEG 1079x2697, Android EXIF. 시각적으로 "모델의 뛰어난 점"을 다루며 cyber security, software engineering, alignment, calibration, visual reasoning을 설명한다.
- 두 이미지는 외부 성능 검증 자료가 아니라 JARVIS constitution/capability target의 제품 원칙 레퍼런스로만 사용한다.

### 17.2 원본 코드/문서 대조 결과

성립하는 주장:

- `/cmux-start`가 컨트롤 타워 workspace 안에 사장(Main), 와쳐(Watcher), 자비스(JARVIS) pane을 만든다는 주장은 `cmux-start/SKILL.md`의 결과물/절차와 맞다.
- Department = workspace(side tab), Team Lead = lead surface, Workers = same workspace panes라는 주장은 `cmux-orchestrator/SKILL.md`의 핵심 구조와 맞다.
- Boss가 팀장에게만 지시하고 팀원 생성/AI 선택/분배는 팀장이 수행한다는 주장은 `cmux-orchestrator/SKILL.md`의 Step 4와 맞다.
- Watcher가 감시/알림만 하고 작업 배정, 코드 수정, surface 생성/해제를 하지 않는다는 주장은 `cmux-watcher/SKILL.md`의 GATE W-9와 맞다.
- JARVIS가 User 직속 참모이자 설정 진화 엔진이라는 주장은 `cmux-jarvis/SKILL.md` 및 `cmux-jarvis/skills/evolution/SKILL.md`와 맞다.
- Watcher가 `/tmp/cmux-surface-map.json`에 departments, team_lead, members, available_tools를 쓰는 구조는 `cmux-watcher/scripts/watcher-scan.py`에 있다.

새로 확인된 충돌:

- `README.md`는 stale surfaces가 제거됐다고 설명하지만, `cmux-orchestrator/config/orchestra-config.json`에는 `surfaces`, `main_surface`, `watcher_surface`, `main_ai`, `auto_synced`가 남아 있다.
- `validate-config.sh`는 `os.path.isfile`을 쓰지만 `import os`가 없어 실제 cmux socket 조건에서 `NameError: name 'os' is not defined`로 실패한다.
- `ai-profile.json`의 저장된 `detected` 값은 `claude`만 true인데, `python3 cmux-orchestrator/scripts/manage-ai-profile.py --list`는 현재 PATH 기준으로 `codex`, `gemini`, `claude`가 설치됨을 보여준다.
- `cmux-watcher/scripts/watcher-scan.py`의 `get_available_tools()`는 저장된 `prof.get("detected")`만 보고 `available_tools.ai_clis`를 구성한다. 따라서 `/cmux-start` 이후 "사용자의 로컬 AI 리스트 확인"은 stale profile 값에 갇힐 수 있다.

결정:

- P0에 `validate-config.sh`의 `import os` 복구를 유지한다.
- P0에 "AI profile detected SSOT 정리"를 추가한다. runtime 판단은 `shutil.which(cli_command)` 또는 `/cmux-config detect` 재실행 결과를 우선하고, stale `detected` 필드만으로 available tools를 확정하지 않는다.
- `orchestra-config.json` runtime fields 제거는 즉시 삭제가 아니라 compat 이관 후 제거로 유지한다.

### 17.3 MemPalace 재검증

성립하는 주장:

- raw verbatim storage 주장은 `README.md`와 `mempalace/searcher.py`, `mempalace/miner.py`와 맞다. `searcher.py`는 ChromaDB `mempalace_drawers`에서 verbatim drawer content를 반환하고, `miner.py`는 "Stores verbatim chunks as drawers. No summaries"를 구현 방향으로 둔다.
- wing/room/hall/tunnel/closet/drawer palace model 주장은 `README.md`와 `mempalace/palace_graph.py`와 맞다. `palace_graph.py`는 rooms를 node로, shared rooms across wings를 tunnel edge로, halls를 edge type으로 사용한다.
- L0/L1/L2/L3 memory stack 주장은 `mempalace/layers.py`와 맞다. L0 identity, L1 essential story, L2 wing/room filtered retrieval, L3 ChromaDB semantic search가 구현되어 있다.
- ChromaDB/MCP 의존성 주장은 `pyproject.toml`과 `mempalace/mcp_server.py`와 맞다. `chromadb>=0.5.0,<0.7`가 필수 dependency이고 MCP server는 read/write tools와 write-ahead log를 가진다.
- AAAK를 기본 저장 포맷으로 흡수하지 않는 결정은 유지한다. README가 AAAK를 experimental/lossy로 설명하고, raw mode가 storage default라고 명시한다.

새로 확인된 리스크:

- MemPalace 전체 test suite는 현재 환경에서 `chromadb` 미설치로 실행되지 않는다. 따라서 외부 레포 런타임 품질은 검증 불가다.
- MemPalace는 raw verbatim 저장과 MCP write tool을 강하게 제공하므로, cmux에 그대로 붙이면 privacy, retention, prompt injection, memory poisoning 리스크가 커진다.

결정:

- P1/P2에서는 MemPalace를 vendoring하지 않고 `palace-memory-ssot.md`와 local JSONL/SQLite substrate 설계로 먼저 흡수한다.
- raw drawer 저장은 opt-in, retention, redaction, export/delete 정책 전까지 구현하지 않는다.
- MCP/ChromaDB adapter는 Phase 3 이후 optional adapter로만 검토한다.

### 17.4 vibe-sunsang 재검증

성립하는 주장:

- 6축 DECOMP/VERIFY/ORCH/FAIL/CTX/META 흡수는 `README.md`, `agents/growth-analyst.md`, `skills/*/growth-metrics.md`와 맞다.
- Builder/Explorer/Designer/Operator workspace type과 유형별 가중치 흡수는 `agents/growth-analyst.md`와 맞다.
- 7단계, 0.5 단위, 내부 소수점 2자리, Fit Score, gate 조건, 최근 5개 세션 중 3개 이상 원칙은 `agents/growth-analyst.md`와 맞다.
- TIMELINE/weekly growth report 패턴은 `README.md`, `agents/growth-analyst.md`, `references/CLAUDE-MD-TEMPLATE.md`와 맞다.

새로 확인된 리스크:

- `referense/vibe-sunsang-main/scripts/convert_sessions.py --help`는 현재 Python 3.9.6에서 `Path | None` annotation 평가 때문에 `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`로 실패한다.
- `python3 -m py_compile`은 이 런타임 annotation 오류를 잡지 못했다. 따라서 단순 문법 검증만으로는 vibe-sunsang script runtime compatibility를 보장할 수 없다.
- vibe-sunsang의 user-facing 레벨명/성장 언어를 그대로 쓰면 cmux가 사용자를 평가하는 제품처럼 보일 수 있다.

결정:

- vibe-sunsang은 그대로 실행 의존성으로 흡수하지 않고 Mentor Ontology로만 흡수한다.
- cmux 구현 시 Python 3.9 호환성을 유지하려면 `Path | None` 같은 런타임 평가 annotation을 쓰지 않거나 `from __future__ import annotations`를 적용한다.
- user-facing 용어는 `Harness Level` 또는 "AI 협업 하네스 개선 신호"로 변환하고, vibe-sunsang의 레벨명은 내부 ontology alias로만 유지한다.

### 17.5 이미지 1/2 재검증

검증 결과:

- `referense/1.jpeg`의 문구는 JARVIS constitution에 반영할 수 있다. 변환: constitutional AI -> Iron Law/SSOT/SRP, adaptive thinking -> task decomposition/failure recovery, agentic scaffolding -> Boss-TeamLead-Worker scaffold, synthetic data/self-play -> simulation fixture/self-play review.
- `referense/2.jpeg`의 문구는 JARVIS capability target에 반영할 수 있다. 변환: cyber security -> secret/path/permission gate, software engineering -> tests/typecheck/build evidence, alignment -> user approval/scope lock, calibration -> confidence/"검증 불가", visual reasoning -> Watcher/Eagle/OCR/screenshot-based surface state support.

주의:

- 이미지 문구의 "Claude Mythos Preview" 또는 성능 우위 표현은 검증된 외부 사실로 주장하지 않는다.
- 이미지 기반 목표는 JARVIS 품질 기준과 acceptance criteria로만 사용한다.

### 17.6 실행 검증

실행한 검증:

- 원본 프로젝트 Python: `find cmux-orchestrator cmux-watcher cmux-jarvis tests -name '*.py' -print0 | xargs -0 python3 -m py_compile` 통과.
- 원본 프로젝트 shell: `find cmux-orchestrator cmux-watcher cmux-jarvis cmux-start -name '*.sh' -print0 | xargs -0 bash -n` 통과.
- 원본 프로젝트 tests: `python3 -m pytest tests` -> 14 passed.
- 실제 cmux socket 조건: `bash cmux-orchestrator/scripts/validate-config.sh` -> 실패. `NameError: name 'os' is not defined`.
- 로컬 AI 확인: `python3 cmux-orchestrator/scripts/manage-ai-profile.py --list` -> `codex`, `gemini`, `claude`는 PATH 기준 Yes, `minimax`, `glm`은 No.
- 두 참고 레포 Python 문법: `find referense/mempalace-main referense/vibe-sunsang-main -name '*.py' -print0 | xargs -0 python3 -m py_compile` 통과.
- 두 참고 레포 shell 문법: `find referense/mempalace-main referense/vibe-sunsang-main -name '*.sh' -print0 | xargs -0 bash -n` 통과.
- MemPalace tests: `python3 -m pytest tests` in `referense/mempalace-main` -> 실패. `ModuleNotFoundError: No module named 'chromadb'`.
- vibe-sunsang script smoke: `python3 referense/vibe-sunsang-main/scripts/convert_sessions.py --help` -> 실패. Python 3.9.6에서 `Path | None` annotation 평가 오류.
- 이미지 확인: `file referense/1.jpeg referense/2.jpeg` 및 실제 이미지 열람 완료.

### 17.7 Cyclic Review 업데이트

SSOT:

- Conditional Pass. `referense/`를 외부 근거 SSOT로 둔 결정은 유지한다.
- 추가 차단: local AI availability SSOT가 `ai-profile.json.detected`, `shutil.which`, Watcher `available_tools` 사이에서 갈라진다.

SRP:

- Pass. Boss/Team Lead/Watcher/JARVIS 역할 경계는 원본 문서와 대체로 일치한다.
- 주의: Watcher는 계속 evidence/report만 해야 하며, nudge 실행권을 갖지 않는다.

FSD/도메인 경계:

- Pass. 프로젝트는 FSD가 아니라 role/domain/module boundary를 쓴다.
- 변경 없음: Orchestrator, Watcher, JARVIS, docs, tests 경계를 유지한다.

Architect:

- Conditional Pass. `/tmp/cmux-surface-map.json`의 departments 구조는 Watcher가 생성하고 Orchestrator가 소비하는 방식으로 정합성이 있다.
- 차단: `validate-config.sh` failure와 stale AI profile detected field 때문에 bootstrap/runtime 검증이 완전히 닫히지 않는다.

Edge Cases:

- Conditional Pass. 새로 추가된 edge: stale AI detection, Python 3.9 annotation runtime failure, missing ChromaDB, screenshot/image fact overclaim.

Coverage:

- Pass. 원본 프로젝트, 2개 레포, 이미지 1/2의 핵심 주장은 플랜의 Chunk A~H와 P0~P6에 매핑되어 있다.

Execution:

- Conditional Pass. P0 순서를 수정한다: `validate-config.sh` 복구와 AI profile detected SSOT 정리를 먼저 처리한 뒤 Mentor/Memory/Nudge 문서화로 간다.

Risk:

- Conditional Pass. 가장 큰 리스크는 "좋은 외부 레포를 그대로 붙이는 것"이 아니라 "cmux의 runtime SSOT와 사용자 로컬 AI 감지 SSOT가 닫히기 전 AGI/Mentor 기능을 올리는 것"이다.

Readiness:

- 최종 판정: Conditional Go.
- 즉시 가능: P0 버그 수정, P1 문서화.
- 보류: raw memory 저장, ChromaDB/MCP adapter, vibe-sunsang script 직접 실행 의존, L2 session interrupt.

### 17.8 최종 업데이트 체크리스트

1. `validate-config.sh`에 `import os`를 추가하고 no-cmux/sandbox/cmux-socket 세 경우의 JSON report를 고정한다.
2. `ai-profile.json.detected`를 runtime truth로 쓰지 않도록 `watcher-scan.py:get_available_tools()`를 `shutil.which(cli_command)` 또는 `manage-ai-profile.py --detect` 결과 우선으로 바꾼다.
3. `orchestra-config.json`의 runtime fields는 compat 이관 후 제거한다.
4. P1 문서 6개를 작성한다: `mentor-ontology.md`, `palace-memory-ssot.md`, `jarvis-constitution.md`, `jarvis-capability-targets.md`, `mentor-privacy-policy.md`, `nudge-escalation-policy.md`.
5. vibe-sunsang 흡수 구현 시 Python 3.9 호환 annotation 정책을 정한다.
6. MemPalace 흡수 구현 시 `chromadb`/MCP는 optional adapter로 두고 기본 storage는 local JSONL/SQLite로 시작한다.
7. 이미지 1/2는 제품 원칙/품질 목표로만 사용하고 외부 성능 사실로 주장하지 않는다.
