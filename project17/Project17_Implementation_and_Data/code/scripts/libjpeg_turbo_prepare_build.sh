#!/usr/bin/env bash
# P09 preparation only. The user executes this after SRC-P09-001 acceptance.
set -euo pipefail
set -C
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2
    exit 64
fi
p09Session="$(cd -- "$1" && pwd -P)"
p09Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p09Docs="$(dirname -- "$p09Scripts")"
p09Setup="$p09Docs/review_evidence/libjpeg_turbo_setup"
p09Base="$HOME/comp5355"
p09Source="$p09Base/sources/libjpeg-turbo-3.1.1"
p09Build="$p09Base/build/libjpeg-turbo-3.1.1"
p09Prep="$p09Base/results/pretest-libjpeg-turbo-3.1.1/preparation/PREP-P09-001"
p09Download="$p09Base/downloads/libjpeg-turbo-3.1.1-DL-P09-001"
p09Archive="$p09Base/downloads/libjpeg-turbo-3.1.1.tar.gz"
p09SourceRecord="$p09Base/results/pretest-libjpeg-turbo-3.1.1/preparation/SRC-P09-001/source-check.json"
p09AcceptedArchive="$p09Docs/review_evidence/libjpeg_turbo_pretest_20261029/Archive_Identity_Check.json"
p09AcceptedSource="$p09Docs/review_evidence/libjpeg_turbo_pretest_20261029/Source_Identity_Check.json"
cd -- "$p09Base"
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || {
    printf '缺少GNU time或Clang18。\n' >&2; exit 69;
}
for p09Command in cmake ninja sha256sum ar python3; do
    command -v "$p09Command" >/dev/null || { printf '缺少命令：%s\n' "$p09Command" >&2; exit 69; }
done
for p09Path in "$p09Build" "$p09Prep"; do
    if [[ -e "$p09Path" || -L "$p09Path" ]]; then
        printf '构建或本编号记录已存在，请先核对进度：%s\n' "$p09Path" >&2
        exit 73
    fi
done
for p09Path in "$p09Base" "$p09Base/build" "$p09Base/results" \
    "$p09Base/results/pretest-libjpeg-turbo-3.1.1" \
    "$p09Base/results/pretest-libjpeg-turbo-3.1.1/preparation"; do
    if [[ -L "$p09Path" || ( -e "$p09Path" && ! -d "$p09Path" ) ]]; then
        printf '父目录状态不符，请返回输出：%s\n' "$p09Path" >&2
        exit 73
    fi
done
for p09Path in "$p09Source/CMakeLists.txt" "$p09Source/BUILDING.md" \
    "$p09Source/LICENSE.md" "$p09Source/README.ijg" "$p09Source/src/jcapimin.c" \
    "$p09SourceRecord" "$p09AcceptedArchive" "$p09AcceptedSource" \
    "$p09Download/archive-check.json" "$p09Archive" \
    "$p09Setup/Download_Profile.json" "$p09Setup/Build_Profile.json" \
    "$p09Setup/Verify_Extracted_Source.py" "$p09Setup/Inspect_Release_Archive.py" \
    "$p09Setup/Verify_Build_Source.py"; do
    [[ -s "$p09Path" && ! -L "$p09Path" ]] || {
        printf '必要输入缺失、为空或为链接：%s\n' "$p09Path" >&2; exit 66;
    }
