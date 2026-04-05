# Iron Law Zero-Trust 감사 — 기존 검증 불신, 원문 직접 재검증

**원칙:** 이전 10회 순환검증의 "✅ 해결" 판정을 신뢰하지 않는다.
계획 원문에서 각 Iron Law가 **실제로** 지켜지는 경로만 추적한다.
"해결되었다고 적혀있다"는 증거가 아니다. "원문에 강제 메커니즘이 있다"만 증거다.

---

## Iron Law #1: NO EVOLUTION WITHOUT USER APPROVAL FIRST

### 테스트 1.1: 파이프라인에서 승인 없이 설정 변경까지 도달할 수 있는 경로가 있는가?

**원문 추적 (L135~170):**
```
① 감지 → ② 분석 → ③ 1차 승인 [수립] → ④ 백업 → ⑤ 계획 → ⑤-b 2차 승인 [실행]
→ ⑥~⑨ Worker → ⑩ [KEEP] → ⑪ 반영
```

**승인 지점 3개:** ③, ⑤-b, ⑩
**설정 적용 지점:** ⑪ (JARVIS가 JSON Patch 적용)

**질문: ⑪에서 JARVIS가 사용자 승인 없이 적용할 수 있나?**
- ⑩에서 [KEEP] = 사용자 선택 → ⑪은 그 결과를 실행 → 사실상 ⑩이 최종 승인
- **하지만 ⑪의 "충돌 키 → AskUserQuestion"은 ⑩ 이후 추가 승인** → OK
- ⑩에서 [KEEP] 없이 ⑪로 갈 수 있나? → 파이프라인상 순차 → **불가** ✓

**질문: ⑩을 건너뛰는 경로가 있나?**
- ⑨ 통과 후 바로 ⑪로? → 파이프라인에 "⑩ 없이 ⑪" 경로 없음 ✓
- ⑤→⑨ 순환 2회 실패 → DISCARD → ⑪ 아닌 롤백 → 적용 없음 ✓

**질문: JARVIS가 프롬프트를 무시하고 Write로 settings.json을 직접 수정하면?**
- GATE hook (L423~427): Write 허용 경로 = `settings.json`, `cmux-jarvis/`, 볼트
- **settings.json이 허용 경로에 포함!** → JARVIS가 파이프라인 무시하고 직접 Write 가능

### ⚠️ FINDING IL1-F1: GATE hook이 settings.json 쓰기를 항상 허용한다

**문제:** L424 "JARVIS Write/Edit 허용 경로: ~/.claude/settings.json"
이것은 JARVIS가 진화 파이프라인 밖에서도 settings.json을 수정할 수 있다는 뜻.
GATE hook은 "경로"만 체크하지 "진화 파이프라인 내에서인지"는 체크하지 않는다.

**영향:** Iron Law #1 위반 가능. JARVIS가 승인 없이 settings.json을 수정할 수 있는 물리적 경로 존재.

**해결안:** GATE hook에 **진화 컨텍스트 체크** 추가:
```bash
# settings.json 쓰기 시 추가 검증
if [[ "$TARGET_PATH" == *"settings.json"* ]]; then
  # CURRENT_LOCK 존재 + phase가 "applying"일 때만 허용
  LOCK_FILE="$HOME/.claude/cmux-jarvis/.evolution-lock"
  if [ -f "$LOCK_FILE" ]; then
    PHASE=$(jq -r '.phase' "$LOCK_FILE" 2>/dev/null)
    if [ "$PHASE" = "applying" ]; then
      # 진화 반영 단계 → 허용
      echo '{"continue":true}'
      exit 0
    fi
  fi
  # 그 외 → deny (승인 없는 직접 수정)
  echo '{"error":"GATE J-1: settings.json은 진화 ⑪ 반영 단계에서만 수정 가능"}'
  exit 1
fi
```

**심각도:** **CRITICAL** — 이것이 없으면 Iron Law #1이 프롬프트 의존이며 강제되지 않음.

---

### 테스트 1.2: "구조화된 선택지만 인정"이 실제로 강제되는가?

**원문 (L56~58):** "free-text → 승인으로 자동 해석 금지"

