#!/usr/bin/env bash
# P02 preparation: user-run configure/build, with separate records for both phases.
set -euo pipefail
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2
    exit 64
fi
session=$(cd "$1" && pwd)
cd "$HOME/comp5355"
source_dir="$HOME/comp5355/sources/lz4-v1.10.0"
build_dir="$HOME/comp5355/build/lz4-v1.10.0"
prep_dir="$HOME/comp5355/results/pretest-lz4-v1.10.0/preparation/PREP-P02-001"
[[ -s "$source_dir/build/cmake/CMakeLists.txt" ]] || { printf '未找到LZ4构建入口。\n' >&2; exit 66; }
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || { printf '未找到计时器或Clang18。\n' >&2; exit 69; }
if [[ -e "$build_dir" || -L "$build_dir" || -e "$prep_dir" || -L "$prep_dir" ]]; then
    printf '构建目录或准备日志已存在，请先核对已有进度：\n%s\n%s\n' "$build_dir" "$prep_dir" >&2
    exit 73
fi
for file in lz4.c lz4hc.c lz4frame.c lz4file.c xxhash.c; do
    [[ -s "$source_dir/lib/$file" ]] || { printf '缺少预定C文件：%s\n' "$file" >&2; exit 66; }
done
mkdir -p "$(dirname "$prep_dir")" "$(dirname "$build_dir")"
mkdir "$prep_dir"
{
    printf 'purpose=preparation\nproject=P02\npreparation_id=PREP-P02-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$session" "$PWD"
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$prep_dir/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$prep_dir/environment-start.txt"
sha256sum "${BASH_SOURCE[0]}" > "$prep_dir/preparation-script.sha256"
sha256sum "$source_dir"/lib/*.c "$source_dir"/lib/*.h \
    "$source_dir/lib/LICENSE" "$source_dir/build/cmake/CMakeLists.txt" \
    "$source_dir/README.md" "$source_dir/LICENSE" \
    "$source_dir/build/cmake/lz4Config.cmake.in" "$source_dir/lib/liblz4.pc.in" \
    > "$prep_dir/source-before-build.sha256"

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
    -S "$source_dir/build/cmake" -B "$build_dir" -G Ninja \
    -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_STATIC_LIBS=ON \
    -DLZ4_BUILD_CLI=OFF \
    -DCMAKE_INSTALL_PREFIX="$HOME/comp5355/deps/lz4-v1.10.0" \
    -DCMAKE_INSTALL_LIBDIR=lib

run_phase build cmake --build "$build_dir" --target lz4_static --parallel 1
printf '配置与构建命令均返回0；请继续核对产物和实际编译数据库。\n'
ls -lh "$build_dir/liblz4.a" "$build_dir/compile_commands.json"
printf 'ended_utc=' >> "$prep_dir/preparation-meta.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >> "$prep_dir/preparation-meta.txt"
printf '准备阶段记录：%s\n' "$prep_dir"
