# 세분화 문서 재검토 (2026-04-03)

**방법:** 17개 문서를 교차 검증 — 문서 간 불일치, 빠진 연결, 엣지케이스

---

## 1. 문서 간 교차 일관성

### ✅ 일관 확인 (문제 없음)
- hook-map.md(6 hook) ↔ directory-structure.md(hooks/ 6파일) → **일치** ✓
- principles.md(7원칙) ↔ iron-laws.md(3 Iron Laws) → **상위/하위 일관** ✓
- gate-logic.md(permissionDecision) ↔ claude-source-findings.md(S1) → **일치** ✓
- worker-protocol.md(STATUS 스키마) ↔ iron-laws.md(evolution_type 검증) → **일치** ✓
- skill-md-spec.md(10줄) ↔ session-lifecycle.md(additionalContext 주입) → **일치** ✓

### ⚠️ 불일치 발견

**X1.** hook-map.md에 6 hook인데 phase-roadmap.md에 "hook 7"이라고 표기
- hook-map: gate, backup, session-start, file-changed, pre-compact, post-compact = **6개**
- phase-roadmap: "**hook 7**" → **불일치**
- 원인: prevent-idle 제거(CE-01) 후 phase-roadmap 미수정
- **수정:** phase-roadmap.md "hook 7" → "hook 6"

**X2.** directory-structure.md의 references/에 gate-5level.md가 있지만 skills/ 문서에서 참조 없음
- gate-5level.md는 hooks/gate-logic.md의 GATE 5단계 매핑과 중복 가능
- **판단:** gate-5level.md = references/ 원본, gate-logic.md = 구현 가이드. SSOT 준수 ✓ (다른 관점)

**X3.** evolution-pipeline.md에 "Phase 1: 6단계 실행"이라 했지만 파이프라인 다이어그램은 11단계 전체 표시
- 6단계(①②③④⑧⑪)와 수동(⑤⑥⑦⑨⑩)의 **시각적 구분이 없음**
- **수정:** 수동 단계에 (수동) 라벨 추가

---

## 2. 엣지케이스 검토

### E1. session-start hook에서 JARVIS surface 식별 실패

**시나리오:** roles.json이 손상/삭제되어 jarvis.surface가 null
**현재 처리:** `JARVIS_SID=$(jq -r '.jarvis.surface // ""'` → 빈 문자열
→ `"$CURRENT_SID" = ""` 비교 → **모든 surface가 조건 실패 → 어디서도 JARVIS 지시 주입 안 됨**
**영향:** JARVIS가 빈 껍데기로 시작. 감지/진화 불가.
**해결:** roles.json 없을 때 폴백 — cmux identify로 자기 surface 확인 후 임시 등록.
```bash
if [ -z "$JARVIS_SID" ]; then
  # 자기 자신이 JARVIS인지 확인 (SKILL.md 이름 기반)
  # 또는 config.json의 jarvis_surface_hint 참조
  JARVIS_SID="unknown"  # fail-safe: 지시 주입 안 함 (안전)
fi
```
**심각도:** MED — roles.json 손상은 드물지만 복구 경로 필요.

### E2. FileChanged hook에서 metric-dictionary.json 자체가 없을 때

**시나리오:** 최초 설치 직후 아직 metric-dictionary.json을 안 만들었을 때
**현재 코드:** `jq -r '.metrics.stall_count.threshold.warning' metric-dictionary.json`
→ 파일 없으면 jq 에러 → hook 비정상 종료 → exit 1 → "show stderr to user only"
**영향:** 에러 메시지가 사용자에게 표시되지만 hook은 계속 동작 (non-blocking)
**해결:** 파일 없으면 하드코딩 기본값 사용:
```bash
STALL_WARN=$(jq -r '.metrics.stall_count.threshold.warning' \
  ~/.claude/cmux-jarvis/metric-dictionary.json 2>/dev/null || echo "3")
```
**심각도:** LOW — 최초 설치 시 1회성.

### E3. Worker가 proposed-settings.json에 잘못된 JSON을 생성했을 때

