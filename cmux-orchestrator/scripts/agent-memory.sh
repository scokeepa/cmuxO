#!/bin/bash
# agent-memory.sh — cmux 오케스트레이션 영구 메모리 CLI
#
# 사용법:
#   bash agent-memory.sh drain       — 저널 → memories.json 통합
#   bash agent-memory.sh query [kw]  — 메모리 검색
#   bash agent-memory.sh stats       — 통계 출력
#   bash agent-memory.sh --self-test — 내장 테스트 실행
#
# memories.json 스키마:
# [{"id":"mem-TS","created_at":"ISO","source":"journal-drain",
#   "summary":"dispatch 5건","events":[...],"event_counts":{...}}]

set -e

MEMORY_DIR="$HOME/.claude/memory/cmux"
JOURNAL="$MEMORY_DIR/journal.jsonl"
MEMORIES="$MEMORY_DIR/memories.json"

# ─── 유틸 ────────────────────────────────────────

_ensure_dir() {
  mkdir -p -m 700 "$MEMORY_DIR" 2>/dev/null || true
}

_file_size() {
  local f="$1"
  [ -f "$f" ] || { echo 0; return; }
  stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0
}

# ─── _merge_draining ─────────────────────────────

_merge_draining() {
  local draining_file="$1"
  [ -f "$draining_file" ] || return 0
  _ensure_dir

  # memories.json 없으면 빈 배열로 생성
  [ -f "$MEMORIES" ] || echo '[]' > "$MEMORIES"

  python3 -c "
import fcntl, json, os, sys, time
from collections import Counter

draining = sys.argv[1]
memories = sys.argv[2]

# JSONL 파싱
events = []
with open(draining) as f:
    for line in f:
        line = line.strip()
        if line:
            try: events.append(json.loads(line))
            except: pass

if not events:
    sys.exit(0)

# 이벤트 집계
counts = Counter(e.get('event','unknown') for e in events)
summary_parts = [f'{k} {v}건' for k,v in counts.most_common()]

entry = {
    'id': f'mem-{int(time.time())}',
    'created_at': events[-1].get('ts', ''),
    'source': 'journal-drain',
    'summary': ', '.join(summary_parts),
    'events': events,
    'event_counts': dict(counts),
}

# memories.json에 atomic append (fcntl.flock)
with open(memories, 'r+') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.seek(0)
    try: mems = json.load(f)
    except: mems = []
    if not isinstance(mems, list): mems = []
    mems.append(entry)
    f.seek(0)
    f.truncate()
    json.dump(mems, f, indent=2, ensure_ascii=False)
    fcntl.flock(f, fcntl.LOCK_UN)

sep = ', '
print(f'[drain] {len(events)}개 이벤트 → memories.json 병합 완료 ({sep.join(summary_parts)})')
" "$draining_file" "$MEMORIES"
}

# ─── drain ───────────────────────────────────────

cmd_drain() {
  _ensure_dir

  # .draining orphan 복구 (#1)
  if [ -f "$JOURNAL.draining" ]; then
    echo "[WARN] orphan .draining 발견 — 복구 처리" >&2
    _merge_draining "$JOURNAL.draining"
    rm -f "$JOURNAL.draining"
  fi

  # 저널 없으면 종료
  if [ ! -f "$JOURNAL" ]; then
    echo "No journal to drain"
    return 0
  fi

  # python3 fcntl.flock으로 rename 보호 (macOS에 bash flock 없음)
  python3 -c "
import fcntl, os, sys
lock_path = sys.argv[1]
journal  = sys.argv[2]
draining = journal + '.draining'
with open(lock_path, 'w') as lf:
    fcntl.flock(lf, fcntl.LOCK_EX)
    if os.path.exists(journal):
        os.rename(journal, draining)
    fcntl.flock(lf, fcntl.LOCK_UN)
" "$JOURNAL.lock" "$JOURNAL"

  # .draining → memories.json 병합
  if [ -f "$JOURNAL.draining" ]; then
    _merge_draining "$JOURNAL.draining"
    rm -f "$JOURNAL.draining"
  else
    echo "No journal to drain"
    return 0
  fi

  # rotation (#13): memories.json 5MB 초과 → 아카이브
  local mem_size
  mem_size=$(_file_size "$MEMORIES")
  if [ "$mem_size" -gt 5242880 ]; then
    local archive_dir="$MEMORY_DIR/archive"
    local archive_file="$archive_dir/$(date +%Y%m%d_%H%M%S).json"
    mkdir -p -m 700 "$archive_dir"
    mv "$MEMORIES" "$archive_file"
    echo '[]' > "$MEMORIES"
    echo "[INFO] memories.json archived → $archive_file" >&2
  fi

  rm -f "$JOURNAL.lock"
}

# ─── query ───────────────────────────────────────

cmd_query() {
  local keyword="$1"
  if [ -z "$keyword" ]; then
    echo "Usage: agent-memory.sh query <keyword>"
    return 1
  fi
  if [ ! -f "$MEMORIES" ]; then
    echo "No memories found"
    return 0
  fi

  python3 -c "
import json, sys
keyword = sys.argv[1]
with open(sys.argv[2]) as f:
    mems = json.load(f)
matches = [m for m in mems if keyword.lower() in json.dumps(m, ensure_ascii=False).lower()]
if not matches:
    print(f'No matches for \"{keyword}\"')
else:
    print(f'{len(matches)}건 매칭:')
    for m in matches[-10:]:
        print(f'  [{m.get(\"id\",\"?\")}] {m.get(\"summary\",\"?\")[:80]}')
" "$keyword" "$MEMORIES"
}

