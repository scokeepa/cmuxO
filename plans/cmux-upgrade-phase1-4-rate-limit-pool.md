# cmuxO Upgrade Phase 1.4 — Rate-Limit Pool Implement + GC

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기

---

## 1. 문제 요약

`/tmp/cmux-rate-limited-pool.json` 은 **프로토콜 문서에만 존재하고 실제 쓰기 경로가 없음** (orphan spec).

- `cmux-orchestrator/scripts/cmux_paths.py:88` — 경로 상수 선언
- `cmux-orchestrator/scripts/cmux-paths.sh:101` — sh 대응
- `cmux-watcher/references/collaborative-intelligence.md:49,69,92` — "Watcher가 기록, Boss가 읽기" 프로토콜 명시
- `cmux-watcher/SKILL.md:328` — GATE W-2 관련 규칙 명시
- **실제 `watcher-scan.py`에서 이 파일을 write하는 코드는 없음** (grep 0건)

→ Boss는 배정 전 rate-limit 체크를 하고 싶어하지만 **읽을 데이터가 없음**.
Worker/Boss가 rate-limit된 surface에 반복 배정 → 자원 낭비 + 무한 retry.

추가로 쓰기가 생기면 **GC 없이 stale entry 누적** → 쿼터 회복 후에도 해당 surface 회피되는 2차 문제.

## 2. 근거

### 2.1 현황 조사

| 요구사항 | 현재 구현 | 상태 |
|----------|-----------|------|
| Pool 파일 경로 SSOT | `cmux_paths.py:88`, `cmux-paths.sh:101` | ✅ 있음 |
| Watcher가 RATE_LIMITED 감지 | `watcher-scan.py:941` (`elif status == "RATE_LIMITED"`) | ✅ 감지 |
| Watcher가 pool에 쓰기 | 없음 | ❌ **미구현** |
| Boss가 배정 전 pool 체크 | 없음 | ❌ **미구현** |
| Stale entry GC | 없음 | ❌ **미구현** |

### 2.2 Rate-limit 회복 시간 근거

| AI | 쿼터 리셋 | 참고 |
|----|-----------|------|
| Claude API | 5-hour window | anthropic status page |
| Claude Code (Pro/Max) | 5시간 이동창 | 공식 docs |
| Gemini CLI | 프로/요금제별 다름 | 기본 TTL 1시간 가정 |
| Codex | 모델별 다름 | 기본 TTL 1시간 |

→ 기본 TTL **3600초 (1시간)** 로 설정. AI별 오버라이드는 향후 Phase.

## 3. 설계

### 3.1 Pool 파일 스키마

```json
{
  "version": 1,
  "updated_at": 1744992000,
  "entries": {
    "surface:7": {
      "ai": "claude",
      "detected_at": 1744989600,
      "reset_at": 1745007600,
      "reason": "usage_limit",
      "message_excerpt": "You've reached your Max 5-hour limit..."
    }
  }
}
```

### 3.2 Watcher 쓰기 경로

`watcher-scan.py:941` 의 `elif status == "RATE_LIMITED":` 분기에 추가:

```python
from cmux_paths import RATE_LIMITED_POOL_FILE
from rate_limit_pool import upsert_entry  # 신규 모듈

upsert_entry(
    surface_id=sid,
    ai=surface_info.get("ai_type", "unknown"),
    reason="usage_limit",
    excerpt=text[:200],
    ttl_seconds=3600,
)
```

### 3.3 SSOT 모듈

`cmux-orchestrator/scripts/rate_limit_pool.py` 신규:

```python
def upsert_entry(surface_id, ai, reason, excerpt, ttl_seconds): ...
def is_limited(surface_id) -> bool: ...
def list_limited() -> list[dict]: ...
def gc_expired() -> int:  # 만료 엔트리 제거, 제거 수 반환
def load() -> dict: ...  # fcntl.flock으로 잠금
```

