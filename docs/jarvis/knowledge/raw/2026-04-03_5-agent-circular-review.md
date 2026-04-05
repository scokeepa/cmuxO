# JARVIS 플랜 5관점 순환 검토 (2026-04-03)

**대상:** JARVIS-PLAN-FULL.md 최신 (1,356줄) + 구현 플랜 (3,586줄)
**관점:** 아키텍트 / 엣지케이스 / SSOT / SRP / 의존성

---

## 1. 아키텍트 — 구조적 정합성

### A1. hook 8개가 모든 surface에서 실행되는 성능 영향

**현황:** 8개 hook이 settings.json에 등록 → 3+ surface에서 모두 실행
**계산:** PreToolUse(Edit|Write|Bash) = 모든 Bash 명령마다 gate.sh 실행
- Main surface: 분당 ~20회 Bash → gate.sh 20회/분
- Worker surface: ~10회 Bash
- JARVIS surface: ~5회 Bash
- 총: **~35회/분 × 3초 타임아웃 = 최악 105초/분 지연 가능**

**실제:** gate.sh가 첫 줄에서 surface 식별 → JARVIS/Worker 아니면 즉시 allow (~1ms)
하지만 **jq 파싱 + roles.json 읽기**는 매번 발생.

**이슈 CA-01:** gate.sh가 Main의 모든 Bash 명령에서 jq를 실행함. 무시 가능한 수준인가?
**측정:** `time echo '{}' | jq -r '.tool_name'` ≈ 5ms. 35회/분 = 175ms/분. **무시 가능** ✓

### A2. FileChanged hook의 eagle-status 감시 범위

**현황:** watchPaths에 `/tmp/cmux-eagle-status.json` 등록
**문제:** eagle-status.json은 Watcher가 **수초마다** 갱신. FileChanged가 수초마다 trigger?
→ hook 타임아웃 5초인데 2초마다 변경되면 hook이 누적 실행.

**이슈 CA-02:** eagle-status가 자주 갱신되면 FileChanged hook 폭주 가능.
**해결:** jarvis-file-changed.sh 내부에서 **디바운싱**: 마지막 실행 시각 기록, 60초 내 재실행 무시.
```bash
LAST_RUN="/tmp/jarvis-file-changed-last"
NOW=$(date +%s)
PREV=$(cat "$LAST_RUN" 2>/dev/null || echo 0)
if [ $((NOW - PREV)) -lt 60 ]; then exit 0; fi
echo "$NOW" > "$LAST_RUN"
```
**심각도:** HIGH — 이것 없으면 hook 폭주.

### A3. gate.sh의 Bash 명령 grep이 false positive 가능

**현황:** `grep -qE "settings\.json"` → 명령에 "settings.json" 문자열 포함 시 차단
**문제:** `cat ~/.claude/settings.json` (읽기)도 차단됨. Read 도구가 아닌 Bash로 읽을 때.
또는 `echo "check settings.json status"` 같은 무해한 명령도 차단.

**이슈 CA-03:** Bash grep이 읽기 명령까지 차단.
**해결:** 쓰기 패턴만 감지: `grep -qE "(>|>>|cp |mv |tee ).*settings\.json|settings\.json.*(>|>>)"`
**심각도:** MED

---

## 2. 엣지케이스 — 경계 조건

### E1. initialUserMessage가 JARVIS 외 surface에서도 실행?

**현황:** session-start hook이 SessionStart에 등록 → 모든 surface에서 실행
**hook 코드:** `if [ "$CURRENT_SID" = "$JARVIS_SID" ]` 체크
**문제:** JARVIS pane이 아직 생성 안 된 시점 (최초 /cmux-start 전) → roles.json에 jarvis 없음
→ `JARVIS_SID=""` → 조건 실패 → initialUserMessage 미주입 → 정상 ✓

**하지만:** /cmux-start에서 JARVIS pane 생성 → claude 시작 → SessionStart hook 실행
→ 이 시점에 roles.json에 jarvis가 등록되어 있는가?
→ cmux-start Step 2.5에서 pane 생성 후 roles.json 등록 → claude 시작 → SessionStart
→ **roles.json 등록이 claude 시작보다 먼저** → 타이밍 OK ✓

### E2. TeammateIdle hook이 JARVIS를 teammate로 인식하는가?

**현황:** TeammateIdle은 "When a teammate is about to go idle" 시 실행
**문제:** JARVIS가 teammate인가? cmux-start에서 JARVIS를 **teammate으로 등록하지 않음.**
JARVIS는 별도 pane이지 Claude Code의 teammate/swarm 시스템이 아님.
→ TeammateIdle hook이 **JARVIS에서 trigger 안 될 수 있음.**

**이슈 CE-01:** JARVIS가 Claude Code teammate이 아니면 TeammateIdle hook 무효.
**해결:** 확인 필요. Claude Code의 teammate = Agent tool로 생성된 서브에이전트.
JARVIS는 cmux new-pane으로 생성 → **teammate 아님** → TeammateIdle 미적용.
→ **jarvis-prevent-idle.sh가 동작하지 않을 수 있음.**
→ 대안: JARVIS idle 방지는 **initialUserMessage + FileChanged hook**으로 충분.
FileChanged가 eagle-status 변경마다 (디바운스 후) JARVIS에 additionalContext 주입 → idle 방지.
**심각도:** HIGH — S8 기능이 실제로 동작하지 않을 가능성.

