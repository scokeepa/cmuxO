# Palace Memory SSOT

> 정본. cmux Mentor Lane의 메모리 구조, 4계층 로딩 정책, 저장소 스키마를 정의한다.
> 원천: `referense/mempalace-main/`의 palace model + mempalace 3.1.0 패키지. **ChromaDB 기반 시맨틱 검색**.

## cmux 용어 매핑

mempalace의 palace 구조를 cmux 오케스트레이션 맥락으로 변환한다.

| mempalace 원어 | cmux 매핑 | 설명 |
|---------------|-----------|------|
| wing | person / project / department | 최상위 분류. 사용자, 프로젝트, 부서 단위 |
| room | topic / feature / failure class / mentoring axis | wing 안의 주제 단위 |
| hall | fact / event / discovery / preference / advice | room 안의 관계 유형 |
| tunnel | cross-wing room | 같은 room이 여러 wing에 걸칠 때의 연결 |
| closet | derived summary | raw drawer에서 파생된 요약 포인터 |
| drawer | raw verbatim source | 원문 대화 발췌 (opt-in 전용) |

## 4계층 로딩 정책

mempalace의 L0~L3 패턴을 cmux에 맞춰 적용한다.

| 계층 | 이름 | 토큰 예산 | 저장 위치 | 로딩 시점 |
|------|------|-----------|-----------|-----------|
| L0 | Identity | ~100 token | `~/.cmux-jarvis-palace/identity.txt` | 세션 시작 시 항상 |
| L1 | Essential Story | ~500-800 token | ChromaDB palace 실시간 생성 (wing=cmux_mentor) | 세션 시작 시 항상 |
| L2 | On-Demand | ~200-500 token/회 | ChromaDB palace query (wing=cmux_mentor) | 사용자 요청 시 |
| L3 | Deep Search | 무제한 | ChromaDB semantic search (all-MiniLM-L6-v2) | evidence 부족 시에만 |

**Wake-up 비용**: L0 + L1 합산 **600~900 token** 이내. 컨텍스트 윈도우의 95% 이상을 작업에 사용 가능.

### L0 — Identity

고정 텍스트. cmux CEO 사용자의 기본 정체성을 기술한다.

```markdown
## L0 — IDENTITY
cmux 오케스트레이션 시스템의 CEO 사용자.
Boss, Watcher, JARVIS로 구성된 컨트롤 타워를 운영.
부서별 팀장-팀원 구조로 멀티 AI 작업을 조율.
```

파일이 없으면 위 기본값을 자동 생성한다. 사용자가 직접 수정 가능.

### L1 — Essential Story

ChromaDB palace에서 `wing=cmux_mentor` 쿼리로 실시간 생성한다.

- 최대 15개 signal에서 top moments 추출
- MAX_CHARS = 3200 (~800 token)
- importance(confidence * evidence_count) 기준 정렬
- 표본 부족 시 "아직 충분한 관찰이 없습니다." 출력

### L2 — On-Demand

사용자 또는 Boss/JARVIS가 특정 주제를 요청할 때 ChromaDB `col.get(where={"wing": ..., "room": ...})` 기준으로 필터한다.

### L3 — Deep Search

ChromaDB 시맨틱 벡터 검색. `col.query(query_texts=["검색어"])` 로 의미 기반 검색을 실행한다. all-MiniLM-L6-v2 embedding 모델 사용 (로컬 ONNX).

## 저장소 구조

```
~/.cmux-jarvis-palace/                    # ChromaDB PersistentClient 경로
├── identity.txt                           # L0 identity (사용자 수정 가능)
├── chroma.sqlite3                         # ChromaDB 내부 DB
└── (ChromaDB internal files)

Collection: cmux_mentor_signals
Wings: cmux_mentor, cmux_nudge, cmux_reports, cmux_timeline, cmux_coaching
```

기존 운영 메모리(`~/.claude/memory/cmux/`)와 완전히 분리된다.

## Signal Schema

`signals.jsonl` 1행 형식:

```json
{
  "ts": "2026-04-11T12:00:00Z",
  "signal_id": "sig-1712000400",
  "round_id": "round-5",
  "window_size": 5,
  "scores": {
    "decomp": 0.75, "verify": 0.45, "orch": 0.80,
    "fail": 0.60, "ctx": 0.70, "meta": 0.50
  },
  "fit_score": 3.2,
  "harness_level": 3.5,
  "antipatterns": ["context_skip"],
  "coaching_hint": "완료 조건을 명시하면 재작업률이 줄어듭니다.",
  "confidence": 0.6,
  "evidence_count": 5,
  "calibration_note": "ok"
}
```

필수 필드: `ts`, `signal_id`, `scores`, `confidence`, `evidence_count`, `calibration_note`.

`calibration_note` 값:
- `"ok"`: 충분한 근거
- `"insufficient_evidence"`: evidence_count < 3 또는 confidence < 0.5

