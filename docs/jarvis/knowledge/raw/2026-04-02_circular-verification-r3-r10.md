# JARVIS 순환검증 3차~10차 (일괄)

**날짜:** 2026-04-02
**이전 결과:** R1(9건) → R2(2건 LOW) → 수렴 추세
**방법:** 이전 라운드에서 발견 못 한 관점을 계속 변경하며 검증

---

## R3: 시간축 검증 — 진화 1건의 전체 타임라인이 일관적인가

**시나리오:** evo-001 실행 full timeline

```
T+0m  ① 감지: dispatch_failure_rate > 20%
T+1m  무한 루프 체크 → 연속 0회, 일일 0회 → PASS
T+1m  CURRENT_LOCK 확인 → 없음 → 진행
T+2m  ② 분석: settings.json에 traits inject 누락 발견
T+3m  ③ 1차 승인: cmux notify → [수립] 선택
T+4m  ④ 백업: 3중화 + CURRENT_LOCK(TTL 60분) + /freeze
T+7m  ⑤ 계획: DAG 3태스크 + evolution_type="settings_change"
T+8m  ⑤-b 2차 승인: diff 표시 → [실행] 선택
T+9m  ⑥ 검증: spec-reviewer → 스펙 준수 확인
T+12m ⑦ TDD: expected outcome 문서화 (설정 변경)
T+13m Worker pane 생성 + 마커 파일
T+15m ⑧ Worker 구현: proposed-settings.json + file-mapping.json 생성
T+17m Worker STATUS = DONE + cmux send "DONE"
T+17m ⑨ jarvis-verify.sh: JSON 유효, checksum 비교
T+18m ⑩ Before/After: 10분 관찰 시작
T+28m ⑩ 관찰 완료 → 사용자에게 diff → [KEEP]
T+29m ⑪ JSON Patch 적용 + CURRENT_LOCK 해제 + /freeze 해제
T+30m Obsidian 문서 저장 + Worker pane 정리
```

**발견:**
- T+4m~T+29m = 25분간 CURRENT_LOCK 보유. TTL 60분 이내 → OK ✓
- T+3m 1차 승인에서 30분 타임아웃 → 최악 T+33m. T+4~T+29 + T+33 = 62분 > TTL 60분
  → **1차 승인에서 29분 대기 + 진화 25분 = 54분. TTL 안에 들어옴** ✓
  → 하지만 2차 승인에서도 30분 대기 가능: T+7m 계획 + T+37m 2차 대기 = T+44m. 잔여 TTL 16분.
  → T+44m + Worker 15분 = T+59m. **TTL 60분에 아슬아슬**

**이슈 R3-01:** 두 번의 승인 대기(각 30분 최대)를 포함하면 TTL 60분이 빠듯하다.
**해결안:** TTL은 ④ 백업 시점부터 시작. 승인 대기는 ④ 이전이므로 TTL에 포함 안 됨.
→ 재확인: CURRENT_LOCK은 ④에서 생성. 1차 승인은 ③, 2차 승인은 ⑤-b.
→ **2차 승인(⑤-b)은 LOCK 생성(④) 이후.** 2차에서 30분 대기 → TTL 소진 가능.
**수정:** CURRENT_LOCK TTL을 **④ 생성 시점이 아닌 ⑤-b 승인 완료 시점부터** 재설정.
또는 TTL을 **120분**으로 상향.
**심각도:** MEDIUM

---

## R4: 데이터 흐름 검증 — 정본 마크다운 ↔ 로컬 캐시 동기화

**시나리오:** 모드 A에서 진화 문서 저장

```
JARVIS가 evo-001 결과를 Obsidian에 저장
  → {OBSIDIAN_VAULT}/JARVIS/Evolutions/evo-001.md (정본)

동시에 로컬 캐시:
  → ~/.claude/cmux-jarvis/evolutions/evo-001/ (STATUS, nav.md, 01~09)

질문: 로컬 evolutions/evo-001/와 Obsidian Evolutions/evo-001.md는 같은 데이터의 다른 형식?
```

**발견:**
- Obsidian: 단일 .md 파일 (wikilink + properties + callouts)
- 로컬: 9개 파일 (01-detection.md ~ 09-result.md + STATUS + nav.md)
- **형식이 완전히 다름.** 어느 쪽이 정본?

