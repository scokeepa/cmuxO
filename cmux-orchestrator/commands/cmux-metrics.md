# /cmux-metrics — 토큰/캐시 텔레메트리

입력: `$ARGUMENTS`

각 surface(= Claude Code cwd 슬러그)의 누적 input/output 토큰, 캐시 히트율, 턴 수, 마지막 활동 시각을 표로 출력한다. 데이터는 watcher 스캔 주기마다 `token_observer.collect_all()`이 `runtime/telemetry/token-metrics.json`에 저장.

---

## 라우팅

### 빈 입력 또는 `table`
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-metrics.sh
```
→ 현재 저장된 metrics 표 형태로 출력

### `refresh`
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-metrics.sh --refresh
```
→ `token_observer.collect_all()` 즉시 실행 후 표 출력

### `json`
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-metrics.sh --json
```
→ raw metrics JSON

### `alerts`
```bash
bash ~/.claude/skills/cmux-orchestrator/scripts/cmux-metrics.sh --alerts
```
→ 캐시 효율 / context 비대 경고만 출력

---

## 알림 임계값 (Phase 2.2)

| 종류 | 조건 | 심각도 |
|------|------|--------|
| `CACHE_INEFFICIENT` | cache_hit < 50% 이면서 turns ≥ 10 | MEDIUM |
| `CONTEXT_LARGE` | input_tokens_total > 200,000 | MEDIUM |

watcher 스캔 루프가 `generate_alerts()` 결과를 읽어 `cmux-watcher-alerts.json`의 PHASE 2.2 섹션에 병합한다.

---

## 예시

```
/cmux-metrics              → 현재 표
/cmux-metrics refresh      → 강제 재수집 후 표
/cmux-metrics json         → JSON 원본
/cmux-metrics alerts       → 경고 목록
```

## 관련

- SSOT: `cmux-orchestrator/scripts/token_observer.py`
- 경로: `cmux_paths.TOKEN_METRICS_FILE`
- Plan: `plans/cmux-upgrade-phase2-2-token-observability.md`