**질문: 이것을 누가 강제하나?**
- AskUserQuestion은 Claude Code의 내장 도구 → JARVIS가 호출
- JARVIS가 응답을 파싱 → "[수립]" 포함 여부 체크
- **JARVIS = LLM.** LLM이 "규칙대로 파싱하겠다"는 약속은 프롬프트 레벨.
- hook으로 강제할 수 없음 (AskUserQuestion 응답은 hook 대상 아님)

### ⚠️ FINDING IL1-F2: 구조화된 선택지 강제가 프롬프트 레벨에 머물러 있다

**문제:** JARVIS가 사용자 응답을 파싱하는 로직은 SKILL.md의 지시. LLM이 이를 무시하면 "좋아"를 승인으로 해석할 수 있다.

**영향:** MEDIUM. LLM이 명시적 지시를 무시할 확률은 낮지만 0은 아님.

**해결안:** 완전한 해결은 어려움. 현실적 완화책:
- Red Flags에 추가: "free-text를 승인으로 해석하려는 충동 → 반드시 구조화 선택지 재요청"
- AskUserQuestion의 options 파라미터 사용 (Claude Code가 선택지 UI 제공 시)

---

## Iron Law #2: NO IMPLEMENTATION WITHOUT EXPECTED OUTCOME FIRST

### 테스트 2.1: Worker가 ⑦ TDD 없이 ⑧ 구현으로 넘어갈 수 있는가?

**원문 추적:**
- ⑦ TDD → ⑧ 구현 (순차)
- Worker는 독립 pane의 Claude 세션
- Worker에게 전달되는 지시는 JARVIS가 cmux send로 보내는 텍스트

**질문: Worker가 지시를 무시하고 바로 구현하면?**
- evolution-worker.md의 지시 = 프롬프트 레벨 → **무시 가능**
- Worker gate hook은 evolutions/ 외부 쓰기만 차단 → **파이프라인 순서는 강제 안 함**

### ⚠️ FINDING IL2-F1: 파이프라인 순서(⑦→⑧)가 프롬프트로만 강제됨

**문제:** Worker가 TDD를 건너뛰고 바로 구현해도 hook이 차단하지 않음.
STATUS 파일의 `tests_failed_before_fix` 필드는 Worker가 보고하는 값 → Worker가 거짓 보고 가능.

**영향:** HIGH. TDD Iron Law가 사실상 자발적 준수.

**해결안:** JARVIS가 Worker 결과물을 검증할 때 **05-tdd.md 파일 존재를 물리적으로 체크:**
```bash
# JARVIS가 Worker 완료 후 검증
TDD_FILE="$EVO_DIR/05-tdd.md"
if [ ! -f "$TDD_FILE" ] || [ ! -s "$TDD_FILE" ]; then
  echo "REJECT: TDD 파일(05-tdd.md) 없음 또는 빈 파일"
  # → DISCARD
fi

# 파일 내용이 최소 요건 충족하는지 (3줄 이상, "test" 또는 "expected" 키워드 포함)
LINE_COUNT=$(wc -l < "$TDD_FILE")
if [ "$LINE_COUNT" -lt 3 ]; then
  echo "REJECT: TDD 파일이 너무 짧음 ($LINE_COUNT줄)"
fi
```

이것은 AI 판단이 아닌 **파일 존재 + 최소 크기 체크** → 자동화 가능 → jarvis-verify.sh에 포함.

---

### 테스트 2.2: settings_change 유형에서 "expected outcome 문서화"가 실제로 검증되는가?

**원문 (L490~491):**
- `settings_change` → `expected_outcomes_documented == true` 필수

**질문: 이 값을 누가 설정하나?**
- Worker가 STATUS 파일에 기록 → Worker 자기 보고
- JARVIS가 체크 → `true`면 통과

**질문: Worker가 expected outcome을 문서화하지 않고 `true`로만 표시하면?**
- 07-e2e.md 또는 별도 expected-outcomes.md 파일이 존재해야 함
- **하지만 파일 존재 체크가 없다!** STATUS의 boolean만 체크.

### ⚠️ FINDING IL2-F2: expected_outcomes_documented가 자기 보고(boolean)에만 의존

**문제:** Worker가 `expected_outcomes_documented: true`를 설정하면 실제 문서 없어도 통과.

