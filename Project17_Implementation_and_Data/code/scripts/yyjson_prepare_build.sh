#!/usr/bin/env bash
# P06 preparation: the user runs this after source acceptance.
set -euo pipefail
set -C
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2
    exit 64
fi
p06Session="$(cd -- "$1" && pwd -P)"
p06Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p06Docs="$(dirname -- "$p06Scripts")"
p06Setup="$p06Docs/review_evidence/yyjson_setup"
p06Base="$HOME/comp5355"
p06Source="$p06Base/sources/yyjson-0.12.0"
p06Build="$p06Base/build/yyjson-0.12.0"
p06Prep="$p06Base/results/pretest-yyjson-0.12.0/preparation/PREP-P06-001"
p06Archive="$p06Base/downloads/yyjson-0.12.0.tar.gz"
p06Accepted="$p06Base/downloads/yyjson-0.12.0-DL-P06-001/archive-check.json"
p06Official="$p06Setup/Official_Identity_Check_20261028/Official_Git_Tree.json"
p06Expected='94e9c90f8f12d8329f2c0756782d21e5c278729023cd2c5fe47e323a35947ed6'
cd "$p06Base"
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || {
    printf '缺少GNU time或Clang18。\n' >&2; exit 69;
}
for p06Command in cmake ninja sha256sum ar python3; do
    command -v "$p06Command" >/dev/null || { printf '缺少命令：%s\n' "$p06Command" >&2; exit 69; }
done
for p06Path in "$p06Build" "$p06Prep"; do
    if [[ -e "$p06Path" || -L "$p06Path" ]]; then
        printf '构建或准备目录已存在，请先核对进度：%s\n' "$p06Path" >&2; exit 73
    fi
done
[[ -s "$p06Source/CMakeLists.txt" && -s "$p06Source/src/yyjson.c" && -s "$p06Source/src/yyjson.h" && -s "$p06Source/LICENSE" ]]
[[ -s "$p06Accepted" && -s "$p06Official" && -s "$p06Setup/Verify_Extracted_Source.py" && -s "$p06Setup/Verify_Source_For_Build.py" ]]
[[ -s "$p06Base/results/pretest-yyjson-0.12.0/preparation/SRC-P06-001/source-check.json" ]]
p06Actual="$(sha256sum "$p06Archive")"
if [[ "${p06Actual%% *}" != "$p06Expected" ]]; then
    printf '原包SHA与验收记录不符，停止。\n' >&2; exit 1
fi
mkdir -p -- "$(dirname -- "$p06Prep")" "$(dirname -- "$p06Build")"
mkdir -- "$p06Prep"
{
    printf 'purpose=preparation\nproject=P06\npreparation_id=PREP-P06-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$p06Session" "$PWD"
    printf 'fixed_commit=8b4a38dc994a110abaec8a400615567bd996105f\n'
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$p06Prep/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$p06Prep/environment-start.txt"
sha256sum "${BASH_SOURCE[0]}" "$p06Setup/Verify_Extracted_Source.py" "$p06Setup/Verify_Source_For_Build.py" "$p06Official" "$p06Accepted" \
    > "$p06Prep/preparation-inputs.sha256"

p06_source_guard() {
    local p06Phase=$1 p06GuardExit=0
    python3 "$p06Setup/Verify_Source_For_Build.py" "$p06Source" "$p06Accepted" "$p06Official" \
        "$p06Prep/source-$p06Phase.json" "$p06Phase" > "$p06Prep/source-$p06Phase-stdout.txt" \
        2> "$p06Prep/source-$p06Phase-stderr.txt" || p06GuardExit=$?
    printf '%s\n' "$p06GuardExit" > "$p06Prep/source-$p06Phase-exit-code.txt"
    if [[ "$p06GuardExit" -ne 0 ]]; then
        cat "$p06Prep/source-$p06Phase-stderr.txt" >&2
        printf '完整源码身份检查失败，保留记录后停止。\n' >&2
    fi
    return "$p06GuardExit"
}
p06_source_guard before-build

p06_run_phase() {
    local p06Phase=$1 p06Exit=0
    shift
    printf '开始%s，日志目录：%s\n' "$p06Phase" "$p06Prep"
    printf '%q ' "$@" > "$p06Prep/$p06Phase-command.txt"
    printf '\n' >> "$p06Prep/$p06Phase-command.txt"
    LC_ALL=C /usr/bin/time -v -o "$p06Prep/$p06Phase-time.txt" -- "$@" \
        > "$p06Prep/$p06Phase-stdout.txt" 2> "$p06Prep/$p06Phase-stderr.txt" || p06Exit=$?
    printf '%s\n' "$p06Exit" > "$p06Prep/$p06Phase-exit-code.txt"
    cat "$p06Prep/$p06Phase-stdout.txt"
    cat "$p06Prep/$p06Phase-stderr.txt" >&2
    printf '%s退出码：%s\n' "$p06Phase" "$p06Exit"
    return "$p06Exit"
}

p06_run_phase configure cmake \
    -S "$p06Source" -B "$p06Build" -G Ninja \
    -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DYYJSON_BUILD_TESTS=OFF \
    -DYYJSON_BUILD_FUZZER=OFF \
    -DYYJSON_BUILD_MISC=OFF \
    -DYYJSON_BUILD_DOC=OFF \
    -DYYJSON_DISABLE_READER=OFF \
    -DYYJSON_DISABLE_WRITER=OFF \
    -DYYJSON_DISABLE_INCR_READER=OFF \
    -DYYJSON_DISABLE_UTILS=OFF \
    -DYYJSON_DISABLE_FAST_FP_CONV=OFF \
    -DYYJSON_DISABLE_NON_STANDARD=OFF \
    -DYYJSON_DISABLE_UTF8_VALIDATION=OFF \
    -DYYJSON_DISABLE_UNALIGNED_MEMORY_ACCESS=OFF \
    -DCMAKE_INSTALL_PREFIX="$p06Base/deps/yyjson-0.12.0"

p06_run_phase build cmake --build "$p06Build" --target yyjson --parallel 1
p06_source_guard after-build
ar t "$p06Build/libyyjson.a" > "$p06Prep/archive-objects.txt"
ninja -C "$p06Build" -t deps > "$p06Prep/ninja-deps.txt"
ninja -C "$p06Build" -t commands yyjson > "$p06Prep/target-commands.txt"
sha256sum "$p06Build/libyyjson.a" "$p06Build/compile_commands.json" "$p06Build/CMakeCache.txt" \
    "$p06Build/build.ninja" "$p06Build/yyjson.pc" > "$p06Prep/build-artifacts.sha256"
printf 'ended_utc=' >> "$p06Prep/preparation-meta.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >> "$p06Prep/preparation-meta.txt"
printf '配置与构建命令均返回0，源码身份保持；请继续核对产物和真实编译数据库。\n'
ls -lh "$p06Build/libyyjson.a" "$p06Build/compile_commands.json"
printf '准备阶段记录：%s\n本步没有运行漏洞检测工具。\n' "$p06Prep"
