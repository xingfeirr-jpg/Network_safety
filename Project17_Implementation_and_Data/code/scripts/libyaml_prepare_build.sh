#!/usr/bin/env bash
# P04 preparation only: the user runs configure/build after source acceptance.
set -euo pipefail
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2
    exit 64
fi
session=$(cd "$1" && pwd)
cd "$HOME/comp5355"
source_dir="$HOME/comp5355/sources/libyaml-0.2.5"
build_dir="$HOME/comp5355/build/libyaml-0.2.5"
prep_dir="$HOME/comp5355/results/pretest-libyaml-0.2.5/preparation/PREP-P04-001"
archive_dir="$HOME/comp5355/downloads"
[[ -s "$source_dir/CMakeLists.txt" && -s "$source_dir/cmake/config.h.in" ]] || {
    printf '未找到libyaml固定源码或配置头模板。\n' >&2
    exit 66
}
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || {
    printf '未找到计时器或Clang18。\n' >&2
    exit 69
}
for required in cmake ninja sha256sum ar; do
    command -v "$required" >/dev/null || { printf '缺少命令：%s\n' "$required" >&2; exit 69; }
done
if [[ -e "$build_dir" || -L "$build_dir" || -e "$prep_dir" || -L "$prep_dir" ]]; then
    printf '构建目录或准备日志已存在，请先核对已有进度：\n%s\n%s\n' "$build_dir" "$prep_dir" >&2
    exit 73
fi
for file in api.c dumper.c emitter.c loader.c parser.c reader.c scanner.c writer.c; do
    [[ -s "$source_dir/src/$file" ]] || { printf '缺少预定C文件：%s\n' "$file" >&2; exit 66; }
done
for file in include/yaml.h src/yaml_private.h License yamlConfig.cmake.in; do
    [[ -s "$source_dir/$file" ]] || { printf '缺少项目上下文：%s\n' "$file" >&2; exit 66; }
done
(
    cd "$archive_dir"
    sha256sum -c libyaml-0.2.5.tar.gz.sha256
)
mkdir -p "$(dirname "$prep_dir")" "$(dirname "$build_dir")"
mkdir "$prep_dir"
{
    printf 'purpose=preparation\nproject=P04\npreparation_id=PREP-P04-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$session" "$PWD"
    printf 'fixed_commit=2c891fc7a770e8ba2fec34fc6b545c672beb37e6\n'
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$prep_dir/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$prep_dir/environment-start.txt"
sha256sum "${BASH_SOURCE[0]}" > "$prep_dir/preparation-script.sha256"
sha256sum "$source_dir"/src/*.c "$source_dir"/src/*.h \
    "$source_dir"/include/*.h "$source_dir/cmake/config.h.in" \
    "$source_dir/CMakeLists.txt" "$source_dir/yamlConfig.cmake.in" \
    "$source_dir/License" > "$prep_dir/source-before-build.sha256"

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
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_TESTING=OFF \
    -DYAML_STATIC_LIB_NAME=yaml \
    -DCMAKE_INSTALL_PREFIX="$HOME/comp5355/deps/libyaml-0.2.5"

run_phase build cmake --build "$build_dir" --target yaml --parallel 1
printf '配置与构建命令均返回0；请继续核对产物、8条真实C动作和生成配置头。\n'
ls -lh "$build_dir/libyaml.a" "$build_dir/compile_commands.json" "$build_dir/include/config.h"
ar t "$build_dir/libyaml.a" > "$prep_dir/archive-objects.txt"
ninja -C "$build_dir" -t deps > "$prep_dir/ninja-deps.txt"
ninja -C "$build_dir" -t commands yaml > "$prep_dir/target-commands.txt"
sha256sum "$build_dir/libyaml.a" "$build_dir/compile_commands.json" \
    "$build_dir/include/config.h" "$build_dir/CMakeCache.txt" \
    > "$prep_dir/build-artifacts.sha256"
printf 'ended_utc=' >> "$prep_dir/preparation-meta.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >> "$prep_dir/preparation-meta.txt"
printf '准备阶段记录：%s\n' "$prep_dir"
