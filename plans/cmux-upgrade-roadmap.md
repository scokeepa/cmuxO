# cmuxO Upgrade Roadmap (Post Tier A-E Migration)

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 전체 로드맵 인덱스

---

## 0. 선행 완료 확인

| 항목 | 상태 | 근거 |
|------|------|------|
| Tier A+B+C hook schema migration | ✅ DONE | PR #8 merged 2026-04-19 |
| Tier D hook schema | ✅ DONE | PR #9 merged 2026-04-19 |
| Tier E hook schema | ✅ DONE | PR #10 merged 2026-04-19 |
| hook_output.py/sh helpers | ✅ DONE | `cmux-orchestrator/scripts/hook_output.{py,sh}` 존재 |
| 레거시 `"decision":"allow"/"approve"` 잔존 | 0개 | grep 결과 0 |

→ **Phase 1.1 "helper 추출"은 이미 완료됨**. Phase 1의 남은 3개 항목부터 시작.

## 1. Phase 1 — 기반 보강 (남은 3개)

| # | 항목 | 상세 플랜 | 예상 PR 크기 |
|---|------|-----------|--------------|
| 1.2 | GATE W-9 Send-Guard Hook | [phase1-2](cmux-upgrade-phase1-2-gate-w9-send-guard.md) | S (신규 훅 1개 + registration) |
| 1.3 | ANE CLI Path Abstraction | [phase1-3](cmux-upgrade-phase1-3-ane-path-abstraction.md) | S (helper 2개 + 4파일 리팩터) |
| 1.4 | Rate-Limit Pool Implement + GC | [phase1-4](cmux-upgrade-phase1-4-rate-limit-pool.md) | M (신규 모듈 + 3곳 연결) |

순서: **1.2 → 1.3 → 1.4** (독립적 — 병렬 가능하나 리뷰 부담 분리 위해 순차).

## 2. Phase 2 — 가시성 & 품질 (순서대로)

| # | 항목 | 상세 플랜 | 선행 |
|---|------|-----------|------|
| 2.1 | Watcher Progressive Disclosure | [phase2-1](cmux-upgrade-phase2-1-progressive-disclosure.md) | - |
| 2.2 | Per-Agent Token/Cache Observability | [phase2-2](cmux-upgrade-phase2-2-token-observability.md) | 2.1 (baseline 측정) |
| 2.3 | Ledger-Based Boss State | [phase2-3](cmux-upgrade-phase2-3-ledger-state.md) | - |
| 2.4 | JARVIS Anti-Rationalization Tables | [phase2-4](cmux-upgrade-phase2-4-anti-rationalization.md) | 2.3 (ledger 소비) |

사용자 지시: "Phase2 범위 동의는 순서대로 해" → **2.1 → 2.2 → 2.3 → 2.4** 엄수.

## 3. Phase 3 — 영구 학습 (선정안)

| # | 항목 | 상세 플랜 | 선행 |
|---|------|-----------|------|
| 3.1 | Persistent Agent Memory (agentmemory) | [phase3-1](cmux-upgrade-phase3-1-agentmemory.md) | Phase 2 전체 |

선택 근거: §9 of phase3-1 문서. Phase 2 데이터 소스를 전부 흡수하는 집약점.

## 4. 진행 절차

각 플랜 파일은 다음을 포함:
1. 문제/근거
2. 설계
3. 5관점 검증 (SSOT/SRP/엣지케이스/아키텍트/Iron Law)
4. 코드 시뮬레이션 (테스트 케이스 + 실행 결과)
5. 구현 절차 + DoD + 리스크

구현은 **항목별 개별 PR** — 리뷰 용이성 & rollback 용이.

## 5. 검증되지 않은 가정 (주의)

- Tier A-E 100% 완료 판단은 scokeepa/cmuxO의 CHANGELOG.md + PR 상태 기반 (커밋 SHA 직접 grep 미수행) — 실제 코드 inspect로 한번 더 검증 권장
- agentmemory 업스트림 API 안정성 — version pin 필수 (phase3-1 §8)
- 각 플랜의 "시뮬레이션 실행 결과"는 모두 **미실행** — 구현 착수 시 필수

## 6. 다음 행동

사용자 승인 후:
1. Phase 1.2 프로토타입 시뮬레이션 → phase1-2 §5.2 업데이트
2. Phase 1.2 PR 제출
3. merge 후 Phase 1.3 진행
4. ...

각 PR별 verification report는 `plans/verification-report-template.md`를 복사하여 작성.
