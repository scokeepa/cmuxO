# JARVIS Plan — 문서 네비게이션

> 기존 JARVIS-PLAN-FULL.md(1,376줄)를 SRP/SSOT 기반으로 세분화.
> 각 문서는 **하나의 책임**만 담당. 정보 중복 없음.

## 아키텍처 (정본)
| 문서 | 책임 | 줄 수 |
|------|------|-------|
| [architecture/principles.md](architecture/principles.md) | 핵심 원칙 7개 (정본+GATE+안전+Worker+2모드+승인+검증) | ~80 |
| [architecture/directory-structure.md](architecture/directory-structure.md) | 디렉토리 구조 (Obsidian+로컬+스킬) | ~60 |
| [architecture/phase-roadmap.md](architecture/phase-roadmap.md) | Phase 1/2/3 범위 + 파일 목록 | ~50 |
| [architecture/cmux-start-integration.md](architecture/cmux-start-integration.md) | cmux-start 수정 상세 + config.json 스키마 | ~60 |
| [architecture/mentor-lane.md](architecture/mentor-lane.md) | Mentor Lane 역할 정의 + Evolution Lane 구분 + Context Injection 정책 | ~90 |
| [architecture/mentor-ontology.md](architecture/mentor-ontology.md) | 6축 기술 차원 + Harness Level + Fit Score + 안티패턴 (vibe-sunsang 흡수) | ~140 |
| [architecture/jarvis-constitution.md](architecture/jarvis-constitution.md) | JARVIS 정체성 + Constitutional Principles + 공통 정책 (1.jpeg 흡수) | ~80 |
| [architecture/jarvis-capability-targets.md](architecture/jarvis-capability-targets.md) | 5대 품질 목표 + Phase별 매핑 + Acceptance Criteria (2.jpeg 흡수) | ~90 |
| [architecture/nudge-escalation-policy.md](architecture/nudge-escalation-policy.md) | 3단계 재촉 + 권한 매트릭스 + Cooldown + Audit Schema (badclaude 흡수) | ~130 |
| [architecture/mentor-privacy-policy.md](architecture/mentor-privacy-policy.md) | 데이터 수집/저장/Retention/Redaction/사용자 권리 | ~110 |
| [architecture/palace-memory-ssot.md](architecture/palace-memory-ssot.md) | Palace Memory 구조 + 4계층 로딩 + Signal/Drawer/Triple 스키마 | ~140 |

## 파이프라인 (정본)
| 문서 | 책임 |
|------|------|
| [pipeline/evolution-pipeline.md](pipeline/evolution-pipeline.md) | 진화 11단계 파이프라인 + 3트리거 + 3레인 |
| [pipeline/feedback-loop.md](pipeline/feedback-loop.md) | 피드백 4채널 + 3유형 처리 + 옵티미스틱 승격 |
| [pipeline/worker-protocol.md](pipeline/worker-protocol.md) | Worker 통신 + STATUS + 완료 감지 + Circuit Breaker |

## Hook (정본)
| 문서 | 책임 |
|------|------|
| [hooks/hook-map.md](hooks/hook-map.md) | 7 hook 등록 맵 + matcher + 타임아웃 |
| [hooks/gate-logic.md](hooks/gate-logic.md) | gate.sh 전체 로직 (GATE+Worker+Bash+/freeze) |
| [hooks/session-lifecycle.md](hooks/session-lifecycle.md) | session-start + file-changed + pre/post-compact |

## 스킬 (정본)
| 문서 | 책임 |
|------|------|
| [skills/skill-md-spec.md](skills/skill-md-spec.md) | SKILL.md 2단계 구조 + additionalContext |
| [skills/iron-laws.md](skills/iron-laws.md) | 3 Iron Laws + evidence 스키마 + 검증 로직 |
| [skills/red-flags.md](skills/red-flags.md) | Red Flags 테이블 (SSOT 단일 정의) |

## 연구 (참조)
| 문서 | 책임 |
|------|------|
| [research/repo-summary.md](research/repo-summary.md) | 20개 레포 조사 요약 + 도입 패턴 |
| [research/claude-source-findings.md](research/claude-source-findings.md) | Claude Code 소스 검증 S1~S12 |

## 리뷰 (이력)
| 문서 | 책임 |
|------|------|
| [reviews/review-history.md](reviews/review-history.md) | 전체 리뷰 이력 (1~5차 + 순환검증 + Iron Law 감사) |
| [reviews/resolved-issues.md](reviews/resolved-issues.md) | 해결된 100+ 이슈 목록 |
| [reviews/segmented-review-2026-04-03.md](reviews/segmented-review-2026-04-03.md) | 세분화 문서 재검토 (엣지케이스 9건) |

## 시뮬레이션 (검증)
| 문서 | 책임 |
|------|------|
| [simulations/v6-stall5.md](simulations/v6-stall5.md) | 최신 시뮬레이션 (STALL 5개 실측) |
