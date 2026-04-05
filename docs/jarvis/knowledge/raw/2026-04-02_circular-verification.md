# JARVIS 계획 순환검증 (4차)

**방법:** 각 해결안이 새로운 문제를 만들지 않는지 역방향 검증
**날짜:** 2026-04-02

---

## 검증 1: 단일 정본 (FIX-01) → 2모드 (FATAL-A3) 순환

**FIX-01:** "Obsidian 마크다운 = 정본"
**FATAL-A3 수정:** "모드 B (Obsidian 없음): ~/.claude/cmux-jarvis/ 마크다운 = 정본"

**순환 체크:**
- 모드 A에서 Obsidian에 쓴 문서가 모드 B로 전환 시 어떻게 되나?
  → config.json에서 obsidian_vault_path 제거 → 정본 위치가 바뀜 → **기존 문서 고아 발생**
- 모드 B에서 모드 A로 전환 시?
  → 로컬 마크다운을 Obsidian 볼트로 이동해야 함 → **마이그레이션 절차 미정의**

**신규 이슈 CV-01:** 모드 전환 시 마이그레이션 절차가 없다.
**해결안:** `jarvis-maintenance.sh migrate-vault <new-path>` 명령 추가.
정본 마크다운 파일을 새 경로로 이동 + config.json 업데이트 + FTS5 재구축.
**심각도:** MEDIUM — 모드 전환은 드문 이벤트.

---

## 검증 2: GATE hook (FIX-02) + Worker gate (FIX-04) 순환

**FIX-02:** "cmux-jarvis-gate.sh가 모든 surface에서 실행"
**FIX-04:** "cmux-jarvis-worker-gate.sh가 CMUX_JARVIS_WORKER=true일 때만"

**순환 체크:**
- gate.sh가 전역 → Main/Watcher에서 불필요한 hook 실행 = 성능 오버헤드?
  → hook 내부 첫 줄에서 JARVIS surface 여부 확인 → 아니면 즉시 exit → **오버헤드 무시 가능** (~1ms)
- Worker pane 생성 시 `CMUX_JARVIS_WORKER=true` 환경변수를 누가 설정하나?
  → JARVIS가 `cmux new-pane`으로 Worker 생성 시 설정해야 함
  → `cmux new-pane`이 환경변수 전달을 지원하는가?

**신규 이슈 CV-02:** cmux new-pane이 환경변수 전달을 지원하지 않을 수 있다.
**해결안:** Worker pane 생성 후 첫 명령으로 `export CMUX_JARVIS_WORKER=true` 실행.
또는 Worker 시작 시 `/tmp/cmux-jarvis-worker-{PID}` 마커 파일 생성 → hook에서 파일 존재 체크.
**심각도:** LOW — 구현 시 확인, 대안 존재.

---

## 검증 3: 2단계 승인 (IL1-V1) + 타임아웃 (IL1-V2) 순환

**수정:** 1차 승인 [수립] → 계획 수립 → 2차 승인 [실행]
**타임아웃:** 30분 → 자동 "보류"

**순환 체크:**
- 1차 승인 [수립] → 계획 수립(5분) → 2차 승인 대기 → 타임아웃 30분
  → 총 35분 JARVIS가 하나의 진화에 묶여 있음 → **다른 모니터링 업무 불가**
- 사용자가 1차에서 [수립] → 계획 수립 중 새로운 CRITICAL 문제 감지 → 어떻게?
  → CURRENT_LOCK은 없음 (④에서 생성) → 새 진화 감지는 가능하지만 큐에 추가됨 ✓

**신규 이슈 CV-03:** 2단계 승인으로 진화 소요시간이 길어져 JARVIS 응답성 저하.
**해결안:** 승인 대기 중에도 모니터링은 계속 실행 (비동기).
승인 대기 = JARVIS가 block되는 것이 아니라, 진화 상태가 "awaiting_approval"로 기록.
JARVIS는 다음 사용자 입력까지 모니터링 계속.
**심각도:** LOW — 설계 의도대로 동작.

---

## 검증 4: JSON Patch (FATAL-E1) + /freeze (FIX-03) 순환

**FATAL-E1 수정:** "JSON Patch — 진화가 변경한 키만 적용"
**FIX-03:** "/freeze — 진화 중 외부 settings.json 수정 차단"

**순환 체크:**
- /freeze가 활성화되면 사용자가 settings.json 수정 시 **hook이 deny** 반환
  → 사용자 작업 차단 가능 → 사용자가 긴급히 설정을 바꿔야 하면?
  → 예: AI 모델을 바꿔야 하는데 진화 중이라 deny

