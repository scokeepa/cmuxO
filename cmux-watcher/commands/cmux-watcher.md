# /cmux-watcher — cmux surface 실시간 감시 에이전트

입력: `$ARGUMENTS`

이 명령어를 실행하면 cmux-watcher 스킬(SKILL.md)을 즉시 로드하고 감시를 시작합니다.

---

## 실행 절차

1. **역할 등록**: `bash role-register.sh register watcher` 실행
2. **동료 발견**: `bash role-register.sh discover-peers` 실행
3. **SKILL.md 로드**: cmux-watcher SKILL.md의 전체 지침을 따라 감시 시작
4. **초기 스캔**: eagle_watcher.sh --once로 전체 surface 상태 파악

## 스킬 로드

반드시 이 스킬의 SKILL.md를 읽고 지침을 따르세요:

```
Skill("cmux-watcher")
```
