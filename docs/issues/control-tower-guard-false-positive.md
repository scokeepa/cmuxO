# BUG: control-tower-guard가 Bash 명령 문자열에서 false positive 차단

## 요약

`cmux-control-tower-guard.py`가 `tool_input.command` 전체 문자열에서 `"close-workspace"` 단순 포함 검사를 하여, 실제 `cmux close-workspace` 명령이 아닌 경우에도 차단됩니다.

## 재현 방법

```bash
# 이 명령이 차단됨:
echo "cmux-stop에서 close-workspace 옵션이 있다"

# 이것도 차단됨:
grep "close-workspace" some-file.md

# 이것도 차단됨:
cat README.md  # README 안에 close-workspace 문자열 포함 시
```

## 에러 메시지

```
PreToolUse:Bash hook blocking error from command: 
"python3 cmux-control-tower-guard.py": 
[CONTROL-TOWER-GUARD] close-workspace에 --workspace 플래그가 필요합니다.
```

## 원인

`cmux-control-tower-guard.py` L32:
```python
if "close-workspace" not in command:
    print(json.dumps({"decision": "approve"}))
    return
```

이 검사는 **Bash 명령 전체 문자열**에서 부분 문자열 매칭을 합니다. `echo "...close-workspace..."` 같은 무해한 명령도 매칭됩니다.

## 영향

- 사용자가 문서나 코드에서 `close-workspace` 문자열을 다루는 모든 Bash 명령이 차단됨
- `echo`, `grep`, `cat`, `sed` 등 읽기/출력 명령도 차단됨
- JARVIS/cmux-stop 등 다른 스킬 개발 시 해당 문자열을 참조하는 것도 불가

## 수정 제안

### 방법 A: 명령 시작 패턴으로 변경 (권장)

```python
# 기존 (L32): 문자열 포함 검사 → false positive
if "close-workspace" not in command:

# 수정: 실제 cmux 명령인지 확인
import shlex
try:
    tokens = shlex.split(command)
except ValueError:
    print(json.dumps({"decision": "approve"}))
    return

# cmux close-workspace 명령인지 정확히 판별
is_close_cmd = False
for i, token in enumerate(tokens):
    if token == "cmux" and i + 1 < len(tokens) and tokens[i + 1] == "close-workspace":
        is_close_cmd = True
        break
    # 파이프(|) 뒤에도 확인
    if token == "|":
        continue

if not is_close_cmd:
    print(json.dumps({"decision": "approve"}))
    return
```

### 방법 B: 정규식으로 변경 (간단)

```python
# 기존
if "close-workspace" not in command:

# 수정: cmux close-workspace 패턴만 매칭
if not re.search(r'\bcmux\s+close-workspace\b', command):
    print(json.dumps({"decision": "approve"}))
    return
```

### 방법 C: 최소 수정 (현실적)

```python
# 기존
if "close-workspace" not in command:

# 수정: cmux 명령이 아니면 통과
if "cmux" not in command or "close-workspace" not in command:
    print(json.dumps({"decision": "approve"}))
    return
```

## 권장

**방법 B(정규식)**가 정확도와 구현 난이도의 균형이 좋습니다.
`\bcmux\s+close-workspace\b` 패턴은 `echo "close-workspace"` 같은 간접 참조를 통과시키면서, 실제 `cmux close-workspace --workspace ...` 명령만 정확히 감지합니다.

## 적용 파일

`cmux-orchestrator/hooks/cmux-control-tower-guard.py` L32