**신규 이슈 CV-04:** /freeze가 긴급 설정 변경을 차단한다.
**해결안:** /freeze는 **경고(warn)** 모드, **차단(deny)** 모드 중 선택:
- 기본: warn — "진화 중입니다. 변경하면 3-way merge가 필요합니다. 계속할까요?"
- 사용자가 계속 선택 → 변경 허용 + JARVIS에 알림
- deny는 CRITICAL 진화(시스템 안정성 관련)에만 적용
**심각도:** HIGH — 사용자 자율성 침해 가능. 기본 모드를 warn으로 변경 필요.

---

## 검증 5: Worker 제안만 (FIX-04) + 진화 실행 아키텍처 순환

**FIX-04:** "Worker는 proposed-settings.json만 생성, JARVIS가 적용"

**순환 체크:**
- Worker가 hook/스킬 변경도 제안만 해야 하나?
  → hook 파일 수정 = evolutions/ 외부 쓰기 = **hook deny**
  → 즉, Worker는 설정 뿐 아니라 **모든 코드 변경도 제안만** 가능
  → 이것이 의도인가?
- 진화 대상이 "activation-hook.sh에 새 hook 등록"이면:
  → Worker가 proposed-activation-hook.sh를 evolutions/ 내에 생성
  → JARVIS가 검증 후 실제 파일에 적용
  → **합리적이지만 파이프라인에 명시되지 않았음**

**신규 이슈 CV-05:** Worker의 "제안" 범위가 settings.json에만 국한되는지, 모든 파일 변경에 적용되는지 모호.
**해결안:** 명시: "Worker의 모든 변경은 evolutions/evo-XXX/ 내부에 제안 파일로 생성.
JARVIS가 검증 후 실제 경로에 복사/적용." 이것은 git의 staging area와 유사한 개념.
**심각도:** MEDIUM — 설계 명확화 필요.

---

## 검증 6: Phase 1 역할 한정 (CROSS-2) + 마이크로 스킬 (FIX-08) 순환

**CROSS-2 수정:** "Phase 1 = 진화 + 모니터링만"
**FIX-08:** "5개 마이크로 스킬 분리 (evolution, knowledge, obsidian-sync, visualization)"

**순환 체크:**
- Phase 1에서 knowledge/obsidian-sync/visualization 스킬 파일을 만들지만 사용 안 함?
  → 불필요한 파일 생성 = YAGNI 위반
- 진화 결과를 Obsidian에 저장하려면 obsidian-sync 스킬 필요 → Phase 1에서 사용 안 함?
  → 모드 B(Obsidian 없음)에서는 로컬 마크다운만 → OK
  → 모드 A(Obsidian 활성)에서는 obsidian-sync 필요 → **Phase 1 역할 한정과 충돌**

**신규 이슈 CV-06:** Phase 1에서 모드 A 사용자는 obsidian-sync가 필요한데, CROSS-2는 Phase 2+로 미뤘다.
**해결안:** Phase 1 역할을 재정의:
- Phase 1 코어: 진화 + 모니터링 (필수)
- Phase 1 선택: obsidian-sync (모드 A에서만 활성화, 단순 파일 쓰기 수준)
- Phase 2: knowledge 관리 + visualization + 하네스 + 학습 + 예산
- obsidian-sync Phase 1은 "obsidian CLI create/append" 수준만 (Basic Memory 불필요)
**심각도:** MEDIUM — Phase 구분 조정.

---

## 검증 7: 사전 정의 검증 스크립트 (IL3-V1) + 진화 유형 다양성 순환

**IL3-V1 수정:** "jarvis-verify.sh는 사전 포함, JARVIS 동적 생성 금지"

**순환 체크:**
- 진화 유형이 다양함 (설정 변경, hook 추가, 스킬 수정, ...)
  → 사전 정의 스크립트가 모든 유형을 검증할 수 있나?
  → 새로운 유형의 진화 → 검증 스크립트에 해당 로직 없음 → **검증 불가**

**신규 이슈 CV-07:** 사전 정의 검증 스크립트가 미래 진화 유형을 커버하지 못한다.
**해결안:** jarvis-verify.sh를 **플러그형** 구조로:
```
jarvis-verify.sh evo-001
  → STATUS 파일에서 진화 유형 읽기
  → verify-plugins/settings-change.sh 호출 (유형별 검증)
  → verify-plugins/hook-addition.sh 호출
  → 새 유형 → "검증 플러그인 없음" 경고 + 기본 검증(JSON 유효성, checksum)만 실행
```
**심각도:** MEDIUM — 확장성 설계.

---

## 검증 8: evidence 스키마 (IL3-V2) + 사용자 판단 (CROSS-3) 순환

