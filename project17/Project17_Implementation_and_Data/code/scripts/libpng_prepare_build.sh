#!/usr/bin/env bash
# P08 preparation only; user executes after SRC-P08-001 and DEP-P08-001 acceptance.
set -euo pipefail
set -C
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2; exit 64
fi
p08Session="$(cd -- "$1" && pwd -P)"
p08Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p08Docs="$(dirname -- "$p08Scripts")"
p08Setup="$p08Docs/review_evidence/libpng_setup"
p08Base="$HOME/comp5355"
p08Source="$p08Base/sources/libpng-1.6.50"
p08Build="$p08Base/build/libpng-1.6.50"
p08Prep="$p08Base/results/pretest-libpng-1.6.50/preparation/PREP-P08-001"
p08Download="$p08Base/downloads/libpng-1.6.50-DL-P08-001"
p08Archive="$p08Base/downloads/libpng-1.6.50.tar.gz"
p08Accepted="$p08Download/archive-check.json"
p08Official="$p08Download/official-reference.json"
p08SourceRecord="$p08Base/results/pretest-libpng-1.6.50/preparation/SRC-P08-001/source-check.json"
p08Expected='fba1c8e793f01b493f3f47a926862edbfab487ae4240e02ec67131f1e2bf067f'
cd "$p08Base"
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || { printf '缺少GNU time或Clang18。\n' >&2; exit 69; }
for p08Command in cmake ninja sha256sum ar python3; do command -v "$p08Command" >/dev/null; done
for p08Path in "$p08Build" "$p08Prep"; do
    if [[ -e "$p08Path" || -L "$p08Path" ]]; then
        printf '构建或准备目录已存在，请先核对进度：%s\n' "$p08Path" >&2; exit 73
    fi
done
for p08Path in "$p08Base" "$p08Base/build" "$p08Base/results" \
    "$p08Base/results/pretest-libpng-1.6.50" "$p08Base/results/pretest-libpng-1.6.50/preparation"; do
    if [[ -L "$p08Path" || ( -e "$p08Path" && ! -d "$p08Path" ) ]]; then
        printf '父目录状态不符，请返回输出：%s\n' "$p08Path" >&2; exit 73
    fi
done
p08Dependency="$p08Base/deps/zlib-v1.3.2"
p08DependencyRecord="$p08Base/results/pretest-libpng-1.6.50/preparation/DEP-P08-001"
[[ -s "$p08Source/CMakeLists.txt" && -s "$p08Source/scripts/pnglibconf.h.prebuilt" \
    && -s "$p08Source/png.c" && -s "$p08Source/png.h" && -s "$p08Source/LICENSE" \
    && -s "$p08DependencyRecord/preflight-check.json" && -s "$p08DependencyRecord/dependency-check.json" \
    && -s "$p08Setup/Verify_Zlib_Dependency.py" ]]
[[ -s "$p08Accepted" && -s "$p08Official" && -s "$p08SourceRecord" \
    && -s "$p08Setup/Verify_Extracted_Source.py" && -s "$p08Setup/Verify_Source_For_Build.py" ]]
