<p align="center">
  <img src="cmuxO-logo.svg" alt="cmuxO 로고" width="260">
</p>

<h1 align="center">cmuxO</h1>
<p align="center"><strong>cmux 오케스트레이션 JARVIS 와쳐 팩</strong></p>
<p align="center"><strong>언어:</strong> 한국어 | <a href="README.md">English</a></p>

---

## 개요

`cmuxO`는 Claude Code 멀티 에이전트 오케스트레이션 팩입니다.  
Boss, Watcher, JARVIS를 결합해 병렬 작업, 상태 감시, 운영 자동화를 제공합니다.

- 병렬 작업 배정 및 수집
- 4계층 watcher 감시(Eagle/OCR/VisionDiff/pipe-pane)
- 운영 가드 훅 + 상태 머신
- 크로스플랫폼 라우팅(macOS=`cmux`, Windows=`cmuxw`)

---

## 빠른 시작

```bash
bash install.sh
```

설치 후:

```text
/cmux-start
```

종료:

```text
/cmux-stop
```

---

## 플랫폼

- macOS 바이너리: [manaflow-ai/cmux](https://github.com/manaflow-ai/cmux)
- Windows 바이너리: [scokeepa/cmuxw](https://github.com/scokeepa/cmuxw)
- 강제 지정: `CMUX_BIN=/path/to/cmux-or-cmuxw`

### Lid Auto-Pause (macOS)

맥북 뚜껑을 닫으면 오케스트레이션이 자동 일시중지되고, 다시 열면 재개됩니다. `install.sh`가 필요 시 `sleepwatcher`를 설치하고 `~/.sleep`/`~/.wakeup`에 마커 블록으로 훅을 심어 `/tmp/cmux-paused.flag`를 토글합니다. 사용자가 직접 작성한 훅 내용은 보존됩니다. `/cmux-uninstall`로 깔끔히 제거.

---

## 문서

- 전체 영문 문서: [README.md](README.md)
- 개발/운영 문서: `docs/`
- 변경 이력: `docs/CHANGELOG.md`

---

## 라이선스

MIT