**해결안:** jarvis-verify.sh에 추가:
```bash
# settings_change 유형일 때 expected-outcomes 파일 존재 체크
if [ "$EVOLUTION_TYPE" = "settings_change" ]; then
  EXPECTED_FILE="$EVO_DIR/07-expected-outcomes.md"
  if [ ! -f "$EXPECTED_FILE" ] || [ ! -s "$EXPECTED_FILE" ]; then
    echo "REJECT: expected outcomes 파일 없음"
  fi
fi
```

---

## Iron Law #3: NO COMPLETION CLAIMS WITHOUT VERIFICATION EVIDENCE

### 테스트 3.1: evidence 스키마가 실제로 강제되는가?

**원문 (L403~411):** evidence 스키마 정의 (JSON)

**질문: 이 스키마를 누가 생성하나?**
- jarvis-verify.sh가 before/after 메트릭 수집 → 자동 생성
- **하지만 jarvis-verify.sh가 evidence 파일을 생성하는 로직이 계획에 없다!**
- jarvis-verify.sh는 "JSON 유효성, checksum 비교, 메트릭 스냅샷" (L70) → **스냅샷은 수집하지만 evidence 스키마 파일을 생성하는지 불명확**

### ⚠️ FINDING IL3-F1: evidence 파일 생성이 jarvis-verify.sh에 명시되지 않음

**문제:** evidence 스키마를 정의했지만, 누가 이 파일을 실제로 만드는지 불분명.
jarvis-verify.sh의 역할이 "수집"인지 "수집+파일생성"인지 모호.

**해결안:** jarvis-verify.sh의 출력을 명시:
```bash
# jarvis-verify.sh의 최종 출력
# → evolutions/evo-001/evidence.json 생성
{
  "evidence_type": "...",
  "before_snapshot": "evolutions/evo-001/before-metrics.json",
  "after_snapshot": "evolutions/evo-001/after-metrics.json",
  ...
}
```
JARVIS가 ⑩ 진행 전 `evidence.json` 존재 체크 → 없으면 REJECT.

---

### 테스트 3.2: "사전 정의 스크립트(JARVIS가 동적 생성 금지)"가 실제로 강제되는가?

**원문 (L68~69):** "jarvis-verify.sh는 cmux 패키지에 사전 포함... JARVIS가 동적 생성 금지"

**질문: JARVIS가 jarvis-verify.sh를 수정하면?**
- 파일 위치: `scripts/jarvis-verify.sh` (cmux 패키지 내)
- GATE hook 허용 경로: `~/.claude/settings.json`, `~/.claude/cmux-jarvis/`, Obsidian 볼트
- **scripts/ 는 허용 경로에 포함되지 않음** → hook deny

**검증:** scripts/ 경로가 GATE hook의 허용 목록에 없는 것이 맞는지 확인.
L424: "허용 경로: `~/.claude/settings.json`, `~/.claude/cmux-jarvis/`, Obsidian 볼트"
→ `scripts/`는 `~/.claude/skills/cmux-jarvis/` 또는 cmux 패키지 내부
→ `~/.claude/cmux-jarvis/`와 `~/.claude/skills/cmux-jarvis/`는 **다른 경로**

### ⚠️ FINDING IL3-F2: GATE hook 허용 경로에 스킬 디렉토리가 포함되어 있다

**문제:** L424의 허용 경로에 `~/.claude/cmux-jarvis/`가 있음.
스킬 디렉토리는 `~/.claude/skills/cmux-jarvis/` (L222)
→ 이 두 경로는 다르므로 스킬 파일(hooks/, references/ 등)은 **허용 경로 밖** → 수정 불가 ✓

하지만 `~/.claude/cmux-jarvis/`에는 `evolutions/`가 있고, Worker 제안 파일도 여기 저장.
→ JARVIS가 `~/.claude/cmux-jarvis/evolutions/evo-001/proposed-settings.json`을 **직접 조작 가능**
→ Worker가 아닌 JARVIS가 제안 파일을 만들면 "Worker 독립 검증" 원칙 위반

### ⚠️ FINDING IL3-F3: JARVIS가 Worker 제안 파일을 직접 조작할 수 있다

**문제:** evolutions/ 디렉토리가 GATE 허용 경로 내 → JARVIS가 proposed-settings.json을 직접 작성/수정 가능 → "Do Not Trust the Report" 원칙의 전제 붕괴

**영향:** MEDIUM. JARVIS가 의도적으로 조작할 동기는 없지만, 구조적으로 가능하다는 것이 문제.

