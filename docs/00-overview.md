# cmux orchestrator + watcher pack — Documentation Overview

> 프로젝트 전체 문서의 네비게이션 허브. 각 문서는 SSOT/SRP 원칙에 따라 정확히 1곳에서만 정의된다.

## Documentation Structure

```
docs/
├── 00-overview.md                 ← 이 파일 (프로젝트 개요 + 문서 맵)
├── 01-architecture/               ← 시스템 아키텍처 (SSOT)
├── 02-jarvis/                     ← JARVIS Evolution + Mentor Lane
├── 03-operations/                 ← 운영 가이드
├── 04-development/                ← 개발 참조
├── 05-research/                   ← 리서치 아카이브
└── 99-archive/                    ← deprecated 문서 보존
```

## 01-architecture — 시스템 아키텍처

| 문서 | 책임 |
|------|------|
| [system-overview.md](01-architecture/system-overview.md) | 3계층 구조, 데이터 흐름, 상태 머신 |
| [orchestrator-architecture.md](01-architecture/orchestrator-architecture.md) | Boss: 디스패치, 수집, 커밋 |
| [watcher-architecture.md](01-architecture/watcher-architecture.md) | 4계층 모니터링 (Eagle/OCR/VisionDiff/Pipe-pane) |
| [hook-enforcement.md](01-architecture/hook-enforcement.md) | 31 hooks, 4-tier 강제, gate matrix |
| [security.md](01-architecture/security.md) | 8대 보안 메커니즘 |
| [principles.md](01-architecture/principles.md) | JARVIS 7대 아키텍처 원칙 |
| [cmux-start-integration.md](01-architecture/cmux-start-integration.md) | cmux-start 수정 + config.json 스키마 |

## 02-jarvis — JARVIS Evolution + Mentor

| 문서 | 책임 |
|------|------|
| [constitution.md](02-jarvis/constitution.md) | 정체성, Constitutional Principles, Iron Laws 참조, 공통 정책 |
| [evolution-pipeline.md](02-jarvis/evolution-pipeline.md) | 11단계 진화 파이프라인, 3트리거, 3레인 |
| [mentor-lane.md](02-jarvis/mentor-lane.md) | Mentor Lane 역할, Evolution 구분, Context Injection |
| [mentor-ontology.md](02-jarvis/mentor-ontology.md) | 6축(DECOMP/VERIFY/ORCH/FAIL/CTX/META), Harness Level, Fit Score |
| [capability-targets.md](02-jarvis/capability-targets.md) | 5대 품질 목표 (Security/Engineering/Alignment/Calibration/Visual) |
| [nudge-escalation.md](02-jarvis/nudge-escalation.md) | 3단계 재촉, 권한 매트릭스, Cooldown, Audit |
| [palace-memory.md](02-jarvis/palace-memory.md) | Palace Memory L0~L3, Signal/Drawer/Triple 스키마 |
| [privacy-policy.md](02-jarvis/privacy-policy.md) | 수집/저장/Retention/Redaction/사용자 권리 |
| [feedback-loop.md](02-jarvis/feedback-loop.md) | 4채널 피드백, 3유형 처리, 옵티미스틱 승격 |
| [worker-protocol.md](02-jarvis/worker-protocol.md) | Worker 통신, STATUS, Circuit Breaker |
| [iron-laws.md](02-jarvis/iron-laws.md) | 3 Iron Laws + evidence 스키마 |
| [red-flags.md](02-jarvis/red-flags.md) | 8 Red Flags 테이블 |

## 03-operations — 운영 가이드

| 문서 | 책임 |
|------|------|
| [quick-start.md](03-operations/quick-start.md) | 설치, 시작, 9개 명령어, 종료 |
| [ai-profiles.md](03-operations/ai-profiles.md) | 6 AI 모델, 자동 감지, 프로파일 관리 |
| [troubleshooting.md](03-operations/troubleshooting.md) | 알려진 이슈 + 복구 절차 |
| [cross-platform.md](03-operations/cross-platform.md) | macOS/Linux/WSL 호환, cmux_compat |

## 04-development — 개발 참조

| 문서 | 책임 |
|------|------|
| [phase-roadmap.md](04-development/phase-roadmap.md) | Phase 1/2/3 범위 + 파일 목록 |
| [directory-structure.md](04-development/directory-structure.md) | 디렉터리 구조 (Obsidian+로컬+스킬) |
| [skill-md-spec.md](04-development/skill-md-spec.md) | SKILL.md 2단계 구조 + additionalContext |
| [test-guide.md](04-development/test-guide.md) | 58 tests 구조, 실행 방법, 패턴 |

## 05-research — 리서치 아카이브

| 문서 | 책임 |
|------|------|
| [repo-summary.md](05-research/repo-summary.md) | 20개 레포 조사 요약 |
| [claude-source-findings.md](05-research/claude-source-findings.md) | Claude Code 소스 검증 S1~S12 |
| [mentor-plan-archive.md](05-research/mentor-plan-archive.md) | AGI Mentor 통합 계획 핵심 요약 |

## 99-archive — deprecated 문서

| 문서 | 사유 |
|------|------|
| JARVIS-PLAN-FULL.md | 세분화 완료 후 deprecated |
| CMUX-AGI-MENTOR-INTEGRATED-PLAN.md | P0~P6 구현 완료 후 아카이브 |
| reviews/ | 리뷰 이력 보존 |
| simulations/ | 시뮬레이션 기록 보존 |
| knowledge-raw/ | 9개 리서치 원본 보존 |

## Changelog

[CHANGELOG.md](CHANGELOG.md) — 전체 변경 이력

## 참조 문서 위치 (이동하지 않음)

스킬 내부 참조 문서는 `cmux-*/references/`에 유지한다. 이동하면 스킬 로딩이 깨진다.

| 위치 | 파일 수 | 용도 |
|------|---------|------|
| `cmux-orchestrator/references/` | 16 | dispatch, gate, recovery 패턴 |
| `cmux-watcher/references/` | 4 | 모니터링 프로토콜 |
| `cmux-jarvis/references/` | 7 | Iron Laws, Red Flags, 메트릭 (런타임 참조) |
