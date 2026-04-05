# Scope Lock 템플릿

진화 ⑤ 계획 수립 시 반드시 작성.

```
bounded_scope: "{변경 대상만 기술}"
  예: "settings.json dispatch.idle_timeout_seconds 추가"

out_of_scope: "{명시적으로 제외할 것}"
  예: "모델 변경, hook 수정, surface 직접 재시작"

followup: "{나중에 할 것}"
  예: "dispatch 로직 자체 개선은 별도 진화로"
```

## 규칙
- Worker에게 Scope Lock 전달 필수
- Outbound Gate에서 out_of_scope 변경 감지 → REJECT
- followup은 evolution-queue.json에 자동 추가
