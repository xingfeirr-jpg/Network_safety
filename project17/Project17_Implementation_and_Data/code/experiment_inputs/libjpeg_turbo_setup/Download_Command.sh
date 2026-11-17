#!/usr/bin/env bash
set -euo pipefail
p09ScriptDir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p09Base="$HOME/comp5355"
p09Downloads="$p09Base/downloads"
p09Archive="$p09Downloads/libjpeg-turbo-3.1.1.tar.gz"
p09Attempt="$p09Downloads/libjpeg-turbo-3.1.1-DL-P09-001"
p09Url='https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.1.1/libjpeg-turbo-3.1.1.tar.gz'
p09Profile="$p09ScriptDir/Download_Profile.json"
for p09Path in "$p09Archive" "$p09Archive.sha256" "$p09Archive.part" "$p09Attempt" "$p09Base/sources/libjpeg-turbo-3.1.1" "$p09Base/build/libjpeg-turbo-3.1.1" "$p09Base/results/pretest-libjpeg-turbo-3.1.1"; do
  if [[ -e "$p09Path" || -L "$p09Path" ]]; then
    printf '已有P09文件或记录，请先核对现有进度：%s\n' "$p09Path" >&2
    exit 1
  fi
done
python3 "$p09ScriptDir/Inspect_Release_Archive.py" profile "$p09Profile"
mkdir -p -- "$p09Downloads"
mkdir -- "$p09Attempt"
printf 'run_id\tDL-P09-001\npurpose\tofficial source archive download only\nstarted_utc\t%s\nurl\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$p09Url" > "$p09Attempt/attempt.tsv"
sha256sum "$p09ScriptDir/Download_Command.sh" "$p09ScriptDir/Inspect_Release_Archive.py" "$p09Profile" "$p09ScriptDir/Official_Identity_Check_20261029/Metadata_Check.json" > "$p09Attempt/preparation-files.sha256"
printf '开始DL-P09-001：下载正式发布源码包，约2.5 MB；最多3次连接尝试。\n日志目录：%s\n' "$p09Attempt"
p09Success=0
for p09N in 1 2 3; do
  p09Stem="$p09Attempt/archive-attempt$(printf '%03d' "$p09N")"
  printf '下载尝试%s/3；完整传输记录保留在日志目录。\n' "$p09N"
  if curl --fail-with-body --location --silent --show-error --connect-timeout 20 --max-time 300 \
      --dump-header "$p09Stem-headers.txt" --output "$p09Stem-body.part" \
      --write-out '%{http_code}\n%{url_effective}\n%{size_download}\n' \
      "$p09Url" > "$p09Stem-meta.txt" 2> "$p09Stem-stderr.txt"; then p09Exit=0; else p09Exit=$?; fi
  printf '%s\n' "$p09Exit" > "$p09Stem-exit-code.txt"
  if [[ "$p09Exit" -eq 0 && "$(head -n 1 "$p09Stem-meta.txt")" == 200 ]]; then
    p09Part="$p09Stem-body.part";p09Success=1;break
  fi
  cat "$p09Stem-stderr.txt" >&2
  if [[ "$p09N" -lt 3 ]]; then sleep 2; fi
done
if [[ "$p09Success" -ne 1 ]]; then printf '下载未成功；各次原件已保留，不会解压或覆盖。\n' >&2;exit 1;fi
if python3 "$p09ScriptDir/Inspect_Release_Archive.py" archive "$p09Profile" "$p09Part" "$p09Attempt/archive-check.json" > "$p09Attempt/identity-stdout.txt" 2> "$p09Attempt/identity-stderr.txt"; then p09IdentityExit=0; else p09IdentityExit=$?;fi
printf '%s\n' "$p09IdentityExit" > "$p09Attempt/identity-exit-code.txt"
cat "$p09Attempt/identity-stdout.txt"
if [[ "$p09IdentityExit" -ne 0 ]]; then cat "$p09Attempt/identity-stderr.txt" >&2;printf '原包保留在：%s；等待核对。\n' "$p09Part";exit "$p09IdentityExit";fi
python3 - "$p09Part" "$p09Archive" <<'PY'
from pathlib import Path
import shutil,sys
with Path(sys.argv[1]).open('rb') as source,Path(sys.argv[2]).open('xb') as target:shutil.copyfileobj(source,target)
PY
sha256sum "$p09Archive" > "$p09Attempt/archive.sha256"
python3 - "$p09Attempt/archive.sha256" "$p09Archive.sha256" <<'PY'
from pathlib import Path
import sys
with Path(sys.argv[2]).open('xb') as target:target.write(Path(sys.argv[1]).read_bytes())
PY
cmp -- "$p09Attempt/archive.sha256" "$p09Archive.sha256"
stat --printf='%n : %s bytes\n' "$p09Archive" > "$p09Attempt/archive-size.txt"
printf 'completed_utc\t%s\nstatus\tdownload and preliminary release identity check passed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p09Attempt/completion.tsv"
cat "$p09Attempt/archive.sha256" "$p09Attempt/archive-size.txt"
printf 'DL-P09-001结束。请返回完整输出或截图，由助手验收原包及日志；本步未解压、构建或检测。\n'
