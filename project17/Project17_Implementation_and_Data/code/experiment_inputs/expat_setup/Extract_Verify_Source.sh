#!/usr/bin/env bash
set -euo pipefail
set -C
p07ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p07Base="$HOME/comp5355"
p07Archive="$p07Base/downloads/expat-2.7.1.tar.gz"
p07Download="$p07Base/downloads/expat-2.7.1-DL-P07-001"
p07Source="$p07Base/sources/expat-2.7.1"
p07Record="$p07Base/results/pretest-expat-2.7.1/preparation/SRC-P07-001"
p07Expected='86f0e8afaf4cd72d806e32afb68e1e84bb2c6e5b0b40de2a34c0970bf8d08c40'

for p07Path in "$p07Source" "$p07Record"; do
  if [[ -e "$p07Path" || -L "$p07Path" ]]; then
    printf '已有源码或核对记录，请先核对进度：%s\n' "$p07Path" >&2
    exit 1
  fi
done
for p07Path in "$p07Base" "$p07Base/sources" "$p07Base/results" \
    "$p07Base/results/pretest-expat-2.7.1" "$p07Base/results/pretest-expat-2.7.1/preparation"; do
  if [[ -L "$p07Path" || ( -e "$p07Path" && ! -d "$p07Path" ) ]]; then
    printf '父目录状态不符，请返回输出：%s\n' "$p07Path" >&2
    exit 1
  fi
done
test -d "$p07Base/sources"
test -s "$p07Download/archive-check.json"
test -s "$p07Download/official-reference.json"
test -s "$p07ScriptDir/Verify_Extracted_Source.py"
p07Actual="$(sha256sum "$p07Archive")"
if [[ "${p07Actual%% *}" != "$p07Expected" ]]; then
  printf '原包SHA与已验收记录不符，停止解压。\n' >&2
  exit 1
fi
mkdir -p -- "$(dirname -- "$p07Record")"
mkdir -- "$p07Record"
printf 'record_id\tSRC-P07-001\nstart_utc\t%s\nsource_directory\t%s\narchive_sha256\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p07Source" "$p07Expected" > "$p07Record/source-meta.tsv"
sha256sum "$p07ScriptDir/Extract_Verify_Source.sh" "$p07ScriptDir/Verify_Extracted_Source.py" \
  "$p07ScriptDir/Inspect_Archive.py" "$p07ScriptDir/Check_Official_Identity.py" \
  "$p07Download/archive-check.json" "$p07Download/official-reference.json" \
  "$p07Download/tag-ref-try1/body" "$p07Download/tag-object-try1/body" \
  "$p07Download/git-commit-try1/body" "$p07Download/recursive-tree-try1/body" \
  > "$p07Record/input-files.sha256"

p07Preflight=(python3 "$p07ScriptDir/Verify_Extracted_Source.py" preflight "$p07Archive" \
  "$p07Download/archive-check.json" "$p07Download/official-reference.json" \
  "$p07Source" "$p07Record/preflight-check.json")
printf '%q ' "${p07Preflight[@]}" > "$p07Record/preflight-command.txt"
printf '\n' >> "$p07Record/preflight-command.txt"
if "${p07Preflight[@]}" > "$p07Record/preflight-stdout.txt" 2> "$p07Record/preflight-stderr.txt"; then p07PreflightExit=0; else p07PreflightExit=$?; fi
printf '%s\n' "$p07PreflightExit" > "$p07Record/preflight-exit-code.txt"
cat "$p07Record/preflight-stdout.txt"
if [[ "$p07PreflightExit" -ne 0 ]]; then cat "$p07Record/preflight-stderr.txt" >&2; exit "$p07PreflightExit"; fi

mkdir -- "$p07Source"
p07Extract=(tar -xzf "$p07Archive" -C "$p07Source" --strip-components=1 --no-same-owner --keep-old-files)
printf '%q ' "${p07Extract[@]}" > "$p07Record/extract-command.txt"
printf '\n' >> "$p07Record/extract-command.txt"
printf '开始解压已验收原包；核对记录：%s\n' "$p07Record"
if "${p07Extract[@]}" > "$p07Record/extract-stdout.txt" 2> "$p07Record/extract-stderr.txt"; then p07ExtractExit=0; else p07ExtractExit=$?; fi
printf '%s\n' "$p07ExtractExit" > "$p07Record/extract-exit-code.txt"
if [[ "$p07ExtractExit" -ne 0 ]]; then
  cat "$p07Record/extract-stderr.txt" >&2
  printf '解压失败，本次源码及日志保留，请返回输出，不要重复运行。\n' >&2
  exit "$p07ExtractExit"
fi

p07Verify=(python3 "$p07ScriptDir/Verify_Extracted_Source.py" verify "$p07Archive" \
  "$p07Download/archive-check.json" "$p07Download/official-reference.json" \
  "$p07Source" "$p07Record/source-check.json")
printf '%q ' "${p07Verify[@]}" > "$p07Record/verify-command.txt"
printf '\n' >> "$p07Record/verify-command.txt"
if "${p07Verify[@]}" > "$p07Record/verify-stdout.txt" 2> "$p07Record/verify-stderr.txt"; then p07VerifyExit=0; else p07VerifyExit=$?; fi
printf '%s\n' "$p07VerifyExit" > "$p07Record/verify-exit-code.txt"
cat "$p07Record/verify-stdout.txt"
if [[ "$p07VerifyExit" -ne 0 ]]; then
  cat "$p07Record/verify-stderr.txt" >&2
  printf '源码核对失败，本次文件和日志保留，请返回输出。\n' >&2
  exit "$p07VerifyExit"
fi
printf 'end_utc\t%s\npreflight_exit_code\t%s\nextract_exit_code\t%s\nverify_exit_code\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p07PreflightExit" "$p07ExtractExit" "$p07VerifyExit" >> "$p07Record/source-meta.tsv"
printf '\n解压退出码：%s；源码核对退出码：%s。\n' "$p07ExtractExit" "$p07VerifyExit"
printf 'SRC-P07-001结束；请返回输出，由助手验收后准备构建。本步没有运行CMake或检测工具。\n'
