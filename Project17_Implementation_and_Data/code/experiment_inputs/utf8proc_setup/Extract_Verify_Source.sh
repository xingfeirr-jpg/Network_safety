#!/usr/bin/env bash
set -euo pipefail
set -C
export PYTHONDONTWRITEBYTECODE=1
p10ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p10Base="$HOME/comp5355"
p10Archive="$p10Base/downloads/utf8proc-2.10.0.tar.gz"
p10Download="$p10Base/downloads/utf8proc-2.10.0-DL-P10-001"
p10Source="$p10Base/sources/utf8proc-2.10.0"
p10Record="$p10Base/results/pretest-utf8proc-2.10.0/preparation/SRC-P10-001"
p10Accepted="$p10ScriptDir/../utf8proc_pretest_20261029/Archive_Identity_Check.json"

for p10Path in "$p10Source" "$p10Record" "$p10Base/build/utf8proc-2.10.0"; do
  if [[ -e "$p10Path" || -L "$p10Path" ]]; then
    printf '已有P10源码、构建或本编号记录，请先核对现有进度：%s\n' "$p10Path" >&2
    exit 1
  fi
done
for p10Parent in "$p10Base" "$p10Base/sources" "$p10Base/results"; do
  if [[ ! -d "$p10Parent" || -L "$p10Parent" ]]; then
    printf '预期父目录缺失或为链接：%s\n' "$p10Parent" >&2
    exit 1
  fi
done
for p10Parent in "$p10Base/results/pretest-utf8proc-2.10.0" "$(dirname -- "$p10Record")"; do
  if [[ -L "$p10Parent" || ( -e "$p10Parent" && ! -d "$p10Parent" ) ]]; then
    printf '记录父目录状态不符：%s\n' "$p10Parent" >&2
    exit 1
  fi
done
test -s "$p10Accepted"
mkdir -p -- "$(dirname -- "$p10Record")"
mkdir -- "$p10Record"
printf 'run_id\tSRC-P10-001\nstarted_utc\t%s\nsource_directory\t%s\narchive\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p10Source" "$p10Archive" > "$p10Record/source-meta.tsv"
trap 'p10FinalExit=$?; printf "ended_utc\t%s\nscript_exit_code\t%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p10FinalExit" >> "$p10Record/source-meta.tsv"' EXIT

p10LogRun() {
  local p10Phase="$1" p10Exit
  shift
  printf '%q ' "$@" > "$p10Record/$p10Phase-command.txt"
  printf '\n' >> "$p10Record/$p10Phase-command.txt"
  if "$@" > "$p10Record/$p10Phase-stdout.txt" 2> "$p10Record/$p10Phase-stderr.txt"; then p10Exit=0; else p10Exit=$?; fi
  printf '%s\n' "$p10Exit" > "$p10Record/$p10Phase-exit-code.txt"
  cat "$p10Record/$p10Phase-stdout.txt"
  if [[ "$p10Exit" -ne 0 ]]; then
    cat "$p10Record/$p10Phase-stderr.txt" >&2
    printf '%s失败；本次记录和可能存在的源码保留，请返回输出。\n' "$p10Phase" >&2
    return "$p10Exit"
  fi
}

printf '开始SRC-P10-001；完整记录目录：%s\n' "$p10Record"
p10LogRun preflight python3 -B "$p10ScriptDir/Verify_Extracted_Source.py" preflight \
  "$p10Archive" "$p10Download" "$p10Accepted" "$p10Source" "$p10Record/preflight-check.json"
sha256sum "$p10ScriptDir/Extract_Verify_Source.sh" "$p10ScriptDir/Verify_Extracted_Source.py" \
  "$p10ScriptDir/Inspect_Archive.py" "$p10ScriptDir/Check_Official_Identity.py" "$p10Accepted" \
  "$p10Download/archive-check.json" "$p10Download/official-reference.json" "$p10Archive" > "$p10Record/input-files.sha256"
python3 --version > "$p10Record/python-version.txt" 2>&1
tar --version > "$p10Record/tar-version.txt" 2>&1
mkdir -- "$p10Source"
p10LogRun extract tar -xzf "$p10Archive" -C "$p10Source" --strip-components=1 --no-same-owner --keep-old-files
p10LogRun verify python3 -B "$p10ScriptDir/Verify_Extracted_Source.py" verify \
  "$p10Archive" "$p10Download" "$p10Accepted" "$p10Source" "$p10Record/source-check.json"
printf '\nSRC-P10-001结束：解压和源码核对均退出0。请返回输出或截图，由助手验收后再准备构建。\n'
printf '本步仅解压与核对源码，尚未运行CMake或三个检测工具。\n'
