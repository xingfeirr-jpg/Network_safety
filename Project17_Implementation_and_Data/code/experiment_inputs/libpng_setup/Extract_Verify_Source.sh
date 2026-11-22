#!/usr/bin/env bash
set -euo pipefail
set -C
p08ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p08Base="$HOME/comp5355"
p08Archive="$p08Base/downloads/libpng-1.6.50.tar.gz"
p08Download="$p08Base/downloads/libpng-1.6.50-DL-P08-001"
p08Source="$p08Base/sources/libpng-1.6.50"
p08Record="$p08Base/results/pretest-libpng-1.6.50/preparation/SRC-P08-001"
p08Expected='fba1c8e793f01b493f3f47a926862edbfab487ae4240e02ec67131f1e2bf067f'

for p08Path in "$p08Source" "$p08Record"; do
  if [[ -e "$p08Path" || -L "$p08Path" ]]; then
    printf '已有源码或核对记录，请先核对进度：%s\n' "$p08Path" >&2
    exit 1
  fi
done
for p08Path in "$p08Base" "$p08Base/sources" "$p08Base/results" \
    "$p08Base/results/pretest-libpng-1.6.50" "$p08Base/results/pretest-libpng-1.6.50/preparation"; do
  if [[ -L "$p08Path" || ( -e "$p08Path" && ! -d "$p08Path" ) ]]; then
    printf '父目录状态不符，请返回输出：%s\n' "$p08Path" >&2
    exit 1
  fi
done
test -d "$p08Base/sources"
test -s "$p08Download/archive-check.json"
test -s "$p08Download/official-reference.json"
test -s "$p08ScriptDir/Verify_Extracted_Source.py"
p08Actual="$(sha256sum "$p08Archive")"
if [[ "${p08Actual%% *}" != "$p08Expected" ]]; then
  printf '原包SHA与已验收记录不符，停止解压。\n' >&2
  exit 1
fi
mkdir -p -- "$(dirname -- "$p08Record")"
mkdir -- "$p08Record"
printf 'record_id\tSRC-P08-001\nstart_utc\t%s\nsource_directory\t%s\narchive_sha256\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p08Source" "$p08Expected" > "$p08Record/source-meta.tsv"
sha256sum "$p08ScriptDir/Extract_Verify_Source.sh" "$p08ScriptDir/Verify_Extracted_Source.py" \
  "$p08ScriptDir/Inspect_Archive.py" "$p08ScriptDir/Check_Official_Identity.py" \
  "$p08Download/archive-check.json" "$p08Download/official-reference.json" \
  "$p08Download/tag-ref-try1/body" "$p08Download/tag-object-try1/body" \
  "$p08Download/git-commit-try1/body" "$p08Download/recursive-tree-try1/body" \
  > "$p08Record/input-files.sha256"

p08Preflight=(python3 "$p08ScriptDir/Verify_Extracted_Source.py" preflight "$p08Archive" \
  "$p08Download/archive-check.json" "$p08Download/official-reference.json" \
  "$p08Source" "$p08Record/preflight-check.json")
printf '%q ' "${p08Preflight[@]}" > "$p08Record/preflight-command.txt"
printf '\n' >> "$p08Record/preflight-command.txt"
if "${p08Preflight[@]}" > "$p08Record/preflight-stdout.txt" 2> "$p08Record/preflight-stderr.txt"; then p08PreflightExit=0; else p08PreflightExit=$?; fi
printf '%s\n' "$p08PreflightExit" > "$p08Record/preflight-exit-code.txt"
cat "$p08Record/preflight-stdout.txt"
if [[ "$p08PreflightExit" -ne 0 ]]; then cat "$p08Record/preflight-stderr.txt" >&2; exit "$p08PreflightExit"; fi

mkdir -- "$p08Source"
p08Extract=(tar -xzf "$p08Archive" -C "$p08Source" --strip-components=1 --no-same-owner --keep-old-files)
printf '%q ' "${p08Extract[@]}" > "$p08Record/extract-command.txt"
printf '\n' >> "$p08Record/extract-command.txt"
printf '开始解压已验收原包；核对记录：%s\n' "$p08Record"
if "${p08Extract[@]}" > "$p08Record/extract-stdout.txt" 2> "$p08Record/extract-stderr.txt"; then p08ExtractExit=0; else p08ExtractExit=$?; fi
printf '%s\n' "$p08ExtractExit" > "$p08Record/extract-exit-code.txt"
if [[ "$p08ExtractExit" -ne 0 ]]; then
  cat "$p08Record/extract-stderr.txt" >&2
  printf '解压失败，本次源码及日志保留，请返回输出，不要重复运行。\n' >&2
  exit "$p08ExtractExit"
fi

p08Verify=(python3 "$p08ScriptDir/Verify_Extracted_Source.py" verify "$p08Archive" \
  "$p08Download/archive-check.json" "$p08Download/official-reference.json" \
  "$p08Source" "$p08Record/source-check.json")
printf '%q ' "${p08Verify[@]}" > "$p08Record/verify-command.txt"
printf '\n' >> "$p08Record/verify-command.txt"
if "${p08Verify[@]}" > "$p08Record/verify-stdout.txt" 2> "$p08Record/verify-stderr.txt"; then p08VerifyExit=0; else p08VerifyExit=$?; fi
printf '%s\n' "$p08VerifyExit" > "$p08Record/verify-exit-code.txt"
cat "$p08Record/verify-stdout.txt"
if [[ "$p08VerifyExit" -ne 0 ]]; then
  cat "$p08Record/verify-stderr.txt" >&2
  printf '源码核对失败，本次文件和日志保留，请返回输出。\n' >&2
  exit "$p08VerifyExit"
fi
printf 'end_utc\t%s\npreflight_exit_code\t%s\nextract_exit_code\t%s\nverify_exit_code\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p08PreflightExit" "$p08ExtractExit" "$p08VerifyExit" >> "$p08Record/source-meta.tsv"
printf '\n解压退出码：%s；源码核对退出码：%s。\n' "$p08ExtractExit" "$p08VerifyExit"
printf 'SRC-P08-001结束；请返回输出，由助手验收后准备构建。本步没有运行CMake或检测工具。\n'
