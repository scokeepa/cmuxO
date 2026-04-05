#!/usr/bin/env python3
"""vision-stall-detector.py — 3단계 surface 상태 감지 + 정체 탐지

메커니즘:
1단계: cmux read-screen (텍스트) → 빠름, 1차 판단
2단계: Apple Vision OCR (ane_tool) → 더블체크, 프롬프트 입력창까지
3단계: 30초 후 재조사 → 변화 없으면 STALLED 확정

출력: JSON {surface_ref: {status, stalled, confidence, details}}

사용법:
  python3 vision-stall-detector.py                 # 1회 스캔 (1+2단계)
  python3 vision-stall-detector.py --with-stall    # 1+2+3단계 (30초 대기 포함)
  python3 vision-stall-detector.py --continuous N   # N초 간격 반복
"""
import json, os, re, shlex, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone

ORCH_DIR = Path.home() / ".claude/skills/cmux-orchestrator"
ANE_TOOL = Path.home() / "Ai/System/11_Modules/ane-cli/ane_tool"
SCAN_FILE = Path("/tmp/cmux-surface-scan.json")
PREV_STATE_FILE = Path("/tmp/cmux-vision-prev-state.json")
STALL_THRESHOLD = 30  # 초

def run(cmd, timeout=15):
    try:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

def read_surface(surface_num, lines=10):
    """read-surface.sh로 surface 읽기"""
    script = ORCH_DIR / "scripts" / "read-surface.sh"
    return run(f'bash {script} {surface_num} --lines {lines}')

def classify_status(text):
    """텍스트에서 상태 판정"""
    if not text:
        return "UNKNOWN", 0.3
    if re.search(r'⏳|Working|running|interrupt|Thinking|■⬝|Crunching|Sautéed|Baked|Slithering|Churned', text):
        return "WORKING", 0.9
    if re.search(r'DONE:|완료|✅.*완료|DONE\b', text):
        return "DONE", 0.9
    if re.search(r'Error|ERROR|API Error|rate.limit|OVERLOADED|context_length_exceeded', text, re.I):
        return "ERROR", 0.85
    if re.search(r'[❯›>]\s*$', text, re.MULTILINE):
        return "IDLE", 0.8
    if re.search(r'bypass permissions|Type your message', text):
        return "IDLE", 0.7
    return "UNKNOWN", 0.4

def vision_ocr_surface(surface_num, workspace):
    """Apple Vision OCR로 individual surface 스크린샷 (cmux 비의존)"""
    if not ANE_TOOL.exists():
        return None
    # 전체 화면 스크린샷에서 surface 영역은 구분 불가
    # → read-screen --scrollback으로 더 많은 텍스트 확보
    script = ORCH_DIR / "scripts" / "read-surface.sh"
    text = run(f'bash {script} {surface_num} --scrollback --lines 30')
    return text

