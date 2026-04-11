# mempalace ChromaDB 전면 전환 계획

## Context

기존 JSONL+SQLite FTS5 기반 mentor memory를 mempalace ChromaDB로 전면 전환한다.

- **mempalace 3.1.0** 패키지 설치 확인됨 (`pip3 install` 성공, `import` 성공)
- **chromadb 1.5.7** 설치 확인됨
- **PR #499** 의 backup/export/import는 포크에서 가져옴

### 변경 범위

| 현재 (JSONL) | 전환 후 (mempalace ChromaDB) |
|-------------|---------------------------|
| signals.jsonl (append-only JSONL) | ChromaDB `cmux_mentor` collection의 drawers |
| palace/drawers/ (opt-in JSONL) | ChromaDB drawers (시맨틱 검색 가능) |
| L0.md/L1.md (직접 생성) | mempalace Layer0/Layer1 클래스 사용 |
| 키워드 검색만 | ChromaDB 시맨틱 벡터 검색 (L3) |
| mentor_redactor.py (독립) | 저장 전 redact → ChromaDB에 저장 |

### badclaude 역할 명확화

badclaude는 메모리 시스템이 아니다. AI가 느리거나 꾀를 부리거나 우회하려 할 때 **채찍질(nudge/interrupt)** 전용이다.
- `jarvis_nudge.py`는 그대로 유지 (cmux send 기반 L1 재촉)
- nudge audit 이벤트는 mempalace의 `cmux_nudge` wing에 drawer로 저장

### vibe-sunsang mempalace 연동

vibe-sunsang (6축 멘토링)의 데이터도 mempalace에 저장한다:
- 현재: `~/vibe-sunsang/exports/growth-report-*.md` + `TIMELINE.md` (파일 시스템)
- 변경: growth report → `cmux_reports` wing drawer, TIMELINE → `cmux_timeline` wing drawer
- 6축 score → `cmux_mentor` wing (축별 room)에 drawer
- 종단 비교 시 mempalace L2 검색으로 이전 report drawers를 조회

---

## Step 1: `cmux-jarvis/scripts/jarvis_palace_memory.py` 전면 재작성

mempalace 패키지를 직접 import해서 사용한다.

**핵심 변경**:

```python
from mempalace.layers import Layer0, Layer1, Layer2, Layer3, MemoryStack
from mempalace.palace import get_collection
from mempalace.config import MempalaceConfig
from mempalace.knowledge_graph import KnowledgeGraph
```

**Palace 경로**: `~/.cmux-jarvis-palace/` (mempalace 기본 `~/.mempalace/`와 분리)

**Wing 구조**:
- `cmux_mentor`: 6축 signal drawers (DECOMP/VERIFY/ORCH/FAIL/CTX/META scores + metadata)
- `cmux_nudge`: nudge audit drawers (target, issuer, reason, outcome)
- `cmux_reports`: 생성된 mentor reports
- `cmux_coaching`: coaching hints + user feedback

**Room 매핑**:
- `cmux_mentor/decomp`, `cmux_mentor/verify`, ... (축별)
- `cmux_nudge/stalled`, `cmux_nudge/idle`, ... (reason별)
- `cmux_reports/weekly`, `cmux_reports/roundly`

**CLI 유지** (기존 인터페이스 호환):
```
python3 jarvis_palace_memory.py generate-context  # L0+L1 (mempalace Layer0/Layer1 사용)
python3 jarvis_palace_memory.py status
python3 jarvis_palace_memory.py export --output ...  # PR #499 exporter.py 패턴
python3 jarvis_palace_memory.py import --input ...
python3 jarvis_palace_memory.py backup
python3 jarvis_palace_memory.py search "query"       # 신규: 시맨틱 검색
```

## Step 2: `cmux-jarvis/scripts/jarvis_mentor_signal.py` — ChromaDB 저장으로 전환

**기존**: `_append_signal()` → signals.jsonl에 JSONL append
**변경**: `_store_signal()` → ChromaDB `cmux_mentor` collection에 drawer로 저장

