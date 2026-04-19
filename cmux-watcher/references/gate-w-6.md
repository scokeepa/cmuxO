# GATE W-6 — Boss Never Blocked

Watcher 는 **항상 백그라운드**, 메인 작업을 차단하지 않는다.

## 규칙

- 사용자 질문 금지 (자동 판단 — W-7 참조)
- 메인 AI에만 SendMessage/cmux notify 보고
- 백그라운드 무한 루프 (`watcher-scan.py --continuous 60`)
- 포그라운드 blocking 호출 금지

## 운영 형태

```bash
# activation-hook.sh 가 세션 시작 시 자동 실행
python3 ~/.claude/skills/cmux-watcher/scripts/watcher-scan.py \
    --continuous 60 --notify-boss --json &
```

수동 테스트 시에도 `--once` 플래그로 단발 실행만 허용, 라운드 블록 금지.

## 관련

- W-7 질문 금지 (사용자 입력 대기 없이 자동 판단)
- W-9 개입 금지 (세션 제어권은 Boss)
