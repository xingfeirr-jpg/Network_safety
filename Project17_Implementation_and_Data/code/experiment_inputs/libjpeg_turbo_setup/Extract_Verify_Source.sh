#!/usr/bin/env bash
set -euo pipefail
set -C
p09ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p09Base="$HOME/comp5355"
p09Archive="$p09Base/downloads/libjpeg-turbo-3.1.1.tar.gz"
p09Download="$p09Base/downloads/libjpeg-turbo-3.1.1-DL-P09-001"
p09Source="$p09Base/sources/libjpeg-turbo-3.1.1"
p09Record="$p09Base/results/pretest-libjpeg-turbo-3.1.1/preparation/SRC-P09-001"
p09Profile="$p09ScriptDir/Download_Profile.json"
p09Accepted="$p09ScriptDir/../libjpeg_turbo_pretest_20261029/Archive_Identity_Check.json"

for p09Path in "$p09Source" "$p09Record" "$p09Base/build/libjpeg-turbo-3.1.1"; do
  if [[ -e "$p09Path" || -L "$p09Path" ]]; then
    printf '已有P09源码、构建或本编号记录，请先核对现有进度：%s\n' "$p09Path" >&2
    exit 1
  fi
done
for p09Parent in "$p09Base" "$p09Base/sources" "$p09Base/results"; do
  if [[ ! -d "$p09Parent" || -L "$p09Parent" ]]; then
    printf '预期父目录缺失或为链接，请返回输出：%s\n' "$p09Parent" >&2
    exit 1
  fi
done
for p09Parent in "$p09Base/results/pretest-libjpeg-turbo-3.1.1" "$(dirname -- "$p09Record")"; do
  if [[ -L "$p09Parent" || ( -e "$p09Parent" && ! -d "$p09Parent" ) ]]; then
    printf '记录父目录不是普通目录，请返回输出：%s\n' "$p09Parent" >&2
    exit 1
  fi
done
mkdir -p -- "$(dirname -- "$p09Record")"
mkdir -- "$p09Record"
printf 'run_id\tSRC-P09-001\npurpose\taccepted release extraction and identity verification only\nstarted_utc\t%s\nsource_directory\t%s\narchive\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p09Source" "$p09Archive" > "$p09Record/source-meta.tsv"
trap 'p09FinalExit=$?; printf "ended_utc\t%s\nscript_exit_code\t%s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p09FinalExit" >> "$p09Record/source-meta.tsv"' EXIT

p09LogRun() {
  local p09Phase="$1"
  shift
  printf '%q ' "$@" > "$p09Record/$p09Phase-command.txt"
  printf '\n' >> "$p09Record/$p09Phase-command.txt"
  local p09Exit
  if "$@" > "$p09Record/$p09Phase-stdout.txt" 2> "$p09Record/$p09Phase-stderr.txt"; then
    p09Exit=0
  else
    p09Exit=$?
  fi
  printf '%s\n' "$p09Exit" > "$p09Record/$p09Phase-exit-code.txt"
  cat "$p09Record/$p09Phase-stdout.txt"
  if [[ "$p09Exit" -ne 0 ]]; then
    cat "$p09Record/$p09Phase-stderr.txt" >&2
    printf '%s失败，记录和可能存在的源码保持；请返回输出，不要重复运行同编号。\n' "$p09Phase" >&2
    return "$p09Exit"
  fi
}

printf '开始SRC-P09-001；完整记录目录：%s\n' "$p09Record"
p09LogRun preflight python3 -B "$p09ScriptDir/Verify_Extracted_Source.py" preflight \
  --profile "$p09Profile" --archive "$p09Archive" \
  --archive-check "$p09Download/archive-check.json" --accepted "$p09Accepted" \
  --output "$p09Record/preflight-check.json"
sha256sum "$p09ScriptDir/Extract_Verify_Source.sh" "$p09ScriptDir/Verify_Extracted_Source.py" \
  "$p09ScriptDir/Inspect_Release_Archive.py" "$p09Profile" "$p09Accepted" \
  "$p09Download/archive-check.json" "$p09Archive" > "$p09Record/input-files.sha256"
python3 --version > "$p09Record/python-version.txt" 2>&1
tar --version > "$p09Record/tar-version.txt" 2>&1
# The accepted release root is 0775; strip-components omits that root entry.
mkdir -m 0775 -- "$p09Source"
p09LogRun extract tar -xzf "$p09Archive" -C "$p09Source" --strip-components=1 \
  --no-same-owner --same-permissions --keep-old-files --delay-directory-restore
p09LogRun verify python3 -B "$p09ScriptDir/Verify_Extracted_Source.py" source \
  --profile "$p09Profile" --archive "$p09Archive" \
  --archive-check "$p09Download/archive-check.json" --accepted "$p09Accepted" \
  --source "$p09Source" --output "$p09Record/source-check.json"
printf '\nSRC-P09-001结束：解压和源码核对均退出0。请返回完整输出或截图，由助手验收后再准备构建。\n'
printf '本步只解压和核对源码；尚未配置、构建或运行三个检测工具。\n'
