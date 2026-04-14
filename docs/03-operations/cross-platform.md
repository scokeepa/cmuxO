# Cross-Platform Compatibility

> macOS, Windows, Linux, WSL 호환 메커니즘.

## cmux_compat 데몬

OS별 명령어 차이를 추상화하는 Python 데몬.

- Unix socket: `/tmp/cmux-compat.sock`
- `/cmux-start` 시 자동 시작
- 데몬 불가 시 inline `python3` fallback

## cmux / cmuxw 라우팅

운영 기본값:

- macOS/Linux/WSL: `cmux`
- Windows: `cmuxw` (없으면 `cmux` fallback)
- 공통 override: `CMUX_BIN` 환경변수

Watcher 런타임은 하드코딩 바이너리 호출 대신 라우팅 함수를 통해 명령을 실행한다.

## 추상화 대상

| 명령 | macOS | Linux | 추상화 |
|------|-------|-------|--------|
| `grep -P` | 미지원 | 지원 | `python3 re` |
| `date -j` | 지원 | 미지원 | `python3 datetime` |
| `stat -f` | 지원 | `stat -c` | `python3 os.stat` |

## Watcher bash-free fallback (Windows 우선)

Windows에서 `bash`가 없더라도 watcher 핵심 경로는 동작해야 한다.

- L1 스캔: `eagle_watcher.sh` 불가 시 `cmux tree --all --json` native fallback
- surface 읽기: `read-surface.sh` 실패 시 `cmux capture-pane/read-screen` fallback
- watcher heartbeat: `role-register.sh` 불가 시 `/tmp/cmux-roles.json` 직접 heartbeat 갱신

## WSL 제약

- tmux 클립보드 통합 제한 (`win32yank` 필요)
- `/tmp` 경로가 Windows와 분리됨
- systemd 미지원 시 데몬 자동 시작 수동 설정 필요
