#!/usr/bin/env bash
# P07 preparation only; user executes after SRC-P07-001 acceptance.
set -euo pipefail
set -C
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2; exit 64
fi
p07Session="$(cd -- "$1" && pwd -P)"
p07Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p07Docs="$(dirname -- "$p07Scripts")"
p07Setup="$p07Docs/review_evidence/expat_setup"
p07Base="$HOME/comp5355"
p07Source="$p07Base/sources/expat-2.7.1"
p07Build="$p07Base/build/expat-2.7.1"
p07Prep="$p07Base/results/pretest-expat-2.7.1/preparation/PREP-P07-001"
p07Download="$p07Base/downloads/expat-2.7.1-DL-P07-001"
p07Archive="$p07Base/downloads/expat-2.7.1.tar.gz"
p07Accepted="$p07Download/archive-check.json"
p07Official="$p07Download/official-reference.json"
p07SourceRecord="$p07Base/results/pretest-expat-2.7.1/preparation/SRC-P07-001/source-check.json"
p07Expected='86f0e8afaf4cd72d806e32afb68e1e84bb2c6e5b0b40de2a34c0970bf8d08c40'
cd "$p07Base"
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || { printf '缺少GNU time或Clang18。\n' >&2; exit 69; }
for p07Command in cmake ninja sha256sum ar python3; do command -v "$p07Command" >/dev/null; done
for p07Path in "$p07Build" "$p07Prep"; do
    if [[ -e "$p07Path" || -L "$p07Path" ]]; then
        printf '构建或准备目录已存在，请先核对进度：%s\n' "$p07Path" >&2; exit 73
    fi
done
for p07Path in "$p07Base" "$p07Base/build" "$p07Base/results" \
    "$p07Base/results/pretest-expat-2.7.1" "$p07Base/results/pretest-expat-2.7.1/preparation"; do
    if [[ -L "$p07Path" || ( -e "$p07Path" && ! -d "$p07Path" ) ]]; then
        printf '父目录状态不符，请返回输出：%s\n' "$p07Path" >&2; exit 73
    fi
done
[[ -s "$p07Source/expat/CMakeLists.txt" && -s "$p07Source/expat/ConfigureChecks.cmake" \
    && -s "$p07Source/expat/lib/xmlparse.c" && -s "$p07Source/expat/lib/xmlrole.c" \
    && -s "$p07Source/expat/lib/xmltok.c" && -s "$p07Source/expat/COPYING" ]]
[[ -s "$p07Accepted" && -s "$p07Official" && -s "$p07SourceRecord" \
    && -s "$p07Setup/Verify_Extracted_Source.py" && -s "$p07Setup/Verify_Source_For_Build.py" ]]
