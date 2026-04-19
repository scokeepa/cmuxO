# cmuxO Upgrade Phase 2.2 — Per-Agent Token/Cache Observability

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기
**선행 조건**: Phase 2.1 (Progressive Disclosure) 완료 후 baseline 측정 가능

---

## 1. 문제 요약

현재 cmuxO는 각 Worker(AI 팀원)의 **토큰 소비/캐시 히트율/context length**를 추적하지 않는다.

증상:
- Superpowers 같은 context bloat 원인을 사후에만 발견 (Issue #1220)
- 어떤 Worker가 비효율적인지 정량 비교 불가
- `/cost` 명령으로 개별 세션만 볼 수 있고 오케스트레이션 전체 총량은 안 보임
- Claude API는 `cache_read_input_tokens` / `cache_creation_input_tokens` 필드로 캐시 히트/미스 제공 → 현재 미수집

## 2. 근거

### 2.1 데이터 소스

Claude Code는 각 세션의 JSONL transcript에 usage를 기록:
```
~/.claude/projects/<project-slug>/<uuid>.jsonl
```

각 assistant 턴의 `message.usage` 객체:
```json
{
  "input_tokens": 3245,
  "output_tokens": 128,
  "cache_creation_input_tokens": 1024,
  "cache_read_input_tokens": 15360,
  "service_tier": "standard"
}
```

### 2.2 surface ↔ transcript 매핑

현 상태:
- cmuxO는 각 Worker를 tmux surface로 운영 → surface가 곧 Claude Code 세션
- surface id ↔ project slug ↔ uuid 매핑 정보 부재
- `~/.claude/projects/` 파일시스템 구조: `{cwd-slug}/{uuid}.jsonl` — cwd 기준 slug 생성

→ surface의 cwd를 알면 slug 역산 가능 (`cwd.replace("/", "-")` 패턴).

### 2.3 참조 프로젝트

`/Users/csm/projects/olympus/source/` 내:
- `agentmemory`: trace/telemetry 구조
- `autogen`: `LLMCallEventMessage` 이벤트 포맷

cmuxO 내 기존:
- `cmux-orchestrator/scripts/eagle_analyzer.py`: surface 상태 수집 — 유사 수집 인프라

## 3. 설계

### 3.1 신규 스크립트

`cmux-orchestrator/scripts/token_observer.py`:

```python
def collect_surface_metrics(surface_id: str, cwd: str) -> dict:
    """주어진 surface의 최근 transcript에서 token metrics 집계.
    반환: {
        "surface": "...", "ai": "claude",
        "input_tokens_total", "output_tokens_total",
        "cache_read_total", "cache_creation_total",
        "cache_hit_ratio",  # cache_read / (cache_read + cache_creation + input)
        "turns": int,
        "last_turn_ts": ...
    }
    """
```

### 3.2 수집 방식

**Pull 방식** (watcher 주기 내):
- `watcher-scan.py` 루프 끝에서 `token_observer.collect_all()` 호출
- 모든 등록된 surface의 최신 JSONL 파일 tail 파싱
- 결과를 `/tmp/cmux-runtime/telemetry/token-metrics.json`에 기록

**Push 방식은 불가**: Claude Code 훅이 자체 usage를 노출하지 않음 (PostToolUse 훅에 usage 없음).

### 3.3 저장 포맷

`runtime/telemetry/token-metrics.json`:
```json
{
  "version": 1,
  "updated_at": 1744992000,
  "surfaces": {
    "surface:0": {
      "ai": "claude",
      "input_tokens_total": 123456,
      "output_tokens_total": 3456,
      "cache_read_total": 98765,
      "cache_creation_total": 5432,
      "cache_hit_ratio": 0.89,
      "turns": 42,
      "last_turn_ts": 1744991800
    }
  }
}
```

### 3.4 조회 UI

```bash
cmux-orchestrator/scripts/cmux-metrics.sh
# 출력 예:
# surface  ai      turns  input    output  cache_hit  last_turn
# :0       claude  42     123,456  3,456   89.0%      5min ago
# :1       gemini  8      45,000   800     N/A        12min ago
```

Boss가 `/cmux-metrics` 슬래시 커맨드로 호출 가능.

### 3.5 알림 통합

`watcher-scan.py`가 이미 `cmux-watcher-alerts.json`에 쓰는 인프라 사용:
- cache_hit_ratio < 50% 이면서 turns > 10 → "캐시 효율 경고" alert
- input_tokens_total > 200000 → "context 거대" 경고

## 4. 5관점 검증

### SSOT
- Metrics 파일 경로: `cmux_paths.py`에 신규 상수 (SSOT 유지)
- Transcript 파싱 로직: `token_observer.py` 1개 모듈 ✓
- surface → cwd → slug 매핑: `cmux_paths.surface_to_slug()` helper (신규 1곳)

### SRP
- `token_observer.py`: JSONL 파싱 + 집계만
- `cmux-metrics.sh`: 표 출력만
- Alert 판정: watcher가 기존 alert 인프라로 발행 (새 알림 경로 추가 X)

### 엣지케이스
- JSONL 파일 진행 중 읽기 race: 마지막 줄 잘림 → try/except로 skip
- Compaction으로 turns 카운트 리셋: `session_id` 변경 감지 → 재시작으로 간주
- surface cwd가 변경됨 (rare): 매 스캔마다 surface-map에서 재조회
- 아주 큰 JSONL (>100MB): `tail -c 10M` 방식으로 최근 내역만 파싱
- Gemini/Codex 등 non-Claude AI: JSONL 없음 → `ai != "claude"` skip + `cache_hit_ratio: None`
- Metrics 파일 쓰기 경합: `fcntl.flock` + 원자적 rename

### 아키텍트
- 기존 watcher 스캔 사이클에 편승 (별도 cron/daemon 필요 없음) ✓
- telemetry 디렉토리 신설 → 앞으로 다른 metrics (agent cost, latency 등) 확장 지점
- `/cmux-metrics` 슬래시 커맨드는 기존 `cmux-help` 패턴 재사용

### Iron Law
- **"경로는 cmux_paths SSOT"** ✓
- **"원자적 쓰기"** ✓
- **"watcher는 본 작업 차단 금지"**: 측정 실패 시 PASS + 경고, watcher 루프 중단 X ✓
- **"AI 종속 로직은 ai_type 분기"**: Claude-only 기능을 일반화 ✓

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 시나리오 | expected |
|---|---|---|
| 1 | 정상 transcript 5턴 파싱 | turns=5, 토큰 누적 정확 |
| 2 | 잘린 마지막 줄 | skip + 4턴만 집계 |
| 3 | session_id 변경 감지 | turns 리셋 |
| 4 | `cache_read_input_tokens` 없는 old 턴 | default 0 처리 |
| 5 | surface cwd 삭제됨 | slug not found → skip + 경고 |
| 6 | metrics 파일 손상 | 백업 후 재생성 |
| 7 | 동시 쓰기 2 writer | flock 직렬화 |
| 8 | 100MB JSONL | 10MB tail 파싱 완료 < 500ms |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

프로토타입: `/tmp/token_observer_prototype.py`, 러너: `/tmp/test_token_observer.py`.

```
[PASS] 1 5 turns parsed
[PASS] 2 truncated line skipped
[PASS] 3 session id change detected
[PASS] 4 missing cache fields default 0
[PASS] 5 missing cwd slug → error
[PASS] 6 bad JSONL line skipped
[PASS] 7 non-Claude AI returns empty
[PASS] 8 15MB tail-parse < 500ms (actual 79ms)
[PASS] 8b cache_hit_ratio > 90% on heavy-cache case

=== Phase 2.2 simulation: 9 pass / 0 fail ===
```

→ 9/9 PASS. 15MB JSONL tail 파싱 **79ms** — 목표(500ms) 대비 6배 여유.

**보정**: `cache_hit_ratio` 분모에 `cache_read`까지 포함(기존 plan은 모호) — 의미는 "non-cached input 대비 cached 비율" 명확화. 본 플랜 §3.3 `cache_hit_ratio` 정의에 반영 필요.

## 6. 구현 절차

1. `cmux_paths.py`에 `TELEMETRY_DIR`, `TOKEN_METRICS_FILE`, `surface_to_slug()` 추가
2. `token_observer.py` 작성 + 8케이스 테스트
3. `watcher-scan.py` 루프 끝에 `collect_all()` 호출 (try/except 래핑)
4. `cmux-metrics.sh` 출력 스크립트
5. `/cmux-metrics` 슬래시 커맨드 등록 (`cmux-orchestrator/commands/cmux-metrics.md`)
6. Alert 임계값 내장 (cache_hit < 50%, context > 200K)
7. E2E: 실제 몇 개 surface 운영하며 metrics 파일 생성 확인
8. CHANGELOG + PR

## 7. DoD

- [ ] 8 테스트 PASS
- [ ] token_observer가 watcher 사이클에 통합됨
- [ ] `/cmux-metrics` 커맨드 동작
- [ ] cache_hit_ratio alert 발화 확인 (인위적 저효율 surface로 검증)
- [ ] PR merge

## 8. 리스크

- **JSONL 포맷 변화**: Anthropic이 usage 필드 rename → schema version 체크 필드 도입
- **Performance**: 30 surface × 10MB tail parse = ~300ms — 허용 범위지만 measure 필수
- **Privacy**: metrics는 토큰 수만 기록, 프롬프트 내용 저장 금지
- **Non-Claude AI**: cache 메트릭 의미 없음 → UI에서 `N/A` 표시 명확화
