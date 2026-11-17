#!/usr/bin/env bash
set -euo pipefail
set -C
p08ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p08Downloads="$HOME/comp5355/downloads"
p08Archive="$p08Downloads/libpng-1.6.50.tar.gz"
p08Attempt="$p08Downloads/libpng-1.6.50-DL-P08-001"
p08Commit='2b978915d82377df13fcbb1fb56660195ded868a'
p08TagObject='1e35d2c82a48c58f8f4d6a66dd92ae5e4cdc3f98'
p08Api='https://api.github.com/repos/pnggroup/libpng'
p08Url="https://codeload.github.com/pnggroup/libpng/tar.gz/$p08Commit"
for p08Command in curl tar sha256sum python3; do command -v "$p08Command" >/dev/null; done
for p08Path in "$p08Archive" "$p08Archive.sha256" "$p08Archive.part" "$p08Attempt"; do
  if [[ -e "$p08Path" || -L "$p08Path" ]]; then
    printf '已有文件或记录，请先核对进度：%s\n' "$p08Path" >&2
    exit 1
  fi
done
if [[ ! -d "$p08Downloads" || -L "$p08Downloads" ]]; then
  printf '下载目录状态不符，请先核对：%s\n' "$p08Downloads" >&2
  exit 1
fi
test -s "$p08ScriptDir/Check_Official_Identity.py"
test -s "$p08ScriptDir/Inspect_Archive.py"
mkdir -- "$p08Attempt"
printf 'attempt_id\tDL-P08-001\nsource_url\t%s\nstart_utc\t%s\n' "$p08Url" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p08Attempt/attempt-meta.tsv"
sha256sum "$p08ScriptDir/Download_Command.sh" "$p08ScriptDir/Check_Official_Identity.py" "$p08ScriptDir/Inspect_Archive.py" > "$p08Attempt/preparation-files.sha256"

# Every request attempt retains its own body/headers/curl status, including failures.
p08Fetch() {
  local p08Label="$1" p08RequestUrl="$2" p08Try p08Dir p08Exit p08Http
  for p08Try in 1 2 3; do
    p08Dir="$p08Attempt/$p08Label-try$p08Try"
    mkdir -- "$p08Dir"
    printf '请求%s，尝试%s/3；完整输出保存到记录目录。\n' "$p08Label" "$p08Try"
    printf '%s\n' "$p08RequestUrl" > "$p08Dir/url.txt"
    local p08Curl=(curl -sS -L --connect-timeout 20 --max-time 180 --dump-header "$p08Dir/headers.txt" --output "$p08Dir/body" --write-out '%{http_code}\n' "$p08RequestUrl")
    printf '%q ' "${p08Curl[@]}" > "$p08Dir/command.txt"
    printf '\n' >> "$p08Dir/command.txt"
    if "${p08Curl[@]}" > "$p08Dir/http-code.txt" 2> "$p08Dir/stderr.txt"; then p08Exit=0; else p08Exit=$?; fi
    printf '%s\n' "$p08Exit" > "$p08Dir/curl-exit-code.txt"
    p08Http="$(cat "$p08Dir/http-code.txt")"
    if [[ "$p08Exit" -eq 0 && "$p08Http" == 200 ]]; then
      p08Fetched="$p08Dir/body"
      return 0
    fi
    printf '%s请求失败：curl=%s，HTTP=%s。\n' "$p08Label" "$p08Exit" "$p08Http"
    cat "$p08Dir/stderr.txt" >&2
    if [[ "$p08Http" == 403 || "$p08Http" == 404 || "$p08Http" == 429 ]]; then break; fi
  done
  printf '请求失败，已有响应／部分文件均保留。请返回输出，不要重复运行同编号脚本。\n' >&2
  return 1
}