**이슈 R4-01:** 진화 문서가 로컬(9파일)과 Obsidian(1파일)에서 다른 형식으로 존재.
단일 정본 원칙과 모순 가능성.
**해결안:** 역할 분리:
- 로컬 9파일 = **실행 중 작업 파일** (Worker가 단계별로 생성, 임시)
- Obsidian 1파일 = **완료 후 정본** (⑪ 이후 생성, 9파일을 통합 요약)
- 로컬 9파일은 진화 완료 후 **보존하되 캐시 취급** (Obsidian이 정본)
**심각도:** LOW — 설계 명확화만 필요.

---

## R5: 실패 경로 검증 — 모든 DISCARD/실패 시나리오가 안전한가

**시나리오 A:** ⑤→⑨ 순환 2회 실패 → DISCARD

```
1회차: ⑨ 검증 실패 → ⑤로 돌아감
2회차: ⑨ 검증 실패 → DISCARD
  → 자동 롤백: backup/settings.json 복원
  → CURRENT_LOCK 해제
  → /freeze 해제
  → failure 문서 저장 (Obsidian)
  → Worker pane 정리
  → evolution-queue.json에서 다음 진화 처리
```
**검증:** 각 단계 누락 없음. ✓

**시나리오 B:** Worker 비정상 종료 → Circuit Breaker

```
Worker pane kill (SIGKILL)
  → JARVIS가 STATUS 폴링 (5초 간격, 30분 타임아웃)
  → Worker PID 사망 감지 (kill -0 실패)
  → Circuit Breaker: retry_count < 1 → 재시도
  → 새 Worker pane 생성 → 재실행
  → 2번째 실패 → retry_count >= 1 → DISCARD + 롤백
```
**검증:** 마커 파일 `/tmp/cmux-jarvis-worker-{PID}` 잔존 → JARVIS 재시작 시 정리. ✓

**시나리오 C:** JARVIS 자체 크래시 (진화 중)

```
JARVIS pane 사망 (T+15m, ⑧ 진행 중)
  → CURRENT_LOCK 남아있음 (TTL 60분)
  → Worker는 계속 실행 (독립 pane)
  → Worker 완료 → cmux send "DONE" → JARVIS 없음 → 메시지 소실

/cmux-start 또는 JARVIS pane 재생성
  → jarvis_recovery_check() 실행
  → CURRENT_LOCK 존재 + STATUS.phase != completed
  → Worker PID 확인: 살아있으면 대기, 죽었으면 롤백
```
**발견:** Worker 완료 후 JARVIS가 없으면 cmux send 메시지 소실.
→ Worker가 STATUS 파일에도 기록하므로 JARVIS 복구 시 STATUS로 감지 ✓
**검증 통과.** 단, cmux send 소실은 정보 손실이지 기능 손실은 아님.

**R5 결과: 신규 이슈 없음.**

---

## R6: 보안 검증 — 악의적 사용/오용 시나리오

**시나리오 A:** 사용자가 JARVIS를 통해 다른 surface의 작업을 방해

→ JARVIS의 allowed-tools에 Write가 없음... 확인:
→ SKILL.md: `allowed-tools: Bash, Read, AskUserQuestion, WebSearch, WebFetch`
→ **Write/Edit 없음!** JARVIS가 직접 파일을 수정할 수 없다.
→ 그러면 ⑪ 반영에서 JSON Patch를 어떻게 적용하나?

**이슈 R6-01:** JARVIS의 allowed-tools에 Write/Edit이 없어서 설정 파일 적용 불가.
**해결안:** JARVIS에 Write/Edit 추가하되 GATE hook이 경로를 제한:
- Write/Edit 허용 경로: `~/.claude/settings.json`, `~/.claude/cmux-jarvis/`, Obsidian 볼트
- GATE hook이 그 외 경로를 deny
또는 `jarvis-evolution.sh apply` 명령으로 Bash를 통해 적용 (cp 명령).
**심각도:** HIGH — 이것을 수정하지 않으면 JARVIS가 진화 결과를 적용할 수 없음.

**시나리오 B:** 외부에서 evolution-queue.json을 조작

→ 큐에 악의적 진화 삽입? → JARVIS가 ② 분석에서 근본 원인 확인 → 실제 문제 없으면 폐기
→ settings.json 직접 조작은 JARVIS가 아닌 사용자/다른 프로세스 → JARVIS 범위 밖 ✓

**R6 결과: HIGH 1건 (R6-01).**

---

## R7: 일관성 검증 — 문서 내 상충하는 서술

**검색:** 문서 전체에서 모순되는 서술 쌍 찾기

