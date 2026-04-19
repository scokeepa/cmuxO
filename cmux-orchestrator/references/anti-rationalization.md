# Anti-Rationalization Tables (Phase 2.4)

LLM/Worker/Boss 가 실패·규칙 위반을 **자기 합리화**로 회피하는 반복 패턴을 표로 차단. `cmux-leceipts-gate.py` 가 이 문서의 excuse 정규식을 감지해 **ask** (denyment 아님, 사용자 확인 요청) 를 반환한다. 증거 조회는 `ledger.py query` 로 `VERIFY_PASS`/`PEER_SEND_FAILED`/`ALERT_RAISED` 이벤트를 읽어 판정.

## Table A — 보고 합리화 (Boss / User 가 보고 받을 때)

| 받은 말 | 실제 가능성 | 대응 |
|---------|-------------|------|
| "완료했습니다" / "completed" | DONE_CLAIMED 이나 VERIFY 미실행 | `ledger query --worker=<sid> --type=VERIFY_PASS` 존재 확인 |
| "테스트 통과" / "tests pass" | 실행 안 했거나 일부만 실행 | `ledger` 의 `VERIFY_PASS.evidence` 필드에 test N/N 수치 요구 |
| "환경 문제로 테스트 못 함" | 구체적 차단 요소 미명시 | "어떤 binary / env var / permission?" 재질문 |
| "peer 로 못 보내도 cmux send 가 있으니 괜찮음" | `PEER_SEND_FAILED` 누적, primary 경로 유기 | `ledger query --type=PEER_SEND_FAILED --since-ts=<24h>` count ≥ 5 → ASK |
| "broker 가 가끔 죽어도 fallback 이 돌아감" | broker 건강성 미점검 | `PEER_SEND_FAILED.reason=broker_unreachable` 빈도 집계 후 복구 요구 |
| "transcript 없어서 token metrics 없음" | slug 미스매치 또는 surface↔cwd 공백 | 구체적으로: 어떤 cwd? `cwd.replace("/","-")` 결과가 `~/.claude/projects/` 에 존재? |
| "JSONL 파싱 실패" | tail 10MiB 가 multiline JSON 중간 절단 | 최근 1~2 라인 skip 은 정상, 3 이상은 전체 재스캔 필요 |

## Table B — 작업 회피 합리화 (Worker 자신)

| 스스로 한 생각 | 실제로 해야 할 것 |
|---------------|------------------|
| "이건 범위 밖" | 범위를 1문장으로 재정의 후 사용자 확인 |
| "아마 동작할 것" / "probably fine" | 테스트/시뮬레이션 실제 실행 후 결과 인용 |
| "리팩터링은 별도 PR" | 해당 PR 범위 내 명시적 생략 이유 기록 |
| "boss peer 등록 안 돼도 polling 돌아가니 됨" | MCP `claude-peers` 초기화 + `ROLE_PEER_BIND` ledger 이벤트 유무 확인 |
| "logical_name 조회 실패는 일시적" | 30분 내 3회 이상 miss → 구성 오류 확정, ASK |
| "관련 없어 보여서 안 건드림" | 실제 영향 확인 후 판단 |
| "edge case 라 무시" | 재현 입력 직접 작성 후 실행 |

## Table C — JARVIS 자기개선 합리화

| JARVIS 가 말하는 것 | 차단 조건 |
|--------------------|----------|
| "개선안 있지만 이번엔 생략" | 개선 유예 이유를 ledger `ALERT_RAISED` 로 기록, 30일 누적 2회 이상 같은 합리화 → 강제 이관 |
| "자동 수집 데이터 없어 판단 보류" | Phase 2.3 ledger 존재 기간 확인, 실제 비어있으면 수집 경로 버그로 전환 |
| "사용자가 원하지 않을 것" | 사용자에게 직접 ASK 로 묻기 (가정 금지) |

## Counter 원칙 (Superpowers 레퍼런스)

| Excuse | Counter | When applicable |
|--------|---------|-----------------|
| "probably fine" | State exact failure mode you're assuming doesn't happen | Any claim of "probably" |
| "edge case, unlikely" | Write input that reproduces it now | Any dismissal of reported issue |
| "environment issue" | Name the specific env variable / binary / permission | "Won't reproduce locally" |

## 훅 동작 규약

- 감지 시 `cmux-leceipts-gate.py` 는 **deny** 가 아니라 **ask** 반환 (사용자 판단 여지 보존).
- `override reason` 필드가 LLM 입력에 포함되면 PASS (명시적 주의 1회 기록 조건).
- Evidence 가 ledger 에 존재하면 PASS (예: VERIFY_PASS + `test N/N`).

## 자동 수집 (appendix — 자동 업데이트 구간)

<!-- BEGIN AUTO — jarvis-anti-rationalization-report.py 가 주기적으로 갱신 -->

_최종 갱신: 2026-04-19 15:11 UTC · 윈도: 최근 30일 · 스캔 파일: 0 · 이벤트: 0_

_데이터 없음. Phase 2.3 ledger 가 채워지면 월 1회 집계 갱신._

<!-- END AUTO -->