done
mkdir -p -- "$(dirname -- "$p09Prep")" "$(dirname -- "$p09Build")"
mkdir -- "$p09Prep"
{
    printf 'purpose=preparation\nproject=P09\npreparation_id=PREP-P09-001\n'
    printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$p09Session" "$PWD"
    printf 'fixed_commit=7723f50f3f66b9da74376e6d8badb6162464212c\n'
    printf 'target=jpeg-static\nparallel_jobs=1\n'
    printf 'started_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
} > "$p09Prep/preparation-meta.txt"
trap 'p09FinalExit=$?; printf "ended_utc=%s\nscript_exit_code=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p09FinalExit" >> "$p09Prep/preparation-meta.txt"' EXIT
{
    printf 'visible_processors='; nproc
    printf '\nmeminfo:\n'; cat /proc/meminfo
    printf '\nloadavg:\n'; cat /proc/loadavg
    printf '\ninherited_limits:\n'; ulimit -a
} > "$p09Prep/environment-start.txt"
{
    for p09Variable in CC CXX CFLAGS CPPFLAGS CXXFLAGS LDFLAGS AR RANLIB \
        CMAKE_TOOLCHAIN_FILE CMAKE_GENERATOR CMAKE_BUILD_PARALLEL_LEVEL; do
        if [[ -v "$p09Variable" ]]; then
            printf '%s=%q\n' "$p09Variable" "${!p09Variable}"
        else
            printf '%s=<unset>\n' "$p09Variable"
        fi
    done
} > "$p09Prep/inherited-build-environment.txt"
sha256sum "${BASH_SOURCE[0]}" "$p09Setup/Verify_Build_Source.py" \
    "$p09Setup/Verify_Extracted_Source.py" "$p09Setup/Inspect_Release_Archive.py" \
    "$p09Setup/Download_Profile.json" "$p09Setup/Build_Profile.json" \
    "$p09AcceptedArchive" "$p09AcceptedSource" "$p09SourceRecord" \
    "$p09Download/archive-check.json" "$p09Archive" \
    "$p09Session/system.txt" "$p09Session/tool-versions.txt" > "$p09Prep/preparation-inputs.sha256"
cp -- "$p09Setup/Build_Profile.json" "$p09Prep/Build_Profile.json"

p09_source_guard() {
    local p09Phase=$1 p09Exit=0
    local p09Guard=(python3 -B "$p09Setup/Verify_Build_Source.py"
        --source "$p09Source" --archive "$p09Archive"
        --archive-check "$p09Download/archive-check.json"
        --accepted-archive "$p09AcceptedArchive" --accepted-source "$p09AcceptedSource"
        --source-record "$p09SourceRecord" --phase "$p09Phase"
        --output "$p09Prep/source-$p09Phase.json")
    printf '%q ' "${p09Guard[@]}" > "$p09Prep/source-$p09Phase-command.txt"
    printf '\n' >> "$p09Prep/source-$p09Phase-command.txt"
    LC_ALL=C "${p09Guard[@]}" > "$p09Prep/source-$p09Phase-stdout.txt" \
        2> "$p09Prep/source-$p09Phase-stderr.txt" || p09Exit=$?
    printf '%s\n' "$p09Exit" > "$p09Prep/source-$p09Phase-exit-code.txt"
    cat "$p09Prep/source-$p09Phase-stdout.txt"
    if [[ "$p09Exit" -ne 0 ]]; then cat "$p09Prep/source-$p09Phase-stderr.txt" >&2; fi
    return "$p09Exit"
}
p09_source_guard before-build

p09_run_phase() {
    local p09Phase=$1 p09Exit=0
    shift
    printf '开始%s；完整日志：%s\n' "$p09Phase" "$p09Prep"
    printf '%q ' "$@" > "$p09Prep/$p09Phase-command.txt"
    printf '\n' >> "$p09Prep/$p09Phase-command.txt"
    LC_ALL=C /usr/bin/time -v -o "$p09Prep/$p09Phase-time.txt" -- "$@" \
        > "$p09Prep/$p09Phase-stdout.txt" 2> "$p09Prep/$p09Phase-stderr.txt" || p09Exit=$?
    printf '%s\n' "$p09Exit" > "$p09Prep/$p09Phase-exit-code.txt"
    cat "$p09Prep/$p09Phase-stdout.txt"
    cat "$p09Prep/$p09Phase-stderr.txt" >&2
    printf '%s退出码：%s\n' "$p09Phase" "$p09Exit"
    return "$p09Exit"
}
p09ConfigureExit=0
p09_run_phase configure cmake \
    -S "$p09Source" -B "$p09Build" -G Ninja \
    -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DENABLE_SHARED=OFF \
    -DENABLE_STATIC=ON \
    -DWITH_SIMD=OFF \
    -DREQUIRE_SIMD=OFF \
    -DWITH_TURBOJPEG=OFF \
    -DWITH_JAVA=OFF \
    -DWITH_FUZZ=OFF \
    -DWITH_ARITH_ENC=ON \
    -DWITH_ARITH_DEC=ON \
    -DWITH_JPEG7=OFF \
    -DWITH_JPEG8=OFF \
    -DCMAKE_INSTALL_PREFIX="$p09Base/deps/libjpeg-turbo-3.1.1" || p09ConfigureExit=$?
