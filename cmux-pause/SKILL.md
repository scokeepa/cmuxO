---
name: cmux-pause
description: "긴급 정지 + 재개. /cmux-pause로 전체 중지, /cmux-pause resume으로 재개."
user-invocable: true
classification: workflow
allowed-tools: Bash, Read
---

# /cmux-pause — 긴급 정지 + 재개

입력: `$ARGUMENTS`

오케스트레이션을 안전하게 일시 중지하거나 재개합니다.

---

## 라우팅

### 빈 입력 또는 `pause` → 일시 중지

```bash
# 1. paused 플래그 생성
touch /tmp/cmux-paused.flag

# 2. 모든 부서 팀장에게 중지 알림
# surface map에서 departments 읽기 → 각 team_lead surface에 전송
python3 -c "
import json
try:
    with open('/tmp/cmux-surface-map.json') as f:
        m = json.load(f)
    depts = m.get('departments', {})
    for ws, dept in depts.items():
        lead = dept.get('team_lead', {}).get('surface', '')
        if lead:
            print(f'{ws}:{lead}')
except: pass
"
# 각 팀장에게:
# cmux send --workspace WS --surface SID "작업 일시 중지. 현재 파일을 저장하세요."
```

> `/tmp/cmux-paused.flag` 존재 시 enforcement hook들이 systemMessage로 "[PAUSED]" 경고를 표시합니다.
> 새 부서 생성이나 작업 배정은 자제하되, 진행 중인 작업은 완료 가능합니다.

출력: "전체 일시 중지. /cmux-pause resume으로 재개."

### `resume` → 재개

```bash
# 1. paused 플래그 삭제
rm -f /tmp/cmux-paused.flag

# 2. 팀장들에게 재개 알림
# 각 팀장에게:
# cmux send --workspace WS --surface SID "작업 재개. 이전 작업을 이어서 진행해."
```

출력: "오케스트레이션 재개."

### `status` → 현재 상태 확인

```bash
if [ -f /tmp/cmux-paused.flag ]; then
    echo "현재 상태: PAUSED (일시 중지)"
else
    echo "현재 상태: ACTIVE (실행 중)"
fi
```
