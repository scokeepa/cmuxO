# JARVIS 디렉토리 구조

> 정본. 디렉토리/파일 위치를 참조할 때 이 파일 링크.

## 1차: Obsidian 볼트 = 정본 (모드 A)
```
{OBSIDIAN_VAULT}/JARVIS/
├── Evolutions/                   # 진화 히스토리
│   ├── evo-001.md                # wikilink + properties + callouts
│   └── Evolution Dashboard.base  # Obsidian Bases 대시보드
├── Knowledge/                    # 학습 지식 (출처별)
│   ├── github/ │ docs/ │ source-code/
│   └── Knowledge Index.base
├── Backups/                      # 설정 스냅샷 (3세대 유지)
├── Daily/                        # Daily Note 연동
└── JARVIS Dashboard.md           # 전체 현황
```

## 2차: 로컬 캐시 + 실행 상태
```
~/.claude/cmux-jarvis/
├── config.json                   # 볼트 경로, 예산, 제한
├── metric-dictionary.json        # 5개 메트릭 + 임계값 (SSOT)
├── budget-tracker.json           # 예산 추적
├── evolution-queue.json          # 진화 대기열 (최대 5건)
├── deferred-issues.json          # 보류된 이슈 + 예측 A/B
├── .evolution-counter            # 연속/일일 카운터
├── .evolution-lock               # CURRENT_LOCK (TTL 60분)
├── .session-context-cache.json   # SessionStart inject 캐시
├── AGENDA_LOG.md                 # 비동기 의사결정 보드
├── evolutions/                   # 진화 실행 상태
│   └── evo-001/
│       ├── STATUS                # {phase, status, evolution_type, tests...}
│       ├── nav.md
│       ├── 01-detection.md ~ 09-result.md
│       ├── proposed-settings.json
│       ├── file-mapping.json
│       ├── evidence.json
│       └── backup/
├── knowledge/raw/                # 연구/학습 원본
└── plan/                         # 이 세분화 문서들
```

## 3차: 스킬 + hook (cmux 패키지)
```
~/.claude/skills/cmux-jarvis/
├── SKILL.md                      # 10줄 최소 (SR-03)
├── skills/
│   ├── evolution/SKILL.md
│   ├── knowledge/SKILL.md
│   ├── obsidian-sync/SKILL.md
│   └── visualization/SKILL.md
├── agents/
│   └── evolution-worker.md
├── hooks/                        # 7 hook
│   ├── cmux-jarvis-gate.sh       # PreToolUse Edit|Write|Bash
│   ├── cmux-settings-backup.sh   # ConfigChange
│   ├── jarvis-session-start.sh   # SessionStart
│   ├── jarvis-file-changed.sh    # FileChanged (디바운싱 60초)
│   ├── jarvis-pre-compact.sh     # PreCompact
│   └── jarvis-post-compact.sh    # PostCompact
├── scripts/
│   ├── jarvis-evolution.sh
│   ├── jarvis-verify.sh
│   ├── verify-plugins/
│   └── jarvis-maintenance.sh
└── references/                   # SSOT 정의 파일
    ├── metric-dictionary.json
    ├── gate-5level.md
    ├── scope-lock-template.md
    ├── red-flags.md
    ├── iron-laws.md
    └── test-templates.md
```
