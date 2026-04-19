# GATE W-3 — Vision Verify IDLE

Eagle(Layer 1)이 `IDLE` 또는 `UNKNOWN` 으로 판정 시 **ANE OCR 로 이중 확인**.

## 흐름

```
Layer 1 (eagle_analyzer.py)  →  IDLE/UNKNOWN
       │
       ▼
Layer 2 (vision-monitor.sh)
  - ane_tool ocr screenshot.png
  - 에러/rate-limit 문자열 재검출
       │
       ▼
Layer 2.5 (Vision Diff)  →  STALLED 정밀 판정
  - T와 T+30s 스크린샷 OCR
  - 시간/숫자 패턴 제거 후 문자열 동일이면 STALLED
```

## ANE 도구 경로

`cmux_paths.ane_tool_path()` 로 해석 (Phase 1.3 SSOT).
기본값: `$HOME/Ai/System/11_Modules/ane-cli/ane_tool`.

## ANE 기능 4종

| 기능 | 커맨드 | 감시 용도 |
|------|--------|-----------|
| OCR | `ane_tool ocr screenshot.png` | 텍스트 재추출 |
| Classify | `ane_tool classify screenshot.png` | idle/working/error 분류 |
| FeaturePrint | `ane_tool classify screenshot.png` | 이미지 유사도 비교 |
| Sentiment | `ane_tool sentiment "..."` | 에러 메시지 심각도 |

## Vision Diff 판정표

| 결과 | 판정 | 신뢰도 |
|------|------|--------|
| 텍스트 동일 (시간/숫자 제외) | STALLED | 0.95 |
| 텍스트 변화 있음 | WORKING (Eagle 오버라이드) | 0.90 |
| 스크린샷 실패 | UNKNOWN | 0.50 |

## STUCK_PROMPT 감지 (v4.1)

`›` 뒤에 셸 명령 잔류 시 `STUCK_PROMPT` 로 보고. Boss가 Esc×3 + `/new` 로 복구.
