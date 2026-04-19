<p align="center">
  <img src="cmuxO-logo.svg" alt="cmuxO 로고" width="260">
</p>

<h1 align="center">cmuxO</h1>
<p align="center"><strong>cmux 오케스트레이션 JARVIS 와쳐 팩</strong></p>
<p align="center"><strong>언어:</strong> 한국어 | <a href="README.md">English</a></p>

---

## 개요

`cmuxO`는 Claude Code 멀티 에이전트 오케스트레이션 팩입니다.
Boss, Watcher, JARVIS를 결합해 병렬 작업, 상태 감시, 운영 자동화, **append-only ledger 기반 SSOT**, **자기 합리화 방지 테이블**을 제공합니다.

- 병렬 작업 배정 및 수집
- 4계층 watcher 감시 (Eagle / OCR / VisionDiff / pipe-pane)
- 운영 가드 훅 + 워크플로 상태 머신
- **Phase 2.3** — append-only JSONL ledger SSOT (14종 이벤트, 원자적 append, 30/90일 rotation)
- **Phase 2.4** — 합리화 패턴 감지 Table A/B/C + ASK(비강제) + 월간 집계 리포트
- **Role peer binding** — `CLAUDE_PEERS_NAME_PREFIX` 기반 논리 이름 등록 + ROLE_PEER_BIND ledger 이벤트
- 크로스플랫폼 라우팅 (macOS=`cmux`, Windows=`cmuxw`, Linux, WSL)

---

## 빠른 시작

```bash
bash install.sh
```

설치 후:

```text
/cmux-start            # 제어탑 가동 (Boss + Watcher + JARVIS)
/cmux-stop             # 종료 (부서만 / 제어탑 포함 선택)
/cmux-pause            # 긴급 동결 / resume
/cmux-watcher-mute     # 와쳐 알림 토글
```

---

## 핵심 구성요소

| 레이어 | 구성 | 책임 |
|-------|-----|-----|
| CEO 참모 | JARVIS | 메트릭 분석, 설정 진화 제안, 정책 전파 |
| 제어탑 | Boss + Watcher | 작업 분해/배정/수집/커밋 + 20초 주기 감시 |
| 부서 | Lead + N Workers | 팀장이 워커 자율 관리, 난이도별 모델 선택 |

---

## Ledger SSOT (Phase 2.3)

오케스트레이션 상태의 단일 진실 공급원 — **append-only JSONL**.

```
runtime/ledger/boss-ledger-YYYY-MM-DD.jsonl
  line 0: {"type":"SCHEMA","version":1}
  line N: {"type":"ASSIGN"|"VERIFY_PASS"|"PEER_SENT"|..., "ts":..., ...}
```

- 원자성: `fcntl.flock(LOCK_EX)` + `O_APPEND` + `fsync()`
- 라인 캡: 4000B (excerpt 자동 축약)
- 회전: 일별 파일, 30일 gzip, 90일 삭제
- 조회: `bash scripts/cmux-ledger.sh tail 20` / `python3 scripts/ledger.py query --type VERIFY_FAIL`

---

## 합리화 방지 테이블 (Phase 2.4)

"아마 동작할 것" / "환경 문제" / "검증은 내가 했음" 류 증거 없는 주장을 감지해 **ASK(deny 아님)** 로 사용자 확인을 유도합니다. 기존 L0 commit-gate 훅과 분리되어 블라스트 반경 보존.

| 테이블 | 카테고리 | 예 |
|-------|--------|----|
| A | 아스피레이셔널 | "probably", "should work", "looks fine" |
| B | 검증 스킵 | "tests pass locally", "I ran it" |
| C | 환경 핑계 | "environment issue", "flaky CI" |

PASS 조건: (1) in-text evidence 마커 (2) override reason 명시 (3) env issue + 구체적 binary/env var (4) ledger VERIFY_PASS 10분 이내.

월간 집계 리포트(Jarvis scheduler `0 0 1 * *`):

```bash
python3 cmux-orchestrator/scripts/jarvis-anti-rationalization-report.py --days 30 --print
```

---

## Role Peer Binding

Boss/Watcher/Peer 세션이 시작 시 MCP `claude-peers` 브로커에 **논리 이름**(`boss@<surface_id_8>` 등)을 등록. peer_id 회전 후에도 안정적 이름으로 재탐색 가능.

```bash
bash cmux-orchestrator/scripts/cmux-role-exec.sh boss [-- claude args...]
bash cmux-orchestrator/scripts/role-register.sh register <role> [peer_id]
```

환경변수 `CLAUDE_PEERS_NAME_PREFIX=<role>` 은 claude 실행 **이전에** 존재해야 합니다 (소급 주입 불가).

---

## 플랫폼

- macOS 바이너리: [manaflow-ai/cmux](https://github.com/manaflow-ai/cmux)
- Windows 바이너리: [scokeepa/cmuxw](https://github.com/scokeepa/cmuxw)
- 강제 지정: `CMUX_BIN=/path/to/cmux-or-cmuxw`

---

## 문서

- 전체 영문 문서 + 아키텍처 다이어그램: [README.md](README.md)
- 개발/운영 문서: `docs/`
- Phase 업그레이드 플랜 + 검증 리포트: `plans/`
- 변경 이력: `docs/CHANGELOG.md`

---

## 라이선스

MIT
