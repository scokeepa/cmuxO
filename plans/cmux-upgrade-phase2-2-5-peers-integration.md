# cmuxO Upgrade Phase 2.2.5 — claude-peers Inter-Session Channel

**작성일**: 2026-04-19
**상태**: APPROVED — 사용자 승인 (`끼워넣어`)
**선행**: Phase 2.2 (Token Observability) 완료
**후행**: Phase 2.3 (Ledger state) 가 peers 메시지를 ledger entry 로 흡수하도록 확장

---

## 1. 문제

현재 cmuxO 의 Boss ↔ Watcher ↔ Worker 통신은 **`cmux send --workspace X --surface Y "msg" && cmux send-key ... enter`** 로 tmux 표면에 직접 타이핑하는 방식. 결과:

- 사용자 프롬프트와 보고 메시지가 같은 터미널에 섞여 혼란
- 보고 메시지를 구조화하지 못함 (from_kind / from_cwd / from_surface 등 메타 손실)
- 표면 죽음/재시작 시 메시지 드롭, ACK 개념 없음
- 이중 주입 위험 (`/new`·`/clear`) — W-9 hook 이 간신히 막음

`claude-peers-oneclick` (이미 olympus/source 에 번들) 의 브로커가 **SQLite 큐 + HTTP API + 폴링 기반 구조화 채널** 을 제공 → 보고 경로에 이상적.

## 2. 근거 (peers 조사 요약)

- 브로커: `localhost:7899` HTTP, 자동 daemon. `bundle/claude-peers-mcp/broker.ts`
- **peer 등록 불필요한 system 송신자 경로 존재**: `POST /send-message { from_id, to_id, text }` (from_pid 생략) → `from_kind='system'` (broker.ts:555-574)
- DB 위치: `~/.claude-peers.db` (SQLite WAL)
- FIFO 순서 보장, 60 초 heartbeat timeout 으로 stale peer 자동 제거

## 3. 설계

### 3.1 도입 범위 (scope 최소화)

| 경로 | 매체 | 이유 |
|---|---|---|
| Boss → Worker **작업 배정** | **cmux send + enter 유지** | 유휴 Worker 깨우기는 터미널 inject 만 가능 |
| Worker → Boss **완료/에러 보고** | **peers** (신규) | 구조화 메타, 사용자 프롬프트와 구분 |
| Watcher → Boss **DONE/IDLE/ERROR 알림** | **peers** (신규) | 현 `[WATCHER→BOSS] ...` 텍스트 프로토콜 승격 |
| 긴급 `/new`·`/clear` | **peers 로 금지** | 별도 guard 로 차단 |

### 3.2 신규 모듈

**`cmux-orchestrator/scripts/peer_channel.py`** — peers 브로커 어댑터
- `send(to: str, text: str, from_id: str = "cmuxO") -> dict` — HTTP POST 래퍼, 3 초 timeout, 재시도 없음 (실패 → 결과 dict 의 ok=False 로 반환, raise 안 함)
- `is_broker_alive() -> bool` — `/health` 체크
- `list_peers(scope="machine") -> list[dict]` — 피어 발견
- `resolve(name: str) -> str | None` — logical_name → peer_id
- `BROKER_URL` 환경변수 override (`CLAUDE_PEERS_BROKER_URL`)
- 위반 감지: `/new`·`/clear`·`cmux send-key` 류 payload 는 `send()` 에서 거절 (W-9 peers 확장)

### 3.3 Watcher 통합

`cmux-watcher/scripts/watcher-scan.py::notify_boss_surface()`:
- 기존 cmux send 경로 유지 (fallback)
- **peer_channel.send() 를 먼저 시도**. 성공 → cmux send 스킵 (**이중 발행 금지**). 실패(or 브로커 dead) → cmux send fallback
- 환경 변수 `CMUX_PEERS_ENABLED=0` 으로 비활성 가능 (rollout kill switch)

### 3.4 Guard Hook (W-9 확장)

`~/.claude/hooks/cmux-peer-send-guard.py` — PreToolUse hook 수준의 가드는 아니고, **`peer_channel.send()` 내부에서 payload 검사**:
- 정규식 `^(/new|/clear|\\[BOSS→|/compact)\\b` → 거절 + 로그
- 허용 패턴: `[WATCHER→BOSS]`, `[WORKER→BOSS]`, `[BOSS→WATCHER] ACK:`

