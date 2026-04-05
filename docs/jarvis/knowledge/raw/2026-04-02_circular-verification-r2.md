# JARVIS 계획 순환검증 2차 (5차 전체)

**방법:** 1차 순환검증(CV-01~09) 해결안이 새로운 문제를 만들지 않는지 재검증
**날짜:** 2026-04-02

---

## 재검증 1: CV-01 migrate-vault + 2모드 아키텍처

**해결안:** `jarvis-maintenance.sh migrate-vault <new-path>`
**순환 체크:**
- 마이그레이션 중 JARVIS가 파일에 접근하면? (진화 진행 중 마이그레이션)
  → CURRENT_LOCK이 있으면 마이그레이션 거부 (진화 완료 후만 허용) ✓
- FTS5 재구축 실패 시?
  → grep 폴백 존재 (FIX-09) → 검색 성능 저하만, 기능 손실 없음 ✓
**결과: 신규 이슈 없음.**

---

## 재검증 2: CV-02 Worker 마커 파일

**해결안:** `/tmp/cmux-jarvis-worker-{PID}` 마커 + trap EXIT 삭제
**순환 체크:**
- Worker 크래시(SIGKILL) 시 trap 실행 안 됨 → 마커 파일 잔존
  → 다른 프로세스가 같은 PID 재사용 → 일반 프로세스가 Worker로 오인?
  → hook은 `$PPID` 체크 → Claude Code 세션의 PPID ≠ 일반 프로세스 PPID
  → **PID 재사용 확률 매우 낮고, 오인되어도 evolutions/ 내부만 쓰기 허용 = 무해** ✓
- 마커 파일 정리: JARVIS 재시작 시 `/tmp/cmux-jarvis-worker-*` 모두 삭제 추가
**결과: 신규 이슈 없음. 재시작 시 정리 로직만 추가 권장 (사소).**

---

## 재검증 3: CV-03 비동기 승인 대기

**해결안:** 진화 상태 "awaiting_approval" + 모니터링 계속
**순환 체크:**
- JARVIS가 모니터링 중 새 문제 감지 → 큐에 추가 → 큐 5건 도달
  → 기존 승인 대기 진화가 큐 1건 차지? → 아님, awaiting은 큐가 아니라 진행 중 상태
  → CURRENT_LOCK은 ④에서만 생성 → ③ 대기 중에는 LOCK 없음
  → **새 진화 감지 → 큐 추가 가능** ✓
- 사용자가 1차 승인 응답 전에 2차 승인 대기 진화가 있을 수 있나?
  → 1차는 LOCK 전 → 2차는 LOCK 후 → 동시에 두 진화가 승인 대기 가능
  → 직렬 실행 원칙: CURRENT_LOCK 없는 것만 1차 승인 가능 → **동시 대기 불가** ✓
**결과: 신규 이슈 없음.**

---

## 재검증 4: CV-04 /freeze warn 모드

**해결안:** 기본 warn, deny는 CRITICAL만
**순환 체크:**
- 사용자가 warn에서 "계속" 선택 → settings.json 변경됨 → 진화 반영 시 충돌
  → JSON Patch가 변경 키만 적용 → 사용자가 변경한 다른 키는 보존 ✓
  → **같은 키**를 사용자+진화 둘 다 변경했으면?
  → JSON Patch 충돌 → AskUserQuestion (이미 설계됨: "충돌 키 → 사용자 해결") ✓
**결과: 신규 이슈 없음. 기존 충돌 해결 로직이 커버.**

---

## 재검증 5: CV-05 Worker 제안 = 모든 파일

**해결안:** "모든 변경은 evolutions/ 내부에 제안 파일로 생성"
**순환 체크:**
- hook 파일 변경 제안: `evolutions/evo-001/proposed-hooks/cmux-jarvis-gate.sh`
  → JARVIS가 `hooks/cmux-jarvis-gate.sh`에 복사
  → **경로 매핑 규칙이 필요** — proposed 파일명에서 실제 경로를 어떻게 결정?

**미세 이슈 CV2-01:** 제안 파일 → 실제 경로 매핑 규칙 미정의.
**해결안:** proposed 파일과 함께 매핑 파일 생성:
```json
// evolutions/evo-001/file-mapping.json
{
  "proposed-hooks/cmux-jarvis-gate.sh": "~/.claude/skills/cmux-jarvis/hooks/cmux-jarvis-gate.sh",
  "proposed-settings.json": "~/.claude/settings.json"
}
```
JARVIS가 매핑 파일 읽고 복사 실행.
**심각도:** LOW — 구현 상세.

---

## 재검증 6: CV-06 Phase 1 obsidian-sync 선택적

