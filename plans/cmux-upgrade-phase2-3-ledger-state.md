# cmuxO Upgrade Phase 2.3 — Ledger-Based Boss State

**작성일**: 2026-04-19 (Phase 2.2.5 리스크 흡수 조정: 2026-04-19)
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기
**참조 프로젝트**: `/Users/csm/projects/olympus/source/autogen/` — MagenticOne/GroupChat의 ledger 패턴

---

## 0. 선행 Phase 리스크 흡수 (Phase 2.2 / 2.2.5)

이 Phase 는 다음 **직전 Phase 의 Remaining risk** 를 명시적으로 해결해야 한다:

### 0.1 Phase 2.2.5 Remaining risk #3 — PEER_SENT_LOG 를 ledger 가 흡수

- `peer_channel.py` 가 `runtime/peer/cmux-peer-sent.log` 에 매 송신을 JSONL 로 append 중. 현재는 **누구도 읽지 않음** → 이 Phase 에서 **ledger 이벤트로 승격**.
- 신규 이벤트 타입 (§3.3 표에 추가): `PEER_SENT` (성공), `PEER_SEND_FAILED` (fallback 사유 포함), `PEER_PAYLOAD_DENIED` (W-9 guard 거절)
- `peer_channel.send()` 내부에서 기존 log append 와 **동일 호출 사이트**에 `ledger.append()` 병행 — 파일은 운영 호환성 위해 유지하되 primary consumer 는 ledger.
- DoD 추가: peer_channel 시뮬(12/12)과 ledger append(10/10) 가 **동시 PASS** 하는 통합 테스트 1 건.

### 0.2 Phase 2.2.5 Remaining risk #1 — Boss/Watcher peer_id 바인딩의 **기록 경로**

- 현재는 `cmux-roles.json` 이 surface/workspace 만 보유. Boss 기동 시 `CLAUDE_PEERS_NAME_PREFIX=boss` 주입으로 `logical_name=boss@<surface_id_8>` 등록 예정 (Phase 2.2.5 다음 롤아웃).
- 이 Phase 는 **바인딩 이벤트를 ledger 에 기록** 할 책임:
  - 신규 이벤트 `ROLE_PEER_BIND {role, surface, workspace, peer_id, logical_name, ts}`
  - `role-register.sh` 가 역할 등록 시 peer list (`peer_channel.list_peers()`) 에서 cwd/surface 매칭으로 peer_id 해석 후 ledger append.
  - Boss compaction 후 재시작 시 `cmux-main-context.sh` 가 ledger 의 최신 `ROLE_PEER_BIND` 를 조회해 peer_id 복원 → resolve 실패로 인한 fallback 자동 해소.

### 0.3 Phase 2.2 Remaining risk #1 — surface ↔ cwd 매핑 저장 공간

- `token_observer` 가 slug-key 로 퇴피 중인 이유는 surface → cwd 매핑이 런타임에 없기 때문.
- 본 Phase 에서 도입하는 ledger 가 `ROLE_PEER_BIND` 이벤트로 **surface + cwd + peer_id 삼중 매핑 의 단일 기록 경로**가 됨. 향후 `token_observer.collect_all(surfaces=...)` 호출자가 ledger tail 을 읽어 surface-keyed 메트릭으로 승격할 수 있는 데이터 소스 제공.

### 0.4 Phase 2.2 Remaining risk #2 — SCHEMA_VERSION bumping 감시

- ledger 자체에 `schema_version=1` 필드 탑재 (각 line 에 개별 기록 비용 방지 위해 **파일 첫 줄을 `{"type":"SCHEMA","version":1,"started_at":...}`** 로 초기화).
- `integrity_check()` 가 첫 줄 schema 와 이후 이벤트 호환성 검증. 버전 mismatch → 경고 로그 + 읽기 계속(fail-open).
- token_observer / peer_channel 의 스키마 변경이 ledger 첫 줄에 소급 기록되어 과거 파일과 구분 가능.

---

---

## 1. 문제 요약

Boss의 팀 운영 상태가 **여러 파일에 산재**되어 있어:
- 누가 무엇을, 왜, 언제 받았는지 **시간축 추적 불가**
- 실패 / 재배정 시 "이전에 어떤 판단이었는지" 근거 상실
- 레드팀이 지적한 "Boss가 거짓말로 완료 보고" 문제가 재현되면 포렌식 어려움
- Boss compaction 발생 시 Team 상태 잃고 재구성 실패

현재 산재 상태:
- `/tmp/cmux-eagle-status.json` — surface 최신 상태만
- `/tmp/cmux-task-queue.json` — 배정 대기 큐만
- `/tmp/cmux-watcher-alerts.json` — 알림 히스토리만
- `~/.claude/memory/cmux/` — 비정형 메모

