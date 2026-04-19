#!/usr/bin/env python3
"""detect-surface-models.py v4 — 실시간 surface 모델/역할/상태 감지 + 자동 boss 등록

핵심 강제 동작:
1. 전 workspace 순차 스캔 (0.3초 스로틀, 소켓 보호)
2. /cmux 입력된 surface → boss로 자동 등록 + 엔터 전송
3. 역할 레지스트리(/tmp/cmux-roles.json) 자동 갱신
4. 스캔 결과를 /tmp/cmux-surface-scan.json에 자동 저장
5. Apple Vision OCR fallback (screen text 감지 실패 시)

AI 판단 의존 ZERO — 모든 동작이 스크립트 내부에서 자동 수행.
"""
import json, re, subprocess, sys, time, os
from pathlib import Path
from datetime import datetime, timezone

THROTTLE_DELAY = 0.3
ROLES_FILE = Path("/tmp/cmux-roles.json")
SCAN_FILE = Path("/tmp/cmux-surface-scan.json")

_SCRIPT_DIR = Path(__file__).parent.resolve()
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
try:
    from cmux_paths import ane_tool_path
except ImportError:
    def ane_tool_path():
        p = Path.home() / "Ai/System/11_Modules/ane-cli/ane_tool"
        return p if p.exists() and os.access(p, os.X_OK) else None

def run(cmd, timeout=10):
    try:
        if isinstance(cmd, str):
            import shlex
            cmd = shlex.split(cmd)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""

def detect_model(screen_text):
    if not screen_text:
        return "unknown"
    m = re.search(r'(Opus|Sonnet|Haiku)\s+[\d]+\.[\d]+(?:\s*\([^)]+\))?', screen_text, re.I)
    if m: return m.group(0).strip()
    m = re.search(r'(gpt-[\d]+\.[\d]+|o[\d]+-?(?:pro|mini)?)', screen_text, re.I)
    if m: return f"Codex ({m.group(0)})"
    m = re.search(r'glm-[\d]+\.[\d]+', screen_text, re.I)
    if m: return m.group(0)
    m = re.search(r'MiniMax-M[\d]+\.[\d]+', screen_text, re.I)
    if m: return m.group(0)
    m = re.search(r'gemini-[\d]+\.[\d]+-?(?:pro|flash|ultra)?', screen_text, re.I)
    if m: return m.group(0)
    m = re.search(r'deepseek-(?:v[\d]+|r[\d]+|coder)', screen_text, re.I)
    if m: return m.group(0)
    m = re.search(r'qwen[\d]*(?:-[\d]+b)?', screen_text, re.I)
    if m: return m.group(0)
    return "unknown"

def detect_status(screen_text):
    if not screen_text: return "UNKNOWN"
    if re.search(r'⏳|Working|running|interrupt|Thinking|■⬝', screen_text): return "WORKING"
    if re.search(r'DONE:|완료', screen_text): return "DONE"
    if re.search(r'Error|ERROR|API Error|rate.limit|OVERLOADED|context_length_exceeded', screen_text, re.I): return "ERROR"
    return "IDLE"

def detect_has_cmux(screen_text):
    """화면에 /cmux가 입력되어 대기 중인지 감지

    실제 화면 출력 예시:
      ❯ /cmux
      ──────────────────────────────────────
      /cmux           /cmux — cmux 멀티 AI …

    /cmux 뒤에 공백 패딩이 많고, 자동완성 메뉴가 아래에 나옴.
    /cmux-watcher, /cmux-orchestrator 등은 다른 명령이므로 제외.
    """
    if not screen_text:
        return False
    # "❯ /cmux" 패턴 — 뒤에 공백/줄끝 허용, -watcher 등 제외
    if re.search(r'[❯›>]\s*/cmux\s*$', screen_text, re.MULTILINE):
        return True
    # "❯ /cmux" + 뒤에 공백 패딩 (read-screen이 공백으로 줄을 채움)
    if re.search(r'[❯›>]\s*/cmux\s{2,}', screen_text):
        return True
    # 자동완성 메뉴 패턴: "/cmux" 줄 + 다음 줄에 "─" 구분선 또는 자동완성 항목
    if re.search(r'❯\s*/cmux\s*\n[─\s]*\n.*?/cmux\s', screen_text):
        return True
    return False

def load_roles():
    try:
        if ROLES_FILE.exists():
            return json.loads(ROLES_FILE.read_text())
    except Exception:
        pass
    return {}

def save_roles(roles):
    tmp = str(ROLES_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(roles, indent=2, ensure_ascii=False))
    os.rename(tmp, str(ROLES_FILE))

