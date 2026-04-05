#!/usr/bin/env python3
"""surface-monitor.py — 4계층 강제 집중 모니터링 (v3.0)

지정 surface들의 DONE을 4계층 전부 사용하여 감지.
DONE 판정 시 30초 후 재검증(Vision Diff) 필수.
Main에만 보고 — Worker 개입 절대 금지 (GATE W-9).

Usage:
    python3 surface-monitor.py --targets "1 3 4 21 22" --main surface:28
    python3 surface-monitor.py --targets "7" --main surface:28 --interval 15
"""

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ORCH_DIR = Path.home() / ".claude" / "skills" / "cmux-orchestrator" / "scripts"
READ_SURFACE = ORCH_DIR / "read-surface.sh"
EAGLE_ANALYZER = ORCH_DIR / "eagle_analyzer.py"
ANE_TOOL = Path.home() / "Ai" / "System" / "11_Modules" / "ane-cli" / "ane_tool"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(cmd: list[str], timeout: int = 15) -> tuple[str, int]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "", -1


def read_surface(sid: str, lines: int = 12) -> str:
    text, rc = run_cmd(["bash", str(READ_SURFACE), sid, "--lines", str(lines)], timeout=10)
    return text if rc == 0 else ""


def ts() -> str:
    return time.strftime("%H:%M:%S")


def notify_main(main_sf: str, msg: str) -> None:
    """Main에 cmux send + enter. Worker에는 절대 전송 금지."""
    run_cmd(["cmux", "send", "--surface", main_sf, msg], timeout=5)
    time.sleep(0.5)
    run_cmd(["cmux", "send-key", "--surface", main_sf, "enter"], timeout=5)


# ---------------------------------------------------------------------------
# 4계층 판정 엔진
# ---------------------------------------------------------------------------

# WORKING 신호 (하나라도 있으면 절대 DONE 아님)
WORKING_PATTERNS = re.compile(
    r'Working|Processing|Choreographing|Compiling|thinking|Honking|Scurrying|'
    r'Running|Actioning|Retrying|attempt|tokens|ctrl\+b|ctrl\+o|interrupt|'
    r'esc to interrupt|run in background',
    re.IGNORECASE,
)

# WAITING 신호 (질문 대기 — DONE 아님)
WAITING_PATTERNS = re.compile(
    r'할까요\?|하시겠습니까\?|선택해|which.*first|proceed\?|y/n|yes/no|\(Y/n\)|'
    r'어떤 것부터|먼저 진행',
    re.IGNORECASE,
)

# 강한 DONE 키워드
DONE_PATTERNS = re.compile(
    r'DONE:|TASK COMPLETE|Brewed|Cooked|Baked|Crunched|Worked',
    re.IGNORECASE,
)

# Codex 프롬프트
CODEX_PROMPT = re.compile(r'›')

# Claude 프롬프트
CLAUDE_PROMPT = re.compile(r'❯|\u276f')


def clean_for_diff(text: str) -> str:
    """시간/숫자 제거 — Vision Diff용."""
    text = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', '', text)
    text = re.sub(r'\d+', '', text)
    return re.sub(r'\s+', ' ', text).strip()


class SurfaceState:
    """한 surface의 4계층 판정 결과."""
    def __init__(self, sid: str):
        self.sid = sid
        self.l1_status = "UNKNOWN"     # L1: 패턴 매칭
        self.l2_status = "UNKNOWN"     # L2: ANE OCR 재검증
        self.l25_prev_text = ""        # L2.5: 이전 캡처
        self.l25_stalled = False       # L2.5: 화면 고정 여부
        self.l3_pipe_flag = False      # L3: pipe-pane 플래그
        self.final_status = "UNKNOWN"
        self.recheck_passed = False    # 30초 재검증 통과 여부

    def __repr__(self):
        return f"S:{self.sid}={self.final_status}"


def layer1_pattern(text: str) -> str:
    """L1: 텍스트 패턴 매칭."""
    if WORKING_PATTERNS.search(text):
        return "WORKING"
    if WAITING_PATTERNS.search(text):
        return "WAITING"
    if DONE_PATTERNS.search(text):
        return "DONE"
    if CODEX_PROMPT.search(text):
        return "DONE"
    if CLAUDE_PROMPT.search(text):
        return "IDLE"  # 프롬프트만 — 추가 검증 필요
    return "UNKNOWN"


def layer2_ocr_verify(sid: str, text: str) -> str:
    """L2: eagle_analyzer로 텍스트 분류."""
    if not EAGLE_ANALYZER.exists():
        return "SKIP"
    try:
        r = subprocess.run(
            ["python3", str(EAGLE_ANALYZER)],
            input=text, capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout.strip())
            return data.get("status", "UNKNOWN")
    except Exception:
        pass
    return "SKIP"


