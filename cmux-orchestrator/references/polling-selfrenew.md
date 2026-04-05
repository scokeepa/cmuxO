# 폴링 패턴 & Self-Renewing Loop 레퍼런스

> SKILL.md Section 7 & 8 — 2분 폴링 패턴과 Self-Renewing Loop 상세

## 2분 폴링 패턴 (Section 7)

### 패턴 구조

```bash
sleep 120 && cmux read-screen --surface surface:N --lines 1
```

### 폴링 로직

```
2분 간격으로 전 surface 상태 확인:
1. DONE 있는 surface → 즉시 다음 작업 재배정
2. 작업 중인 surface → 대기
3. IDLE + DONE 없음 → scrollback 분석
```

### 상태 분류

| 상태 | 의미 | 행동 |
|------|------|------|
| DONE | 작업 완료 | 즉시 재배정 |
| WORK(Xm) | 작업 진행 중 | 대기 |
| RATE_LIM | API 제한 | 해제까지 스킵 |
| IDLE + DONE 없음 | 멈춤 가능 | scrollback 분석 |

## Self-Renewing Loop (Section 8)

### 진입 조건

```
컨텍스트 50%+ AND 모든 surface IDLE AND 미커밋 변경 없음
```

### 루프 구조

```
컨텍스트 50%+ AND 모든 surface IDLE AND 미커밋 변경 없음
→ pytest+tsc 최종 확인 → git commit → 워크트리 정리
→ /smart-handoff → 이번 루프 종료
→ 다음 크론: /new → /load-context → 작업 재개
```

### 루프 종료 조건

1. pytest + tsc 최종 확인 통과
2. git commit 완료
3. 워크트리 정리 완료
4. /smart-handoff 실행
5. 다음 크론 예약 (cronjob)

## 2분 폴링 구현

### 단일 surface 폴링

```bash
# surface:N 상태 확인
cmux read-screen --surface surface:N --lines 3
```

### 전 surface 상태 확인 (스크립트)

```bash
#!/bin/bash
# 전 surface 상태 확인 스크립트

SURFACES="surface:1 surface:2 surface:3 surface:4 surface:5"
for SURFACE in $SURFACES; do
    STATUS=$(cmux read-screen --surface $SURFACE --lines 1 2>/dev/null)
    if echo "$STATUS" | grep -q "DONE"; then
        echo "$SURFACE: DONE"
    elif echo "$STATUS" | grep -q "WORKING"; then
        echo "$SURFACE: WORKING"
    elif echo "$STATUS" | grep -q "IDLE"; then
        echo "$SURFACE: IDLE"
    else
        echo "$SURFACE: UNKNOWN"
    fi
done
```

### 자동 폴링 루프

```bash
# 무한 폴링 루프 (Ctrl+C로 중단)
while true; do
    echo "=== $(date '+%H:%M:%S') ==="
    bash ${SKILL_DIR}/scripts/surface-dispatcher.sh "1 2 3 4 5"
    echo "---"
    sleep 120  # 2분 대기
done
```

## scrollback 분석

### IDLE 감지 시 분석 순서

```
1. cmux read-screen --scrollback --lines 50
   → "DONE" 발견 → ✅ 완료

2. 진행 바(■), Working → ⏳ 대기

3. 에러 키워드 → ❌ 에러 → 재배정

4. 프롬프트만 보임 → scrollback 100줄로 확장

5. 그래도 없으면 → 질문 (최후 수단)
```

### scrollback 분석 스크립트

```bash
# surface:N scrollback 분석
cmux read-screen --surface surface:N --scrollback --lines 100

# DONE 키워드 검색
if cmux read-screen --surface surface:N --scrollback --lines 100 | grep -q "DONE"; then
    echo "DONE found"
else
    echo "DONE not found"
fi
```

## 상태 기반 행동 매트릭스

| 상태 | 2분 후 | 추가 조치 |
|------|--------|----------|
| DONE | 재배정 | /new + 새 작업 |
| WORKING | 대기 | 계속 폴링 |
| IDLE+DONE | 재배정 | /new + 새 작업 |
| IDLE+진행중 | 대기 | 2분 후 재확인 |
| RATE_LIMIT | 스킵 | rate limit 해제 후 재확인 |
| ERROR | 재배정 | /clear + 다른 surface에 배정 |
