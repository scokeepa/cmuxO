# cmux 명령어 전체 레퍼런스

> ## ⛔ GATE 8 경고
> **이 문서에서 cmux 명령어 사용 시 `--workspace` 파라미터 필수 포함**
> - GATE 6: 서브에이전트 git 금지 + cmux send로 작업 위임
> - GATE 8: **모든 cmux 명령어에 `--workspace` 필수**
> - 예: `cmux send --workspace workspace:1 --surface surface:N "text"` ✅
> - 예: `cmux send --workspace workspace:1 --surface surface:N --buffer-name task1` ✅
> - `--workspace` 누락 시 명령이 다른 workspace에 전달될 수 있음

## 기본 명령 (필수)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux tree --all` | surface 구조 | 전체 구조 파악 |
| `cmux identify` | 현재 위치 | 내가 어느 surface인지 |
| `cmux send --workspace workspace:1 --surface surface:N "text"` | 텍스트 전송 | 작업 지시 |
| `cmux send-key --workspace workspace:1 --surface surface:N enter` | Enter 키 | 전송 확인 |
| `cmux read-screen --workspace workspace:1 --surface surface:N --lines N` | 화면 읽기 | 결과 확인 |
| `cmux capture-pane --workspace workspace:1 --surface surface:N --lines N` | tmux 호환 캡처 | read-screen 대체 |
| `cmux notify --title "t" --body "b"` | 알림 | 완료 알림 |

## 상태 관리 (v4.1)

| 명령 | 용도 | 오케스트레이션 활용 |
|------|------|-------------------|
| `cmux surface-health` | surface 건강 상태 | eagle 감시에 통합 가능 |
| `cmux set-status "task" "building auth"` | 사이드바 상태 표시 | 현재 작업 표시 |
| `cmux clear-status "task"` | 상태 초기화 | 작업 완료 시 |
| `cmux list-status` | 현재 상태 목록 | 전체 진행 현황 |
| `cmux set-progress 0.75 --label "3/4 done"` | 프로그레스 바 | 작업 큐 진행률 |
| `cmux clear-progress` | 프로그레스 초기화 | 작업 완료 |

## 로깅 (v4.1)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux log --level info --source eagle "IDLE: surface:3"` | 이벤트 기록 | 오케스트레이션 로그 |
| `cmux list-log --limit 20` | 최근 로그 | 작업 이력 확인 |
| `cmux clear-log` | 로그 초기화 | 세션 시작 시 |

## 동기화 (v4.1)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux wait-for --signal "task-done" --timeout 60` | 시그널 대기 | surface 간 동기화 |
| `cmux wait-for -S "task-done"` | 시그널 발신 | 작업 완료 알림 |

## 복구 (v4.1)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux respawn-pane --surface surface:N` | surface 재시작 | 크래시 복구 |
| `cmux close-surface --surface surface:N` | surface 종료 | 장애 surface 제거 |
| `cmux new-surface --pane pane:N` | 새 surface 생성 | 동적 팀원 추가 |

## 검색 (v4.1)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux find-window --content "DONE:"` | 내용 검색 | 완료 메시지 탐색 |
| `cmux find-window --select "error"` | 검색+포커스 | 에러 surface로 이동 |

## Claude 세션 감지 (v4.2 — 핵심!)

| 명령 | 용도 | 오케스트레이션 활용 |
|------|------|-------------------|
| `echo '{}' \| cmux claude-hook session-start` | Claude 세션 시작 알림 | 팀원 활성화 감지 |
| `echo '{}' \| cmux claude-hook stop` | Claude 세션 종료 알림 | **완료 감지 — eagle보다 정확** |
| `echo '{}' \| cmux claude-hook idle` | Claude IDLE 알림 | 유휴 감지 |
| `echo '{}' \| cmux claude-hook notification` | 알림 전달 | 에러/완료 이벤트 전달 |
| `echo '{}' \| cmux claude-hook prompt-submit` | 프롬프트 제출 | 작업 시작 감지 |

> **claude-hook은 Claude Code가 자동 호출하는 것이지 우리가 호출하는 것이 아님.**
> 우리는 `set-hook`으로 이 이벤트에 반응하는 핸들러를 등록할 수 있음.