def detect_role(screen_text, surface_ref=""):
    """역할 감지: 1) 레지스트리(TTL 검증) → 2) 화면 패턴"""
    from datetime import datetime, timezone, timedelta
    roles = load_roles()
    for role, info in roles.items():
        if info.get("surface") == surface_ref:
            # TTL 검증: last_heartbeat가 5분 이내인지
            hb = info.get("last_heartbeat", "")
            if hb:
                try:
                    ts = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - ts) > timedelta(minutes=5):
                        continue  # stale role → 무시, 다음 엔트리 확인
                except (ValueError, TypeError):
                    pass
            return role
    if not screen_text:
        return "worker"
    if re.search(r'W:\d.*I:\d|요약\s*:|watcher|센티넬|eagle|감시', screen_text):
        return "watcher"
    return "worker"

def parse_tree(tree_text):
    ws_map = {}
    titles = {}
    current_ws = None
    for line in tree_text.splitlines():
        wm = re.search(r'workspace:\d+', line)
        if wm: current_ws = wm.group(0)
        sm = re.search(r'(surface:\d+)', line)
        if sm and current_ws:
            ws_map[sm.group(1)] = current_ws
        tm = re.search(r'"([^"]+)"', line)
        if sm and tm:
            titles[sm.group(1)] = tm.group(1)
    return ws_map, titles

def vision_ocr_fallback(surf_ref, ws_ref):
    """Apple Vision OCR — ane_tool 사용 (외부 의존 없음, macOS 전용)"""
    ane = ane_tool_path()
    if ane is None:
        return None
    try:
        tmpimg = f"/tmp/cmux-vision-{surf_ref.replace(':','')}.png"
        run(f"screencapture -x {tmpimg}", timeout=5)
        if os.path.exists(tmpimg) and os.path.getsize(tmpimg) > 100:
            out = run(f"{ane} ocr {tmpimg}", timeout=15)
            try:
                os.unlink(tmpimg)
            except Exception:
                pass
            return out
    except Exception:
        pass
    return None

