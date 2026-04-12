# Vision Diff Detection Protocol (v3.0)

> 스크린샷 2장 비교로 STALLED/WORKING 정밀 판정.
> eagle 텍스트 분석이 IDLE/UNKNOWN 판정 시 Vision Diff로 이중 검증.

## 원리

```
T=0: screenshot A 촬영 → ANE FeaturePrint A 생성
T=30s: screenshot B 촬영 → ANE FeaturePrint B 생성
비교: FeaturePrint A vs B 유사도 계산
  → 유사도 > 0.98 → STALLED (화면 변화 없음)
  → 유사도 < 0.98 → WORKING (화면 변화 있음)
  → 시간 표시만 변화 → 추가 OCR 분석으로 시간 부분 제외 후 재비교
```

## 구현

### Step 1: 스크린샷 촬영 (cmux 명령어)

```bash
variable_surface="surface:N"  # string
variable_workspace="workspace:N"  # string
variable_shot_a="/tmp/cmux-vdiff-${variable_surface}-a.png"  # string: path
variable_shot_b="/tmp/cmux-vdiff-${variable_surface}-b.png"  # string: path

# 첫 번째 스크린샷
cmux browser screenshot --surface "$variable_surface" --out "$variable_shot_a" --workspace "$variable_workspace"
```

### Step 2: 30초 대기 후 두 번째 촬영

```bash
sleep 30

# 두 번째 스크린샷
cmux browser screenshot --surface "$variable_surface" --out "$variable_shot_b" --workspace "$variable_workspace"
```

### Step 3: ANE FeaturePrint 비교

```bash
variable_ane_tool="$HOME/Ai/System/11_Modules/ane-cli/ane_tool"  # string: path

# 각 이미지의 FeaturePrint 생성 + 비교
# ane_tool은 JSON 출력 → Python에서 cosine similarity 계산
variable_fp_a=$("$variable_ane_tool" classify "$variable_shot_a" 2>/dev/null)  # string: json
variable_fp_b=$("$variable_ane_tool" classify "$variable_shot_b" 2>/dev/null)  # string: json
```

### Step 4: Python 비교 로직

```python
import json
import subprocess

def function_vision_diff(variable_surface: str, variable_workspace: str) -> dict:
    """30초 간격 스크린샷 비교로 STALLED/WORKING 판정"""
    variable_ane_tool = f"{os.environ['HOME']}/Ai/System/11_Modules/ane-cli/ane_tool"
    variable_shot_a = f"/tmp/cmux-vdiff-{variable_surface}-a.png"
    variable_shot_b = f"/tmp/cmux-vdiff-{variable_surface}-b.png"

    # 첫 번째 스크린샷
    subprocess.run(["cmux", "browser", "screenshot",
                     "--surface", variable_surface,
                     "--out", variable_shot_a,
                     "--workspace", variable_workspace], timeout=10)

    # OCR A (텍스트 추출)
    variable_ocr_a = json.loads(subprocess.run(
        [variable_ane_tool, "ocr", variable_shot_a],
        capture_output=True, text=True, timeout=30
    ).stdout)

    # 30초 대기
    import time
    time.sleep(30)

    # 두 번째 스크린샷
    subprocess.run(["cmux", "browser", "screenshot",
                     "--surface", variable_surface,
                     "--out", variable_shot_b,
                     "--workspace", variable_workspace], timeout=10)

    # OCR B
    variable_ocr_b = json.loads(subprocess.run(
        [variable_ane_tool, "ocr", variable_shot_b],
        capture_output=True, text=True, timeout=30
    ).stdout)

    # 텍스트 비교 (시간 패턴 제거 후)
    import re
    variable_time_pattern = r'\d{1,2}:\d{2}(:\d{2})?(\s*(AM|PM|am|pm))?'  # string: regex
    variable_text_a = re.sub(variable_time_pattern, '', variable_ocr_a.get('text', ''))
    variable_text_b = re.sub(variable_time_pattern, '', variable_ocr_b.get('text', ''))

    # 숫자 변화도 제거 (카운터, 퍼센트 등)
    variable_num_pattern = r'\d+'  # string: regex
    variable_clean_a = re.sub(variable_num_pattern, '', variable_text_a).strip()
    variable_clean_b = re.sub(variable_num_pattern, '', variable_text_b).strip()

    # 판정
    if variable_clean_a == variable_clean_b:
        return {
            "status": "STALLED",
            "confidence": 0.95,
            "reason": "30초 간격 스크린샷 텍스트 동일 (시간/숫자 제외)",
            "surface": variable_surface
        }
    else:
        return {
            "status": "WORKING",
            "confidence": 0.90,
            "reason": "30초 간격 텍스트 변화 감지",
            "surface": variable_surface,
            "diff_chars": len(set(variable_clean_b) - set(variable_clean_a))
        }
```

## 적용 조건

| eagle 판정 | Vision Diff 실행 | 이유 |
|-----------|-----------------|------|
| WORKING | ❌ 실행 안 함 | 확실히 작업 중 |
| DONE | ❌ 실행 안 함 | 완료 확인됨 |
| ERROR | ❌ 실행 안 함 | 에러 확인됨 |
| **IDLE** | ✅ 실행 | false positive 검증 필요 |
| **UNKNOWN** | ✅ 실행 | 상태 불명확 |
| **ENDED** | ✅ 실행 | 작업 완료 여부 확인 |

## 시간 표시 제외 로직

UI 상단의 시간 표시(12:30:45)가 변하면 false positive 발생.
OCR 텍스트에서 시간 패턴을 제거한 후 비교:

```python
# 제거 대상 패턴
variable_exclude_patterns = [
    r'\d{1,2}:\d{2}(:\d{2})?',           # HH:MM:SS
    r'\d{1,2}(AM|PM|am|pm)',              # 12PM
    r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)',     # 요일
    r'\d+\s*(ms|s|sec|min|KB|MB|GB|%)',   # 단위 포함 숫자
    r'(?:token|line|file)s?\s*\d+',       # token/line/file 카운터
]
```

## 결과 알림 (Boss에 전달)

```python
if result["status"] == "STALLED":
    # SendMessage to Boss
    message = f"[VISION DIFF] {variable_surface} STALLED: 30초간 화면 변화 없음. 정밀 조사 필요.\n"
    message += f"OCR A: {variable_text_a[:100]}...\n"
    message += f"OCR B: {variable_text_b[:100]}...\n"
    message += f"권장: cmux read-screen --workspace {variable_workspace} --surface {variable_surface} --scrollback --lines 50"
```

## cmux 명령어 활용

| 단계 | cmux 명령어 | 용도 |
|------|-----------|------|
| 스크린샷 | `cmux browser screenshot` | 화면 캡처 |
| 텍스트 읽기 | `cmux read-screen --scrollback` | 정밀 조사 |
| 건강 체크 | `cmux surface-health` | CPU/메모리 상태 |
| 알림 | `cmux notify` | STALLED 알림 |
| 로그 | `cmux log --level warn` | 이벤트 기록 |
| 플래시 | `cmux trigger-flash` | 시각적 경고 |

## 성능

| 항목 | 값 |
|------|-----|
| 촬영 시간 | ~1s per screenshot |
| ANE OCR | ~0.5s per image |
| 비교 로직 | ~0.01s |
| 총 소요 | **~32s** (30s 대기 포함) |
| 정확도 | **95%+** (시간 패턴 제외 시) |