### E3. deferred-issues.json 위치 미정의

**현황:** 보류 후 재감지 시 deferred-issues.json 참조
**문제:** 이 파일이 어디 저장되는지 디렉토리 구조에 없음.
**해결:** `~/.claude/cmux-jarvis/deferred-issues.json` 추가.
**심각도:** LOW

---

## 3. SSOT (Single Source of Truth) — 정보 중복/불일치

### SS1. 메트릭 임계값이 2곳에 정의

**위치 1:** `references/metric-dictionary.json` — 공식 정의
**위치 2:** `jarvis-file-changed.sh` 내부 하드코딩 — `if [ "$STALL" -ge 3 ]`
→ metric-dictionary에서 stall warning=2로 바꿔도 file-changed.sh는 3 유지.

**이슈 SS-01:** 임계값이 2곳에 하드코딩.
**해결:** file-changed.sh가 metric-dictionary.json에서 임계값을 읽어야 함:
```bash
STALL_WARN=$(jq -r '.metrics.stall_count.threshold.warning' \
  ~/.claude/cmux-jarvis/metric-dictionary.json)
if [ "$STALL" -ge "$STALL_WARN" ]; then ...
```
**심각도:** MED

### SS2. Red Flags가 SKILL.md와 references/red-flags.md 2곳에 존재

**SKILL.md L436~441:** Red Flags 테이블 인라인
**references/red-flags.md:** 별도 파일

→ 하나를 수정하면 다른 곳은 구버전 유지.
**해결:** SKILL.md에서 `(상세: references/red-flags.md 참조)` 링크만 남기고 테이블 제거.
**심각도:** MED

### SS3. GATE 규칙이 3곳에 분산

**위치 1:** SKILL.md "GATE J-1" 섹션 — 프롬프트 레벨
**위치 2:** gate.sh 코드 — 하드코딩된 경로 패턴
**위치 3:** references/gate-5level.md — 5단계 기준

→ GATE 규칙 변경 시 3곳 동시 수정 필요.
**해결:** gate.sh가 gate-5level.md 또는 gate-rules.json을 읽어 동적 로드.
Phase 1에서는 하드코딩 허용하되, **gate.sh 상단에 "규칙 출처: gate-5level.md" 주석** 추가.
**심각도:** MED (Phase 2에서 외부 config 로드)

---

## 4. SRP (Single Responsibility Principle) — 단일 책임

### SR1. gate.sh가 3가지 역할을 동시에 수행

**현재:** gate.sh = GATE 판정 + Worker 경로 제한 + /freeze 체크
→ 원래 gate.sh + worker-gate.sh + freeze-check 3파일이었으나 S4에서 통합.

**문제:** gate.sh 변경 시 3가지 기능 모두에 영향. 테스트 범위 넓어짐.
**평가:** hook 수를 줄이는 것이 성능에 유리 (병렬 실행 비용). **현재 통합이 올바른 결정.**
하지만 내부적으로 **함수 분리** 필요:
```bash
# 명확한 함수 분리
check_gate()          # GATE J-1 경로 체크
check_worker()        # Worker 경로 제한
check_freeze()        # /freeze 상태 체크
check_settings()      # settings.json 조건부
```
**심각도:** LOW — 내부 구조화만 필요.

### SR2. jarvis-session-start.sh가 4가지를 동시에 수행

**현재:** 캐시 inject + initialUserMessage + watchPaths 등록 + surface 식별
**평가:** SessionStart hook은 세션당 1회만 실행 → 통합해도 문제 없음.
**심각도:** LOW

### SR3. JARVIS SKILL.md가 여전히 과도한 내용 포함

**현황:** SKILL.md에 Iron Laws + GATE + Red Flags + 안전 제한 + 스킬 라우팅 + 모니터링
→ 약 100줄 이상의 지시사항.

**문제:** 모든 surface의 모든 세션에서 로드됨 → **불필요한 컨텍스트 소모.**
JARVIS가 아닌 Main/Worker에서도 이 100줄을 읽음.

**이슈 SR-03:** cmux-jarvis SKILL.md가 전 surface에서 불필요하게 로드.
**해결:** `~/.claude/skills/cmux-jarvis/SKILL.md`는 **10줄 미만**으로 최소화:
```markdown
---
name: cmux-jarvis
description: "JARVIS 시스템 관리자"
user-invocable: false
---
JARVIS는 오케스트레이션 설정 진화 엔진입니다.
상세 지시사항은 JARVIS surface에서만 로드됩니다.
(session-start hook이 JARVIS surface에서 additionalContext로 전체 지시 주입)
```
전체 Iron Laws/GATE/Red Flags는 **session-start hook의 additionalContext**로 JARVIS에만 주입.
**심각도:** HIGH — 불필요한 컨텍스트 절약.

---

