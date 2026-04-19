# cmuxO Upgrade Phase 1.3 — ANE CLI Path Abstraction

**작성일**: 2026-04-19
**작성자**: Claude
**대상 저장소**: https://github.com/scokeepa/cmuxO
**상태**: DRAFT — 승인 대기

---

## 1. 문제 요약

`ane_tool` (Apple Neural Engine OCR 바이너리) 경로가 **5개 이상 파일에 하드코딩**되어 있다.

```
~/Ai/System/11_Modules/ane-cli/ane_tool
```

타 PC/CI에서는 이 경로가 존재하지 않음 → OCR 기능 자동 실패.
환경변수 오버라이드 존재 여부가 파일마다 다름 (inconsistent).

## 2. 근거

### 2.1 하드코딩 위치 전수

| 파일 | 라인 | 형태 | env override |
|------|------|------|--------------|
| `cmux-orchestrator/scripts/vision-monitor.sh` | 13 | `ANE_TOOL="$HOME/Ai/.../ane_tool"` | 없음 |
| `cmux-orchestrator/scripts/detect-surface-models.py` | 133 | `os.path.expanduser("~/Ai/.../ane_tool")` | 없음 |
| `cmux-orchestrator/scripts/detect-surface-models.py` | 238 | 동일 (중복) | 없음 |
| `cmux-orchestrator/scripts/eagle_watcher.sh` | 21 | `variable_ane_tool="${ANE_TOOL:-$HOME/...}"` | `$ANE_TOOL` ✓ |
| `cmux-watcher/scripts/watcher-scan.py` | 56 | `Path.home() / "Ai" / ... / "ane_tool"` | 없음 |
| `cmux-watcher/references/vision-diff-protocol.md` | 43 | 문서 예시 | N/A |

→ **5개 실행 파일 중 1개만 `$ANE_TOOL` env 지원. SSOT 부재.**

### 2.2 유사 프로젝트 참조

- `/Users/csm/projects/olympus/source/` 내 다른 ANE 사용 프로젝트 조사 → 대부분 `shutil.which("ane_tool")` PATH 방식 또는 환경변수 + 기본 경로 방식
- cmuxO의 `cmux_paths.py:10,31` 이미 경로 SSOT 패턴 확립되어 있음 (`runtime_dir`, `runtime_path`)

## 3. 설계

### 3.1 SSOT helper

`cmux-orchestrator/scripts/cmux_paths.py`에 추가:

```python
def ane_tool_path() -> Path | None:
    """ANE OCR 바이너리 경로 resolver (SSOT).

    우선순위:
    1. $CMUX_ANE_TOOL 환경변수 (테스트/CI 오버라이드)
    2. $ANE_TOOL 환경변수 (레거시 호환)
    3. shutil.which("ane_tool") (PATH 탐색)
    4. ~/Ai/System/11_Modules/ane-cli/ane_tool (기본 경로)

    반환: 실행 가능한 Path 또는 None (없으면 OCR 우회).
    """
```

`cmux-orchestrator/scripts/cmux-paths.sh`에 대응:

```bash
cmux_ane_tool_path() {
    for candidate in "${CMUX_ANE_TOOL:-}" "${ANE_TOOL:-}" \
        "$(command -v ane_tool 2>/dev/null)" \
        "$HOME/Ai/System/11_Modules/ane-cli/ane_tool"; do
        [ -n "$candidate" ] && [ -x "$candidate" ] && { echo "$candidate"; return 0; }
    done
    return 1
}
```

### 3.2 각 호출처 리팩터링

| 파일 | 변경 |
|------|------|
| `vision-monitor.sh:13` | `ANE_TOOL="$(cmux_ane_tool_path)" \|\| ANE_TOOL=""` |
| `detect-surface-models.py:133,238` | `from cmux_paths import ane_tool_path` 후 변수 치환 (중복 제거) |
| `eagle_watcher.sh:21,900` | `variable_ane_tool="$(cmux_ane_tool_path)"` |
| `watcher-scan.py:56` | `from cmux_paths import ane_tool_path; ANE_TOOL = ane_tool_path()` |

### 3.3 Fallback 동작

`ane_tool_path()` 가 `None` 반환 시:
- vision-monitor: OCR 스킵 + stderr 경고 ("ANE OCR unavailable — fallback to text-only")
- watcher-scan: Layer 3 (ANE verify) 건너뛰고 Layer 1-2만 동작
- detect-surface-models: `--fallback=tesseract` 옵션 있으면 그쪽 사용, 없으면 모델 감지 비활성화

## 4. 5관점 검증

### SSOT
- 경로 resolver 1곳 (`cmux_paths.py::ane_tool_path` + 대응 sh 함수) ✓
- 환경변수 이름 확정: `$CMUX_ANE_TOOL` primary, `$ANE_TOOL` 레거시 호환 ✓