printf '开始DL-P08-001：先核对官方固定身份，再下载原包。\n日志目录：%s\n' "$p08Attempt"
p08Fetch tag-ref "$p08Api/git/ref/tags/v1.6.50"; p08Ref="$p08Fetched"
p08Fetch tag-object "$p08Api/git/tags/$p08TagObject"; p08Tag="$p08Fetched"
p08Fetch git-commit "$p08Api/git/commits/$p08Commit"; p08GitCommit="$p08Fetched"
if python3 "$p08ScriptDir/Check_Official_Identity.py" chain "$p08Ref" "$p08Tag" "$p08GitCommit" > "$p08Attempt/root-tree-sha.txt" 2> "$p08Attempt/chain-stderr.txt"; then p08ChainExit=0; else p08ChainExit=$?; fi
printf '%s\n' "$p08ChainExit" > "$p08Attempt/chain-exit-code.txt"
if [[ "$p08ChainExit" -ne 0 ]]; then cat "$p08Attempt/chain-stderr.txt" >&2; exit "$p08ChainExit"; fi
p08TreeSha="$(cat "$p08Attempt/root-tree-sha.txt")"
p08Fetch recursive-tree "$p08Api/git/trees/$p08TreeSha?recursive=1"; p08Tree="$p08Fetched"
if python3 "$p08ScriptDir/Check_Official_Identity.py" tree "$p08Ref" "$p08Tag" "$p08GitCommit" "$p08Tree" "$p08Attempt/official-reference.json" > "$p08Attempt/official-identity-stdout.txt" 2> "$p08Attempt/official-identity-stderr.txt"; then p08OfficialExit=0; else p08OfficialExit=$?; fi
printf '%s\n' "$p08OfficialExit" > "$p08Attempt/official-identity-exit-code.txt"
cat "$p08Attempt/official-identity-stdout.txt"
if [[ "$p08OfficialExit" -ne 0 ]]; then cat "$p08Attempt/official-identity-stderr.txt" >&2; exit "$p08OfficialExit"; fi
p08Fetch archive "$p08Url"; p08Part="$p08Fetched"
if tar -tzf "$p08Part" > "$p08Attempt/archive-members.txt" 2> "$p08Attempt/tar-stderr.txt"; then p08TarExit=0; else p08TarExit=$?; fi
printf '%s\n' "$p08TarExit" > "$p08Attempt/tar-exit-code.txt"
if [[ "$p08TarExit" -ne 0 ]]; then cat "$p08Attempt/tar-stderr.txt" >&2; exit "$p08TarExit"; fi
if python3 "$p08ScriptDir/Inspect_Archive.py" "$p08Part" "$p08Attempt/archive-check.json" "$p08Attempt/official-reference.json" > "$p08Attempt/identity-stdout.txt" 2> "$p08Attempt/identity-stderr.txt"; then p08IdentityExit=0; else p08IdentityExit=$?; fi
printf '%s\n' "$p08IdentityExit" > "$p08Attempt/identity-exit-code.txt"
cat "$p08Attempt/identity-stdout.txt"
if [[ "$p08IdentityExit" -ne 0 ]]; then
  cat "$p08Attempt/identity-stderr.txt" >&2
  printf '原包仍保留在：%s；等待核对，不解压。\n' "$p08Part"
  exit "$p08IdentityExit"
fi
# Copy exclusively; preserve the successful HTTP body as an original response.
python3 - "$p08Part" "$p08Archive" <<'PY'
from pathlib import Path
import shutil,sys
with Path(sys.argv[1]).open('rb') as source,Path(sys.argv[2]).open('xb') as target:
    shutil.copyfileobj(source,target)
PY
sha256sum "$p08Archive" > "$p08Attempt/archive.sha256"
python3 - "$p08Attempt/archive.sha256" "$p08Archive.sha256" <<'PY'
from pathlib import Path
import sys
with Path(sys.argv[2]).open('xb') as target:target.write(Path(sys.argv[1]).read_bytes())
PY
cmp -- "$p08Attempt/archive.sha256" "$p08Archive.sha256"
stat --printf='%n : %s bytes\n' "$p08Archive" > "$p08Attempt/archive-size.txt"
printf 'completed_utc\t%s\nstatus\tdownloaded and preliminary identity check passed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p08Attempt/completion.tsv"
cat "$p08Attempt/archive.sha256" "$p08Attempt/archive-size.txt"
sed -n '1,12p' "$p08Attempt/archive-members.txt"
printf 'DL-P08-001结束。请返回输出或截图，由助手验收实际原包与日志；本步未解压／构建／运行检测工具。\n'