## 5. 의존성 — 외부 의존 + 순환 의존

### D1. jq 의존

**현황:** gate.sh, file-changed.sh, settings-backup.sh 등 모든 hook이 jq 사용
**문제:** jq가 설치되지 않은 환경? → macOS는 기본 미포함 (Homebrew 필요)
**해결:** `command -v jq >/dev/null || { allow; exit 0; }` — jq 없으면 GATE 비활성 (fail-open)
또는 Python 폴백: `python3 -c "import json,sys; ..."`
**심각도:** MED

### D2. JARVIS → Watcher 순환 의존

**현황:**
- Watcher → JARVIS: STALL 3회 시 cmux send 알림
- JARVIS → Watcher: Watcher SKILL.md 수정 가능 (진화 대상)

**문제:** JARVIS가 Watcher를 진화시키면 → Watcher 동작 변경 → JARVIS 감지 데이터 변경
→ JARVIS가 또 진화 → **잠재적 순환**

**해결:** Watcher SKILL.md 진화는 **Phase 2 이후** + 별도 검증 체인.
Phase 1에서 JARVIS는 **settings.json + ai-profile.json만** 진화 대상.
**심각도:** LOW (Phase 1 범위 한정으로 차단됨)

### D3. /tmp/ 파일 의존

**현황:** roles.json, eagle-status, watcher-alerts, evolution-lock 등이 /tmp/에 저장
**문제:** 시스템 재부팅 시 /tmp/ 초기화 → 모든 상태 손실
→ CURRENT_LOCK, roles, evolution-counter 모두 소실

**이슈 CD-03:** /tmp/ 기반 상태가 재부팅 시 소실.
**해결:** JARVIS 전용 상태는 `~/.claude/cmux-jarvis/`에 저장 (이미 설계됨).
cmux 공유 파일 (roles.json, eagle-status)은 /tmp/에 있으므로 /cmux-start 재실행 필요.
→ **재부팅 후 /cmux-start 필수** 를 문서에 명시.
**심각도:** LOW (기존 cmux 동작과 동일)

---

## 순환 검증 — 해결안 교차 체크

### 교차 1: CA-02(디바운싱) + SS-01(임계값 SSOT)
디바운싱을 60초로 하면 → 60초간 eagle-status 변경 무시 → 임계값 초과 감지 지연 60초.
→ **수용 가능.** Watcher cmux send가 즉시 알림 (트리거 A)이므로 FileChanged 지연은 보완됨.

### 교차 2: CE-01(TeammateIdle 미적용) + S8(idle 방지)
TeammateIdle이 JARVIS에서 동작 안 하면 → JARVIS가 idle 됨.
→ **대안:** FileChanged hook이 eagle-status 변경마다 additionalContext 주입 → AI가 "반응해야 할 새 데이터"를 받으므로 idle 방지 효과.
→ 추가 대안: session-start initialUserMessage에서 "새 데이터 없어도 5분마다 상태 확인" 지시.
→ **S8은 제거하고 FileChanged + initialUserMessage로 대체.**

### 교차 3: SR-03(SKILL.md 최소화) + S5(initialUserMessage)
SKILL.md를 10줄로 줄이면 → JARVIS 지시사항은 어디?
→ session-start hook의 additionalContext에 전체 지시 주입.
→ 하지만 additionalContext 크기 제한이 있나? → Claude Code 소스에 크기 제한 없음 (string).
→ **100줄 지시 ≈ 3000토큰을 additionalContext로 주입 가능.**

---

## 결과 요약

| # | 이슈 | 관점 | 심각도 | 해결 |
|---|------|------|--------|------|
| **CA-02** | FileChanged hook 폭주 | 아키텍트 | **HIGH** | 디바운싱 60초 |
| **CE-01** | TeammateIdle JARVIS에서 미적용 | 엣지케이스 | **HIGH** | S8 제거, FileChanged+initialUserMessage로 대체 |
| **SR-03** | SKILL.md가 전 surface에서 100줄 로드 | SRP | **HIGH** | 10줄 최소화, additionalContext로 JARVIS에만 주입 |
| **CA-03** | Bash grep false positive | 아키텍트 | **MED** | 쓰기 패턴만 감지 |
| **SS-01** | 임계값 2곳 하드코딩 | SSOT | **MED** | metric-dictionary.json에서 읽기 |
| **SS-02** | Red Flags 2곳 | SSOT | **MED** | SKILL.md에서 참조 링크만 |
| **SS-03** | GATE 규칙 3곳 분산 | SSOT | **MED** | Phase 1 주석, Phase 2 외부 config |
| **D1** | jq 미설치 환경 | 의존성 | **MED** | fail-open 폴백 |
| CE-03 | deferred-issues 위치 | 엣지케이스 | LOW | cmux-jarvis/ 추가 |
| SR-01 | gate.sh 3역할 | SRP | LOW | 내부 함수 분리 |
| D2 | JARVIS↔Watcher 순환 | 의존성 | LOW | Phase 1 범위 한정 |
| D3 | /tmp/ 소실 | 의존성 | LOW | 재부팅 후 /cmux-start 필수 |