if [[ "$p09ConfigureExit" -ne 0 ]]; then
    p09_source_guard after-configure-failure || true
    exit "$p09ConfigureExit"
fi
p09BuildExit=0
p09_run_phase build cmake --build "$p09Build" --target jpeg-static --parallel 1 || p09BuildExit=$?
if [[ "$p09BuildExit" -ne 0 ]]; then
    p09_source_guard after-build-failure || true
    exit "$p09BuildExit"
fi
p09_source_guard after-build

p09_capture() {
    local p09Name=$1 p09Exit=0
    shift
    printf '%q ' "$@" > "$p09Prep/$p09Name-command.txt"
    printf '\n' >> "$p09Prep/$p09Name-command.txt"
    LC_ALL=C "$@" > "$p09Prep/$p09Name.txt" 2> "$p09Prep/$p09Name-stderr.txt" || p09Exit=$?
    printf '%s\n' "$p09Exit" > "$p09Prep/$p09Name-exit-code.txt"
    if [[ "$p09Exit" -ne 0 ]]; then cat "$p09Prep/$p09Name-stderr.txt" >&2; fi
    return "$p09Exit"
}
p09_capture archive-objects ar t "$p09Build/libjpeg.a"
p09_capture ninja-deps ninja -C "$p09Build" -t deps
p09_capture target-commands ninja -C "$p09Build" -t commands jpeg-static
p09_capture target-query ninja -C "$p09Build" -t query jpeg-static
p09_capture archive-query ninja -C "$p09Build" -t query libjpeg.a
p09_capture jpeg12-query ninja -C "$p09Build" -t query jpeg12-static
p09_capture jpeg16-query ninja -C "$p09Build" -t query jpeg16-static

# Preserve the real unfiltered database and generated configuration independently
# of later analysis; peripheral configured targets can also appear in this DB.
mkdir -- "$p09Prep/build-context"
for p09Relative in compile_commands.json CMakeCache.txt build.ninja \
    CMakeFiles/rules.ninja jconfig.h jconfigint.h jversion.h libjpeg.a \
    .ninja_log .ninja_deps CMakeFiles/CMakeConfigureLog.yaml; do
    [[ -s "$p09Build/$p09Relative" && ! -L "$p09Build/$p09Relative" ]] || {
        printf '待保存构建上下文缺失或不符：%s\n' "$p09Relative" >&2; exit 1;
    }
    mkdir -p -- "$(dirname -- "$p09Prep/build-context/$p09Relative")"
    cp -- "$p09Build/$p09Relative" "$p09Prep/build-context/$p09Relative"
done
shopt -s nullglob
p09CompilerFiles=("$p09Build"/CMakeFiles/*/CMakeCCompiler.cmake)
[[ ${#p09CompilerFiles[@]} -eq 1 ]] || { printf '编译器上下文数量异常，请返回输出。\n' >&2; exit 1; }
p09CompilerRelative="${p09CompilerFiles[0]#"$p09Build/"}"
mkdir -p -- "$(dirname -- "$p09Prep/build-context/$p09CompilerRelative")"
cp -- "${p09CompilerFiles[0]}" "$p09Prep/build-context/$p09CompilerRelative"
(
    cd -- "$p09Prep/build-context"
    sha256sum compile_commands.json CMakeCache.txt build.ninja CMakeFiles/rules.ninja \
        jconfig.h jconfigint.h jversion.h libjpeg.a .ninja_log .ninja_deps \
        CMakeFiles/CMakeConfigureLog.yaml "$p09CompilerRelative"
) > "$p09Prep/build-context.sha256"
sha256sum "$p09Build/libjpeg.a" "$p09Build/compile_commands.json" "$p09Build/CMakeCache.txt" \
    "$p09Build/build.ninja" "$p09Build/jconfig.h" "$p09Build/jconfigint.h" "$p09Build/jversion.h" \
    > "$p09Prep/build-artifacts.sha256"
printf '\n配置与jpeg-static构建均退出0，构建前后完整源码身份保持。\n'
printf '请返回完整输出或截图；实际动作、位深宏、生成头和覆盖仍由助手验收。\n'
printf '准备记录：%s\n本步没有运行三个漏洞检测工具。\n' "$p09Prep"
