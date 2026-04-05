# JARVIS 핵심 아키텍처 원칙

> 정본. 다른 문서에서 원칙을 참조할 때 이 파일을 링크.

## 1. 단일 정본 (FIX-01)
- 마크다운 파일 = 정본. SQLite = 검색 캐시 (split-brain 방지)
- Phase 1: sqlite3 CLI FTS5 (macOS 내장)
- Phase 3: Basic Memory WatchService 양방향 동기화

## 2. GATE 이중 강제 (FIX-02)
- SKILL.md 프롬프트 + PreToolUse hook 물리 차단
- permissionDecision: "allow" / "deny" / "ask" (S1)
- settings.json → phase="applying" 조건부만 허용 (IL1-F1)
- Bash 간접 수정도 차단: matcher "Edit|Write|Bash" (S3)
- /freeze: 기본 warn, CRITICAL만 deny (CV-04)

## 3. 진화 안전 제한 (FIX-03, FIX-05)
- 직렬 실행: CURRENT_LOCK (TTL 60분, 2차 승인 시 리셋)
- MAX_CONSECUTIVE_EVOLUTIONS = 3
- MAX_DAILY_EVOLUTIONS = 10
- 동일 영역 3회 반복 → 에스컬레이션

## 4. Worker 권한 분리 (FIX-04)
- Worker = 제안만 (proposed-settings.json + file-mapping.json)
- JARVIS만 설정 적용 (검증 + 사용자 승인 후)
- gate.sh 내부 Worker 분기 (S4)

## 5. 2모드 아키텍처 (FATAL-A3)
- 모드 A: Obsidian 볼트 = 정본
- 모드 B: ~/.claude/cmux-jarvis/ = 정본
- config.json `obsidian_vault_path` 유무로 결정

## 6. 승인 + 큐 (IL1)
- 구조화 선택지만 인정: [수립][보류][폐기], [실행][수정][폐기], [KEEP][DISCARD]
- 타임아웃 30분 → 자동 보류
- 큐 최대 5건, CRITICAL은 예외 허용
- 보류 재감지 → 예측 A/B 보고서 (deferred-issues.json)

## 7. 독립 검증 (IL3)
- jarvis-verify.sh: cmux 사전 포함, JARVIS 수정 금지
- 플러그형: verify-plugins/{type}.sh
- evidence.json 자동 생성
- 최종 판단은 사용자 (Iron Law #1)

## 메트릭 사전 필수 항목 (V7-02 반영)
- stall_count: warning≥2, critical≥5
- error_count: warning≥1, critical≥3
- **ended_count**: warning≥1 (V7-02 추가)
- **idle_count**: warning≥2
- dispatch_failure_rate: warning≥20%, critical≥50%
- context_overflow_count: warning≥5, critical≥10

## GATE 삭제 방어 (META-1, S2)
- ConfigChange hook exit 2 → 삭제 자체 차단
- /hooks 명령 SKILL.md에서 금지
