#!/usr/bin/env bash
set -euo pipefail
p05Downloads="$HOME/comp5355/downloads"
p05Archive="$p05Downloads/json-c-0.18.tar.gz"
p05Attempt="$p05Downloads/json-c-0.18-DL-P05-002"
p05Url='https://codeload.github.com/json-c/json-c/tar.gz/41a55cfcedb54d9c1874f2f0eb07b504091d7e37'

for p05Path in "$p05Archive" "$p05Archive.sha256" "$p05Attempt"; do
  if [[ -e "$p05Path" || -L "$p05Path" ]]; then
    printf '已存在，请先核对进度：%s\n' "$p05Path" >&2
    exit 1
  fi
done
if [[ ! -d "$p05Downloads" || -L "$p05Downloads" ]]; then
  printf '下载目录状态不符，请先核对：%s\n' "$p05Downloads" >&2
  exit 1
fi
mkdir -- "$p05Attempt"
p05Part="$p05Attempt/json-c-0.18.tar.gz.part"
printf 'attempt_id\tDL-P05-002\nsource_url\t%s\nstart_utc\t%s\n' \
  "$p05Url" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p05Attempt/attempt-meta.tsv"
if [[ -f "$p05Archive.part" && ! -L "$p05Archive.part" ]]; then
  sha256sum "$p05Archive.part" > "$p05Attempt/preserved-attempt001-part.sha256"
fi
p05Curl=(curl -fL --retry 2 --retry-all-errors --connect-timeout 20 --max-time 180 \
  --output "$p05Part" "$p05Url")
printf '%q ' "${p05Curl[@]}" > "$p05Attempt/command.txt"
printf '\n' >> "$p05Attempt/command.txt"
printf '开始DL-P05-002；旧part保留。完成后显示结果；连接错误最多自动重试两次。\n日志目录：%s\n' "$p05Attempt"
if "${p05Curl[@]}" > "$p05Attempt/curl-stdout.txt" 2> "$p05Attempt/curl-stderr.txt"; then
  p05CurlExit=0
else
  p05CurlExit=$?
fi
printf '%s\n' "$p05CurlExit" > "$p05Attempt/curl-exit-code.txt"
printf 'end_utc\t%s\ncurl_exit_code\t%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p05CurlExit" >> "$p05Attempt/attempt-meta.tsv"
printf 'curl退出码：%s\n' "$p05CurlExit"
if [[ "$p05CurlExit" -ne 0 ]]; then
  tr '\r' '\n' < "$p05Attempt/curl-stderr.txt" | tail -n 15
  printf '本次未完成，文件和日志已保留在：%s\n' "$p05Attempt" >&2
  exit "$p05CurlExit"
fi
if tar -tzf "$p05Part" > "$p05Attempt/archive-members.txt" 2> "$p05Attempt/tar-stderr.txt"; then
  p05TarExit=0
else
  p05TarExit=$?
fi
printf '%s\n' "$p05TarExit" > "$p05Attempt/tar-exit-code.txt"
if [[ "$p05TarExit" -ne 0 ]]; then
  cat "$p05Attempt/tar-stderr.txt" >&2
  printf '归档读取失败，本次文件保持原样：%s\n' "$p05Part" >&2
  exit "$p05TarExit"
fi
mv -n -- "$p05Part" "$p05Archive"
if [[ -e "$p05Part" || -L "$p05Part" ]]; then
  printf '原包未转存到最终位置，请核对已有文件；本次part仍保留。\n' >&2
  exit 1
fi
sha256sum "$p05Archive" | tee "$p05Archive.sha256" "$p05Attempt/archive.sha256"
stat --printf='%n : %s bytes\n' "$p05Archive"
sed -n '1,12p' "$p05Attempt/archive-members.txt"
printf 'DL-P05-002下载及归档读取完成；请返回输出，继续核对固定版本身份。\n'
