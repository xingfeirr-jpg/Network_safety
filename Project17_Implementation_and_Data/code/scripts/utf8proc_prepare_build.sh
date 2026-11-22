#!/usr/bin/env bash
# P10 preparation only; run by the user after SRC-P10-001 acceptance.
set -euo pipefail
set -C
export PYTHONDONTWRITEBYTECODE=1
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
  printf '请传入本次环境快照目录。\n' >&2
  exit 64
fi
p10Session="$(cd -- "$1" && pwd -P)"
p10Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p10Docs="$(dirname -- "$p10Scripts")"
p10Setup="$p10Docs/review_evidence/utf8proc_setup"
p10Base="$HOME/comp5355"
p10Source="$p10Base/sources/utf8proc-2.10.0"
p10Build="$p10Base/build/utf8proc-2.10.0"
p10Prep="$p10Base/results/pretest-utf8proc-2.10.0/preparation/PREP-P10-001"
p10Archive="$p10Base/downloads/utf8proc-2.10.0.tar.gz"
p10Download="$p10Base/downloads/utf8proc-2.10.0-DL-P10-001"
p10ArchiveAccepted="$p10Setup/../utf8proc_pretest_20261029/Archive_Identity_Check.json"
p10SourceAccepted="$p10Setup/../utf8proc_pretest_20261029/Source_Identity_Check.json"
p10SourceRecord="$p10Base/results/pretest-utf8proc-2.10.0/preparation/SRC-P10-001/source-check.json"
cd -- "$p10Base"
[[ -x /usr/bin/time && -x /usr/bin/clang-18 ]] || {
  printf '缺少GNU time或Clang18。\n' >&2; exit 69;
}
for p10Command in cmake ninja sha256sum ar python3; do
  command -v "$p10Command" >/dev/null || { printf '缺少命令：%s\n' "$p10Command" >&2; exit 69; }
done
for p10Path in "$p10Build" "$p10Prep"; do
  if [[ -e "$p10Path" || -L "$p10Path" ]]; then
    printf '构建或准备目录已存在，请先核对现有进度：%s\n' "$p10Path" >&2; exit 73
  fi
  p10Parent="$(dirname -- "$p10Path")"
  while [[ "$p10Parent" != / ]]; do
    if [[ -L "$p10Parent" || ( -e "$p10Parent" && ! -d "$p10Parent" ) ]]; then
      printf '父目录状态不符：%s\n' "$p10Parent" >&2; exit 73
    fi
    p10Parent="$(dirname -- "$p10Parent")"
  done
done
for p10Input in "$p10ArchiveAccepted" "$p10SourceAccepted" "$p10SourceRecord" \
    "$p10Source/CMakeLists.txt" "$p10Source/utf8proc.c" "$p10Source/utf8proc.h" \
    "$p10Source/utf8proc_data.c" "$p10Source/LICENSE.md"; do
  test -s "$p10Input"
done
mkdir -p -- "$(dirname -- "$p10Prep")" "$(dirname -- "$p10Build")"
mkdir -- "$p10Prep"
{
  printf 'purpose=preparation\nproject=P10\npreparation_id=PREP-P10-001\n'
  printf 'environment_session=%s\nworking_directory=%s\nlocale=C\n' "$p10Session" "$PWD"
  printf 'fixed_commit=a1b99daa2a3393884220264c927a48ba1251a9c6\n'
  printf 'started_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$p10Prep/preparation-meta.txt"
trap 'p10FinalExit=$?; printf "ended_utc=%s\nscript_exit_code=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p10FinalExit" >> "$p10Prep/preparation-meta.txt"' EXIT
{ cat /proc/meminfo; cat /proc/loadavg; } > "$p10Prep/environment-start.txt"
sha256sum "$p10Scripts/utf8proc_prepare_build.sh" "$p10Setup/Verify_Source_For_Build.py" \
  "$p10Setup/Verify_Extracted_Source.py" "$p10Setup/Inspect_Archive.py" \
  "$p10Setup/Check_Official_Identity.py" "$p10ArchiveAccepted" "$p10SourceAccepted" \
  "$p10SourceRecord" "$p10Download/archive-check.json" "$p10Download/official-reference.json" \
  "$p10Archive" > "$p10Prep/preparation-inputs.sha256"

p10_source_guard() {
  local p10Phase="$1" p10GuardExit=0
  python3 -B "$p10Setup/Verify_Source_For_Build.py" "$p10Source" "$p10Archive" "$p10Download" \
    "$p10ArchiveAccepted" "$p10SourceAccepted" "$p10SourceRecord" "$p10Phase" \
    "$p10Prep/source-$p10Phase.json" > "$p10Prep/source-$p10Phase-stdout.txt" \
    2> "$p10Prep/source-$p10Phase-stderr.txt" || p10GuardExit=$?
  printf '%s\n' "$p10GuardExit" > "$p10Prep/source-$p10Phase-exit-code.txt"
  cat "$p10Prep/source-$p10Phase-stdout.txt"
  if [[ "$p10GuardExit" -ne 0 ]]; then cat "$p10Prep/source-$p10Phase-stderr.txt" >&2; fi
  return "$p10GuardExit"
}

p10_run_phase() {
  local p10Phase="$1" p10Exit=0
  shift
  printf '开始%s；完整日志：%s\n' "$p10Phase" "$p10Prep"
  printf '%q ' "$@" > "$p10Prep/$p10Phase-command.txt"
  printf '\n' >> "$p10Prep/$p10Phase-command.txt"
  LC_ALL=C /usr/bin/time -v -o "$p10Prep/$p10Phase-time.txt" -- "$@" \
    > "$p10Prep/$p10Phase-stdout.txt" 2> "$p10Prep/$p10Phase-stderr.txt" || p10Exit=$?
  printf '%s\n' "$p10Exit" > "$p10Prep/$p10Phase-exit-code.txt"
  cat "$p10Prep/$p10Phase-stdout.txt"
  cat "$p10Prep/$p10Phase-stderr.txt" >&2
  printf '%s退出码：%s\n' "$p10Phase" "$p10Exit"
  return "$p10Exit"
}

p10_source_guard before-build
p10_run_phase configure cmake \
  -S "$p10Source" -B "$p10Build" -G Ninja \
  -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DBUILD_SHARED_LIBS=OFF \
  -DUTF8PROC_ENABLE_TESTING=OFF \
  -DUTF8PROC_INSTALL=ON \
  -DCMAKE_INSTALL_PREFIX="$p10Base/deps/utf8proc-2.10.0"
p10_run_phase build cmake --build "$p10Build" --target utf8proc --parallel 1 --verbose
p10_source_guard after-build
ar t "$p10Build/libutf8proc.a" > "$p10Prep/archive-objects.txt"
ninja -C "$p10Build" -t deps > "$p10Prep/ninja-deps.txt"
ninja -C "$p10Build" -t commands utf8proc > "$p10Prep/target-commands.txt"
sha256sum "$p10Build/libutf8proc.a" "$p10Build/compile_commands.json" \
  "$p10Build/CMakeCache.txt" "$p10Build/build.ninja" "$p10Build/libutf8proc.pc" \
  > "$p10Prep/build-artifacts.sha256"
printf '\n配置和构建命令均退出0；完整源码身份保持。\n'
printf '请返回输出，由助手验收真实数据库、C99／优化选项、归档对象及数据表依赖。\n'
ls -lh "$p10Build/libutf8proc.a" "$p10Build/compile_commands.json"
printf '准备记录：%s\n本步没有运行三个漏洞检测工具，也没有执行安装。\n' "$p10Prep"