def layer3_check_pipe_flag(sid: str) -> bool:
    """L3: pipe-pane DONE 플래그 확인."""
    flag = Path(f"/tmp/cmux-done-s{sid}.flag")
    return flag.exists() and flag.stat().st_size > 0


def judge_status(state: SurfaceState) -> str:
    """4계층 종합 판정.

    규칙:
    1. WORKING/WAITING이 하나라도 있으면 → 해당 상태 (DONE 아님)
    2. L3 pipe-pane DONE → DONE (가장 신뢰도 높음)
    3. L1 DONE + L2 일치 → DONE
    4. L1 IDLE + L2.5 화면 고정 → STALLED (DONE 아닐 수 있음)
    5. 불일치 → UNKNOWN (재검사 필요)
    """
    # WORKING/WAITING 우선
    if state.l1_status in ("WORKING", "WAITING"):
        return state.l1_status
    if state.l2_status in ("WORKING", "WAITING"):
        return state.l2_status

    # L3 pipe-pane (가장 신뢰)
    if state.l3_pipe_flag:
        return "DONE"

    # L1 DONE
    if state.l1_status == "DONE":
        if state.l2_status in ("DONE", "IDLE", "ENDED", "SKIP"):
            return "DONE"
        # L2가 WORKING이면 L1 오판
        if state.l2_status == "WORKING":
            return "WORKING"

    # L1 IDLE (프롬프트만) — 추가 증거 필요
    if state.l1_status == "IDLE":
        if state.l2_status in ("DONE", "IDLE", "ENDED", "SKIP"):
            return "DONE"  # 프롬프트 + L2 일치 → DONE
        if state.l25_stalled:
            return "STALLED"

    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Main Monitor Loop
# ---------------------------------------------------------------------------