**해결안:** 모드 A에서 obsidian CLI create/append 수준
**순환 체크:**
- obsidian CLI가 설치되지 않았는데 모드 A인 경우?
  → Obsidian 앱은 있지만 CLI 없음 → 직접 파일 쓰기 폴백 (FIX-09) ✓
- Phase 1에서 obsidian-sync SKILL.md를 만들되, 내용을 최소화?
  → "obsidian CLI create/append + 직접 파일 쓰기 폴백" 정도면 20줄 미만 ✓
**결과: 신규 이슈 없음.**

---

## 재검증 7: CV-07 verify-plugins 플러그형

**해결안:** `verify-plugins/settings-change.sh` 등 유형별
**순환 체크:**
- 플러그인 파일 없는 유형 → "기본 검증 + 경고" → 검증 부족한 진화가 통과?
  → 기본 검증 = JSON 유효성 + checksum → 최소 안전성 보장 ✓
  → 사용자가 ⑩에서 최종 판단 (Iron Law #1) → 인간 게이트 존재 ✓
- 플러그인 자체의 버그?
  → 사전 정의(cmux 패키지 포함) → 테스트 후 배포 → cmux 업데이트로 수정 ✓
**결과: 신규 이슈 없음.**

---

## 재검증 8: CV-08 큐 우선순위 + CRITICAL 예외

**해결안:** CRITICAL은 절대 자동 폐기 안 함 (큐 6건째 허용)
**순환 체크:**
- CRITICAL이 계속 쌓이면? CRITICAL 10건 → 큐 무한 성장?
  → CRITICAL은 사용자 즉시 알림 필요 → 승인 타임아웃 30분 + 모니터링 계속
  → 연속 CRITICAL → MAX_CONSECUTIVE=3 → 4번째에서 사용자 에스컬레이션 ✓
  → 에스컬레이션 = "연속 CRITICAL 발생 중. 근본 원인 조사 필요." → **진화 중단, 사용자 개입**
**결과: 신규 이슈 없음. 기존 안전장치(MAX_CONSECUTIVE)가 커버.**

---

## 재검증 9: CV-09 evolution_type 유형별 검증

**해결안:** settings_change → expected_outcomes, 나머지 → TDD
**순환 체크:**
- evolution_type을 Worker가 설정 → Worker가 잘못 분류하면?
  → hook_change를 settings_change로 분류 → TDD 면제 → 위험
  → JARVIS가 ⑤ 계획 수립 시 evolution_type 결정 → Worker가 변경 불가
  → **계획 문서에 evolution_type 포함** → Worker는 복사만 ✓
- 복합 진화 (설정 + hook 동시 변경)?
  → evolution_type = "mixed" → **가장 엄격한 기준 적용** (TDD 필수)

**미세 이슈 CV2-02:** 복합 진화 유형 미정의.
**해결안:** evolution_type에 "mixed" 추가. mixed = 모든 유형의 검증 적용 (가장 엄격).
**심각도:** LOW — 구현 상세.

---

## 2차 순환검증 결과

| # | 검증 대상 | 결과 | 신규 이슈 |
|---|----------|------|----------|
| CV-01 | migrate-vault | ✅ 문제 없음 | - |
| CV-02 | Worker 마커 파일 | ✅ 문제 없음 | 재시작 시 정리 (사소) |
| CV-03 | 비동기 승인 | ✅ 문제 없음 | - |
| CV-04 | /freeze warn | ✅ 문제 없음 | 기존 충돌 해결이 커버 |
| CV-05 | Worker 제안 전체 | ⚠️ 미세 이슈 | **CV2-01:** file-mapping.json 필요 (LOW) |
| CV-06 | Phase 1 obsidian | ✅ 문제 없음 | - |
| CV-07 | verify-plugins | ✅ 문제 없음 | - |
| CV-08 | 큐 CRITICAL 예외 | ✅ 문제 없음 | MAX_CONSECUTIVE가 커버 |
| CV-09 | evolution_type | ⚠️ 미세 이슈 | **CV2-02:** mixed 유형 추가 (LOW) |

**신규 이슈: LOW 2건만.** 순환이 수렴하고 있음.

### CV2-01: file-mapping.json
Worker가 제안 파일 생성 시 매핑 파일도 함께 생성:
```json
{"proposed-hooks/gate.sh": "~/.claude/skills/cmux-jarvis/hooks/cmux-jarvis-gate.sh"}
```

### CV2-02: mixed evolution_type
```
evolution_type: "settings_change" | "hook_change" | "skill_change" | "code_change" | "mixed"
mixed → 모든 유형의 검증 적용 (TDD + expected_outcomes + 플러그인 전부)
```

**판정: 순환 수렴 확인. 추가 순환검증 불필요.**
