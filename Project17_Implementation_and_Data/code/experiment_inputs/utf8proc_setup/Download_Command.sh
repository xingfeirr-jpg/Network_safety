#!/usr/bin/env bash
set -euo pipefail
set -C
export PYTHONDONTWRITEBYTECODE=1
p10ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p10Downloads="$HOME/comp5355/downloads"
p10Archive="$p10Downloads/utf8proc-2.10.0.tar.gz"
p10Attempt="$p10Downloads/utf8proc-2.10.0-DL-P10-001"
p10Commit='a1b99daa2a3393884220264c927a48ba1251a9c6'
p10Api='https://api.github.com/repos/JuliaStrings/utf8proc'
p10Url="https://codeload.github.com/JuliaStrings/utf8proc/tar.gz/$p10Commit"
for p10Command in curl tar sha256sum python3; do command -v "$p10Command" >/dev/null; done
for p10Path in "$p10Archive" "$p10Archive.sha256" "$p10Archive.part" "$p10Attempt" "$HOME/comp5355/sources/utf8proc-2.10.0" "$HOME/comp5355/build/utf8proc-2.10.0" "$HOME/comp5355/results/pretest-utf8proc-2.10.0"; do
  if [[ -e "$p10Path" || -L "$p10Path" ]]; then
    printf '已有文件或记录，请先核对进度：%s\n' "$p10Path" >&2
    exit 1
  fi
done
if [[ ! -d "$p10Downloads" || -L "$p10Downloads" ]]; then
  printf '下载目录状态不符，请先核对：%s\n' "$p10Downloads" >&2
  exit 1
fi
test -s "$p10ScriptDir/Check_Official_Identity.py"
test -s "$p10ScriptDir/Inspect_Archive.py"
mkdir -- "$p10Attempt"
printf 'attempt_id\tDL-P10-001\nsource_url\t%s\nstart_utc\t%s\n' "$p10Url" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p10Attempt/attempt-meta.tsv"
sha256sum "$p10ScriptDir/Download_Command.sh" "$p10ScriptDir/Check_Official_Identity.py" "$p10ScriptDir/Inspect_Archive.py" > "$p10Attempt/preparation-files.sha256"

# Every request attempt retains its own body/headers/curl status, including failures.
p10Fetch() {
  local p10Label="$1" p10RequestUrl="$2" p10Try p10Dir p10Exit p10Http
  for p10Try in 1 2 3; do
    p10Dir="$p10Attempt/$p10Label-try$p10Try"
    mkdir -- "$p10Dir"
    printf '请求%s，尝试%s/3；完整输出保存到记录目录。\n' "$p10Label" "$p10Try"
    printf '%s\n' "$p10RequestUrl" > "$p10Dir/url.txt"
    local p10Curl=(curl -sS -L --connect-timeout 20 --max-time 180 --dump-header "$p10Dir/headers.txt" --output "$p10Dir/body" --write-out '%{http_code}\n' "$p10RequestUrl")
    printf '%q ' "${p10Curl[@]}" > "$p10Dir/command.txt"
    printf '\n' >> "$p10Dir/command.txt"
    if "${p10Curl[@]}" > "$p10Dir/http-code.txt" 2> "$p10Dir/stderr.txt"; then p10Exit=0; else p10Exit=$?; fi
    printf '%s\n' "$p10Exit" > "$p10Dir/curl-exit-code.txt"
    p10Http="$(cat "$p10Dir/http-code.txt")"
    if [[ "$p10Exit" -eq 0 && "$p10Http" == 200 ]]; then
      p10Fetched="$p10Dir/body"
      return 0
    fi
    printf '%s请求失败：curl=%s，HTTP=%s。\n' "$p10Label" "$p10Exit" "$p10Http"
    cat "$p10Dir/stderr.txt" >&2
    if [[ "$p10Http" == 403 || "$p10Http" == 404 || "$p10Http" == 429 ]]; then break; fi
  done
  printf '请求失败，已有响应／部分文件均保留。请返回输出，不要重复运行同编号脚本。\n' >&2
  return 1
}