def scan_all_surfaces():
    """전 surface 1+2단계 스캔"""
    # scan 캐시에서 surface 목록 가져오기
    surfaces = {}
    try:
        if SCAN_FILE.exists():
            data = json.load(open(SCAN_FILE))
            surfaces = data.get("surfaces", {})
    except Exception:
        pass

    if not surfaces:
        # 캐시 없으면 detect 실행
        result = run(f'python3 {ORCH_DIR}/scripts/detect-surface-models.py --no-activate')
        try:
            surfaces = json.loads(result)
        except Exception:
            return {}

    results = {}
    for surf_ref, info in surfaces.items():
        surf_num = surf_ref.split(':')[1]
        ws = info.get("workspace", "")
        role = info.get("role", "worker")

        # 1단계: capture-pane (input buffer + 자동완성 포함)
        text_l1 = run(f'cmux capture-pane --workspace "{ws}" --surface {surf_ref} --scrollback --lines 20')
        status_l1, conf_l1 = classify_status(text_l1) if text_l1 else ("UNKNOWN", 0.3)

        # 2단계: read-screen (capture-pane 실패 시 또는 더블체크)
        text_l2 = ""
        status_l2, conf_l2 = status_l1, conf_l1
        if not text_l1 or status_l1 in ("IDLE", "UNKNOWN"):
            text_l2 = read_surface(surf_num, lines=15)
            if text_l2:
                status_l2, conf_l2 = classify_status(text_l2)

        # 3단계: Apple Vision (1+2단계 모두 IDLE/UNKNOWN일 때)
        status_l3, conf_l3 = status_l2, conf_l2
        if status_l2 in ("IDLE", "UNKNOWN") and conf_l2 < 0.85:
            text_l3 = vision_ocr_surface(surf_num, ws)
            if text_l3:
                status_l3, conf_l3 = classify_status(text_l3)
                if status_l3 == "WORKING" and status_l2 in ("IDLE", "UNKNOWN"):
                    print(f"[VISION] {surf_ref}: {status_l2}→WORKING 수정", file=sys.stderr)

        # 최종 판정: 가장 높은 confidence
        layers = [(status_l1, conf_l1), (status_l2, conf_l2), (status_l3, conf_l3)]
        final_status, final_conf = max(layers, key=lambda x: x[1])

        # 사용된 텍스트 (가장 긴 것)
        text = max([text_l1 or "", text_l2 or ""], key=len)

        results[surf_ref] = {
            "status": final_status,
            "confidence": round(final_conf, 2),
            "model": info.get("model", "unknown"),
            "role": role,
            "workspace": ws,
            "layer1_capture": {"status": status_l1, "confidence": round(conf_l1, 2)},
            "layer2_read": {"status": status_l2, "confidence": round(conf_l2, 2)},
            "layer3_vision": {"status": status_l3, "confidence": round(conf_l3, 2)},
            "layer2": {"status": status_l2, "confidence": round(conf_l2, 2)},
            "text_snippet": (text or "")[-80:].replace("\n", " "),
        }

        time.sleep(0.3)  # 소켓 스로틀

    return results

def detect_stalls(current, previous, threshold=STALL_THRESHOLD):
    """이전 상태와 비교하여 정체 감지"""
    stalled = []
    for surf_ref, cur in current.items():
        prev = previous.get(surf_ref, {})
        prev_snippet = prev.get("text_snippet", "")
        cur_snippet = cur.get("text_snippet", "")

        # WORKING인데 출력이 변하지 않음 → 정체
        if cur["status"] in ("WORKING", "IDLE") and prev.get("status") == cur["status"]:
            if prev_snippet and cur_snippet and prev_snippet == cur_snippet:
                cur["stalled"] = True
                stalled.append(surf_ref)
                print(f"[STALL] {surf_ref}: {threshold}초 동안 변화 없음 → STALLED", file=sys.stderr)
            else:
                cur["stalled"] = False
        else:
            cur["stalled"] = False

    return stalled

def main():
    with_stall = "--with-stall" in sys.argv
    continuous = None
    if "--continuous" in sys.argv:
        idx = sys.argv.index("--continuous")
        continuous = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 60

    while True:
        now = datetime.now(timezone.utc).isoformat()

        # 1+2단계 스캔
        print(f"[SCAN] {now} — 1+2단계 스캔 시작", file=sys.stderr)
        results = scan_all_surfaces()

        if with_stall and results:
            # 3단계: 30초 후 재조사
            print(f"[SCAN] {STALL_THRESHOLD}초 대기 후 재조사...", file=sys.stderr)
            prev_state = dict(results)  # 복사
            time.sleep(STALL_THRESHOLD)

            print(f"[SCAN] 재조사 시작", file=sys.stderr)
            results2 = scan_all_surfaces()
            stalled = detect_stalls(results2, prev_state, STALL_THRESHOLD)
            results = results2

            if stalled:
                print(f"[STALL] 정체 surface {len(stalled)}개: {stalled}", file=sys.stderr)

        # 이전 상태 저장 (연속 모드용)
        PREV_STATE_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))

        # 요약
        total = len(results)
        by_status = {}
        for r in results.values():
            s = r["status"]
            by_status[s] = by_status.get(s, 0) + 1
        stalled_count = sum(1 for r in results.values() if r.get("stalled"))

        summary = {
            "timestamp": now,
            "total": total,
            "by_status": by_status,
            "stalled": stalled_count,
            "surfaces": results,
        }

        print(json.dumps(summary, indent=2, ensure_ascii=False))

        if not continuous:
            break
        time.sleep(continuous)

if __name__ == "__main__":
    main()
