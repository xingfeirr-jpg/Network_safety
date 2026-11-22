#!/usr/bin/env bash
set -euo pipefail
set -C
p07ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p07Downloads="$HOME/comp5355/downloads"
p07Archive="$p07Downloads/expat-2.7.1.tar.gz"
p07Attempt="$p07Downloads/expat-2.7.1-DL-P07-001"
p07Commit='f9a3eeb3e09fbea04b1c451ffc422ab2f1e45744'
p07TagObject='436d5aa84b32fd2826c883ca543ddda6145d6a5a'
p07Api='https://api.github.com/repos/libexpat/libexpat'
p07Url="https://codeload.github.com/libexpat/libexpat/tar.gz/$p07Commit"
for p07Command in curl tar sha256sum python3; do command -v "$p07Command" >/dev/null; done
for p07Path in "$p07Archive" "$p07Archive.sha256" "$p07Archive.part" "$p07Attempt"; do
  if [[ -e "$p07Path" || -L "$p07Path" ]]; then
    printf '已有文件或记录，请先核对进度：%s\n' "$p07Path" >&2
    exit 1
  fi
done
if [[ ! -d "$p07Downloads" || -L "$p07Downloads" ]]; then
  printf '下载目录状态不符，请先核对：%s\n' "$p07Downloads" >&2
  exit 1
fi
test -s "$p07ScriptDir/Check_Official_Identity.py"
test -s "$p07ScriptDir/Inspect_Archive.py"
mkdir -- "$p07Attempt"
printf 'attempt_id\tDL-P07-001\nsource_url\t%s\nstart_utc\t%s\n' "$p07Url" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p07Attempt/attempt-meta.tsv"
sha256sum "$p07ScriptDir/Download_Command.sh" "$p07ScriptDir/Check_Official_Identity.py" "$p07ScriptDir/Inspect_Archive.py" > "$p07Attempt/preparation-files.sha256"

# Every request attempt retains its own body/headers/curl status, including failures.
p07Fetch() {
  local p07Label="$1" p07RequestUrl="$2" p07Try p07Dir p07Exit p07Http
  for p07Try in 1 2 3; do
    p07Dir="$p07Attempt/$p07Label-try$p07Try"
    mkdir -- "$p07Dir"
    printf '请求%s，尝试%s/3；完整输出保存到记录目录。\n' "$p07Label" "$p07Try"
    printf '%s\n' "$p07RequestUrl" > "$p07Dir/url.txt"
    local p07Curl=(curl -sS -L --connect-timeout 20 --max-time 180 --dump-header "$p07Dir/headers.txt" --output "$p07Dir/body" --write-out '%{http_code}\n' "$p07RequestUrl")
    printf '%q ' "${p07Curl[@]}" > "$p07Dir/command.txt"
    printf '\n' >> "$p07Dir/command.txt"
    if "${p07Curl[@]}" > "$p07Dir/http-code.txt" 2> "$p07Dir/stderr.txt"; then p07Exit=0; else p07Exit=$?; fi
    printf '%s\n' "$p07Exit" > "$p07Dir/curl-exit-code.txt"
    p07Http="$(cat "$p07Dir/http-code.txt")"
    if [[ "$p07Exit" -eq 0 && "$p07Http" == 200 ]]; then
      p07Fetched="$p07Dir/body"
      return 0
    fi
    printf '%s请求失败：curl=%s，HTTP=%s。\n' "$p07Label" "$p07Exit" "$p07Http"
    cat "$p07Dir/stderr.txt" >&2
    if [[ "$p07Http" == 403 || "$p07Http" == 404 || "$p07Http" == 429 ]]; then break; fi
  done
  printf '请求失败，已有响应／部分文件均保留。请返回输出，不要重复运行同编号脚本。\n' >&2
  return 1
}