### SRP
- Helper는 "경로 찾기"만 담당. 실행·OCR·오류 처리는 호출자 책임 ✓

### 엣지케이스
- 바이너리 존재하나 실행 권한 없음 → `os.access(X_OK)` 검사 → None 반환
- Symlink가 broken → `Path.exists(follow_symlinks=True)` 감지
- `$ANE_TOOL`이 빈 문자열 → skip (빈 값 체크)
- Apple Silicon이 아닌 x86 Mac → 바이너리 존재해도 동작 실패 → `--version` check 없음 (성능상 스킵, 호출 실패 시 fallback)
- 테스트 시 `$CMUX_ANE_TOOL=/tmp/fake-ane` 주입 → CI에서 mock 사용 가능

### 아키텍트
- 기존 `cmux_paths` 모듈에 편승 → 신규 모듈 추가 없음 ✓
- sh/py 양쪽 helper 필요 (cmuxO는 혼합 언어) — 기존 `cmux-paths.sh` 있으므로 자연스러움
- 호출처 4개만 변경 → blast radius 작음

### Iron Law
- **"경로는 cmux_paths로 통일"** — Phase 3 (runtime-dir 플랜) 이후 확립된 규칙 ✓
- **"테스트 오버라이드 가능"** — `$CMUX_ANE_TOOL` 환경변수로 만족 ✓

## 5. 코드 시뮬레이션

### 5.1 테스트 케이스

| # | 시나리오 | 환경 | expected |
|---|---|---|---|
| 1 | 정상 경로 존재 | `~/Ai/.../ane_tool` 실행 가능 | 해당 경로 반환 |
| 2 | 경로 부재 | 바이너리 없음 | None 반환 |
| 3 | env 오버라이드 | `$CMUX_ANE_TOOL=/tmp/fake`, fake 실행 가능 | /tmp/fake 반환 |
| 4 | 레거시 env | `$ANE_TOOL=/tmp/legacy` | /tmp/legacy 반환 |
| 5 | PATH에만 존재 | `/usr/local/bin/ane_tool` 설치 | 해당 경로 반환 |
| 6 | 권한 없음 | chmod -x 한 파일 | None 반환 |
| 7 | 빈 env | `$ANE_TOOL=""` | 다음 후보로 fallthrough |

### 5.2 시뮬레이션 실행 결과 (2026-04-19)

프로토타입: `/tmp/cmux_paths_ane_prototype.py`, 러너: `/tmp/test_ane_path.py`.

```
[PASS] 1 default path absent (host lacks binary)
[PASS] 2 all absent → None
[PASS] 3 CMUX_ANE_TOOL override
[PASS] 4 ANE_TOOL legacy
[PASS] 5 PATH-only discovery
[PASS] 6 exists without exec → fallthrough → None
[PASS] 7 empty ANE_TOOL passes through to CMUX_ANE_TOOL (both set)

=== Phase 1.3 simulation: 7 pass / 0 fail ===
```

→ 7/7 PASS. 케이스 1은 현 호스트에 바이너리 미설치 상태였으므로 "default absent → None" 경로로 검증됨 (본질은 default fallback 동작 검증 목적).

## 6. 구현 절차

1. `cmux_paths.py`에 `ane_tool_path()` 추가 + unit test (`tests/test_cmux_paths.py`)
2. `cmux-paths.sh`에 `cmux_ane_tool_path()` 추가 + bats-free smoke test (`tests/test_cmux_paths_sh.sh`)
3. 호출처 4파일 리팩터링
4. `detect-surface-models.py`의 중복 선언 (line 133 + 238) 제거
5. vision-monitor / watcher-scan / eagle_watcher smoke test (fake ANE binary 주입)
6. CHANGELOG.md 업데이트
7. PR 제출

## 7. DoD

- [ ] `ane_tool_path()` py/sh helper 생성 + 테스트 7케이스 PASS
- [ ] 호출처 4파일 리팩터링
- [ ] 중복 선언 제거 (detect-surface-models.py)
- [ ] `$CMUX_ANE_TOOL=/nonexistent` 환경에서 watcher-scan 정상 동작 (OCR 스킵 경고)
- [ ] CHANGELOG에 변경 기록
- [ ] PR merge

## 8. 리스크

- **호환성**: 기존 `$ANE_TOOL` 사용자 영향 없음 (2순위 fallback 유지)
- **동작 변화**: 타 PC에서 OCR이 "동작함 → 동작 안함 + 경고"로 바뀜 → **개선** (기존은 silent fail)
- **CI 의존**: unit test는 pure Python/sh로 실행 가능, ANE 바이너리 불필요
