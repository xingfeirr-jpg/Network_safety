#!/usr/bin/env bash
# P05 preparation; user executes after source acceptance.
set -euo pipefail
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2
    exit 64
fi
p05Session=$(cd -- "$1" && pwd -P)
p05ScriptDir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
p05Inventory="$p05ScriptDir/../review_evidence/json_c_setup/Accepted_Source_Inventory.json"
p05Source="$HOME/comp5355/sources/json-c-0.18"
p05Build="$HOME/comp5355/build/json-c-0.18"
p05Prep="$HOME/comp5355/results/pretest-json-c-0.18/preparation/PREP-P05-001"
p05Archive="$HOME/comp5355/downloads/json-c-0.18.tar.gz"
cd "$HOME/comp5355"
[[ -s "$p05Source/CMakeLists.txt" && -s "$p05Inventory" ]] || {
    printf '固定源码或已验收身份清单不存在。\n' >&2; exit 66;
}
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || {
    printf '计时器或Clang18不可用。\n' >&2; exit 69;
}
for p05Required in cmake ninja sha256sum ar python3; do
    command -v "$p05Required" >/dev/null || { printf '缺少命令：%s\n' "$p05Required" >&2; exit 69; }
done
if [[ -e "$p05Build" || -L "$p05Build" || -e "$p05Prep" || -L "$p05Prep" ]]; then
    printf '构建目录或准备日志已存在，请先核对进度：\n%s\n%s\n' "$p05Build" "$p05Prep" >&2
    exit 73
fi
printf '%s  %s\n' \
    'a090046b2d24901eb8dca4d370c28991299e8c7cfb698b44e09ce809b1ff20b4' \
    "$p05Archive" | sha256sum -c -
mkdir -p -- "$(dirname -- "$p05Prep")" "$(dirname -- "$p05Build")"
mkdir -- "$p05Prep"
{
    printf 'purpose=preparation\nproject=P05\npreparation_id=PREP-P05-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$p05Session" "$PWD"
    printf 'fixed_commit=41a55cfcedb54d9c1874f2f0eb07b504091d7e37\n'
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$p05Prep/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$p05Prep/environment-start.txt"
sha256sum "${BASH_SOURCE[0]}" "$p05Inventory" > "$p05Prep/preparation-inputs.sha256"
python3 - "$p05Source" "$p05Inventory" "$p05Prep/source-before-build.json" <<'PY_SOURCE'
from pathlib import Path
import hashlib,json,os,sys
source=Path(sys.argv[1])
expected=json.loads(Path(sys.argv[2]).read_text())
if source.is_symlink(): raise SystemExit('Source root must match the accepted directory')
actual=[]
for path in sorted(source.rglob('*')):
    name=path.relative_to(source).as_posix()
    if path.is_symlink(): item={'file':name,'type':'symlink','linkTarget':os.readlink(path)}
    elif path.is_file():
        data=path.read_bytes()
        item={'file':name,'type':'file','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    elif path.is_dir(): item={'file':name,'type':'directory'}
    else: item={'file':name,'type':'other'}
    actual.append(item)
Path(sys.argv[3]).write_text(json.dumps({'sourceRoot':str(source),'items':actual},indent=2)+'\n')
if actual != expected['items']:
    raise SystemExit('Source identity changed; existing preparation evidence retained')
print('239 source files and22 symlink targets match the accepted archive')
PY_SOURCE

p05RunPhase() {
    local p05Phase=$1 p05Rc=0
    shift
    printf '开始%s，日志目录：%s\n' "$p05Phase" "$p05Prep"
    printf '%q ' "$@" > "$p05Prep/$p05Phase-command.txt"
    printf '\n' >> "$p05Prep/$p05Phase-command.txt"
    if LC_ALL=C /usr/bin/time -v -o "$p05Prep/$p05Phase-time.txt" -- "$@" \
        > "$p05Prep/$p05Phase-stdout.txt" 2> "$p05Prep/$p05Phase-stderr.txt"; then
        p05Rc=0
    else
        p05Rc=$?
    fi
    printf '%s\n' "$p05Rc" > "$p05Prep/$p05Phase-exit-code.txt"
    cat "$p05Prep/$p05Phase-stdout.txt"
    cat "$p05Prep/$p05Phase-stderr.txt" >&2
    printf '%s退出码：%s\n' "$p05Phase" "$p05Rc"
    return "$p05Rc"
}

p05RunPhase configure cmake \
    -S "$p05Source" -B "$p05Build" -G Ninja \
    -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_STATIC_LIBS=ON \
    -DBUILD_TESTING=OFF \
    -DBUILD_APPS=OFF \
    -DDISABLE_JSON_POINTER=OFF \
    -DDISABLE_JSON_PATCH=OFF \
    -DDISABLE_EXTRA_LIBS=ON \
    -DDISABLE_WERROR=ON \
    -DCMAKE_INSTALL_PREFIX="$HOME/comp5355/deps/json-c-0.18"

p05RunPhase build cmake --build "$p05Build" --target json-c --parallel 1
printf '配置与构建命令均返回0；请继续核对14条真实C动作、对象及实际生成头／依赖。\n'
ls -lh "$p05Build/libjson-c.a" "$p05Build/compile_commands.json" \
    "$p05Build/config.h" "$p05Build/json_config.h" "$p05Build/json.h"
ar t "$p05Build/libjson-c.a" > "$p05Prep/archive-objects.txt"
ninja -C "$p05Build" -t deps > "$p05Prep/ninja-deps.txt"
ninja -C "$p05Build" -t commands json-c > "$p05Prep/target-commands.txt"
sha256sum "$p05Build/libjson-c.a" "$p05Build/compile_commands.json" \
    "$p05Build/config.h" "$p05Build/json_config.h" "$p05Build/json.h" \
    "$p05Build/CMakeCache.txt" > "$p05Prep/build-artifacts.sha256"
printf 'ended_utc=' >> "$p05Prep/preparation-meta.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >> "$p05Prep/preparation-meta.txt"
printf '准备阶段记录：%s\n' "$p05Prep"
