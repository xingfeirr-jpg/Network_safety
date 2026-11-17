#!/usr/bin/env bash
# P01 preparation only: configure and build; no analyzer or target execution.
set -euo pipefail
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入已经验收的环境快照目录。\n' >&2
    exit 64
fi
session=$1
cd "$HOME/comp5355"
source_dir="$HOME/comp5355/sources/zlib-v1.3.2"
build_dir="$HOME/comp5355/build/zlib-v1.3.2"
prep_dir="$HOME/comp5355/results/pretest-zlib-v1.3.2/preparation/PREP-P01-001"
[[ -s "$source_dir/CMakeLists.txt" ]] || { printf '未找到zlib源码。\n' >&2; exit 66; }
[[ -x /usr/bin/time ]] || { printf '未找到/usr/bin/time。\n' >&2; exit 69; }
if [[ -e "$build_dir" || -e "$prep_dir" ]]; then
    printf '构建目录或准备日志已存在，请保留已有记录并先核对进度：\n%s\n%s\n' "$build_dir" "$prep_dir" >&2
    exit 73
fi
mkdir -p "$(dirname "$prep_dir")" "$(dirname "$build_dir")"
mkdir "$prep_dir"
{
    printf 'purpose=preparation\nproject=P01\npreparation_id=PREP-P01-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$session" "$PWD"
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$prep_dir/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$prep_dir/environment-start.txt"

run_phase() {
    local phase=$1 rc=0
    shift
    printf '开始%s，日志目录：%s\n' "$phase" "$prep_dir"
    printf '%q ' "$@" > "$prep_dir/$phase-command.txt"
    printf '\n' >> "$prep_dir/$phase-command.txt"
    LC_ALL=C /usr/bin/time -v -o "$prep_dir/$phase-time.txt" -- "$@" \
        > "$prep_dir/$phase-stdout.txt" 2> "$prep_dir/$phase-stderr.txt" || rc=$?
    printf '%s\n' "$rc" > "$prep_dir/$phase-exit-code.txt"
    cat "$prep_dir/$phase-stdout.txt"
    cat "$prep_dir/$phase-stderr.txt" >&2
    printf '%s退出码：%s\n' "$phase" "$rc"
    return "$rc"
}

run_phase configure cmake \
    -S "$source_dir" -B "$build_dir" -G Ninja \
    -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DZLIB_BUILD_SHARED=OFF \
    -DZLIB_BUILD_STATIC=ON \
    -DZLIB_BUILD_TESTING=OFF \
    -DZLIB_PREFIX=OFF \
    -DZLIB_INSTALL=ON \
    -DCMAKE_INSTALL_PREFIX="$HOME/comp5355/deps/zlib-v1.3.2" \
    -DCMAKE_INSTALL_LIBDIR=lib

run_phase build cmake --build "$build_dir" --target zlibstatic --parallel 1
printf '配置与构建命令均返回0；请继续核对产物和实际编译数据库。\n'
ls -lh "$build_dir/libz.a" "$build_dir/compile_commands.json" "$build_dir/zconf.h"
printf 'ended_utc=' >> "$prep_dir/preparation-meta.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >> "$prep_dir/preparation-meta.txt"
printf '准备阶段记录：%s\n' "$prep_dir"