## 이벤트 훅 (v4.2)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux set-hook <event> <command>` | 이벤트 핸들러 등록 | 자동 완료 감지 |
| `cmux set-hook --list` | 등록된 훅 목록 | 현재 훅 확인 |
| `cmux set-hook --unset <event>` | 훅 제거 | 훅 해제 |

## 출력 파이프 (v4.2 — 자동 로그 수집)

| 명령 | 용도 | 오케스트레이션 활용 |
|------|------|-------------------|
| `cmux pipe-pane --surface surface:N --command "tee /tmp/s1.log"` | surface 출력을 파일로 | **자동 로그 수집 (eagle 대체 가능)** |
| `cmux pipe-pane --surface surface:N --command "grep DONE:"` | 완료 메시지만 필터 | 완료 자동 감지 |

## 버퍼 (v4.2 — 큰 텍스트 전송)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux set-buffer --name task1 "긴 프롬프트..."` | 버퍼에 텍스트 저장 | 200자+ 프롬프트 준비 |
| `cmux paste-buffer --workspace workspace:1 --name task1 --surface surface:N` | 버퍼 붙여넣기 | 긴 프롬프트 한 번에 전송 |
| `cmux list-buffers` | 버퍼 목록 | 준비된 작업 확인 |

## Panel 전송 (v4.2)

| 명령 | 용도 | 예시 |
|------|------|------|
| `cmux send-panel --panel surface:N "text"` | panel에 텍스트 전송 | surface ref로 panel 지정 |
| `cmux send-key-panel --panel surface:N enter` | panel에 키 전송 | Enter 실행 |
| `cmux list-panels` | panel 목록 + 이름 | 현재 panel 확인 |

## Workspace/Pane 관리 (v4.2)

| 명령 | 용도 | 오케스트레이션 활용 |
|------|------|-------------------|
| `cmux new-pane --type terminal` | 새 pane 생성 | 동적 팀원 추가 |
| `cmux new-split right` | 오른쪽 분할 | 새 작업 영역 |
| `cmux new-workspace --command "claude"` | 새 workspace + 명령 실행 | 새 Claude 세션 시작 |
| `cmux close-workspace --workspace workspace:N` | workspace 종료 | 불필요 팀원 제거 |
| `cmux select-workspace --workspace workspace:N` | workspace 전환 | 다른 workspace로 이동 |
| `cmux list-panes` | pane 목록 | 현재 레이아웃 확인 |
| `cmux list-workspaces` | workspace 목록 | 전체 환경 파악 |

## 연결/정보 (v4.2)

| 명령 | 용도 |
|------|------|
| `cmux ping` | 소켓 연결 확인 |
| `cmux capabilities` | 지원 기능 JSON |
| `cmux version` | 버전 확인 |
| `cmux current-workspace` | 현재 workspace |
| `cmux sidebar-state` | 사이드바 상태 |
| `cmux display-message -p "text"` | 사용자에게 메시지 표시 |
| `cmux refresh-surfaces` | surface 상태 강제 갱신 |
| `cmux list-notifications` | 알림 목록 확인 |
| `cmux clear-notifications` | 알림 정리 |
| `cmux claude-teams` | Claude Teams 모드 연동 |

## 브라우저 (--surface 필수, 테스트 검증 완료)

> 브라우저 명령은 `--surface surface:N` 지정 필수. `cmux browser open` 시 새 surface 생성됨.

```bash
# 사용 패턴
cmux browser open "https://example.com"                    # → surface:N 생성됨
cmux browser --surface surface:N snapshot                  # 접근성 트리 (DOM 구조)
cmux browser --surface surface:N get-url                   # 현재 URL
cmux browser --surface surface:N goto "https://github.com" # 네비게이션
cmux browser --surface surface:N screenshot --out /tmp/s.png  # 스크린샷
cmux browser --surface surface:N click "[ref=e1]"          # 요소 클릭 (snapshot의 ref 사용)
cmux browser --surface surface:N type "[ref=e5]" "text"    # 텍스트 입력
cmux browser --surface surface:N fill "[ref=e5]" "text"    # 필드 채우기
cmux browser --surface surface:N wait --selector "h1"      # 요소 대기
cmux close-surface --surface surface:N                     # 브라우저 닫기
```