printf '开始DL-P10-001：先核对官方固定身份，再下载原包。\n日志目录：%s\n' "$p10Attempt"
p10Fetch tag-ref "$p10Api/git/ref/tags/v2.10.0"; p10Ref="$p10Fetched"
p10Fetch git-commit "$p10Api/git/commits/$p10Commit"; p10GitCommit="$p10Fetched"
if python3 "$p10ScriptDir/Check_Official_Identity.py" chain "$p10Ref" "$p10GitCommit" > "$p10Attempt/root-tree-sha.txt" 2> "$p10Attempt/chain-stderr.txt"; then p10ChainExit=0; else p10ChainExit=$?; fi
printf '%s\n' "$p10ChainExit" > "$p10Attempt/chain-exit-code.txt"
if [[ "$p10ChainExit" -ne 0 ]]; then cat "$p10Attempt/chain-stderr.txt" >&2; exit "$p10ChainExit"; fi
p10TreeSha="$(cat "$p10Attempt/root-tree-sha.txt")"
p10Fetch recursive-tree "$p10Api/git/trees/$p10TreeSha?recursive=1"; p10Tree="$p10Fetched"
if python3 "$p10ScriptDir/Check_Official_Identity.py" tree "$p10Ref" "$p10GitCommit" "$p10Tree" "$p10Attempt/official-reference.json" > "$p10Attempt/official-identity-stdout.txt" 2> "$p10Attempt/official-identity-stderr.txt"; then p10OfficialExit=0; else p10OfficialExit=$?; fi
printf '%s\n' "$p10OfficialExit" > "$p10Attempt/official-identity-exit-code.txt"
cat "$p10Attempt/official-identity-stdout.txt"
if [[ "$p10OfficialExit" -ne 0 ]]; then cat "$p10Attempt/official-identity-stderr.txt" >&2; exit "$p10OfficialExit"; fi
p10Fetch archive "$p10Url"; p10Part="$p10Fetched"
if tar -tzf "$p10Part" > "$p10Attempt/archive-members.txt" 2> "$p10Attempt/tar-stderr.txt"; then p10TarExit=0; else p10TarExit=$?; fi
printf '%s\n' "$p10TarExit" > "$p10Attempt/tar-exit-code.txt"
if [[ "$p10TarExit" -ne 0 ]]; then cat "$p10Attempt/tar-stderr.txt" >&2; exit "$p10TarExit"; fi
if python3 "$p10ScriptDir/Inspect_Archive.py" "$p10Part" "$p10Attempt/archive-check.json" "$p10Attempt/official-reference.json" > "$p10Attempt/identity-stdout.txt" 2> "$p10Attempt/identity-stderr.txt"; then p10IdentityExit=0; else p10IdentityExit=$?; fi
printf '%s\n' "$p10IdentityExit" > "$p10Attempt/identity-exit-code.txt"
cat "$p10Attempt/identity-stdout.txt"
if [[ "$p10IdentityExit" -ne 0 ]]; then
  cat "$p10Attempt/identity-stderr.txt" >&2
  printf '原包仍保留在：%s；等待核对，不解压。\n' "$p10Part"
  exit "$p10IdentityExit"
fi
# Copy exclusively; preserve the successful HTTP body as an original response.
python3 - "$p10Part" "$p10Archive" <<'PY'
from pathlib import Path
import shutil,sys
with Path(sys.argv[1]).open('rb') as source,Path(sys.argv[2]).open('xb') as target:
    shutil.copyfileobj(source,target)
PY
sha256sum "$p10Archive" > "$p10Attempt/archive.sha256"
python3 - "$p10Attempt/archive.sha256" "$p10Archive.sha256" <<'PY'
from pathlib import Path
import sys
with Path(sys.argv[2]).open('xb') as target:target.write(Path(sys.argv[1]).read_bytes())
PY
cmp -- "$p10Attempt/archive.sha256" "$p10Archive.sha256"
stat --printf='%n : %s bytes\n' "$p10Archive" > "$p10Attempt/archive-size.txt"
printf 'completed_utc\t%s\nstatus\tdownloaded and preliminary identity check passed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p10Attempt/completion.tsv"
cat "$p10Attempt/archive.sha256" "$p10Attempt/archive-size.txt"
sed -n '1,12p' "$p10Attempt/archive-members.txt"
printf 'DL-P10-001结束。请返回输出或截图，由助手验收实际原包与日志；本步未解压／构建／运行检测工具。\n'