**해결안:**
- evolutions/evo-XXX/가 Worker에 의해 생성된 후, JARVIS는 **Read만** 허용
- 구현: JARVIS가 evolutions/ 내 파일을 Write/Edit 할 때 STATUS.phase가 "implementing"이면 deny
- 또는 Worker 전용 하위 디렉토리: `evolutions/evo-001/worker-output/` → JARVIS deny

---

## Iron Law 메타 검증: "Iron Law를 지키게 만드는 메커니즘 자체"가 견고한가?

### 메타-1: GATE hook이 비활성화되면 모든 Iron Law가 무력화

**질문:** hook을 비활성화하는 경로가 있나?
- `/hooks` 슬래시 명령으로 hook 설정 변경 가능 (L322)
- JARVIS가 `/hooks`를 실행하면 자기 GATE hook을 제거할 수 있음
- GATE hook에 `/hooks` 명령 차단이 없음

### ⚠️ FINDING META-1: JARVIS가 /hooks 명령으로 자기 GATE를 제거할 수 있다

**문제:** JARVIS의 allowed-tools에 Bash 포함 → `/hooks` 실행 가능 → settings.json의 hook 설정 변경 → GATE hook 제거

**하지만:** settings.json 수정은 GATE hook이 차단... **하는가?**
- `/hooks`는 Claude Code 내장 명령 → settings.json을 Claude Code 내부에서 수정
- **이것은 "내부 변경"** → ConfigChange hook은 감지하지만 PreToolUse hook은 트리거 안 됨
- 왜? `/hooks`는 Tool 호출이 아니라 Claude Code 내부 로직

**영향:** **CRITICAL.** `/hooks` 명령으로 GATE hook을 제거하면 모든 보호 해제.

**해결안:** GATE J-1 금지 목록에 `/hooks` 추가:
```markdown
## ⛔ GATE J-1: 권한 제한
- /hooks 명령 금지 (자기 GATE 제거 방지)
```
+ ConfigChange hook에서 hook 항목 삭제 감지 → 자동 복원:
```bash
# cmux-settings-backup.sh 에 추가
# settings.json에서 jarvis gate hook이 제거되었는지 체크
if ! jq -e '.hooks[] | select(.command | contains("cmux-jarvis-gate"))' "$SETTINGS_JSON" >/dev/null 2>&1; then
  echo "WARNING: JARVIS GATE hook 삭제 감지. 자동 복원."
  # 복원 로직
fi
```

---

### 메타-2: SKILL.md 자체를 수정하면 Iron Laws가 사라진다

**질문:** JARVIS가 자기 SKILL.md를 수정할 수 있나?
- SKILL.md 위치: `~/.claude/skills/cmux-jarvis/SKILL.md`
- GATE 허용 경로: `~/.claude/cmux-jarvis/` (스킬 경로와 다름)
- **`~/.claude/skills/cmux-jarvis/`는 허용 경로에 없음** → Write deny ✓

**검증 통과.** JARVIS는 자기 SKILL.md를 수정할 수 없다.

---

## 최종 판정

### CRITICAL — 구현 차단

| # | 발견 | Iron Law | 문제 |
|---|------|----------|------|
| **IL1-F1** | GATE가 settings.json 쓰기를 항상 허용 | #1 | 승인 없이 직접 수정 가능 |
| **META-1** | /hooks로 GATE 자체 제거 가능 | 전체 | 모든 보호 해제 |

### HIGH — 구현 시 필수 반영

| # | 발견 | Iron Law | 문제 |
|---|------|----------|------|
| **IL2-F1** | ⑦→⑧ 순서가 프롬프트로만 강제 | #2 | TDD 건너뛰기 가능 |
| **IL2-F2** | expected_outcomes가 boolean 자기보고 | #2 | 문서 없어도 통과 |
| **IL3-F1** | evidence 파일 생성 주체 불명확 | #3 | 증거 누락 가능 |

### MEDIUM

| # | 발견 | 문제 |
|---|------|------|
| IL1-F2 | 구조화 선택지 강제 = 프롬프트 레벨 |
| IL3-F2 | 스킬 경로 vs cmux-jarvis 경로 혼동 가능 |
| IL3-F3 | JARVIS가 Worker 제안 파일 조작 가능 |
