#!/usr/bin/env bash
set -euo pipefail
set -C
p06ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p06Downloads="$HOME/comp5355/downloads"
p06Archive="$p06Downloads/yyjson-0.12.0.tar.gz"
p06Attempt="$p06Downloads/yyjson-0.12.0-DL-P06-001"
p06Url='https://codeload.github.com/ibireme/yyjson/tar.gz/8b4a38dc994a110abaec8a400615567bd996105f'
p06Reference="$p06ScriptDir/Official_Identity_Check_20261028/Official_Git_Tree.json"

for p06Command in curl tar sha256sum python3; do
  command -v "$p06Command" >/dev/null || exit 1
done
for p06Path in "$p06Archive" "$p06Archive.sha256" "$p06Archive.part" "$p06Attempt"; do
  if [[ -e "$p06Path" || -L "$p06Path" ]]; then
    printf '已有文件或记录，请先核对进度：%s\n' "$p06Path" >&2
    exit 1
  fi
done
if [[ ! -d "$p06Downloads" || -L "$p06Downloads" ]]; then
  printf '下载目录状态不符，请先核对：%s\n' "$p06Downloads" >&2
  exit 1
fi
test -s "$p06Reference"
test -s "$p06ScriptDir/Inspect_Archive.py"
mkdir -- "$p06Attempt"
p06Part="$p06Attempt/yyjson-0.12.0.tar.gz.part"
printf 'attempt_id\tDL-P06-001\nsource_url\t%s\nstart_utc\t%s\n' \
  "$p06Url" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p06Attempt/attempt-meta.tsv"
sha256sum "$p06ScriptDir/Download_Command.sh" "$p06ScriptDir/Inspect_Archive.py" \
  "$p06Reference" > "$p06Attempt/preparation-files.sha256"
p06Curl=(curl -fL --retry 2 --retry-all-errors --connect-timeout 20 --max-time 180 \
  --write-out 'http_code\t%{http_code}\nurl_effective\t%{url_effective}\nsize_download\t%{size_download}\n' \
  --output "$p06Part" "$p06Url")
printf '%q ' "${p06Curl[@]}" > "$p06Attempt/command.txt"
printf '\n' >> "$p06Attempt/command.txt"
printf '开始DL-P06-001，完成后显示摘要；连接错误最多自动重试两次。\n日志目录：%s\n' "$p06Attempt"
if "${p06Curl[@]}" > "$p06Attempt/curl-stdout.txt" 2> "$p06Attempt/curl-stderr.txt"; then
  p06CurlExit=0
else
  p06CurlExit=$?
fi
printf '%s\n' "$p06CurlExit" > "$p06Attempt/curl-exit-code.txt"
printf 'download_end_utc\t%s\ncurl_exit_code\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p06CurlExit" >> "$p06Attempt/attempt-meta.tsv"
printf 'curl退出码：%s\n' "$p06CurlExit"
if [[ "$p06CurlExit" -ne 0 ]]; then
  if [[ -f "$p06Part" ]]; then
    sha256sum "$p06Part" > "$p06Attempt/partial.sha256"
    stat --printf='%n : %s bytes\n' "$p06Part" > "$p06Attempt/partial-size.txt"
  fi
  printf 'not run: curl failed\n' > "$p06Attempt/tar-status.txt"
  tr '\r' '\n' < "$p06Attempt/curl-stderr.txt" | tail -n 15
  printf '下载未完成，本次产物与日志已保留。下次使用新编号，不要重复执行本脚本。\n' >&2
  exit "$p06CurlExit"
fi
if tar -tzf "$p06Part" > "$p06Attempt/archive-members.txt" 2> "$p06Attempt/tar-stderr.txt"; then
  p06TarExit=0
else
  p06TarExit=$?
fi
printf '%s\n' "$p06TarExit" > "$p06Attempt/tar-exit-code.txt"
if [[ "$p06TarExit" -ne 0 ]]; then
  cat "$p06Attempt/tar-stderr.txt" >&2
  printf '归档读取失败，本次part与日志已保留。\n' >&2
  exit "$p06TarExit"
fi
if python3 "$p06ScriptDir/Inspect_Archive.py" "$p06Part" "$p06Attempt/archive-check.json" "$p06Reference" \
  > "$p06Attempt/identity-stdout.txt" 2> "$p06Attempt/identity-stderr.txt"; then
  p06IdentityExit=0
else
  p06IdentityExit=$?
fi
printf '%s\n' "$p06IdentityExit" > "$p06Attempt/identity-exit-code.txt"
cat "$p06Attempt/identity-stdout.txt"
if [[ "$p06IdentityExit" -ne 0 ]]; then
  cat "$p06Attempt/identity-stderr.txt" >&2
  printf '固定版本身份检查失败，part与记录保留，尚未转存最终包。\n' >&2
  exit "$p06IdentityExit"
fi
mv -n -- "$p06Part" "$p06Archive"
if [[ -e "$p06Part" || -L "$p06Part" ]]; then
  printf '最终位置已有文件，本次part仍保留，请核对。\n' >&2
  exit 1
fi
sha256sum "$p06Archive" > "$p06Attempt/archive.sha256"
cp -n -- "$p06Attempt/archive.sha256" "$p06Archive.sha256"
cmp -- "$p06Attempt/archive.sha256" "$p06Archive.sha256"
stat --printf='%n : %s bytes\n' "$p06Archive" > "$p06Attempt/archive-size.txt"
printf 'completed_utc\t%s\nattempt_directory\t%s\nstatus\tdownloaded and preliminary identity check passed\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p06Attempt" > "$p06Attempt/completion.tsv"
cat "$p06Attempt/archive.sha256" "$p06Attempt/archive-size.txt"
sed -n '1,12p' "$p06Attempt/archive-members.txt"
printf 'DL-P06-001下载与身份初检结束。请返回输出，再由助手验收原包及日志；本步没有解压、构建或检测。\n'
