#!/bin/bash
# role-register.sh — cmux 역할 등록/조회 시스템
#
# Usage:
#   bash role-register.sh register <role>   # boss|watcher|peer 등록
#   bash role-register.sh whoami            # 내 역할 확인
#   bash role-register.sh whois <role>      # 특정 역할의 surface 조회
#   bash role-register.sh status            # 전체 역할 상태
#   bash role-register.sh workers           # worker surface 목록 (boss/watcher/peer 제외)
#   bash role-register.sh heartbeat <role>  # 하트비트 갱신
#   bash role-register.sh check-boss        # Boss 생존 확인 (watcher용)
#   bash role-register.sh discover-peers    # 활성 동료(boss/watcher/peer) 목록 조회
#   bash role-register.sh peer-status       # 동료 상태 + 하트비트 확인
#
# 역할 레지스트리: /tmp/cmux-roles.json
# 동료 역할: boss, watcher, peer (작업 배정 대상에서 제외)

set -u

ROLES_FILE="/tmp/cmux-roles.json"
HEARTBEAT_TIMEOUT=120  # 2분 이상 하트비트 없으면 dead 판정

# 현재 surface 정보 가져오기
function_get_my_surface() {
  local variable_identify=""
  variable_identify=$(cmux identify 2>/dev/null) || return 1
  echo "$variable_identify" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
caller = data.get('caller') or data.get('focused', {})
print(caller.get('surface_ref', ''))
" 2>/dev/null
}

function_get_my_workspace() {
  local variable_identify=""
  variable_identify=$(cmux identify 2>/dev/null) || return 1
  echo "$variable_identify" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
caller = data.get('caller') or data.get('focused', {})
print(caller.get('workspace_ref', ''))
" 2>/dev/null
}

# 역할 등록
function_register() {
  local variable_role="$1"  # boss | watcher
  local variable_surface=""
  local variable_workspace=""
  local variable_timestamp=""

  variable_surface=$(function_get_my_surface)
  variable_workspace=$(function_get_my_workspace)
  variable_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  if [ -z "$variable_surface" ]; then
    echo "ERROR: cmux identify 실패 — cmux 환경이 아닙니다" >&2
    return 1
  fi

  python3 - "$ROLES_FILE" "$variable_role" "$variable_surface" "$variable_workspace" "$variable_timestamp" "$$" <<'PY'
import json
import sys
from pathlib import Path

roles_file = Path(sys.argv[1])
role = sys.argv[2]
surface = sys.argv[3]
workspace = sys.argv[4]
timestamp = sys.argv[5]
pid = sys.argv[6]

# 기존 파일 읽기
data = {}
if roles_file.exists():
    try:
        data = json.loads(roles_file.read_text())
    except (json.JSONDecodeError, OSError):
        data = {}

# 역할 등록
data[role] = {
    "surface": surface,
    "workspace": workspace,
    "pid": int(pid),
    "started_at": timestamp,
    "last_heartbeat": timestamp,
}

roles_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(f"REGISTERED: {role} = {surface} (workspace: {workspace}, pid: {pid})")
PY
}

# 내 역할 확인
function_whoami() {
  local variable_surface=""
  variable_surface=$(function_get_my_surface)

  if [ -z "$variable_surface" ]; then
    echo "UNKNOWN (cmux 환경 아님)"
    return 1
  fi

  if [ ! -f "$ROLES_FILE" ]; then
    echo "UNREGISTERED ($variable_surface)"
    return 0
  fi

  python3 - "$ROLES_FILE" "$variable_surface" <<'PY'
import json
import sys

roles_file = sys.argv[1]
my_surface = sys.argv[2]

with open(roles_file) as f:
    data = json.load(f)

for role, info in data.items():
    if info.get("surface") == my_surface:
        print(f"{role.upper()} ({my_surface})")
        sys.exit(0)

print(f"WORKER ({my_surface})")
PY
}

# 특정 역할의 surface 조회
function_whois() {
  local variable_role="$1"

  if [ ! -f "$ROLES_FILE" ]; then
    echo "UNKNOWN (역할 파일 없음)"
    return 1
  fi

  python3 - "$ROLES_FILE" "$variable_role" <<'PY'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

role = sys.argv[2]
info = data.get(role)
if info:
    print(f"{info['surface']} (workspace: {info['workspace']}, pid: {info['pid']})")
else:
    print(f"NOT_REGISTERED")
PY
}

