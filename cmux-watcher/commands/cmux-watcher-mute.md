# /cmux-watcher-mute — 와쳐 알림 토글

입력: `$ARGUMENTS`

와쳐의 다른 세션 메시지 전송을 켜고 끕니다. 스캔은 계속됩니다.

---

## 라우팅

### 빈 입력 → 토글 (현재 상태 반전)

```bash
if [ -f /tmp/cmux-watcher-muted.flag ]; then
    rm -f /tmp/cmux-watcher-muted.flag
    echo "🔊 와쳐 알림 켜짐 (unmuted)"
else
    touch /tmp/cmux-watcher-muted.flag
    echo "🔇 와쳐 알림 꺼짐 (muted) — 스캔은 계속됩니다"
fi
```

### `on` → 알림 끄기 (mute)

```bash
touch /tmp/cmux-watcher-muted.flag
echo "🔇 와쳐 알림 꺼짐 (muted)"
```

### `off` → 알림 켜기 (unmute)

```bash
rm -f /tmp/cmux-watcher-muted.flag
echo "🔊 와쳐 알림 켜짐 (unmuted)"
```

### `status` → 현재 상태

```bash
if [ -f /tmp/cmux-watcher-muted.flag ]; then
    echo "현재 상태: 🔇 MUTED (알림 꺼짐, 스캔 중)"
else
    echo "현재 상태: 🔊 ACTIVE (알림 + 스캔 모두 동작)"
fi
```
