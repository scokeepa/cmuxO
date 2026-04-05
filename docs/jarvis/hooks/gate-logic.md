# GATE hook 전체 로직

> 정본. gate.sh 구현 시 이 파일만 참조.

## 입력 (Claude Code PreToolUse)
```json
{"hook_event_name":"PreToolUse", "tool_name":"Edit|Write|Bash", "tool_input":{...}}
```

## 출력 (Claude Code 공식 스키마, S1)
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow|deny|ask","permissionDecisionReason":"..."}}
```

## GATE 5단계 → permissionDecision 매핑
| GATE | permissionDecision | 동작 |
|------|--------------------|------|
| ALLOW | "allow" | 무조건 통과 |
| WARN | "allow" + stderr 경고 | 경고+실행 |
| HOLD | "ask" | Claude Code 승인 UI (S6) |
| BLOCK | "deny" | 즉시 거부 |
| ESCALATE | "deny" + cmux notify | 거부+알림 |

## 분기 로직
```
INPUT → tool_name 확인
├── Edit/Write → check_gate(file_path)
└── Bash → 쓰기 패턴 감지 (CA-03)
    ├── settings.json 쓰기 → check_settings_gate()
    ├── Worker surface → check_worker_gate()
    └── 그 외 → allow

check_gate(path):
├── Worker surface + evolutions/ 외부 → deny (S4)
├── settings.json → check_settings_gate()
├── ~/.claude/cmux-jarvis/ 또는 Obsidian 볼트 → allow
└── 그 외 → deny

check_settings_gate():
├── CURRENT_LOCK 존재 + phase="applying" + evidence.json 존재 (IL3-ATK-1) → allow
└── 그 외 → deny

Bash settings.json 감지 (CA-03 + IL1-ATK-1):
  명령에 "settings.json" 포함 시:
    읽기 전용: cat|head|tail|grep|wc|jq -r|less|file → allow
    그 외 (쓰기/python3/node/ruby 포함) → deny
  ```bash
  if echo "$COMMAND" | grep -q "settings\.json"; then
    if echo "$COMMAND" | grep -qE "^(cat|head|tail|grep|wc|less|file) |jq -r "; then
      allow  # 읽기 전용
    else
      deny "settings.json 비읽기 명령 차단"
    fi
  fi
  ```

check_gate(path) 추가 (IL1-ATK-3):
  .evolution-lock 직접 Write/Edit → deny
  ```
  if [[ "$path" == *".evolution-lock"* ]]; then
    deny "LOCK 파일은 jarvis-evolution.sh만 생성 가능"
  fi
  ```
```

## Outbound Gate 추가 체크 (E4: 배열 덮어쓰기 방지)
```bash
# proposed-settings.json에 hooks/배열 키 포함 시 REJECT
if jq -e '.hooks' proposed-settings.json >/dev/null 2>&1; then
  deny "proposed에 hooks 키 포함. 기존 hooks 덮어쓰기 위험."
fi
```

## jq 미설치 폴백 (D1)
```bash
command -v jq >/dev/null || { allow; exit 0; }  # fail-open
```