p07Actual="$(sha256sum "$p07Archive")"
if [[ "${p07Actual%% *}" != "$p07Expected" ]]; then printf '原包SHA不符，停止。\n' >&2; exit 1; fi
mkdir -p -- "$(dirname -- "$p07Prep")" "$(dirname -- "$p07Build")"
mkdir -- "$p07Prep"
{
    printf 'purpose=preparation\nproject=P07\npreparation_id=PREP-P07-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$p07Session" "$PWD"
    printf 'fixed_commit=f9a3eeb3e09fbea04b1c451ffc422ab2f1e45744\n'
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$p07Prep/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$p07Prep/environment-start.txt"
sha256sum "${BASH_SOURCE[0]}" "$p07Setup/Verify_Extracted_Source.py" "$p07Setup/Verify_Source_For_Build.py" \
    "$p07Setup/Inspect_Archive.py" "$p07Setup/Check_Official_Identity.py" "$p07Accepted" "$p07Official" \
    "$p07SourceRecord" "$p07Download/tag-ref-try1/body" "$p07Download/tag-object-try1/body" \
    "$p07Download/git-commit-try1/body" "$p07Download/recursive-tree-try1/body" \
    "$p07Session/system.txt" "$p07Session/tool-versions.txt" > "$p07Prep/preparation-inputs.sha256"

p07_source_guard() {
    local p07Phase=$1 p07Exit=0
    local p07Guard=(python3 "$p07Setup/Verify_Source_For_Build.py" "$p07Source" "$p07Archive" \
        "$p07Accepted" "$p07Official" "$p07SourceRecord" "$p07Prep/source-$p07Phase.json" "$p07Phase")
    printf '%q ' "${p07Guard[@]}" > "$p07Prep/source-$p07Phase-command.txt"
    printf '\n' >> "$p07Prep/source-$p07Phase-command.txt"
    "${p07Guard[@]}" > "$p07Prep/source-$p07Phase-stdout.txt" 2> "$p07Prep/source-$p07Phase-stderr.txt" || p07Exit=$?
    printf '%s\n' "$p07Exit" > "$p07Prep/source-$p07Phase-exit-code.txt"
    cat "$p07Prep/source-$p07Phase-stdout.txt"
    if [[ "$p07Exit" -ne 0 ]]; then cat "$p07Prep/source-$p07Phase-stderr.txt" >&2; fi
    return "$p07Exit"
}
p07_source_guard before-build

p07_run_phase() {
    local p07Phase=$1 p07Exit=0
    shift
    printf '开始%s，日志目录：%s\n' "$p07Phase" "$p07Prep"
    printf '%q ' "$@" > "$p07Prep/$p07Phase-command.txt"
    printf '\n' >> "$p07Prep/$p07Phase-command.txt"
    LC_ALL=C /usr/bin/time -v -o "$p07Prep/$p07Phase-time.txt" -- "$@" \
        > "$p07Prep/$p07Phase-stdout.txt" 2> "$p07Prep/$p07Phase-stderr.txt" || p07Exit=$?
    printf '%s\n' "$p07Exit" > "$p07Prep/$p07Phase-exit-code.txt"
    cat "$p07Prep/$p07Phase-stdout.txt"
    cat "$p07Prep/$p07Phase-stderr.txt" >&2
    printf '%s退出码：%s\n' "$p07Phase" "$p07Exit"
    return "$p07Exit"
}

p07ConfigureExit=0
p07_run_phase configure cmake \
    -S "$p07Source/expat" -B "$p07Build" -G Ninja \
    -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DEXPAT_SHARED_LIBS=OFF \
    -DEXPAT_BUILD_TOOLS=OFF \
    -DEXPAT_BUILD_EXAMPLES=OFF \
    -DEXPAT_BUILD_TESTS=OFF \
    -DEXPAT_BUILD_DOCS=OFF \
    -DEXPAT_BUILD_FUZZERS=OFF \
    -DEXPAT_OSSFUZZ_BUILD=OFF \
    -DEXPAT_CHAR_TYPE=char \
    -DEXPAT_DTD=ON \
    -DEXPAT_GE=ON \
    -DEXPAT_NS=ON \
    -DEXPAT_WITH_LIBBSD=OFF \
    -DEXPAT_MIN_SIZE=OFF \
    -DEXPAT_LARGE_SIZE=OFF \
    -DEXPAT_ATTR_INFO=OFF \
    -DEXPAT_CONTEXT_BYTES=1024 \
    -DEXPAT_WARNINGS_AS_ERRORS=OFF \
    -DCMAKE_INSTALL_PREFIX="$p07Base/deps/expat-2.7.1" || p07ConfigureExit=$?
if [[ "$p07ConfigureExit" -ne 0 ]]; then p07_source_guard after-configure-failure || true; exit "$p07ConfigureExit"; fi

p07BuildExit=0
p07_run_phase build cmake --build "$p07Build" --target expat --parallel 1 || p07BuildExit=$?
if [[ "$p07BuildExit" -ne 0 ]]; then p07_source_guard after-build-failure || true; exit "$p07BuildExit"; fi
p07_source_guard after-build

p07_capture() {
    local p07Name=$1 p07Exit=0
    shift
    printf '%q ' "$@" > "$p07Prep/$p07Name-command.txt"
    printf '\n' >> "$p07Prep/$p07Name-command.txt"
    LC_ALL=C "$@" > "$p07Prep/$p07Name.txt" 2> "$p07Prep/$p07Name-stderr.txt" || p07Exit=$?
    printf '%s\n' "$p07Exit" > "$p07Prep/$p07Name-exit-code.txt"
    if [[ "$p07Exit" -ne 0 ]]; then cat "$p07Prep/$p07Name-stderr.txt" >&2; fi
    return "$p07Exit"
}
p07_capture archive-objects ar t "$p07Build/libexpat.a"
p07_capture ninja-deps ninja -C "$p07Build" -t deps
p07_capture target-commands ninja -C "$p07Build" -t commands expat
sha256sum "$p07Build/libexpat.a" "$p07Build/compile_commands.json" "$p07Build/CMakeCache.txt" \
    "$p07Build/build.ninja" "$p07Build/expat_config.h" "$p07Build/Debug/expat.pc" \
    > "$p07Prep/build-artifacts.sha256"
printf 'ended_utc=' >> "$p07Prep/preparation-meta.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >> "$p07Prep/preparation-meta.txt"
printf '配置与构建命令均返回0，完整源码身份保持；请继续核对产物、3条真实C动作和生成头／依赖。\n'
ls -lh "$p07Build/libexpat.a" "$p07Build/compile_commands.json" "$p07Build/expat_config.h"
printf '准备阶段记录：%s\n本步没有运行漏洞检测工具。\n' "$p07Prep"