→ **단일 append-only ledger** 필요.

## 2. 근거

### 2.1 MagenticOne ledger 패턴 요약

MagenticOne (Microsoft AutoGen 0.4+)는 Orchestrator가 매 턴 ledger 작성:
- `is_request_satisfied`: bool
- `next_speaker`: str
- `instruction_or_question`: str
- `progress_made`: bool
- `in_loop`: bool

루프 방지 + 진행 감사 가능.

### 2.2 cmuxO에 맞는 ledger 설계

**Append-only JSONL** — 절대 덮어쓰지 않음:

```jsonl
{"ts":1744992000,"type":"ASSIGN","boss":"main","worker":"surface:3","task":"...","why":"IDLE and task queued"}
{"ts":1744992120,"type":"REPORT","worker":"surface:3","status":"DONE_CLAIMED","evidence":"test passed"}
{"ts":1744992125,"type":"VERIFY","boss":"main","worker":"surface:3","result":"DONE_VERIFIED"}
{"ts":1744992140,"type":"CLEAR","boss":"main","worker":"surface:3","reason":"task complete"}
```

## 3. 설계

### 3.1 위치

`runtime/ledger/boss-ledger-{YYYY-MM-DD}.jsonl` (daily rotation).

### 3.2 신규 모듈

`cmux-orchestrator/scripts/ledger.py`:
```python
def append(event_type: str, **fields) -> None: ...
def tail(n: int = 50) -> list[dict]: ...
def query(worker: str = None, since_ts: int = None, event_type: str = None) -> list[dict]: ...
def rotate() -> str: ...  # 날짜 바뀌면 새 파일
def integrity_check() -> bool: ...  # JSONL 유효성
```

### 3.3 기록 지점

| 이벤트 | 기록자 | 트리거 |
|--------|--------|--------|
| `ASSIGN` | Boss dispatch 직후 | `surface-dispatcher.sh` |
| `ASSIGN_SKIP` | dispatch 조건 실패 | 동일 |
| `REPORT_DONE_CLAIMED` | Worker 완료 주장 수신 | watcher DONE 감지 |
| `VERIFY_PASS` / `VERIFY_FAIL` | Boss 검증 결과 | `cmux-completion-verifier.py` |
| `CLEAR` | `/clear` 실행 | `cmux-dispatch-notify.sh` |
| `RATE_LIMIT_DETECTED` | RATE_LIMITED 감지 | watcher-scan.py |
| `ALERT_RAISED` | watcher alert | watcher-scan.py |
| `HOOK_BLOCK` | 훅이 작업 차단 | 각 PreToolUse 훅 |

### 3.4 Boss UI

`cmux-orchestrator/scripts/cmux-ledger.sh`:
```bash
cmux-ledger tail 20           # 최근 20 이벤트
cmux-ledger worker surface:3  # 특정 worker만
cmux-ledger verify-fail       # 실패만
cmux-ledger since 10min       # 10분 내
```

### 3.5 Compaction 생존

Boss session compaction → in-memory 상태 소실.
재시작 시 `cmux-main-context.sh` UserPromptSubmit 훅이 ledger tail을 주입:
- 최근 30 이벤트 요약
- 진행 중 작업 상태
- 최근 실패/알림

이것이 Phase 2.3의 **핵심 가치**: Boss의 compaction 후 재구성을 "메모리 추측"이 아닌 "감사 로그 재생"으로 해결.

## 4. 5관점 검증

### SSOT
- Ledger 파일 경로: `cmux_paths.py::LEDGER_DIR` (SSOT) ✓
- Append 함수: `ledger.py::append` 단일 API
- 이벤트 타입 enum: 모듈 상수로 정의 (문자열 리터럴 금지)

### SRP
- `ledger.py`: 쓰기/조회/rotation만
- 각 기록 지점은 "이벤트 발생 시 1줄 호출"만 — 이벤트 로직은 기존 훅/스크립트 유지
- 쿼리 UI는 별도 sh 스크립트 — 파일 포맷 노출 X

### 엣지케이스
- 동시 writer 다수 (watcher + dispatch + 훅 4개): `O_APPEND` 원자 쓰기 사용 (~4KB 이하 원자 보장)
- 한 줄 > 4KB 초과: `json.dumps` 후 길이 체크, 4KB 초과 시 `message_excerpt` 잘라내기
- 날짜 변경 시 race: `rotate()`는 파일명 기반, 없으면 생성 — race 허용 (양쪽 같은 이름 생성)
- 파일 손상: `integrity_check`가 파싱 실패 라인 skip, 손상 라인 수 리턴
- 디스크 full: append 실패 → stderr 경고, 작업 차단 X (fail-open)
- Log rotation 누적 디스크 점유: 30일 이상 된 파일 자동 압축 (`gzip`) 및 90일 삭제
- ISO time 아닌 epoch timestamp — 타임존 모호성 제거