근거: peers 는 out-of-band 이므로 cmux-send-guard.py 가 못 잡음 → 모듈 내부 guard 로 대응.

### 3.5 저장/관측

- 전송 메타는 `runtime/peer/cmux-peer-sent.log` (append-only JSONL) 에 기록 → Phase 2.3 ledger 흡수 지점
- `/cmux-peers` 슬래시 커맨드는 **Phase 2.2.5 범위 밖** (Phase 2.3 ledger UI 로 통합)

## 4. 5관점 검증

### SSOT
- 브로커 URL: `peer_channel.BROKER_URL` (1 곳), env override 허용
- 경로: `cmux_paths.PEER_SENT_LOG_FILE` (신규 1 상수)
- logical_name 규약: `{role}@{surface_id_8}` — 1 곳(peer_channel)에서 생성

### SRP
- `peer_channel.py`: HTTP 송수신만
- watcher-scan.py 통합: "send via peer, fallback to cmux" 라우팅만
- guard: payload 검사만, 라우팅 결정 X

### 엣지케이스
- 브로커 dead → `is_broker_alive()` False → cmux send 즉시 fallback (레이턴시 100 ms 이하)
- 대상 peer_id 모름 → logical_name(`boss@…`) 으로 resolve 시도, 그래도 None → cmux send fallback
- HTTP timeout → ok=False 반환, fallback 경로
- 이중 발행 가드: send() 성공 시 send_via_cmux 호출 안 함 (if/else 배타)

### 아키텍트
- peers 도입이 cmuxO 의 기존 `cmux-roles.json` SSOT 를 훼손하지 않음 (peer_id 는 보조 식별자, roles 가 정본)
- Phase 2.3 ledger 가 `PEER_SENT_LOG_FILE` 를 소스로 ledger entry 생성 예정

### Iron Law
- watcher 루프 non-blocking ✓ (HTTP 3 s timeout)
- 경로는 cmux_paths SSOT ✓
- AI 분기 불필요 (peers 는 AI 무관)
- W-9 확장 guard ✓

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 시나리오 | expected |
|---|---|---|
| 1 | 브로커 alive → send 정상 | ok=True, status 200 |
| 2 | 브로커 down → is_broker_alive False | send() 호출 없이 ok=False 빠른 반환 |
| 3 | 대상 peer 없음 | ok=False, error="Peer ... not found" |
| 4 | logical_name resolve 정상 | peer_id 반환 |
| 5 | resolve 실패 | None 반환 |
| 6 | `/new` payload | guard 가 거절, 브로커 호출 X |
| 7 | `/clear` payload | 거절 |
| 8 | `[WATCHER→BOSS] DONE: s:7` | 허용, 통과 |
| 9 | send 결과가 `PEER_SENT_LOG_FILE` 에 JSONL 로 append | 파일 1 줄 증가 |

### 5.2 실행 예정 — 구현 후 mock broker 로 검증

## 6. 구현 절차

1. `cmux_paths.py` — `PEER_SENT_LOG_FILE`, `PEER_CHANNEL_PORT_DEFAULT` 상수
2. `peer_channel.py` 작성 + CLI (`send|health|list|resolve`)
3. `/tmp/mock_peers_broker.py` 로 9 케이스 시뮬
4. watcher-scan.py `notify_boss_surface()` 를 peer-first 로 전환
5. 설치 스킬 싱크 (`~/.claude/skills/cmux-orchestrator/scripts/peer_channel.py`)
6. CHANGELOG Phase 2.2.5 항목 추가

## 7. DoD

- [ ] peer_channel.py 9/9 PASS (mock broker)
- [ ] 브로커 down 시 watcher 가 cmux send fallback 으로 정상 보고
- [ ] `/new`·`/clear` payload 가 guard 에 차단되는 것을 테스트로 확인
- [ ] `~/.claude-peers.db` 가 있는 환경에서 실제 brooker 로 E2E 스모크 1 회

## 8. 리스크

- **이중 발행**: if/else 배타 라우팅 + `CMUX_PEERS_ENABLED` kill switch
- **브로커 SPOF**: fallback 경로로 완화
- **logical_name 정규화 손실** (한글 탈락): Watcher/Boss 이름은 ASCII 고정 (`watcher@…`, `boss@…`) 로 회피
- **Phase 2.3 ledger 의존성**: 현 Phase 는 로그 파일까지만. ledger 통합은 2.3 범위.
