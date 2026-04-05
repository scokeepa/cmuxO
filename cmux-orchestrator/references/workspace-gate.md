# GATE 8: --workspace 필수 GATE 상세 설명

> SKILL.md Section GATE 8 — cmux 멀티 workspace 환경에서 --workspace 파라미터 사용 규칙 상세

## 규칙 요약 (SKILL.md에 유지할 3줄)

```
⛔ 다른 workspace의 surface에 접근할 때 --workspace 파라미터 없이 cmux 명령 실행 금지.
⛔ workspace:1 surface만 --workspace 생략 가능 (현재 workspace이므로).
✅ 모든 cmux send/read-screen/send-key/paste-buffer 명령에 --workspace 포함 필수.
```

## 상세 설명

### workspace란?

cmux는 복수의 workspace를 지원한다. 각 workspace는 독립적인 surface 모음이다.

```
workspace:1  → surface:1, surface:2, surface:3
workspace:2  → surface:4, surface:5, surface:6
workspace:3  → surface:7, surface:8, surface:9
```

### 문제 발생 상황

다른 workspace의 surface에 --workspace 없이 접근하면:

```bash
# ❌ 잘못된 사용 (workspace:2의 surface:5에 접근)
cmux send --surface "surface:5" "내용"
# → Error: Surface is not a terminal

# ✅ 올바른 사용
cmux send --workspace "workspace:2" --surface "surface:5" "내용"
```

### Surface → Workspace 매핑 확인

세션 시작 시 `cmux tree --all`로 매핑 파악 필수:

```bash
cmux tree --all
# 출력 예:
# workspace:1
#   surface:1 (Claude Code)
#   surface:2 (Codex)
# workspace:2
#   surface:4 (GLM-1)
#   surface:5 (GLM-2)
```

## 명령별 --workspace 사용 패턴

### cmux send

```bash
# ✅ 현재 workspace (workspace:1의 surface:2)
cmux send --surface "surface:2" "내용"
cmux send --workspace "workspace:1" --surface "surface:2" "내용"  # 명시적도 OK

# ✅ 다른 workspace (workspace:2의 surface:5)
cmux send --workspace "workspace:2" --surface "surface:5" "내용"

# ❌ 잘못됨 — workspace:2인데 --workspace 없음
cmux send --surface "surface:5" "내용"
# → Error: Surface is not a terminal
```

### cmux send-key

```bash
# ✅ 현재 workspace
cmux send-key --surface "surface:2" enter
cmux send-key --workspace "workspace:1" --surface "surface:2" enter

# ✅ 다른 workspace
cmux send-key --workspace "workspace:2" --surface "surface:5" enter

# ❌ 잘못됨
cmux send-key --surface "surface:5" enter
```

### cmux read-screen

```bash
# ✅ 현재 workspace
cmux read-screen --surface "surface:2" --lines 20
cmux read-screen --workspace "workspace:1" --surface "surface:2" --lines 20

# ✅ 다른 workspace
cmux read-screen --workspace "workspace:2" --surface "surface:5" --lines 20

# ✅ scrollback 포함
cmux read-screen --workspace "workspace:2" --surface "surface:5" --scrollback --lines 80

# ❌ 잘못됨
cmux read-screen --surface "surface:5" --lines 20
```

### cmux paste-buffer (200자+ 긴 내용)

```bash
# 버퍼 먼저 설정
cmux set-buffer --name task1 -- "매우 긴 내용..."

# ✅ 현재 workspace
cmux paste-buffer --name task1 --workspace "workspace:1" --surface "surface:2"
cmux send-key --workspace "workspace:1" --surface "surface:2" enter

# ✅ 다른 workspace
cmux paste-buffer --name task1 --workspace "workspace:2" --surface "surface:5"
cmux send-key --workspace "workspace:2" --surface "surface:5" enter

# ❌ 잘못됨
cmux paste-buffer --name task1 --surface "surface:5"
```

## 자주 하는 실수

| 실수 | 결과 | 올바른 방법 |
|------|------|------------|
| --workspace 누락 | `Error: Surface is not a terminal` | 항상 --workspace 명시 |
| workspace 번호 오기 | 다른 surface에 전송 | `cmux tree --all`로 확인 |
| 현재 workspace에도 명시 안 함 | 괜찮지만 일관성 문제 | 명시적 권장 |

## 자동 검증 스크립트

```bash
# 잘못된 --workspace 사용 감지
grep -r "cmux send.*surface:.*--workspace" . 2>/dev/null || echo "OK: No bare surface references"

# 또는 eagle_watcher.sh에서 자동 검증
bash ${SKILL_DIR}/scripts/eagle_watcher.sh --workspace-check
```

## GATE 8 자가 점검 체크리스트

```
□ cmux send 사용 시 --workspace 명시 (다른 workspace 접근 시)
□ cmux send-key 사용 시 --workspace 명시
□ cmux read-screen 사용 시 --workspace 명시
□ cmux paste-buffer 사용 시 --workspace 명시
□ workspace 번호가 정확한지 cmux tree --all로 확인
□ 현재 workspace (workspace:1)도 명시적으로 사용 권장
```