# ─── stats ───────────────────────────────────────

cmd_stats() {
  _ensure_dir
  echo "=== agent-memory stats ==="

  if [ -f "$JOURNAL" ]; then
    local j_size j_lines
    j_size=$(_file_size "$JOURNAL")
    j_lines=$(wc -l < "$JOURNAL" 2>/dev/null || echo 0)
    echo "journal: ${j_lines} lines, ${j_size} bytes"
  else
    echo "journal: (none)"
  fi

  if [ -f "$MEMORIES" ]; then
    local m_size m_count
    m_size=$(_file_size "$MEMORIES")
    m_count=$(python3 -c "
import json
with open('$MEMORIES') as f: d=json.load(f)
print(len(d) if isinstance(d,list) else 0)
" 2>/dev/null || echo "?")
    echo "memories: ${m_count} entries, ${m_size} bytes"
  else
    echo "memories: (none)"
  fi

  if [ -d "$MEMORY_DIR/archive" ]; then
    local a_count
    a_count=$(ls "$MEMORY_DIR/archive/"*.json 2>/dev/null | wc -l || echo 0)
    echo "archives: ${a_count} files"
  fi

  if [ -f "$JOURNAL.draining" ]; then
    echo "WARNING: orphan .draining file exists!"
  fi
}

# ─── self-test ───────────────────────────────────

cmd_self_test() {
  set +e  # 테스트 내부에서 에러가 스크립트를 종료하지 않도록
  echo "=== agent-memory self-test ==="
  local TEST_DIR
  TEST_DIR=$(mktemp -d /tmp/cmux-mem-test-XXXXXX)
  local ORIG_MEMORY_DIR="$MEMORY_DIR"
  local ORIG_JOURNAL="$JOURNAL"
  local ORIG_MEMORIES="$MEMORIES"

  # 테스트용 디렉토리로 교체
  MEMORY_DIR="$TEST_DIR"
  JOURNAL="$TEST_DIR/journal.jsonl"
  MEMORIES="$TEST_DIR/memories.json"

  local passed=0
  local failed=0

  # T1: 저널 기록 + drain → memories.json 생성
  echo '{"ts":"2026-03-31T00:00:00Z","event":"dispatch","surface":"surface:5","cmd_short":"cmux send --surface surface:5"}' > "$JOURNAL"
  echo '{"ts":"2026-03-31T00:01:00Z","event":"dept_create","surface":"","cmd_short":"cmux create-workspace test"}' >> "$JOURNAL"
  cmd_drain > /dev/null 2>&1
  if [ -f "$MEMORIES" ] && python3 -c "import json; d=json.load(open('$MEMORIES')); assert len(d)==1; assert d[0]['event_counts']['dispatch']==1" 2>/dev/null; then
    echo "  T1 drain basic: PASS"
    passed=$((passed+1))
  else
    echo "  T1 drain basic: FAIL"
    failed=$((failed+1))
  fi

  # T2: .draining orphan 복구
  echo '{"ts":"2026-03-31T01:00:00Z","event":"dispatch","surface":"surface:7","cmd_short":"cmux send orphan"}' > "$JOURNAL.draining"
  cmd_drain > /dev/null 2>&1
  if python3 -c "import json; d=json.load(open('$MEMORIES')); assert len(d)==2" 2>/dev/null; then
    echo "  T2 orphan recovery: PASS"
    passed=$((passed+1))
  else
    echo "  T2 orphan recovery: FAIL"
    failed=$((failed+1))
  fi

  # T3: 빈 저널 drain
  local drain_out
  drain_out=$(cmd_drain 2>/dev/null)
  if echo "$drain_out" | grep -q "No journal"; then
    echo "  T3 empty drain: PASS"
    passed=$((passed+1))
  else
    echo "  T3 empty drain: FAIL"
    failed=$((failed+1))
  fi

  # T4: query 키워드 검색
  local query_out
  query_out=$(cmd_query "dispatch" 2>/dev/null)
  if echo "$query_out" | grep -q "매칭"; then
    echo "  T4 query: PASS"
    passed=$((passed+1))
  else
    echo "  T4 query: FAIL"
    failed=$((failed+1))
  fi

  # T5: stats 출력
  local stats_out
  stats_out=$(cmd_stats 2>/dev/null)
  if echo "$stats_out" | grep -q "memories:"; then
    echo "  T5 stats: PASS"
    passed=$((passed+1))
  else
    echo "  T5 stats: FAIL"
    failed=$((failed+1))
  fi

  # 복원
  MEMORY_DIR="$ORIG_MEMORY_DIR"
  JOURNAL="$ORIG_JOURNAL"
  MEMORIES="$ORIG_MEMORIES"
  rm -rf "$TEST_DIR"

  local total=$((passed + failed))
  echo "=== ${passed}/${total} PASSED ==="
  if [ "$failed" -gt 0 ]; then
    echo "FAILED: $failed"
    set -e
    return 1
  fi
  echo "=== ALL PASSED ==="
  set -e
}

# ─── main ────────────────────────────────────────

case "${1:-}" in
  drain)      cmd_drain ;;
  query)      cmd_query "${2:-}" ;;
  stats)      cmd_stats ;;
  --self-test) cmd_self_test ;;
  *)
    echo "Usage: agent-memory.sh {drain|query <keyword>|stats|--self-test}"
    exit 1
    ;;
esac