def run_monitor(targets: list[str], main_sf: str, interval: int, max_rounds: int):
    states: dict[str, SurfaceState] = {sid: SurfaceState(sid) for sid in targets}
    done_set: set[str] = set()
    target_count = len(targets)

    print(f"[{ts()}] 4계층 모니터링 시작: {target_count}개 surface, {interval}초 간격")
    print(f"[{ts()}] L1(패턴) L2(OCR) L2.5(VisionDiff) L3(pipe-pane) 전부 가동")

    for round_num in range(1, max_rounds + 1):
        new_done: list[str] = []
        active_sids = [sid for sid in targets if sid not in done_set]

        if not active_sids:
            break

        # === 병렬 캡처 (L1 + L2 + L3 동시) ===
        def scan_one(sid: str) -> tuple[str, str, str, str, bool]:
            text = read_surface(sid, lines=12)
            l1 = layer1_pattern(text)
            l2 = layer2_ocr_verify(sid, text)
            l3 = layer3_check_pipe_flag(sid)
            return sid, text, l1, l2, l3

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(scan_one, sid): sid for sid in active_sids}
            for future in as_completed(futures, timeout=30):
                try:
                    sid, text, l1, l2, l3 = future.result(timeout=10)
                except Exception:
                    continue

                state = states[sid]
                state.l1_status = l1
                state.l2_status = l2
                state.l3_pipe_flag = l3

                # L2.5 Vision Diff
                cleaned = clean_for_diff(text)
                if state.l25_prev_text and cleaned == state.l25_prev_text:
                    state.l25_stalled = True
                else:
                    state.l25_stalled = False
                state.l25_prev_text = cleaned

                # 종합 판정
                state.final_status = judge_status(state)

        # === 판정 결과 출력 + DONE 수집 ===
        for sid in active_sids:
            state = states[sid]
            status = state.final_status
            layers = f"L1={state.l1_status} L2={state.l2_status} L2.5={'STALLED' if state.l25_stalled else 'OK'} L3={'FLAG' if state.l3_pipe_flag else '-'}"

            if status == "DONE":
                print(f"[{ts()}] surface:{sid} DONE 감지 → 30초 재검증 시작 [{layers}]")
            elif status == "WAITING":
                print(f"[{ts()}] surface:{sid} WAITING (질문 대기) [{layers}]")
                notify_main(main_sf, f"[WATCHER→MAIN] WAITING: surface:{sid} 사용자 입력 대기 중")
            elif status == "STALLED":
                print(f"[{ts()}] surface:{sid} STALLED (화면 고정) [{layers}]")
            else:
                print(f"[{ts()}] surface:{sid} {status} [{layers}]")

        # === 30초 재검증 (DONE 판정된 surface만) ===
        pending_done = [sid for sid in active_sids if states[sid].final_status == "DONE"]
        if pending_done:
            print(f"[{ts()}] 재검증 대기 30초... ({len(pending_done)}개: {','.join(pending_done)})")
            time.sleep(30)

            for sid in pending_done:
                recheck_text = read_surface(sid, lines=12)
                recheck_l1 = layer1_pattern(recheck_text)

                if recheck_l1 in ("WORKING", "WAITING"):
                    print(f"[{ts()}] surface:{sid} ❌ DONE 취소 — 재검증 시 {recheck_l1}")
                    states[sid].final_status = recheck_l1
                    states[sid].recheck_passed = False
                    if recheck_l1 == "WAITING":
                        notify_main(main_sf, f"[WATCHER→MAIN] WAITING: surface:{sid} 사용자 입력 대기 중")
                else:
                    # L2.5 Vision Diff 재확인
                    recheck_cleaned = clean_for_diff(recheck_text)
                    prev_cleaned = states[sid].l25_prev_text
                    if prev_cleaned and recheck_cleaned != prev_cleaned:
                        # 화면이 변했음 → 아직 진행 중일 수 있음
                        print(f"[{ts()}] surface:{sid} ❌ DONE 취소 — 30초간 화면 변화 감지")
                        states[sid].final_status = "WORKING"
                        states[sid].recheck_passed = False
                    else:
                        print(f"[{ts()}] surface:{sid} ✅ DONE 확정 (재검증 통과)")
                        states[sid].recheck_passed = True
                        new_done.append(sid)
                        # === 즉시 개별 보고 — DONE + IDLE 재배정 촉구 강제 ===
                        done_set.add(sid)
                        done_count = len(done_set)
                        remaining = target_count - done_count
                        notify_main(main_sf,
                            f"[WATCHER→MAIN] DONE: s:{sid} 완료 ({done_count}/{target_count}). "
                            f"s:{sid} 지금 IDLE — 다음 작업 배정하세요!"
                            + (f" 나머지 {remaining}개 작업 중." if remaining > 0 else ""))
                        print(f"[{ts()}] Main 즉시 알림: s:{sid} ({done_count}/{target_count}) + IDLE 재배정 촉구")
                    states[sid].l25_prev_text = recheck_cleaned

        # === IDLE 재촉: DONE 확정 후 60초+ 경과한 surface가 여전히 IDLE이면 재촉 ===
        if done_set and not pending_done:
            idle_still = []
            for sid in done_set:
                text = read_surface(sid, lines=5)
                # 아직 IDLE (새 작업 안 받음)
                if not WORKING_PATTERNS.search(text):
                    idle_still.append(sid)
            if idle_still:
                idle_list = ", ".join(f"s:{s}" for s in idle_still)
                print(f"[{ts()}] IDLE 재촉: {idle_list} 아직 놀고 있음")
                notify_main(main_sf, f"[WATCHER→MAIN] ⚠️ IDLE 재촉: {idle_list} 아직 놀고 있음! 작업 배정하세요!")

        # === 전부 DONE이면 최종 알림 ===
        if len(done_set) >= target_count:
            print(f"[{ts()}] ALL {target_count} DONE ✅✅✅")
            notify_main(main_sf, f"[WATCHER→MAIN] ⚠️ ALL {target_count} DONE: 전부 완료! 즉시 결과 수집.")
            return

        # DONE 재검증에서 30초 썼으면 interval 조절
        if not pending_done:
            time.sleep(interval)

    # 타임아웃
    done_count = len(done_set)
    remaining = [sid for sid in targets if sid not in done_set]
    print(f"[{ts()}] 타임아웃. {done_count}/{target_count} 완료. 미완료: {remaining}")
    if done_count > 0 or remaining:
        notify_main(main_sf, f"[WATCHER→MAIN] TIMEOUT: {done_count}/{target_count} 완료. 미완료: s:{', s:'.join(remaining)}")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="4계층 강제 surface 모니터링")
    parser.add_argument("--targets", required=True, help="모니터링 대상 surface IDs (공백 구분)")
    parser.add_argument("--main", required=True, help="Main surface (예: surface:28)")
    parser.add_argument("--interval", type=int, default=20, help="폴링 간격 초 (기본 20)")
    parser.add_argument("--max-rounds", type=int, default=90, help="최대 라운드 (기본 90)")
    args = parser.parse_args()

    targets = args.targets.split()
    run_monitor(targets, args.main, args.interval, args.max_rounds)


if __name__ == "__main__":
    main()