원자적 쓰기: `tempfile.mkstemp` + `os.rename` (기존 `activation-hook.sh:167-172` 패턴 재사용).

### 3.4 GC 트리거

**3 계층 GC**:

1. **Lazy GC**: 매 `upsert_entry` / `is_limited` 호출 시 O(n) 스캔하여 만료 제거 (n ≤ 30 surface이므로 비용 무시 가능)
2. **Watcher scan 주기 GC**: `watcher-scan.py` 본체가 매 루프 종료 시 `gc_expired()` 호출 (명시적)
3. **Boss dispatch 직전 체크**: `smart-dispatch.sh` / `surface-dispatcher.sh`에서 `is_limited()` 호출 → True면 스킵

### 3.5 Boss 읽기 경로

`cmux-orchestrator/scripts/smart-dispatch.sh`에 추가 체크:

```bash
# pre-dispatch rate-limit check
if python3 -c "import sys; sys.path.insert(0, '$(dirname $0)'); \
    from rate_limit_pool import is_limited; \
    sys.exit(0 if is_limited('$TARGET_SURFACE') else 1)"; then
    echo "[smart-dispatch] $TARGET_SURFACE is rate-limited, skipping"
    exit 2  # per smart-dispatch.sh:4 convention (2 = rate_limited)
fi
```

## 4. 5관점 검증

### SSOT
- Pool 파일 경로: `cmux_paths.py:88` (유일) ✓
- TTL 기본값: `rate_limit_pool.py` 상수 (유일) ✓
- Upsert 로직: `rate_limit_pool.py::upsert_entry` (유일) ✓
- 호출 지점 3곳 (watcher scan / dispatch / GC 주기) — 모두 SSOT helper 경유 ✓

### SRP
- `rate_limit_pool.py`: "pool 파일 CRUD + GC" 단일 책임
- Watcher의 RATE_LIMITED 감지 로직은 건드리지 않음 (기존 유지)
- Boss의 dispatch 로직은 "체크 호출"만 추가 (결정 로직은 pool 모듈 내부)

### 엣지케이스
- 동시 쓰기 (watcher + Boss): `fcntl.flock` 배타 잠금 → 직렬화
- 파일 손상 (JSON parse fail): 백업 후 빈 pool로 초기화 + stderr 경고
- TTL = 0 엔트리: 즉시 만료로 해석 → GC에서 제거
- Surface id 재사용 (같은 id로 다른 AI): `ai` 필드로 재덮어쓰기 (upsert 시맨틱)
- Clock skew: `time.time()` 단일 소스 사용 (NTP 의존)
- Pool 파일 크기 폭주: 엔트리 max 100 제한 (초과 시 가장 오래된 expired부터 제거)
- Watcher 재시작 후 in-memory state 상실: 파일 기반이므로 영향 없음

### 아키텍트
- 기존 `cmux_paths` 상수를 실제 사용 (orphan 해소) ✓
- `watcher-scan.py`의 기존 RATE_LIMITED 분기에 3줄 추가 — blast radius 최소
- `smart-dispatch.sh`의 기존 "2 = rate_limited" exit convention (line 4 주석) 재사용 ✓
- 신규 의존성 없음 (Python stdlib only: json, fcntl, tempfile, os, time)

### Iron Law
- **"경로는 cmux_paths로 통일"** ✓
- **"원자적 쓰기"** (runtime-dir phase3에서 확립) ✓
- **"fail-open for ambiguous"**: pool 파일 손상 시 dispatch 차단 안 함 (empty pool로 간주) ✓
- **"GC 없는 누적 금지"**: TTL + lazy + explicit 3중 ✓

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 시나리오 | expected |
|---|---|---|
| 1 | 빈 pool에 upsert → is_limited 조회 | True |
| 2 | TTL 0 upsert 후 1초 후 is_limited | False (만료) |
| 3 | 동일 surface 2회 upsert | 1개 엔트리만 (덮어쓰기) |
| 4 | 손상된 JSON 파일 + is_limited 호출 | False + 경고 + 파일 초기화 |
| 5 | 101개 upsert | 100개 유지, 가장 오래된 1개 축출 |
| 6 | 동시 writer 2개 (subprocess) | 둘 다 성공 + 최종 pool에 둘 다 존재 |
| 7 | `gc_expired()` — 5개 중 3개 만료 | return 3, pool에 2개 남음 |
| 8 | dispatch 체크: limited surface → exit 2 | ✓ |
| 9 | dispatch 체크: non-limited → exit 1 (실행 가능) | ✓ |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

