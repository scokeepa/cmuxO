# 진화 유형별 테스트 템플릿

## settings_change
1. JSON 유효성: `python3 -c "import json; json.load(open('settings.json'))"`
2. 변경 키 존재: `jq -e '.{변경키경로}' settings.json`
3. surface 정상: `cmux surface-health` → ERROR 없음

## hook_change
1. 파일 존재 + 실행 권한: `[ -x "$HOOK_PATH" ]`
2. stdin 파이프: `echo '{}' | bash $HOOK_PATH`
3. JSON 출력: `echo '{}' | bash $HOOK_PATH | python3 -c "import json,sys;json.load(sys.stdin)"`
4. 기존 hook 비간섭 확인

## skill_change
1. YAML frontmatter: `head -10 SKILL.md | grep "^name:"`
2. 스킬 로드 가능 여부

## code_change
1. 구문: `bash -n script.sh` / `python3 -c "compile(open('f').read(),'f','exec')"`
2. 실행: 예상 입력 → 예상 출력