```python
def _store_signal(signal):
    col = get_collection(PALACE_PATH, "cmux_mentor_signals")
    doc = json.dumps(signal["scores"]) + " " + " ".join(signal.get("antipatterns", []))
    meta = {
        "wing": "cmux_mentor",
        "room": _weakest_axis(signal["scores"]),  # 가장 약한 축이 room
        "signal_id": signal["signal_id"],
        "ts": signal["ts"],
        "fit_score": signal["fit_score"],
        "harness_level": signal["harness_level"],
        "confidence": signal["confidence"],
        "coaching_hint": signal.get("coaching_hint", ""),
    }
    col.add(ids=[signal["signal_id"]], documents=[doc], metadatas=[meta])
```

**query**: ChromaDB `.get()` + `.query()` 사용
**prune**: ChromaDB에서 날짜 기반 삭제

**호환성**: 기존 signals.jsonl이 있으면 migration 명령으로 ChromaDB로 이관

## Step 3: `jarvis_nudge.py` — audit을 palace에 저장

nudge audit 이벤트를 `cmux_nudge` wing의 drawer로 저장.

```python
def _store_nudge_audit(event):
    col = get_collection(PALACE_PATH, "cmux_mentor_signals")
    doc = f"NUDGE {event['level']} → {event['target_surface_id']}: {event['evidence_span']}"
    meta = {
        "wing": "cmux_nudge",
        "room": event["reason_code"].lower(),
        **event,
    }
    col.add(ids=[f"nudge-{event['timestamp']}"], documents=[doc], metadatas=[meta])
```

기존 `nudge-audit.jsonl` 유지하되, ChromaDB에도 동시 저장 (검색 가능).

## Step 4: `jarvis_mentor_report.py` — signals를 ChromaDB에서 읽기 + report를 palace에 저장

`_read_signals()` → ChromaDB `col.get(where={"wing": "cmux_mentor"})` 사용
report 결과도 `cmux_reports` wing에 drawer로 저장.
TIMELINE 행도 `cmux_timeline` wing에 drawer로 저장 (종단 검색 가능).

vibe-sunsang growth-analyst의 report 패턴을 따르되, 저장소를 파일 시스템에서 mempalace palace로 전환:
- `growth-report-*.md` → `cmux_reports/weekly` room drawer
- `TIMELINE.md` 행 → `cmux_timeline/entries` room drawer
- 종단 비교 시 L2 `col.get(where={"wing": "cmux_reports"})` → 이전 report 조회

## Step 5: `jarvis_failure_classifier.py` — ChromaDB에서 signal 읽기

`_read_signals()` → ChromaDB 기반으로 전환

## Step 6: `cmux-main-context.sh` — mempalace L0/L1 사용

기존 직접 파일 읽기 → `python3 -c "from mempalace.layers import MemoryStack; ..."` 호출

## Step 7: PR #499 exporter 통합

포크의 `exporter.py` 핵심 로직 (backup + integrity validation + export/import)을 `jarvis_palace_memory.py`에 통합. `_read_all_drawers`, `_validate_backup`, `import_palace(skip_existing=True)` 패턴 적용.

## Step 8: 문서 업데이트

- `docs/02-jarvis/palace-memory.md` — JSONL → ChromaDB 전환 반영
- `docs/01-architecture/security.md` — ChromaDB 로컬 전용 명시

## Step 9: 테스트 전면 재작성

- 기존 test_palace_memory.py의 JSONL 테스트 → ChromaDB 테스트로 전환
- mempalace 테스트 패턴 (tmpdir + PersistentClient) 사용
- signal 시맨틱 검색 테스트 추가

## Step 10: identity.txt 설정

`~/.cmux-jarvis-palace/identity.txt` 생성:
```
cmux 오케스트레이션 시스템의 CEO 사용자.
Boss(Main), Watcher, JARVIS로 구성된 컨트롤 타워를 운영.
부서별 팀장-팀원 구조로 멀티 AI 작업을 조율.
```

---

## 수정 대상 파일