1. L14 "Basic Memory WatchService가 파일→DB 단방향 동기화" vs L52 "Phase 1은 sqlite3 CLI + 자체 FTS5"
   → Phase 1에서는 Basic Memory 사용 안 함 → WatchService도 없음
   → L14의 다이어그램은 **Phase 3 이후 아키텍처**
   → Phase 1 다이어그램이 별도로 없음

**이슈 R7-01:** 상단 아키텍처 다이어그램이 Phase 3 기준이라 Phase 1과 불일치.
**해결안:** Phase 1 아키텍처 다이어그램을 별도 추가하거나, 기존 다이어그램에 "(Phase 3)" 라벨.
**심각도:** LOW — 혼란 방지용 라벨 추가.

2. L324 "A/B 테스트 구현 — jarvis-evolution.sh에서 처리" vs L160 "사용자에게 diff → [KEEP][DISCARD]"
   → L324는 구버전 설명 (자동 비교), L160은 수정된 설명 (사용자 판단)
   → L324 섹션이 아직 구버전 서술 잔재

**이슈 R7-02:** L324 "A/B 테스트 구현" 섹션이 구버전 서술 (자동 비교) 잔재.
**해결안:** L324 섹션을 Phase 1 기준으로 수정.
**심각도:** LOW — 구버전 잔재 정리.

3. 파일 번호 중복: L352 "15. metric-dictionary" vs L349 "15. jarvis-maintenance"
   → 번호 15가 2번 사용됨
**이슈 R7-03:** 파일 목록 번호 중복 (15번 2개).
**심각도:** 사소 — 번호 수정만.

**R7 결과: LOW 3건.**

---

## R8: 운영 검증 — 실제 cmux 환경에서의 호환성

1. **cmux send가 구조화된 선택지를 지원하는가?**
   → cmux send는 텍스트 전달. AskUserQuestion의 [수립][보류][폐기] 선택지는 **Claude Code가 렌더링**
   → JARVIS 세션 내에서 AskUserQuestion 호출 → Claude Code가 사용자에게 표시 → OK ✓

2. **cmux notify가 존재하는가?**
   → cmux 기존 명령어 확인 필요. 없으면 cmux send --surface main "알림" 으로 대체
   → 계획에서 cmux notify는 개념적 명칭일 수 있음
**이슈 R8-01:** cmux notify 명령이 실제로 존재하는지 확인 필요.
**해결안:** 존재하면 사용, 없으면 cmux send로 대체. 계획에 폴백 명시.
**심각도:** LOW — 구현 시 확인.

3. **Worker pane에서 Claude Code가 SKILL.md를 자동 로드하는가?**
   → cmux new-pane으로 생성된 Claude 세션이 evolution-worker.md를 어떻게 인식?
   → JARVIS가 cmux send로 "다음 진화 계획을 실행하세요: [계획 내용]"을 전달
   → Worker는 일반 Claude 세션 + JARVIS가 보낸 지시사항으로 동작
   → evolution-worker.md는 JARVIS가 Worker에게 보내는 프롬프트 템플릿
**이슈 없음.** Worker는 독립 SKILL이 아니라 JARVIS가 전달하는 프롬프트. ✓

**R8 결과: LOW 1건 (R8-01).**

---

## R9: 확장성 검증 — 장기 운영 시 문제

1. **evolutions/ 디렉토리가 무한히 쌓이면?**
   → 로컬: evo-001, evo-002, ... evo-500
   → 각 10파일 = 5000파일 → 디렉토리 성능 저하
   → Obsidian: evo-001.md ~ evo-500.md = 500 파일 → 볼트 검색 가능
**이슈 R9-01:** 장기 운영 시 evolutions/ 디렉토리 파일 수 증가.
**해결안:** 3세대 초과 로컬 evolutions/ 아카이브 (Obsidian에는 보존).
또는 연/월 하위 폴더: `evolutions/2026-04/evo-001/`
**심각도:** LOW — Phase 2에서 대응.

2. **FTS5 인덱스 크기 증가?**
   → sqlite3 FTS5는 수만 건까지 성능 유지 → 진화 500건 수준에서는 문제 없음 ✓

3. **config.json, evolution-queue.json 등 동시 접근?**
   → JARVIS만 접근 (단일 세션) → 동시성 문제 없음 ✓
   → 단, ConfigChange hook이 3 surface에서 동시 실행 → flock 해결 ✓

**R9 결과: LOW 1건 (R9-01).**

---

## R10: 최종 종합 검증 — Iron Law 3개가 전 파이프라인에서 지켜지는가

