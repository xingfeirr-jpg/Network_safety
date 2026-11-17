#!/usr/bin/env bash
set -euo pipefail
set -C
p06ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p06Base="$HOME/comp5355"
p06Archive="$p06Base/downloads/yyjson-0.12.0.tar.gz"
p06Download="$p06Base/downloads/yyjson-0.12.0-DL-P06-001"
p06Source="$p06Base/sources/yyjson-0.12.0"
p06Record="$p06Base/results/pretest-yyjson-0.12.0/preparation/SRC-P06-001"
p06Expected='94e9c90f8f12d8329f2c0756782d21e5c278729023cd2c5fe47e323a35947ed6'

for p06Path in "$p06Source" "$p06Record"; do
  if [[ -e "$p06Path" || -L "$p06Path" ]]; then
    printf '已有源码或核对记录，请先核对进度：%s\n' "$p06Path" >&2
    exit 1
  fi
done
if [[ ! -d "$p06Base/sources" || -L "$p06Base/sources" || ! -f "$p06Archive" || -L "$p06Archive" ]]; then
  printf '源码父目录或原包状态不符，请返回输出。\n' >&2
  exit 1
fi
test -s "$p06Download/archive-check.json"
test -s "$p06ScriptDir/Verify_Extracted_Source.py"
test -s "$p06ScriptDir/Official_Identity_Check_20261028/Official_Git_Tree.json"
p06Actual="$(sha256sum "$p06Archive")"
if [[ "${p06Actual%% *}" != "$p06Expected" ]]; then
  printf '原包SHA与已验收记录不符，停止解压。\n' >&2
  exit 1
fi
mkdir -p -- "$(dirname -- "$p06Record")"
mkdir -- "$p06Record"
printf 'record_id\tSRC-P06-001\nstart_utc\t%s\nsource_directory\t%s\narchive_sha256\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p06Source" "$p06Expected" > "$p06Record/source-meta.tsv"
sha256sum "$p06ScriptDir/Extract_Verify_Source.sh" "$p06ScriptDir/Verify_Extracted_Source.py" \
  "$p06Download/archive-check.json" "$p06ScriptDir/Official_Identity_Check_20261028/Official_Git_Tree.json" \
  > "$p06Record/input-files.sha256"
mkdir -- "$p06Source"
p06Extract=(tar -xzf "$p06Archive" -C "$p06Source" --strip-components=1 --no-same-owner --keep-old-files)
printf '%q ' "${p06Extract[@]}" > "$p06Record/extract-command.txt"
printf '\n' >> "$p06Record/extract-command.txt"
printf '开始解压已验收原包；核对记录：%s\n' "$p06Record"
if "${p06Extract[@]}" > "$p06Record/extract-stdout.txt" 2> "$p06Record/extract-stderr.txt"; then
  p06ExtractExit=0
else
  p06ExtractExit=$?
fi
printf '%s\n' "$p06ExtractExit" > "$p06Record/extract-exit-code.txt"
if [[ "$p06ExtractExit" -ne 0 ]]; then
  cat "$p06Record/extract-stderr.txt" >&2
  printf '解压失败，本次源码及日志保持，请返回输出，不要重复运行。\n' >&2
  exit "$p06ExtractExit"
fi
p06Verify=(python3 "$p06ScriptDir/Verify_Extracted_Source.py" "$p06Source" \
  "$p06Download/archive-check.json" "$p06ScriptDir/Official_Identity_Check_20261028/Official_Git_Tree.json" \
  "$p06Record/source-check.json")
printf '%q ' "${p06Verify[@]}" > "$p06Record/verify-command.txt"
printf '\n' >> "$p06Record/verify-command.txt"
if "${p06Verify[@]}" > "$p06Record/verify-stdout.txt" 2> "$p06Record/verify-stderr.txt"; then
  p06VerifyExit=0
else
  p06VerifyExit=$?
fi
printf '%s\n' "$p06VerifyExit" > "$p06Record/verify-exit-code.txt"
cat "$p06Record/verify-stdout.txt"
if [[ "$p06VerifyExit" -ne 0 ]]; then
  cat "$p06Record/verify-stderr.txt" >&2
  printf '源码核对失败，本次文件和日志保留，请返回输出。\n' >&2
  exit "$p06VerifyExit"
fi
printf 'end_utc\t%s\nextract_exit_code\t%s\nverify_exit_code\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p06ExtractExit" "$p06VerifyExit" >> "$p06Record/source-meta.tsv"
printf '\n解压退出码：%s；源码核对退出码：%s。\n' "$p06ExtractExit" "$p06VerifyExit"
printf 'SRC-P06-001结束；请返回输出，由助手核对后准备构建。本步没有运行CMake或检测工具。\n'
