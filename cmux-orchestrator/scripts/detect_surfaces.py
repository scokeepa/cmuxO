#!/usr/bin/env python3
"""cmux surface 자동 감지 — cmux tree --all 출력을 파싱하여 각 AI의 surface 번호를 매핑.

Usage:
    python3 detect_surfaces.py          # JSON 출력
    python3 detect_surfaces.py --env    # export 형식
    python3 detect_surfaces.py --test   # 셀프테스트
"""

import json
import re
import subprocess
import sys


def detect_surfaces() -> dict:
    """cmux tree --all 출력에서 surface 정보를 추출."""
    try:
        tree = subprocess.run(
            ["cmux", "tree", "--all"],
            capture_output=True, text=True, timeout=5
        )
        if tree.returncode != 0:
            return {"error": "cmux tree failed", "surfaces": {}}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"error": "cmux not available", "surfaces": {}}

    # identify로 현재 surface 확인
    try:
        ident = subprocess.run(
            ["cmux", "identify"],
            capture_output=True, text=True, timeout=5
        )
        ident_data = json.loads(ident.stdout) if ident.returncode == 0 else {}
        my_surface = ident_data.get("caller", {}).get("surface_ref", "unknown")
    except Exception:
        my_surface = "unknown"

    lines = tree.stdout.strip().split("\n")
    surfaces = {}

    for line in lines:
        # surface:N [terminal] "title" 패턴 매칭
        match = re.search(r'(surface:\d+)\s+\[terminal\]\s+"([^"]*)"', line)
        if not match:
            continue

        surface_ref = match.group(1)
        title = match.group(2).strip()

        # AI 타입 판별
        ai_type = "unknown"
        if "here" in line:
            ai_type = "opus_main"
        elif "codex" in title.lower():
            ai_type = "codex"
        elif "gemini" in title.lower() or "Ready" in title:
            ai_type = "gemini"
        elif "glm" in title.lower():
            ai_type = "glm"
        elif "Claude Code" in title or "bookforge" in title.lower():
            # Claude Code일 수 있지만 "here"가 아니면 워커
            if surface_ref == my_surface:
                ai_type = "opus_main"
            else:
                ai_type = "claude_worker"

        surfaces[surface_ref] = {
            "title": title,
            "ai_type": ai_type,
            "is_main": "here" in line,
        }

    # 워커 surface 목록 (main 제외)
    workers = {k: v for k, v in surfaces.items() if not v["is_main"]}

    return {
        "my_surface": my_surface,
        "total_surfaces": len(surfaces),
        "worker_count": len(workers),
        "surfaces": surfaces,
        "workers": workers,
        "codex": next((k for k, v in surfaces.items() if v["ai_type"] == "codex"), None),
        "gemini": next((k for k, v in surfaces.items() if v["ai_type"] == "gemini"), None),
        "glm_surfaces": [k for k, v in surfaces.items() if v["ai_type"] in ("glm", "claude_worker")],
    }


def _run_test():
    """셀프테스트."""
    result = detect_surfaces()
    assert isinstance(result, dict), "Must return dict"
    assert "surfaces" in result, "Must have surfaces key"
    assert "my_surface" in result, "Must have my_surface key"
    print(json.dumps({"status": "success", "detected": result}, indent=2, ensure_ascii=False))
    return True


if __name__ == "__main__":
    if "--test" in sys.argv:
        success = _run_test()
        sys.exit(0 if success else 1)
    elif "--env" in sys.argv:
        result = detect_surfaces()
        if result.get("codex"):
            print(f"export CMUX_CODEX={result['codex']}")
        if result.get("gemini"):
            print(f"export CMUX_GEMINI={result['gemini']}")
        for i, glm in enumerate(result.get("glm_surfaces", []), 1):
            print(f"export CMUX_GLM{i}={glm}")
    else:
        print(json.dumps(detect_surfaces(), indent=2, ensure_ascii=False))