p08Actual="$(sha256sum "$p08Archive")"
if [[ "${p08Actual%% *}" != "$p08Expected" ]]; then printf '原包SHA不符，停止。\n' >&2; exit 1; fi
mkdir -p -- "$(dirname -- "$p08Prep")" "$(dirname -- "$p08Build")"
mkdir -- "$p08Prep"
{
    printf 'purpose=preparation\nproject=P08\npreparation_id=PREP-P08-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$p08Session" "$PWD"
    printf 'fixed_commit=2b978915d82377df13fcbb1fb56660195ded868a\n'
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$p08Prep/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$p08Prep/environment-start.txt"
sha256sum "${BASH_SOURCE[0]}" "$p08Setup/Verify_Extracted_Source.py" "$p08Setup/Verify_Source_For_Build.py" \
    "$p08Setup/Inspect_Archive.py" "$p08Setup/Check_Official_Identity.py" "$p08Accepted" "$p08Official" \
    "$p08SourceRecord" "$p08Download/tag-ref-try1/body" "$p08Download/tag-object-try1/body" \
    "$p08Download/git-commit-try1/body" "$p08Download/recursive-tree-try1/body" \
    "$p08Session/system.txt" "$p08Session/tool-versions.txt" > "$p08Prep/preparation-inputs.sha256"

p08_source_guard() {
    local p08Phase=$1 p08Exit=0
    local p08Guard=(python3 "$p08Setup/Verify_Source_For_Build.py" "$p08Source" "$p08Archive" \
        "$p08Accepted" "$p08Official" "$p08SourceRecord" "$p08Prep/source-$p08Phase.json" "$p08Phase")
    printf '%q ' "${p08Guard[@]}" > "$p08Prep/source-$p08Phase-command.txt"
    printf '\n' >> "$p08Prep/source-$p08Phase-command.txt"
    "${p08Guard[@]}" > "$p08Prep/source-$p08Phase-stdout.txt" 2> "$p08Prep/source-$p08Phase-stderr.txt" || p08Exit=$?
    printf '%s\n' "$p08Exit" > "$p08Prep/source-$p08Phase-exit-code.txt"
    cat "$p08Prep/source-$p08Phase-stdout.txt"
    if [[ "$p08Exit" -ne 0 ]]; then cat "$p08Prep/source-$p08Phase-stderr.txt" >&2; fi
    return "$p08Exit"
}
p08_source_guard before-build

p08_run_phase() {
    local p08Phase=$1 p08Exit=0
    shift
    printf '开始%s，日志目录：%s\n' "$p08Phase" "$p08Prep"
    printf '%q ' "$@" > "$p08Prep/$p08Phase-command.txt"
    printf '\n' >> "$p08Prep/$p08Phase-command.txt"
    LC_ALL=C /usr/bin/time -v -o "$p08Prep/$p08Phase-time.txt" -- "$@" \
        > "$p08Prep/$p08Phase-stdout.txt" 2> "$p08Prep/$p08Phase-stderr.txt" || p08Exit=$?
    printf '%s\n' "$p08Exit" > "$p08Prep/$p08Phase-exit-code.txt"
    cat "$p08Prep/$p08Phase-stdout.txt"
    cat "$p08Prep/$p08Phase-stderr.txt" >&2
    printf '%s退出码：%s\n' "$p08Phase" "$p08Exit"
    return "$p08Exit"
}

p08_dependency_guard() {
    local p08Phase=$1 p08Exit=0
    local p08Guard=(python3 "$p08Setup/Verify_Zlib_Dependency.py" verify \
        "$p08Prep/dependency-$p08Phase.json" "$p08DependencyRecord/preflight-check.json")
    printf '%q ' "${p08Guard[@]}" > "$p08Prep/dependency-$p08Phase-command.txt"
    printf '\n' >> "$p08Prep/dependency-$p08Phase-command.txt"
    "${p08Guard[@]}" > "$p08Prep/dependency-$p08Phase-stdout.txt" 2> "$p08Prep/dependency-$p08Phase-stderr.txt" || p08Exit=$?
    printf '%s\n' "$p08Exit" > "$p08Prep/dependency-$p08Phase-exit-code.txt"
    cat "$p08Prep/dependency-$p08Phase-stdout.txt"
    if [[ "$p08Exit" -ne 0 ]]; then cat "$p08Prep/dependency-$p08Phase-stderr.txt" >&2; fi
    return "$p08Exit"
}
p08_dependency_guard before-build
sha256sum "$p08Setup/Verify_Zlib_Dependency.py" "$p08DependencyRecord/preflight-check.json" \
    "$p08DependencyRecord/dependency-check.json" "$p08Dependency/include/zlib.h" \
    "$p08Dependency/include/zconf.h" "$p08Dependency/lib/libz.a" \
    "$p08Dependency/lib/pkgconfig/zlib.pc" > "$p08Prep/dependency-inputs.sha256"

p08ConfigureExit=0
p08_run_phase configure cmake \
    -S "$p08Source" -B "$p08Build" -G Ninja \
    -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DPNG_SHARED=OFF \
    -DPNG_STATIC=ON \
    -DPNG_FRAMEWORK=OFF \
    -DPNG_TESTS=OFF \
    -DPNG_TOOLS=OFF \
    -DPNG_HARDWARE_OPTIMIZATIONS=OFF \
    -DPNG_LIBCONF_HEADER:FILEPATH="$p08Source/scripts/pnglibconf.h.prebuilt" \
    -DZLIB_ROOT:PATH="$p08Dependency" \
    -DZLIB_USE_STATIC_LIBS=ON \
    -DZLIB_INCLUDE_DIR:PATH="$p08Dependency/include" \
    -DZLIB_LIBRARY:FILEPATH="$p08Dependency/lib/libz.a" \
    -DCMAKE_INSTALL_PREFIX="$p08Base/deps/libpng-1.6.50" || p08ConfigureExit=$?
if [[ "$p08ConfigureExit" -ne 0 ]]; then
    p08_source_guard after-configure-failure || true
    p08_dependency_guard after-configure-failure || true
    exit "$p08ConfigureExit"
fi

p08BuildExit=0
p08_run_phase build cmake --build "$p08Build" --target png_static --parallel 1 || p08BuildExit=$?
if [[ "$p08BuildExit" -ne 0 ]]; then
    p08_source_guard after-build-failure || true
    p08_dependency_guard after-build-failure || true
    exit "$p08BuildExit"
fi
p08_source_guard after-build
p08_dependency_guard after-build

p08_capture() {
    local p08Name=$1 p08Exit=0
    shift
    printf '%q ' "$@" > "$p08Prep/$p08Name-command.txt"
    printf '\n' >> "$p08Prep/$p08Name-command.txt"
    LC_ALL=C "$@" > "$p08Prep/$p08Name.txt" 2> "$p08Prep/$p08Name-stderr.txt" || p08Exit=$?
    printf '%s\n' "$p08Exit" > "$p08Prep/$p08Name-exit-code.txt"
    if [[ "$p08Exit" -ne 0 ]]; then cat "$p08Prep/$p08Name-stderr.txt" >&2; fi
    return "$p08Exit"
}
p08_capture archive-objects ar t "$p08Build/libpng16d.a"
p08_capture ninja-deps ninja -C "$p08Build" -t deps
p08_capture target-commands ninja -C "$p08Build" -t commands png_static
sha256sum "$p08Build/libpng16d.a" "$p08Build/compile_commands.json" "$p08Build/CMakeCache.txt" \
    "$p08Build/build.ninja" "$p08Build/pnglibconf.h" "$p08Source/scripts/pnglibconf.h.prebuilt" \
    > "$p08Prep/build-artifacts.sha256"
printf 'ended_utc=' >> "$p08Prep/preparation-meta.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >> "$p08Prep/preparation-meta.txt"
printf '配置与构建命令均返回0，完整源码身份保持；请继续核对产物、15条目标C动作及原始数据库筛选依据、生成头／依赖。\n'
ls -lh "$p08Build/libpng16d.a" "$p08Build/compile_commands.json" "$p08Build/pnglibconf.h"
printf '准备阶段记录：%s\n本步没有运行漏洞检测工具。\n' "$p08Prep"
