# SKILL.md 2단계 구조 (SR-03)

> 정본. SKILL.md 작성 시 이 사양을 따름.

## 문제
SKILL.md가 100줄이면 **모든 surface** (Main/Worker/Watcher)에서 불필요하게 로드.
→ surface당 ~3000토큰 낭비.

## 해결: 2단계 분리

### 1단계: 파일 SKILL.md (10줄 미만 — 전 surface 로드)
```markdown
---
name: cmux-jarvis
description: "JARVIS 시스템 관리자"
user-invocable: false
classification: workflow
allowed-tools: Bash, Read, Write, Edit, AskUserQuestion, WebSearch, WebFetch
---
# JARVIS
JARVIS는 오케스트레이션 설정 진화 엔진입니다.
상세 지시사항은 JARVIS surface 세션 시작 시 자동 로드됩니다.
```

### 2단계: additionalContext (JARVIS surface에서만 로드)
jarvis-session-start.sh → hookSpecificOutput.additionalContext로 주입.
내용: Iron Laws + GATE + Red Flags + 안전 제한 + 모니터링 + 스킬 라우팅 (~100줄)

## Write/Edit 허용 (R6-01)
allowed-tools에 Write/Edit 포함. GATE hook이 허용 경로만 통과.
