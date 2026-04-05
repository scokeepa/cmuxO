# Worktree Workflow Reference (GATE 7)

## Full Worktree Lifecycle

### Step 1: 라운드 시작 — 워크트리 생성

```bash
PROJECT="프로젝트 절대경로"
ROUND="r$(date +%H%M)"

# surface별 워크트리 생성 (HEAD 기준)
git -C "$PROJECT" worktree add "/tmp/wt-codex-${ROUND}" -b "codex-${ROUND}" HEAD
git -C "$PROJECT" worktree add "/tmp/wt-glm1-${ROUND}" -b "glm1-${ROUND}" HEAD
git -C "$PROJECT" worktree add "/tmp/wt-glm2-${ROUND}" -b "glm2-${ROUND}" HEAD
git -C "$PROJECT" worktree add "/tmp/wt-minimax-${ROUND}" -b "minimax-${ROUND}" HEAD

# 확인
git worktree list
```

### Step 2: 작업 배정 — 경로 명시 필수

```bash
cmux send --surface surface:39 "TASK: ... 프로젝트 경로: /tmp/wt-codex-${ROUND} ..."
cmux send --surface surface:27 "TASK: ... 프로젝트 경로: /tmp/wt-glm1-${ROUND} ..."
```

프롬프트에 `/tmp/wt-*` 경로가 없으면 GATE 7 위반.

### Step 3: DONE 후 — 개별 검증

```bash
# 각 워크트리에서 검증
cd "/tmp/wt-codex-${ROUND}"
python3 -m pytest sidecar/tests/ -q
node_modules/.bin/tsc --noEmit  # 심볼릭 링크 필요 시: ln -s "$PROJECT/node_modules" .

# diff 확인
git -C "/tmp/wt-codex-${ROUND}" diff HEAD
```

### Step 4: Main 병합 판단

```bash
cd "$PROJECT"

# 순차 병합 (충돌 시 Main이 해결 — 유일한 코드 수정 허용)
git merge "codex-${ROUND}" --no-edit
git merge "glm1-${ROUND}" --no-edit
git merge "glm2-${ROUND}" --no-edit
git merge "minimax-${ROUND}" --no-edit
```

**REJECT 시:**
```bash
# 해당 브랜치 병합 안 함 — 워크트리만 정리
git worktree remove "/tmp/wt-codex-${ROUND}"
git branch -D "codex-${ROUND}"
```

### Step 5: 최종 검증 (메인)

```bash
cd "$PROJECT"
python3 -m pytest sidecar/tests/ -q  # 전체 PASS 필수
node_modules/.bin/tsc --noEmit       # 0 에러 필수
```

### Step 6: 워크트리 + 브랜치 정리

```bash
for SURFACE in codex glm1 glm2 minimax; do
    git worktree remove "/tmp/wt-${SURFACE}-${ROUND}" 2>/dev/null
    git branch -d "${SURFACE}-${ROUND}" 2>/dev/null
done

# 확인 — /tmp/wt-* 0개여야 함
git worktree list  # main만 남아야 함
```

## node_modules 공유 팁

워크트리에는 node_modules가 없음. 심볼릭 링크로 해결:
```bash
ln -s "$PROJECT/node_modules" "/tmp/wt-codex-${ROUND}/node_modules"
```

## 충돌 해결 패턴

```bash
git merge "glm1-${ROUND}"
# CONFLICT 발생 시:
git diff --name-only --diff-filter=U  # 충돌 파일 목록
# Main이 직접 해결 (이것은 코드 수정 허용 예외)
git add <resolved_files>
git commit  # merge commit
```

## MiniMax 워크트리 제한

| 구분 | 내용 |
|------|------|
| **제한 사항** | MiniMax(Claude Code with MiniMax-M2.7)는 절대경로 프롬프트를 무시하고 CWD 기준으로 파일 생성하는 경향이 있음 |
| **해결책** | MiniMax에는 메인 프로젝트 경로로 직접 배정 + 파일 스코프 격리 |
| **권장** | Codex만 워크트리 사용 권장 — MiniMax는 메인 프로젝트에서 직접 작업 |