| 명령 | 테스트 결과 | 주의사항 |
|------|-----------|---------|
| `browser open <url>` | ✅ 작동 | 새 surface 번호 반환 |
| `browser goto <url>` | ✅ 작동 | 이미 열린 브라우저에서 |
| `browser snapshot` | ✅ 작동 | 접근성 트리 반환 (`[ref=eN]`) |
| `browser screenshot` | ✅ 작동 | `--out` 필수 |
| `browser get-url` | ✅ 작동 | |
| `browser click` | ⚠️ 불안정 | 페이지 로드 후 snapshot 다시 해야 ref 유효 |
| `browser eval` | ⚠️ 문법 민감 | 에러 발생 빈번, snapshot+click 우선 |

## 레이아웃 (참고)

| 명령 | 용도 |
|------|------|
| `cmux resize-pane --pane pane:N -R --amount 20` | pane 크기 조절 |
| `cmux swap-pane --pane pane:N --target-pane pane:M` | pane 교체 |
| `cmux break-pane --surface surface:N` | pane에서 분리 |
| `cmux join-pane --target-pane pane:N` | pane 합치기 |
| `cmux move-surface --surface surface:N --pane pane:M` | surface 이동 |
| `cmux rename-tab --surface surface:N "이름"` | 탭 이름 변경 |
| `cmux rename-workspace "이름"` | workspace 이름 변경 |

## UI/시스템 명령어 (오케스트레이션 미사용 — 참조용)

| 명령 | 용도 |
|------|------|
| `cmux bind-key <key> <command>` | 키 바인딩 등록 |
| `cmux unbind-key <key>` | 키 바인딩 해제 |
| `cmux clear-history --surface surface:N` | 스크롤백 히스토리 삭제 |
| `cmux close-window --window window:N` | window 닫기 |
| `cmux current-window` | 현재 window 확인 |
| `cmux display-message [-p] "text"` | 상태 바 메시지 표시 |
| `cmux drag-surface-to-split --surface surface:N <방향>` | surface 드래그 분할 |
| `cmux feedback --body "text"` | cmux 피드백 전송 |
| `cmux focus-pane --pane pane:N` | pane 포커스 |
| `cmux focus-panel --panel surface:N` | panel 포커스 |
| `cmux focus-window --window window:N` | window 포커스 |
| `cmux help` | 도움말 |
| `cmux last-pane` | 마지막 pane으로 전환 |
| `cmux list-pane-surfaces --pane pane:N` | pane 내 surface 목록 |
| `cmux list-windows` | window 목록 |
| `cmux markdown <path>` | 마크다운 뷰어 열기 |
| `cmux new-window` | 새 window 생성 |
| `cmux next-window` / `cmux previous-window` | window 전환 |
| `cmux popup` | 팝업 열기 |
| `cmux rename-window "name"` | window 이름 변경 |
| `cmux reorder-surface --surface surface:N --index N` | surface 순서 변경 |
| `cmux shortcuts` | 단축키 목록 표시 |
| `cmux themes [list\|set\|clear]` | 테마 관리 |
| `cmux trigger-flash --surface surface:N` | 플래시 효과 |
| `cmux welcome` | 웰컴 메시지 표시 |
| `cmux copy-mode` | 복사 모드 진입 |

## 알림 단축키

| 단축키 | 기능 |
|--------|------|
| `⌘⇧I` | 알림 패널 열기 |
| `⌘⇧U` | 최근 읽지 않은 알림으로 점프 |
| `⌘N` | 새 workspace |
| `⌘D` | 오른쪽 분할 |
| `⌘⇧D` | 아래 분할 |
| `⌘B` | 사이드바 토글 |
| `⌘⇧L` | 브라우저 분할 열기 |

## Automation Mode 설정 (필수 확인)

cmux Settings > Automation Mode:

| 모드 | 설명 | 우리 환경 |
|------|------|----------|
| `Off` | 소켓 비활성화, CLI 불가 | ❌ 사용 금지 |
| `cmux processes only` | **기본값**, cmux 내부 프로세스만 | ✅ 현재 설정 |
| `allowAll` | 모든 로컬 프로세스 허용 | 외부 스크립트 필요 시 |

> **⚠️ 기본값이 `cmux processes only`이므로:**
> - `nohup`으로 외부에서 실행한 스크립트는 cmux 명령 사용 불가
> - eagle_watcher.sh는 반드시 **cmux 내부 쉘**에서 실행
> - 환경변수 `CMUX_SOCKET_MODE=allowAll`로 외부 접근 허용 가능