**IL3-V2 수정:** evidence 스키마에 before/after 스냅샷 필수
**CROSS-3 수정:** "Phase 1 = 사용자 판단, 자동 비교 Phase 2"

**순환 체크:**
- evidence 스키마에 metric_comparison 필드가 있지만, Phase 1에서는 자동 비교 안 함
  → evidence_type = "user_approval"만 사용?
  → 스키마는 정의되었지만 Phase 1에서 metric_comparison은 빈 값?

**신규 이슈 없음.** evidence_type이 다중 값을 지원하므로:
- Phase 1: `evidence_type: "user_approval"` + 사용자 판단 기록
- Phase 2: `evidence_type: "metric_comparison"` + 자동 수치 비교 추가
- 스키마는 확장 가능하게 설계됨 ✓

---

## 검증 9: 큐 5건 제한 (IL1-V2) + 진화 직렬 실행 (FIX-03) 순환

**순환 체크:**
- 큐 5건 + 직렬 실행 → 최악의 경우 6번째 감지가 자동 폐기
  → 폐기된 감지가 CRITICAL 문제였다면?
  → 우선순위 기반 폐기이므로 CRITICAL > HIGH > MEDIUM > LOW
  → **CRITICAL이 6번째라면 기존 LOW를 밀어내야 함, 자동 폐기가 아님**

**신규 이슈 CV-08:** "우선순위 낮은 것 자동 폐기"의 우선순위 기준이 없다.
**해결안:** 메트릭 사전의 threshold를 기준으로:
- critical 임계 초과 → 우선순위 CRITICAL
- warning 임계 초과 → 우선순위 HIGH
- good 범위 내 개선 → 우선순위 LOW
큐 초과 시 가장 낮은 우선순위 폐기. 동일 우선순위면 FIFO.
**심각도:** LOW — 구현 시 반영.

---

## 검증 10: STATUS 파일 TDD 필드 (IL2-V2) + 설정 변경 TDD 완화 (IL2-V1) 순환

**IL2-V2:** `tests_failed_before_fix > 0`이면 TDD 준수
**IL2-V1:** 설정 변경은 "expected outcome 문서화"로 대체

**순환 체크:**
- 설정 변경 진화 시 `tests_failed_before_fix = 0` (테스트 대신 expected outcome)
  → JARVIS가 `tests_failed_before_fix == 0` → REJECT?
  → **Iron Law #2 검증 로직과 설정 변경 완화 조건이 충돌**

**신규 이슈 CV-09:** STATUS 검증에서 설정 변경과 코드 변경을 구분하는 로직이 없다.
**해결안:** STATUS 파일에 `evolution_type` 필드 추가:
```json
{
  "evolution_type": "settings_change",  // settings_change | hook_change | skill_change | code_change
  "tests_failed_before_fix": 0,        // 설정 변경은 0 허용
  "expected_outcomes_documented": true  // 설정 변경은 이것이 true여야 함
}
```
검증 로직:
- `evolution_type == "settings_change"` → `expected_outcomes_documented == true` 체크
- 그 외 → `tests_failed_before_fix > 0` 체크
**심각도:** HIGH — 이것을 수정하지 않으면 모든 설정 변경 진화가 REJECT됨.

---

## 순환검증 결과 요약

| # | 이슈 | 심각도 | 해결안 |
|---|------|--------|--------|
| **CV-09** | STATUS 검증이 설정/코드 변경을 구분 못함 | **HIGH** | evolution_type 필드 + 유형별 검증 로직 |
| **CV-04** | /freeze가 긴급 설정 변경 차단 | **HIGH** | 기본 warn 모드, deny는 CRITICAL만 |
| **CV-05** | Worker 제안 범위 모호 (설정만? 모든 파일?) | **MEDIUM** | "모든 변경은 evolutions/ 내부에 제안" 명시 |
| **CV-06** | Phase 1 모드 A에서 obsidian-sync 필요 | **MEDIUM** | Phase 1 선택적 포함 (단순 파일 쓰기) |
| **CV-07** | 검증 스크립트 미래 유형 미대응 | **MEDIUM** | 플러그형 verify-plugins/ 구조 |
| **CV-01** | 모드 전환 마이그레이션 | **MEDIUM** | migrate-vault 명령 |
| **CV-08** | 큐 우선순위 기준 미정의 | **LOW** | 메트릭 threshold 기반 |
| **CV-02** | Worker 환경변수 전달 | **LOW** | 마커 파일 폴백 |
| **CV-03** | 2단계 승인 → 응답성 저하 | **LOW** | 비동기 대기 (모니터링 계속) |