### Iron Law #1: "NO EVOLUTION WITHOUT USER APPROVAL"
| 단계 | 승인 지점 | 우회 가능성 |
|------|----------|-----------|
| ③ 1차 승인 | [수립] 필수 | 구조화 선택지 → 우회 불가 ✓ |
| ⑤-b 2차 승인 | [실행] 필수 | diff 표시 → 정보 비대칭 해소 ✓ |
| ⑩ KEEP/DISCARD | 사용자 선택 | Before/After diff → 증거 기반 ✓ |
| ⑪ 충돌 시 | AskUserQuestion | 사용자 해결 ✓ |
**위반 경로 없음.** ✓

### Iron Law #2: "NO IMPLEMENTATION WITHOUT EXPECTED OUTCOME"
| 단계 | 검증 지점 | 우회 가능성 |
|------|----------|-----------|
| ⑦ TDD/문서화 | Worker가 수행 | STATUS 필수 필드로 강제 ✓ |
| ⑥ spec-reviewer | 테스트 품질 검토 | trivial 테스트 감지 ✓ |
| STATUS 검증 | JARVIS가 체크 | evolution_type별 분기 ✓ (CV-09) |
**위반 경로:** Worker가 STATUS를 조작 (tests_failed_before_fix를 거짓으로 기입)?
→ Worker는 LLM이므로 의도적 거짓은 발생 어려움
→ 하지만 할루시네이션 가능 → ⑥ spec-reviewer가 실제 테스트 파일 존재 확인
→ 테스트 파일이 없으면 REJECT ✓
**위반 경로 봉쇄됨.** ✓

### Iron Law #3: "NO COMPLETION CLAIMS WITHOUT VERIFICATION EVIDENCE"
| 단계 | 증거 지점 | 우회 가능성 |
|------|----------|-----------|
| ⑨ jarvis-verify.sh | 사전 정의 스크립트 | AI 미개입 → 조작 불가 ✓ |
| ⑩ evidence 스키마 | before/after 필수 | 자동 수집 → 누락 불가 ✓ |
| STATUS 파일 | 증거 경로 포함 | 파일 부재 시 REJECT ✓ |
**위반 경로:** jarvis-verify.sh 자체를 수정하면?
→ cmux 패키지 사전 포함 → JARVIS/Worker가 수정 불가 (evolutions/ 외부)
→ GATE hook이 차단 ✓
**위반 경로 봉쇄됨.** ✓

---

## R3~R10 전체 결과

| 라운드 | 관점 | 발견 | HIGH | MED | LOW |
|--------|------|------|------|-----|-----|
| R3 | 시간축 | TTL 빠듯 | 0 | 1 | 0 |
| R4 | 데이터 흐름 | 로컬/Obsidian 형식 차이 | 0 | 0 | 1 |
| R5 | 실패 경로 | 전부 안전 | 0 | 0 | 0 |
| R6 | 보안 | allowed-tools Write 누락 | **1** | 0 | 0 |
| R7 | 일관성 | 구버전 잔재 3건 | 0 | 0 | 3 |
| R8 | 운영 호환 | cmux notify 확인 | 0 | 0 | 1 |
| R9 | 확장성 | evolutions 증가 | 0 | 0 | 1 |
| R10 | Iron Law 종합 | 3개 모두 봉쇄 확인 | 0 | 0 | 0 |
| **합계** | | | **1** | **1** | **6** |

### 즉시 수정 필요: HIGH 1건

**R6-01: JARVIS allowed-tools에 Write/Edit 없어 설정 적용 불가**
- SKILL.md: `allowed-tools: Bash, Read, AskUserQuestion, WebSearch, WebFetch`
- 진화 결과 반영(⑪)에서 settings.json 수정 필요 → Write 없으면 불가
- **해결:** Bash를 통해 `jarvis-evolution.sh apply evo-001` 실행 → 스크립트가 cp/mv로 적용
- 또는 allowed-tools에 Write 추가 + GATE hook이 허용 경로만 통과

### MEDIUM 1건

**R3-01: 2차 승인이 CURRENT_LOCK 이후 → TTL 빠듯**
- **해결:** ⑤-b 승인 완료 시 CURRENT_LOCK의 created_at를 현재 시각으로 갱신 (TTL 리셋)

### LOW 6건 (Phase 2 백로그)
- R4-01: 로컬 9파일 = 작업 파일, Obsidian 1파일 = 정본 (설계 명확화)
- R7-01: 상단 다이어그램에 "(Phase 3)" 라벨
- R7-02: L324 A/B 구버전 서술 정리
- R7-03: 파일 번호 15 중복
- R8-01: cmux notify 폴백 명시
- R9-01: evolutions/ 연월 하위 폴더