**시나리오:** Worker LLM이 JSON 구문 오류 포함 파일 생성
**현재 처리:** jarvis-verify.sh에서 JSON 유효성 체크 → FAIL → ⑤ 순환
**하지만:** jq deep merge 전에 jarvis-verify.sh가 실행되므로 → **잡힘** ✓
**추가 확인:** file-mapping.json도 JSON 유효성 체크 필요 (현재 미포함)
**해결:** jarvis-verify.sh에 file-mapping.json 유효성 체크 추가.
**심각도:** LOW

### E4. jq deep merge에서 배열 병합 문제

**시나리오:** settings.json에 `"hooks": {"PreToolUse": [...]}`이 있고
proposed에도 `"hooks": {"PreToolUse": [...]}`가 있으면
`jq -s '.[0] * .[1]'`은 배열을 **덮어씀** (병합 아님)
**영향:** JARVIS가 proposed에 hooks 포함하면 기존 hooks가 **전부 삭제됨**
**해결:**
1. Worker의 proposed는 **hooks 키를 포함하면 안 됨** (Scope Lock으로 제한)
2. jarvis-verify.sh Outbound Gate에서 "proposed에 hooks 키 → REJECT" 체크 추가
3. 또는 `jq` 재귀 deep merge 함수 사용 (Phase 2)
**심각도:** **HIGH** — hooks 삭제는 치명적.

### E5. 동시에 2개 surface에서 /cmux-start 실행

**시나리오:** 사용자가 실수로 2번 /cmux-start → JARVIS pane 2개 생성
**현재 처리:** roles.json에 jarvis 등록 → 2번째가 덮어씀
→ 첫 JARVIS는 roles.json에서 인식 안 됨 → session-start에서 지시 미주입 → 빈 껍데기
**영향:** 두 JARVIS 중 하나만 작동. 다른 하나는 무해하지만 리소스 낭비.
**해결:** cmux-start에서 JARVIS pane 생성 전 기존 존재 체크:
```bash
EXISTING=$(jq -r '.jarvis.surface // ""' /tmp/cmux-roles.json 2>/dev/null)
if [ -n "$EXISTING" ]; then
  echo "⚠️ JARVIS 이미 실행 중: $EXISTING"
  # 확인 후 진행 또는 중단
fi
```
**심각도:** MED

### E6. evolution-queue.json이 커져서 읽기 느릴 때

**시나리오:** 큐 5건 제한이지만 deferred-issues도 같은 파일?
**확인:** 아님. evolution-queue.json(큐)과 deferred-issues.json(보류)은 별도 파일. ✓
**하지만:** 큐 5건 + deferred 무제한 → deferred가 100건 이상이면?
**해결:** deferred-issues도 **최대 20건** 제한 + 오래된 것 자동 정리.
**심각도:** LOW

### E7. AGENDA_LOG.md가 무한히 성장

**시나리오:** 모든 결정 기록 → 수개월 후 수천 줄
**현재 처리:** 없음 (무제한 append)
**해결:** 월별 로테이션: `AGENDA_LOG_2026-04.md`, 현재 월만 활성. 이전은 아카이브.
**심각도:** LOW — Phase 2에서 대응.

---

## 3. 빠진 문서/항목

| # | 빠진 것 | 위치 | 영향 |
|---|--------|------|------|
| **M1** | config.json 스키마 정의 | architecture/ | 구현 시 무슨 필드 필요한지 모호 |
| **M2** | evolution-worker.md 프롬프트 템플릿 상세 | skills/ 또는 pipeline/ | Worker가 뭘 받는지 불명확 |
| **M3** | install.sh 수정 상세 (HOOK_MAP 추가 방법) | hooks/ | 기존 패턴 참조로 충분하지만 명시 필요 |
| **M4** | cmux-start 수정 상세 (JARVIS pane 코드) | pipeline/ 또는 architecture/ | 시뮬레이션에는 있지만 정본 문서에 없음 |

---

## 4. 결과 요약

| 심각도 | 건수 | 내용 |
|--------|------|------|
| **HIGH** | 1건 | E4: jq 배열 덮어쓰기 → hooks 삭제 가능 |
| **MED** | 3건 | X1(hook 수 불일치), E1(roles.json 손상), E5(JARVIS 중복) |
| **LOW** | 5건 | X3(수동 라벨), E2(dict 없음), E3(file-mapping), E6(deferred), E7(AGENDA) |
| **빠진 문서** | 4건 | M1~M4 |
