# JARVIS Phase 로드맵

## Phase 1 — 코어 (현재)
**역할:** 설정 진화 엔진 + 모니터링
**모드:** B (로컬 전용), A 선택적
**파이프라인:** 핵심 6단계 (TDD/검증/A·B는 수동)

### 구현 파일 (22 신규 + 2 수정 = 24)
**스킬 3** + **hook 6** + **스크립트 5(+3 플러그인)** + **참조 7** + **에이전트 1** + **activation 1** + **수정 2(install.sh, cmux-start)**

### 구현 순서 (6 Step)
1. config.json + references/ 6파일
2. gate.sh + settings-backup.sh (GATE)
3. session-start + file-changed (트리거)
4. SKILL.md + evolution + visualization
5. jarvis-evolution.sh + verify.sh + worker.md
6. cmux-start 수정 + install.sh

## Phase 2 — 확장
- 지식 관리 (FTS5 + Progressive Disclosure)
- 시각화 (Excalidraw/Mermaid/Canvas)
- 하네스 추천 (harness-100)
- 능동적 학습 (GitHub/Docs 탐색)
- 예산 관리 (Budget enforcement)
- Worker 출력 압축 (300줄+)
- GATE 외부 config 로드
- 3계층 메모리 + GC
- QUARANTINE 판정

## Phase 3 — 고급
- Basic Memory MCP (하이브리드 검색)
- Obsidian 전체 연동 (Bases + Canvas)
- PermissionRequest 자동 처리
- CLAUDE_ENV_FILE 동적 환경변수
