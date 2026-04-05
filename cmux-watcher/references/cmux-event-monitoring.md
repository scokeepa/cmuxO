# cmux Event-Driven Monitoring Protocol (v3.0)

> 폴링(60초 주기)에 이벤트 기반 감지를 추가하여 DONE/ERROR를 즉시 감지.

## 아키텍처

```
┌──────────────────────────────────────────────┐
│              Event Layer (즉시)               │
│  set-hook → claude-hook events → 즉시 알림    │
│  pipe-pane → 출력 자동 캡처 → DONE/ERROR 감지  │
│  find-window → 텍스트 검색 → 완료 surface 발견  │
└──────────────────────┬───────────────────────┘
                       │ 보완
┌──────────────────────▼───────────────────────┐
│              Polling Layer (60초 주기)         │
│  eagle_watcher.sh → 텍스트 패턴 분류           │
│  vision-monitor.sh → ANE OCR 이중 검증         │
│  watcher-scan.py → 통합 분석 + 알림            │
└──────────────────────────────────────────────┘
```

## 1. cmux set-hook : 이벤트 핸들러 등록

### 세션 시작 시 등록 (Watcher Phase 0)

```bash
variable_workspace="workspace:1"  # string

# 키 입력 후 자동 eagle 스캔 (Main 디스패치 감지)
cmux set-hook after-send-keys \
  "bash ~/.claude/skills/cmux-orchestrator/scripts/eagle_watcher.sh --once"

# 등록된 훅 확인
cmux set-hook --list

# 해제 (세션 종료 시)
cmux set-hook --unset after-send-keys
```

### 활용 가능한 이벤트

| 이벤트 | 트리거 | Watcher 활용 |
|--------|--------|-------------|
| `after-send-keys` | 키 입력 후 | Main 디스패치 후 즉시 eagle 스캔 |
| `after-resize-pane` | pane 크기 변경 | 레이아웃 변화 감지 |
| `after-split-window` | 창 분할 | 새 surface 감지 |
| `pane-died` | pane 종료 | Worker 크래시 감지 |
| `window-linked` | 창 연결 | 새 workspace 감지 |
| `session-closed` | 세션 종료 | Worker 완전 종료 |

## 2. cmux claude-hook : 세션 라이프사이클 이벤트

Claude Code가 자동 발생시키는 이벤트. Watcher가 감지하여 상태 업데이트.

```bash
# Claude Code가 자동 호출 (우리가 호출하는 것 아님)
# cmux claude-hook session-start   → Worker 활성화 감지
# cmux claude-hook stop            → Worker 완료 감지 (eagle보다 정확!)
# cmux claude-hook idle            → Worker IDLE 감지
# cmux claude-hook notification    → 에러/완료 이벤트
# cmux claude-hook prompt-submit   → 작업 시작 감지
```

### Watcher가 이 이벤트를 활용하는 방법

```bash
# set-hook으로 claude-hook 이벤트에 반응하는 핸들러 등록
cmux set-hook session-closed \
  "python3 ~/.claude/skills/cmux-watcher/scripts/watcher-scan.py --quick --json"
```

## 3. cmux pipe-pane : 자동 출력 캡처

### 각 surface 출력을 파일로 자동 캡처

```bash
# Worker surface 출력을 자동 파일로 저장
cmux pipe-pane --surface surface:2 --command "tee -a /tmp/cmux-output-s2.log" --workspace "$variable_workspace"
cmux pipe-pane --surface surface:3 --command "tee -a /tmp/cmux-output-s3.log" --workspace "$variable_workspace"

# DONE 자동 감지 (grep 파이프)
cmux pipe-pane --surface surface:2 --command "grep -m1 'DONE' > /tmp/cmux-done-s2.flag" --workspace "$variable_workspace"
```

### DONE 확인 (polling 없이)

```bash
# 파일 존재 여부로 DONE 확인 (read-screen보다 빠름)
[ -s /tmp/cmux-done-s2.flag ] && echo "surface:2 DONE" || echo "surface:2 진행 중"
```

### 로그 파일 분석 (post-mortem)

```bash
# 에러 패턴 검색
grep -i "error\|failed\|429\|timeout" /tmp/cmux-output-s2.log

# 마지막 N줄 확인
tail -20 /tmp/cmux-output-s2.log
```

### 정리

```bash
# 세션 종료 시 pipe 해제 + 로그 삭제
cmux pipe-pane --surface surface:2 --workspace "$variable_workspace"  # 빈 명령 = 해제
rm -f /tmp/cmux-output-s*.log /tmp/cmux-done-s*.flag
```

## 4. cmux find-window : 텍스트 검색 DONE 감지

```bash
# "DONE:" 텍스트를 포함하는 모든 surface 찾기
variable_done_surfaces=$(cmux find-window --content "DONE:" --workspace "$variable_workspace" 2>/dev/null)

# 결과: DONE 완료된 surface 목록 → Main에 알림
if [ -n "$variable_done_surfaces" ]; then
    cmux notify --title "WATCHER" --body "DONE surfaces found: $variable_done_surfaces" --workspace "$variable_workspace"
fi
```

## 5. cmux surface-health : 종합 건강 체크

```bash
# 모든 surface의 건강 상태 확인
variable_health=$(cmux surface-health --workspace "$variable_workspace" 2>/dev/null)

# JSON 파싱: in_window=false → surface 접근 불가
echo "$variable_health" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
for surface, info in data.items():
    if not info.get('in_window', True):
        print(f'WARNING: {surface} not in window — inaccessible')
    if info.get('dead', False):
        print(f'CRITICAL: {surface} dead')
"
```

## 6. cmux wait-for : 동기화 시그널

```bash
# Watcher가 시그널 대기 (Main이 작업 배정 완료 시 발신)
cmux wait-for --signal "dispatch-complete" --timeout 300 --workspace "$variable_workspace"

# Main이 배정 완료 후 시그널 발신
cmux wait-for -S "dispatch-complete" --workspace "$variable_workspace"
```

## 통합 감시 흐름 (Event + Polling 하이브리드)

```
세션 시작:
  1. set-hook 등록 (after-send-keys → eagle 자동 트리거)
  2. pipe-pane 등록 (각 surface → 자동 출력 캡처)
  3. 60초 폴링 루프 시작 (watcher-scan.py --continuous 60)

매 폴링 주기:
  1. find-window --content "DONE:" → 빠른 완료 스캔
  2. eagle_watcher.sh --once → 전체 상태 분류
  3. IDLE/UNKNOWN → Vision Diff (30초 비교)
  4. STALLED → cmux surface-health + 정밀 조사
  5. 알림 생성 → Main SendMessage

이벤트 발생 시 (폴링과 독립):
  - set-hook 트리거 → 즉시 eagle 스캔
  - pipe-pane DONE 감지 → 즉시 알림
  - claude-hook stop → Worker 종료 감지
```

## 성능 비교

| 방식 | DONE 감지 지연 | 리소스 | 정확도 |
|------|-------------|--------|--------|
| 60초 폴링만 | 0~60초 | 낮음 | 높음 |
| pipe-pane | **즉시** | 낮음 | 높음 |
| find-window | ~1초 | 낮음 | 높음 |
| set-hook | **즉시** | 낮음 | 중간 |
| **하이브리드** | **즉시~1초** | 중간 | **최고** |