| # | 파일 | 작업 |
|---|------|------|
| 1 | `cmux-jarvis/scripts/jarvis_palace_memory.py` | 전면 재작성 (mempalace 사용) |
| 2 | `cmux-jarvis/scripts/jarvis_mentor_signal.py` | ChromaDB 저장 전환 |
| 3 | `cmux-jarvis/scripts/jarvis_nudge.py` | audit → palace drawer 추가 |
| 4 | `cmux-jarvis/scripts/jarvis_mentor_report.py` | signals 읽기 → ChromaDB |
| 5 | `cmux-jarvis/scripts/jarvis_failure_classifier.py` | signals 읽기 → ChromaDB |
| 6 | `cmux-orchestrator/hooks/cmux-main-context.sh` | mempalace L0/L1 사용 |
| 7 | `docs/02-jarvis/palace-memory.md` | ChromaDB 전환 반영 |
| 8 | `tests/test_palace_memory.py` | ChromaDB 기반 테스트 |
| 9 | `tests/test_mentor_signal.py` | ChromaDB 기반 테스트 |

> 9개 파일. 기존 파일 수정이지만 코드 로직 전면 전환.

## 검증 계획

| 단계 | 명령 | 기대 |
|------|------|------|
| mempalace import | `python3 -c "from mempalace.layers import MemoryStack"` | OK |
| py_compile | 5개 수정 스크립트 | exit 0 |
| signal 저장 | emit → ChromaDB에 drawer 생성 | drawer 존재 |
| 시맨틱 검색 | `search "verification"` → verify 관련 signal 반환 | 유사도 기반 결과 |
| L0/L1 생성 | mempalace Layer0/Layer1 → 600-900 token | 예산 준수 |
| 전체 테스트 | `python3 -m pytest tests/ -v` | 전부 passed |
| nudge audit | nudge → palace drawer 저장 | 검색 가능 |

## 플랜 품질 게이트

### 5관점 순환검증
1. **SSOT** — ChromaDB `~/.cmux-jarvis-palace/`가 유일 저장소. signals.jsonl은 migration 후 제거
2. **SRP** — mempalace가 저장/검색, cmux scripts가 비즈니스 로직(scoring/nudge/report)
3. **엣지케이스** — ChromaDB 미설치, palace 디렉터리 없음, 빈 collection, migration 중 중단
4. **아키텍트** — mempalace를 라이브러리로 사용. vendor 아닌 pip install 의존
5. **Iron Law** — 기존 API 인터페이스(CLI) 유지. 내부 저장소만 전환

### 코드 시뮬레이션 (`/tmp/test_chromadb_migration.py` 실행 완료)
- ChromaDB palace signal 저장+조회: **PASS**
- 시맨틱 검색 ("testing and validation" → sig-2 verify): **PASS**
- mempalace Layer0 identity: **PASS** (13 tokens)
- Nudge audit drawer 저장+필터: **PASS**
- Dedup (skip existing): **PASS** (1 skipped, 2 total)
- Backup: **PASS**
- ONNX embedding model (all-MiniLM-L6-v2) 캐시 완료
- **ALL PASS**

---

## 구현 완료 후 마무리 작업

### 1. 문서 체계 반영
- `docs/02-jarvis/palace-memory.md` 업데이트 (JSONL → ChromaDB)
- `docs/01-architecture/security.md` ChromaDB 로컬 전용 명시 추가
- `docs/00-overview.md` palace memory 설명 업데이트
- 이 플랜 파일 → `docs/99-archive/` 또는 삭제

### 2. README.md 업데이트
- JARVIS Mentor Lane 섹션: JSONL → ChromaDB 시맨틱 검색 반영
- Performance Indicators: 시맨틱 검색 지표 추가
- Prerequisites: `chromadb`, `mempalace` 의존성 추가

### 3. CHANGELOG.md 업데이트
- `feat: mempalace ChromaDB 전면 전환` 엔트리 추가

### 4. install.sh 업데이트
- `pip3 install mempalace` 또는 `pip3 install chromadb` 의존성 설치 단계 추가

### 5. 로컬 스킬 동기화
- `~/.claude/skills/cmux-jarvis` 재동기화