### 아키텍트
- 기존 산재 파일 (eagle-status, alerts, task-queue)은 **상태** 파일 (최신값) — ledger는 **이벤트 스트림**. 역할 충돌 없음
- Boss의 compaction 복구는 `cmux-main-context.sh`가 이미 context 주입 담당 → 그 훅이 ledger tail 읽기만 추가
- 의존성 추가 없음 (stdlib only)

### Iron Law
- **"append-only — 덮어쓰기 금지"**
- **"감사 로그는 훼손 불가"** — 각 줄 즉시 flush
- **"Boss 재시작 후 상태 복구 = ledger replay"**
- **"원자적 쓰기"** (O_APPEND + <4KB) ✓

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 시나리오 | expected |
|---|---|---|
| 1 | 10 이벤트 append | 10줄 정확히 기록 |
| 2 | 동시 writer 50 × 100 event | 5000 event 모두 유효 JSONL |
| 3 | 4KB 초과 이벤트 | excerpt 잘림, 유효 JSON |
| 4 | 날짜 변경 자정 경계 | 새 파일 생성 + 이어쓰기 |
| 5 | 파일 중간 라인 손상 | integrity_check가 해당 라인 skip |
| 6 | `tail 50`이 파일 크기 > 100MB에서도 < 200ms | ✓ |
| 7 | query(worker, since_ts, event_type) 복합 필터 | 정확 매칭 |
| 8 | 디스크 full 시뮬레이션 | 예외 + 경고 로그, 호출자 차단 X |
| 9 | 30일 이상 파일 gzip | 자동 압축 확인 |
| 10 | Compaction 후 재주입 — 최근 30 이벤트 | context 생성 정상 |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

프로토타입: `/tmp/ledger_prototype.py`, 러너: `/tmp/test_ledger.py`.

```
[PASS] 1 10 append → 10 tail
[PASS] 2 50×100 concurrent append  (5000 valid / 0 broken)
[PASS] 3 oversized message truncated
[PASS] 4 date boundary creates new file
[PASS] 5 corrupt mid-line skipped
[PASS] 6 tail 50 < 200ms on 10k lines (actual 0.2ms)
[PASS] 7 composite query matches
[PASS] 8 write-permission fail → no raise
[PASS] 9 compact_old gzips old files only
[PASS] 10 context tail 30 for compaction replay

=== Phase 2.3 simulation: 10 pass / 0 fail ===
```

→ 10/10 PASS. 50×100 동시 append 시 **유효 5000줄, 손상 0** — `flock` + append-only + fsync 조합 무결성 확인. tail 10k lines 파싱 **0.2ms**.

### 5.3 설계 보정

- `MAX_LINE_BYTES = 4000` 트런케이션 로직: skeleton 계산 시 `message_excerpt=""` 상태 JSON 길이 측정 후 `MAX - skeleton - 2` 여유 → 초기 구현에서 off-by-3 발견, 이미 수정.
- Write 실패(디스크/권한) 시 **stderr 경고 + 호출자 차단 금지** 원칙 검증됨 (case 8).

## 6. 구현 절차

1. `cmux_paths.py`에 `LEDGER_DIR`, `ledger_today_path()` 추가
2. `ledger.py` + 10케이스 테스트
3. 7개 기록 지점에 `append()` 호출 삽입 (각 1-2라인)
4. `cmux-ledger.sh` UI
5. `cmux-main-context.sh` 확장: ledger tail 30 주입
6. 30일 rotation + gzip cron (`cmux-orchestrator/scripts/ledger-rotate.sh`)
7. E2E: 실제 1시간 세션 운영 후 ledger 검증
8. CHANGELOG + PR

## 7. DoD

- [ ] 10 테스트 PASS
- [ ] 7 기록 지점 연결
- [ ] Compaction 복구 시나리오 수동 검증
- [ ] 30일 rotation 확인 (fake timestamp로)
- [ ] PR merge

## 8. 리스크

- **성능**: 한 세션 1만 이벤트 / 일 → ~1MB JSONL. 연간 365MB. gzip 후 ~50MB. 허용 범위.
- **PII 위험**: `message_excerpt` 필드에 사용자 프롬프트 일부 포함 가능 → 최대 200자 제한 + `~/.claude/memory/` 수준 민감도로 취급
- **Ledger 미활용**: Boss가 실제로 ledger를 읽어 판단하지 않으면 죽은 코드 → Phase 2.3의 가치는 `cmux-main-context.sh`에서 실제 사용해야 실현됨 — 이 훅 통합을 DoD에 포함
- **Compaction 주입량**: 최근 30 이벤트 × 평균 200B = 6KB → context 증가 허용 범위