def main():
    self_surface = sys.argv[1] if len(sys.argv) > 1 else ""
    no_activate = "--no-activate" in sys.argv
    no_save = "--no-save" in sys.argv
    as_watcher = "--as-watcher" in sys.argv  # 와쳐 자체 등록 + 감지 + 엔터 한번에

    my_ref = f"surface:{self_surface}"

    # --as-watcher: 먼저 와쳐로 등록 (detect 전에!)
    if as_watcher and self_surface:
        roles = load_roles()
        now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        # cmux identify에서 workspace 가져오기
        id_out = run("cmux identify")
        my_ws = ""
        if id_out:
            try:
                import json as _j
                my_ws = _j.loads(id_out).get("caller", {}).get("workspace_ref", "")
            except Exception:
                pass
        roles["watcher"] = {
            "surface": my_ref, "workspace": my_ws,
            "pid": os.getpid(),
            "started_at": now_iso, "last_heartbeat": now_iso,
        }
        save_roles(roles)
        print(f"[AUTO] {my_ref} → watcher 등록 완료", file=sys.stderr)

    # 엔터 전송은 와쳐만 가능
    caller_is_watcher = False
    roles = load_roles()
    if roles.get("watcher", {}).get("surface") == my_ref:
        caller_is_watcher = True

    tree = run("cmux tree --all")
    if not tree:
        print("{}")
        return

    ws_map, titles = parse_tree(tree)

    by_ws = {}
    for surf_ref, ws_ref in ws_map.items():
        surf_num = surf_ref.split(':')[1]
        if surf_num == self_surface:
            continue
        by_ws.setdefault(ws_ref, []).append(surf_ref)

    result = {}
    cmux_surfaces = []  # /cmux가 감지된 surface들

    for ws_ref in sorted(by_ws.keys()):
        surfaces = sorted(by_ws[ws_ref], key=lambda x: int(x.split(':')[1]))
        for surf_ref in surfaces:
            # capture-pane 우선 (input buffer + 자동완성 메뉴 포함, 30줄로 충분히)
            screen = run(f'cmux capture-pane --workspace "{ws_ref}" --surface {surf_ref} --scrollback --lines 30')
            if not screen:
                # fallback: read-screen
                screen = run(f'cmux read-screen --workspace "{ws_ref}" --surface {surf_ref} --lines 15')
            if not screen:
                screen = ""

            model = detect_model(screen)
            if model == "unknown" and surf_ref in titles:
                title = titles[surf_ref]
                if "codex" in title.lower(): model = "Codex (tab)"
                elif "claude" in title.lower(): model = "Claude (tab)"
                else: model = f"({title})"

            role = detect_role(screen, surf_ref)
            has_cmux = detect_has_cmux(screen)

            result[surf_ref] = {
                "model": model,
                "status": detect_status(screen),
                "role": role,
                "workspace": ws_ref,
            }

            if has_cmux:
                cmux_surfaces.append((surf_ref, ws_ref))
                result[surf_ref]["has_cmux"] = True

            time.sleep(THROTTLE_DELAY)

    # === 0. /cmux 미감지 + 와쳐 → 3단계 강제 감지 ===
    if not cmux_surfaces and not no_activate and caller_is_watcher:
        ane_tool = ane_tool_path()

        # --- 단계 1: Apple Vision OCR 강제 시도 ---
        if ane_tool is not None:
            print("[VISION] read-screen 미감지 → Apple Vision OCR 강제 실행", file=sys.stderr)
            run("screencapture -x /tmp/cmux-vision-scan.png", timeout=5)
            vision_out = run(f"{ane_tool} ocr /tmp/cmux-vision-scan.png", timeout=15)
            if vision_out:
                try:
                    vdata = json.loads(vision_out)
                    texts = vdata.get("texts", [])
                    cmux_texts = [t for t in texts if "/cmux" in str(t) and "/cmux-" not in str(t)]
                    if cmux_texts:
                        print(f"[VISION] /cmux 감지됨: {cmux_texts[:3]}", file=sys.stderr)
                        # 어느 surface인지 특정 불가 → scrollback으로 재확인
                        for s, i in result.items():
                            if i.get("status") in ("IDLE", "UNKNOWN") and ("Opus" in i.get("model","") or "Claude" in i.get("model","")):
                                ws = i.get("workspace", "")
                                screen2 = run(f'cmux read-screen --workspace "{ws}" --surface {s} --scrollback --lines 30')
                                if screen2 and detect_has_cmux(screen2):
                                    cmux_surfaces.append((s, ws))
                                    result[s]["has_cmux"] = True
                                    print(f"[VISION] {s}에서 /cmux 확인!", file=sys.stderr)
                                    break
                    else:
                        print("[VISION] OCR에서 /cmux 미발견", file=sys.stderr)
                except Exception as e:
                    print(f"[VISION] OCR 파싱 실패: {e}", file=sys.stderr)

        # --- 단계 2: Vision도 실패 → 같은 workspace IDLE Opus에 /cmux 직접 전송 ---
        if not cmux_surfaces:
            print("[FORCE] 감지 전부 실패 → IDLE surface를 boss 후보로 등록 (엔터는 step 3에서)", file=sys.stderr)
            my_ref = f"surface:{self_surface}"
            for s, i in result.items():
                if s == my_ref:
                    continue
                if i.get("status") in ("IDLE", "UNKNOWN") and ("Opus" in i.get("model","") or "Claude" in i.get("model","")):
                    ws = i.get("workspace", "")
                    print(f"[FORCE] {s} → boss 후보 (엔터는 아직 안 침)", file=sys.stderr)
                    cmux_surfaces.append((s, ws))
                    result[s]["has_cmux"] = True
                    result[s]["needs_cmux_send"] = True  # step 3에서 /cmux 전송 필요
                    break

    # === 1. boss 역할 등록 (엔터 전에 먼저) ===
    if cmux_surfaces and not no_activate:
        roles = load_roles()
        now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        boss_surf, boss_ws = cmux_surfaces[0]
        roles["boss"] = {
            "surface": boss_surf, "workspace": boss_ws,
            "pid": os.getpid(), "started_at": now_iso, "last_heartbeat": now_iso,
        }
        save_roles(roles)
        result[boss_surf]["role"] = "boss"
        print(f"[AUTO] {boss_surf} → boss 등록 완료", file=sys.stderr)

    # === 2. 스캔 결과 저장 (와쳐 자신도 포함!) ===
    if not no_save:
        my_ref = f"surface:{self_surface}" if self_surface else "unknown"
        # 와쳐 자신을 결과에 추가 (스캔 시 self_surface 스킵하므로)
        if self_surface and my_ref not in result:
            roles_now = load_roles()
            my_role = "worker"
            for role, info in roles_now.items():
                if info.get("surface") == my_ref:
                    my_role = role
                    break
            my_ws = roles_now.get(my_role, {}).get("workspace", "")
            result[my_ref] = {
                "model": "self (scanner)",
                "status": "ACTIVE",
                "role": my_role,
                "workspace": my_ws,
            }
        scan_data = {
            "surfaces": result,
            "scanned_by": my_ref,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        SCAN_FILE.write_text(json.dumps(scan_data, indent=2, ensure_ascii=False))
        print(f"[AUTO] 스캔 결과 저장: {SCAN_FILE}", file=sys.stderr)

    # === 3. 엔터 신호 파일 생성 (detect 안에서 엔터 안 침! Stop hook이 처리) ===
    if cmux_surfaces and not no_activate and caller_is_watcher:
        boss_surf, boss_ws = cmux_surfaces[0]
        needs_send = result.get(boss_surf, {}).get("needs_cmux_send", False)
        signal = {
            "boss_surface": boss_surf,
            "boss_workspace": boss_ws,
            "needs_cmux_send": needs_send,
            "ready_at": datetime.now(timezone.utc).isoformat(),
        }
        Path("/tmp/cmux-watcher-enter-signal.json").write_text(json.dumps(signal, indent=2))
        print(f"[AUTO] 엔터 신호 저장: /tmp/cmux-watcher-enter-signal.json (Stop hook이 처리)", file=sys.stderr)

    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
