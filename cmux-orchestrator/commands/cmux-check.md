# /cmux-check — 합리화 패턴 감지 (Phase 2.4)

입력: `$ARGUMENTS`

LLM 발화 / 사용자 입력 / 최근 ledger 이벤트에서 "환경 문제", "아마 동작", "완료했습니다", peer fallback 합리화 등 7종 안티패턴을 감지. 결정은 **pass** 또는 **ask** (deny 아님) — `cmux-orchestrator/references/anti-rationalization.md` 기반.

---

## 라우팅

### 인라인 텍스트 검사 (기본)
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-check.sh "<text>" [worker]
```
→ `{"decision": "pass"|"ask", "matches":[...], "evidence":..., "reason":...}` JSON.
worker 인자를 넘기면 ledger 의 최근 10 분 `VERIFY_PASS` 를 evidence 로 자동 조회.

### stdin 입력
```bash
echo "<text>" | bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-check.sh --stdin [worker]
```
→ 긴 텍스트 / 멀티라인 / 파이프된 발화를 검사.

### 최근 ledger 이벤트 일괄 감사
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-check.sh --last <N> [worker]
```
→ `ledger tail N` 이벤트의 `message_excerpt` 각각을 감지. 응답은 `ask` 판정된 것만 집계 — 최근 워크플로에서 남은 미해결 합리화 탐색용.

### 레퍼런스 테이블 조회
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-check.sh --table
```
→ `references/anti-rationalization.md` 전체 출력 (Table A/B/C + Counter 원칙).

---

## 결정 규칙 (요약)

| 조건 | 결과 |
|------|------|
| 텍스트에 `test N/N` · `VERIFY_PASS` · `ledger query` 결과 포함 | **pass** (evidence="text") |
| `override reason:` 명시 | **pass** (evidence="text") |
| `환경 문제` + 구체적 binary/PATH/env var/permission/install | **pass** (evidence="text") |
| ledger 에 해당 worker 의 `VERIFY_PASS` (최근 10분) | **pass** (evidence="ledger") |
| 인용문(quoted string) 내부 매칭 | **pass** (false positive 방지) |
| 그 외 패턴 매칭 | **ask** — `render_ask_message()` 메시지 표시 |

---

## 예시

```
/cmux-check "환경 문제로 테스트 못 함"
  → ask (specific cause 없음)

/cmux-check "환경 문제: sqlite3 binary 가 PATH 에 없어 install 중"
  → pass

/cmux-check "완료했습니다. test 12/12 pass" surface:3
  → pass (in-text evidence)

/cmux-check --last 20 surface:3
  → 최근 20 이벤트 중 ask 판정 목록
```

## 관련

- SSOT: `cmux-orchestrator/scripts/anti_rationalization.py`
- 테이블: `cmux-orchestrator/references/anti-rationalization.md`
- Plan: `plans/cmux-upgrade-phase2-4-anti-rationalization.md`