# 전체 역할 상태
function_status() {
  if [ ! -f "$ROLES_FILE" ]; then
    echo "역할 파일 없음. register 먼저 실행하세요."
    return 1
  fi

  python3 - "$ROLES_FILE" "$HEARTBEAT_TIMEOUT" <<'PY'
import json
import sys
from datetime import datetime, timezone

with open(sys.argv[1]) as f:
    data = json.load(f)

timeout = int(sys.argv[2])
now = datetime.now(timezone.utc)

print("=== cmux Role Registry ===")
for role in ["boss", "watcher"]:
    info = data.get(role)
    if not info:
        print(f"  {role:8s}: NOT_REGISTERED")
        continue

    surface = info.get("surface", "?")
    workspace = info.get("workspace", "?")
    pid = info.get("pid", "?")
    hb = info.get("last_heartbeat", "")

    alive = "ALIVE"
    if hb:
        try:
            hb_dt = datetime.strptime(hb, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age = (now - hb_dt).total_seconds()
            if age > timeout:
                alive = f"DEAD ({int(age)}s since heartbeat)"
        except ValueError:
            alive = "UNKNOWN"

    print(f"  {role:8s}: {surface} | {workspace} | pid:{pid} | {alive}")

workers = data.get("workers", [])
if workers:
    print(f"  workers : {', '.join(workers)}")
PY
}

# Worker 목록 (boss/watcher 제외)
function_workers() {
  if [ ! -f "$ROLES_FILE" ]; then
    echo "[]"
    return 0
  fi

  local variable_eagle="/tmp/cmux-eagle-status.json"

  python3 - "$ROLES_FILE" "$variable_eagle" <<'PY'
import json
import sys
from pathlib import Path

roles_file = Path(sys.argv[1])
eagle_file = Path(sys.argv[2])

data = json.loads(roles_file.read_text()) if roles_file.exists() else {}
excluded = set()
for role_name, info in data.items():
    if role_name in ("boss", "watcher") or role_name.startswith("peer"):
        surface = info.get("surface", "") if isinstance(info, dict) else ""
        if surface:
            num = surface.replace("surface:", "")
            excluded.add(num)

# Eagle에서 전체 surface 가져오기
eagle = json.loads(eagle_file.read_text()) if eagle_file.exists() else {}
all_surfaces = set(eagle.get("surfaces", {}).keys())

workers = sorted(all_surfaces - excluded, key=lambda x: int(x) if x.isdigit() else 999)
print(" ".join(f"surface:{s}" for s in workers))
PY
}

# 하트비트 갱신
function_heartbeat() {
  local variable_role="$1"
  local variable_timestamp=""
  variable_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  if [ ! -f "$ROLES_FILE" ]; then
    return 1
  fi

  python3 - "$ROLES_FILE" "$variable_role" "$variable_timestamp" <<'PY'
import json
import sys
from pathlib import Path

roles_file = Path(sys.argv[1])
role = sys.argv[2]
timestamp = sys.argv[3]

data = json.loads(roles_file.read_text())
if role in data:
    data[role]["last_heartbeat"] = timestamp
    roles_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"HEARTBEAT: {role} @ {timestamp}")
else:
    print(f"NOT_REGISTERED: {role}")
PY
}