printf '开始DL-P07-001：先核对官方固定身份，再下载原包。\n日志目录：%s\n' "$p07Attempt"
p07Fetch tag-ref "$p07Api/git/ref/tags/R_2_7_1"; p07Ref="$p07Fetched"
p07Fetch tag-object "$p07Api/git/tags/$p07TagObject"; p07Tag="$p07Fetched"
p07Fetch git-commit "$p07Api/git/commits/$p07Commit"; p07GitCommit="$p07Fetched"
if python3 "$p07ScriptDir/Check_Official_Identity.py" chain "$p07Ref" "$p07Tag" "$p07GitCommit" > "$p07Attempt/root-tree-sha.txt" 2> "$p07Attempt/chain-stderr.txt"; then p07ChainExit=0; else p07ChainExit=$?; fi
printf '%s\n' "$p07ChainExit" > "$p07Attempt/chain-exit-code.txt"
if [[ "$p07ChainExit" -ne 0 ]]; then cat "$p07Attempt/chain-stderr.txt" >&2; exit "$p07ChainExit"; fi
p07TreeSha="$(cat "$p07Attempt/root-tree-sha.txt")"
p07Fetch recursive-tree "$p07Api/git/trees/$p07TreeSha?recursive=1"; p07Tree="$p07Fetched"
if python3 "$p07ScriptDir/Check_Official_Identity.py" tree "$p07Ref" "$p07Tag" "$p07GitCommit" "$p07Tree" "$p07Attempt/official-reference.json" > "$p07Attempt/official-identity-stdout.txt" 2> "$p07Attempt/official-identity-stderr.txt"; then p07OfficialExit=0; else p07OfficialExit=$?; fi
printf '%s\n' "$p07OfficialExit" > "$p07Attempt/official-identity-exit-code.txt"
cat "$p07Attempt/official-identity-stdout.txt"
if [[ "$p07OfficialExit" -ne 0 ]]; then cat "$p07Attempt/official-identity-stderr.txt" >&2; exit "$p07OfficialExit"; fi
p07Fetch archive "$p07Url"; p07Part="$p07Fetched"
if tar -tzf "$p07Part" > "$p07Attempt/archive-members.txt" 2> "$p07Attempt/tar-stderr.txt"; then p07TarExit=0; else p07TarExit=$?; fi
printf '%s\n' "$p07TarExit" > "$p07Attempt/tar-exit-code.txt"
if [[ "$p07TarExit" -ne 0 ]]; then cat "$p07Attempt/tar-stderr.txt" >&2; exit "$p07TarExit"; fi
if python3 "$p07ScriptDir/Inspect_Archive.py" "$p07Part" "$p07Attempt/archive-check.json" "$p07Attempt/official-reference.json" > "$p07Attempt/identity-stdout.txt" 2> "$p07Attempt/identity-stderr.txt"; then p07IdentityExit=0; else p07IdentityExit=$?; fi
printf '%s\n' "$p07IdentityExit" > "$p07Attempt/identity-exit-code.txt"
cat "$p07Attempt/identity-stdout.txt"
if [[ "$p07IdentityExit" -ne 0 ]]; then
  cat "$p07Attempt/identity-stderr.txt" >&2
  printf '原包仍保留在：%s；等待核对，不解压。\n' "$p07Part"
  exit "$p07IdentityExit"
fi
# Copy exclusively; preserve the successful HTTP body as an original response.
python3 - "$p07Part" "$p07Archive" <<'PY'
from pathlib import Path
import shutil,sys
with Path(sys.argv[1]).open('rb') as source,Path(sys.argv[2]).open('xb') as target:
    shutil.copyfileobj(source,target)
PY
sha256sum "$p07Archive" > "$p07Attempt/archive.sha256"
python3 - "$p07Attempt/archive.sha256" "$p07Archive.sha256" <<'PY'
from pathlib import Path
import sys
with Path(sys.argv[2]).open('xb') as target:target.write(Path(sys.argv[1]).read_bytes())
PY
cmp -- "$p07Attempt/archive.sha256" "$p07Archive.sha256"
stat --printf='%n : %s bytes\n' "$p07Archive" > "$p07Attempt/archive-size.txt"
printf 'completed_utc\t%s\nstatus\tdownloaded and preliminary identity check passed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p07Attempt/completion.tsv"
cat "$p07Attempt/archive.sha256" "$p07Attempt/archive-size.txt"
sed -n '1,12p' "$p07Attempt/archive-members.txt"
printf 'DL-P07-001结束。请返回输出或截图，由助手验收实际原包与日志；本步未解压／构建／运行检测工具。\n'