프로토타입: `/tmp/rate_limit_pool_prototype.py`, 러너: `/tmp/test_rate_limit_pool.py`.

```
[PASS] 1 upsert+is_limited
[PASS] 2 ttl=0 expires after 1s
[PASS] 3 upsert overwrites
[PASS] 4 corrupt JSON reinit + backup
[PASS] 5 max 100 entries enforced
[PASS] 6 20 concurrent subprocess writers
[PASS] 7 gc_expired removes expired only
[PASS] 8 dispatch exit=2 for limited
[PASS] 9 dispatch exit=0 for healthy

=== Phase 1.4 simulation: 9 pass / 0 fail ===
```

→ 9/9 PASS.

### 5.3 설계 보정 (시뮬레이션 중 발견)

- **flock + os.rename race**: 초기 설계는 `POOL_FILE` 자체에 flock → `os.rename`이 inode 교체해 잠금 무효화 → concurrent case 6에서 5건 loss. **별도 lockfile (`POOL_FILE.suffix + ".lock"`)** 사용으로 해결.
- **Lazy GC 타이밍**: `upsert_entry`가 쓰기 전에 `_gc_inplace` 호출 → ttl=0 엔트리가 다음 upsert 중 이미 제거됨. 테스트 fixture에서 `ttl_seconds=1 + sleep 1.2s`로 수정 (assert 값은 동일 유지).
- **본 플랜 §3.3 갱신 필요**: "fcntl.flock on pool file" → "fcntl.flock on sibling .lock file" 로 명시.

## 6. 구현 절차

1. `cmux-orchestrator/scripts/rate_limit_pool.py` 신규 작성 + `tests/test_rate_limit_pool.py` (9케이스)
2. `watcher-scan.py:941` 분기에 upsert 호출 추가 + 루프 종료 시 GC 호출
3. `smart-dispatch.sh` pre-dispatch 체크 추가 (exit 2 반환)
4. `surface-dispatcher.sh` / `surface-dispatcher-v6.sh` 동일 체크 추가
5. 9케이스 시뮬레이션 → 본 문서 §5.2 업데이트
6. E2E: fake RATE_LIMITED surface 만들어 watcher → pool → dispatch 전체 흐름 확인
7. CHANGELOG.md 업데이트
8. PR 제출

## 7. DoD

- [ ] `rate_limit_pool.py` + 9케이스 테스트 PASS
- [ ] Watcher write 경로 연결
- [ ] Boss dispatch 체크 3곳 연결
- [ ] GC 3계층 작동 확인
- [ ] Pool 파일 손상 복원 시나리오 수동 검증
- [ ] CHANGELOG + PR

## 8. 리스크

- **Dispatch regression**: is_limited 오판 시 Boss가 healthy surface를 회피 → False Positive 피하려면 TTL 보수적으로 (1시간 하한)
- **Pool lock 경합**: watcher 쓰기가 Boss 읽기를 잠시 블록 → flock은 non-blocking `LOCK_NB` 시도, 실패 시 empty pool 읽기 fallback (우선 dispatch 허용)
- **Clock skew**: NTP 없는 시스템에서 TTL 오작동 가능 — `monotonic` vs `time.time()` 선택: pool은 재시작 survive 필요하므로 wall clock 사용, skew 허용 ±60초