# Boss 생존 확인 (watcher용)
function_check_boss() {
  if [ ! -f "$ROLES_FILE" ]; then
    echo "NO_ROLES_FILE"
    return 1
  fi

  python3 - "$ROLES_FILE" "$HEARTBEAT_TIMEOUT" <<'PY'
import json
import sys
from datetime import datetime, timezone

with open(sys.argv[1]) as f:
    data = json.load(f)

timeout = int(sys.argv[2])
now = datetime.now(timezone.utc)

boss = data.get("boss")
if not boss:
    print("BOSS_NOT_REGISTERED")
    sys.exit(1)

surface = boss.get("surface", "?")
hb = boss.get("last_heartbeat", "")

if not hb:
    print(f"BOSS_NO_HEARTBEAT|{surface}")
    sys.exit(1)

try:
    hb_dt = datetime.strptime(hb, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    age = int((now - hb_dt).total_seconds())
    if age > timeout:
        print(f"BOSS_DEAD|{surface}|{age}s")
        sys.exit(2)
    else:
        print(f"BOSS_ALIVE|{surface}|{age}s")
        sys.exit(0)
except ValueError:
    print(f"BOSS_UNKNOWN|{surface}")
    sys.exit(1)
PY
}

# 활성 동료 목록 조회
function_discover_peers() {
  if [ ! -f "$ROLES_FILE" ]; then
    echo "NO_PEERS (역할 파일 없음)"
    return 0
  fi

  python3 - "$ROLES_FILE" "$HEARTBEAT_TIMEOUT" <<'PY'
import json
import sys
from datetime import datetime, timezone

with open(sys.argv[1]) as f:
    data = json.load(f)

timeout = int(sys.argv[2])
now = datetime.now(timezone.utc)

peers = []
for role, info in data.items():
    if not isinstance(info, dict):
        continue
    surface = info.get("surface", "?")
    workspace = info.get("workspace", "?")
    hb = info.get("last_heartbeat", "")

    alive = "UNKNOWN"
    if hb:
        try:
            hb_dt = datetime.strptime(hb, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age = (now - hb_dt).total_seconds()
            alive = "ALIVE" if age <= timeout else f"DEAD({int(age)}s)"
        except ValueError:
            alive = "UNKNOWN"

    if role in ("boss", "watcher") or role.startswith("peer"):
        peers.append(f"{role}={surface}|{workspace}|{alive}")

if peers:
    print("PEERS: " + ", ".join(peers))
else:
    print("NO_PEERS")
PY
}

# 동료 상태 + 하트비트 확인 (상세)
function_peer_status() {
  if [ ! -f "$ROLES_FILE" ]; then
    echo "역할 파일 없음. register 먼저 실행하세요."
    return 1
  fi

  python3 - "$ROLES_FILE" "$HEARTBEAT_TIMEOUT" <<'PY'
import json
import sys
from datetime import datetime, timezone

with open(sys.argv[1]) as f:
    data = json.load(f)

timeout = int(sys.argv[2])
now = datetime.now(timezone.utc)

print("=== cmux Peer Status (동료 상태) ===")
peer_roles = []
worker_count = 0

for role, info in sorted(data.items()):
    if not isinstance(info, dict):
        continue

    is_peer = role in ("boss", "watcher") or role.startswith("peer")
    surface = info.get("surface", "?")
    workspace = info.get("workspace", "?")
    hb = info.get("last_heartbeat", "")

    alive = "ALIVE"
    age_str = ""
    if hb:
        try:
            hb_dt = datetime.strptime(hb, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age = int((now - hb_dt).total_seconds())
            age_str = f" ({age}s ago)"
            if age > timeout:
                alive = "DEAD"
        except ValueError:
            alive = "UNKNOWN"

    if is_peer:
        relation = "colleague" if alive == "ALIVE" else "unreachable"
        print(f"  [{role:8s}] {surface} | {workspace} | {alive}{age_str} | {relation}")
        peer_roles.append(role)

print(f"\n  Active peers: {len(peer_roles)}")
print(f"  Relationship: peer-to-peer (동료 관계, 상하 아님)")
PY
}

# 메인 라우터
case "${1:-status}" in
  register)
    function_register "${2:?역할을 지정하세요 (boss|watcher)}"
    ;;
  whoami)
    function_whoami
    ;;
  whois)
    function_whois "${2:?역할을 지정하세요 (boss|watcher)}"
    ;;
  status)
    function_status
    ;;
  workers)
    function_workers
    ;;
  heartbeat)
    function_heartbeat "${2:?역할을 지정하세요 (boss|watcher)}"
    ;;
  check-boss)
    function_check_boss
    ;;
  discover-peers)
    function_discover_peers
    ;;
  peer-status)
    function_peer_status
    ;;
  *)
    echo "Usage: role-register.sh {register|whoami|whois|status|workers|heartbeat|check-boss|discover-peers|peer-status} [role]"
    ;;
esac