## Drawer Schema (opt-in, Phase 3+)

opt-in raw drawer 1행 형식:

```json
{
  "drawer_id": "drawer_{wing}_{room}_{hash24}",
  "wing": "project_cmux",
  "room": "orchestration_setup",
  "content": "원문 대화 발췌...",
  "source": "user_instruction",
  "filed_at": "2026-04-11T12:00:00Z",
  "importance": 3.0,
  "chunk_index": 0
}
```

## Triple Schema (Phase 3+)

knowledge graph triple:

```json
{
  "triple_id": "t_{subject}_{predicate}_{object}_{hash}",
  "subject": "user",
  "predicate": "prefers",
  "object": "explicit_completion_criteria",
  "valid_from": "2026-04-01",
  "valid_to": null,
  "confidence": 0.8,
  "source_signal": "sig-1712000400"
}
```

## 기존 agent-memory.sh와의 관계

| 영역 | 저장소 | SSOT |
|------|--------|------|
| orchestration events | `~/.claude/memory/cmux/journal.jsonl` | agent-memory.sh |
| aggregated memories | `~/.claude/memory/cmux/memories.json` | agent-memory.sh |
| mentor signals | `~/.cmux-jarvis-palace` (ChromaDB, wing=cmux_mentor) | jarvis_mentor_signal.py |
| session context | `~/.claude/cmux-jarvis/mentor/context/` | jarvis_palace_memory.py |
| JARVIS telemetry | `~/.claude/cmux-jarvis/telemetry/` | jarvis_telemetry.py |

각 저장소는 독립적이다. 하나의 `memories.json`에 합치지 않는다.

## Export / Import / Backup

### Export

mentor 데이터를 단일 JSON 파일로 내보낸다.

```bash
python3 jarvis_palace_memory.py export --output /path/to/export.json
```

포맷 (v2, ChromaDB-based):
```json
{
  "format": "cmux_mentor_export",
  "version": 2,
  "exported_at": "ISO-8601",
  "palace_path": "~/.cmux-jarvis-palace",
  "drawers": [
    {"id": "drawer-id", "document": "텍스트", "metadata": {"wing": "...", "room": "...", "ts": "..."}}
  ]
}
```

embedding은 포함하지 않으며, import 시 ChromaDB가 자동 re-embed한다.

### Import

```bash
python3 jarvis_palace_memory.py import --input /path/to/export.json
```

- **format/version 검증**: `cmux_mentor_export` + version ≤ 2만 허용. 미래 버전은 거부 (forward-compat rejection)
- **drawer dedup**: `id` 기반. 이미 존재하면 skip (기본값). `--no-skip-existing` 플래그로 비활성화 가능
- **batch**: 100개 단위로 `col.add()` 호출

### Backup

```bash
python3 jarvis_palace_memory.py backup [--max-backups 5]
```

- `~/.cmux-jarvis-palace/` → `cmux-jarvis-palace-backup-YYYYMMDD-HHMMSS/` 복사
- 무결성 검증: 백업 내 SQLite `PRAGMA integrity_check`
- retention: `--max-backups N`으로 오래된 백업 자동 정리 (기본 5)

### Restore

```bash
python3 jarvis_palace_memory.py restore --backup-path /path [--dry-run] [--overwrite]
```

- SQL 직접 추출 기반 복원 (mempalace/migrate.py 패턴)
- ChromaDB 0.6.x에서 copytree 복원 시 disk I/O error가 발생하므로, 백업 SQLite에서 raw SQL로 drawer를 추출하여 새 palace에 import
- `--dry-run`: drawer 수/wing 분포만 출력
- `--overwrite`: 기존 palace를 덮어쓰기 (미지정 시 자동 export 후 교체)

### Embedding 정책

cmux palace memory는 ChromaDB PersistentClient 기반이다.
- 검색은 ChromaDB 내장 embedding (all-MiniLM-L6-v2, ONNX 로컬) 기반 시맨틱 검색
- export/import 시 embedding은 포함하지 않으며, import 시 ChromaDB가 자동 재생성
- signals.jsonl은 레거시 마이그레이션 소스로만 사용 (`migrate` 명령)

## SRP

Palace Memory SSOT는 **저장 구조, 스키마, 로딩 정책만** 담당한다.

담당하지 않는 것:
- scoring 기준 정의 → Mentor Ontology
- 조언 생성 → Mentor Lane
- 프라이버시/retention → Mentor Privacy Policy
- 진화 적용 → Evolution Lane
- context injection 실행 → cmux-main-context.sh

## 참조

- Mentor Privacy Policy: [mentor-privacy-policy.md](mentor-privacy-policy.md)
- Mentor Ontology: [mentor-ontology.md](mentor-ontology.md)
- 원천: `referense/mempalace-main/mempalace/layers.py`
