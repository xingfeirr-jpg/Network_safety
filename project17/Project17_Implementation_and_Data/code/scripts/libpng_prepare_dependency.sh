#!/usr/bin/env bash
# User-executed P08 dependency installation only; no build or analyzer invocation.
set -euo pipefail
set -C
if [[ $# -ne 1 || ! -s "$1/system.txt" || ! -s "$1/tool-versions.txt" ]]; then
    printf '请传入本次环境快照目录。\n' >&2
    exit 64
fi
p08Session="$(cd -- "$1" && pwd -P)"
p08Docs="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
p08Base="$HOME/comp5355"
p08Build="$p08Base/build/zlib-v1.3.2"
p08Prefix="$p08Base/deps/zlib-v1.3.2"
p08Record="$p08Base/results/pretest-libpng-1.6.50/preparation/DEP-P08-001"
p08Helper="$p08Docs/review_evidence/libpng_setup/Verify_Zlib_Dependency.py"
for p08Command in cmake python3 sha256sum; do command -v "$p08Command" >/dev/null; done
[[ -x /usr/bin/time && -s "$p08Helper" ]] || exit 69
if [[ -n "${DESTDIR:-}" || -n "${CMAKE_INSTALL_MODE:-}" ]]; then
    printf '发现影响安装目的地或复制方式的环境变量，请返回输出核对。\n' >&2
    exit 65
fi
for p08Path in "$p08Prefix" "$p08Record" "$p08Build/install_manifest_Development.txt"; do
    if [[ -e "$p08Path" || -L "$p08Path" ]]; then
        printf '已有依赖前缀或安装记录，请先核对进度：%s\n' "$p08Path" >&2
        exit 73
    fi
done
for p08Path in "$p08Base" "$p08Base/deps" "$p08Base/results" \
    "$p08Base/results/pretest-libpng-1.6.50" "$p08Base/results/pretest-libpng-1.6.50/preparation"; do
    if [[ -L "$p08Path" || ( -e "$p08Path" && ! -d "$p08Path" ) ]]; then
        printf '准备父目录状态不符：%s\n' "$p08Path" >&2
        exit 65
    fi
done
cd -- "$p08Base"
mkdir -p -- "$(dirname -- "$p08Record")"
mkdir -- "$p08Record"
printf 'purpose=dependency preparation\nproject=P08\nrecord_id=DEP-P08-001\nenvironment_session=%s\nprefix=%s\ncomponent=Development\nstarted_utc=%s\n' \
    "$p08Session" "$p08Prefix" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$p08Record/preparation-meta.txt"
{ cat /proc/meminfo; cat /proc/loadavg; } > "$p08Record/environment-start.txt"
sha256sum "${BASH_SOURCE[0]}" "$p08Helper" \
    "$p08Docs/review_evidence/zlib_pretest_20261027/Build_Identity_Check.json" \
    "$p08Docs/review_evidence/zlib_pretest_20261027/Source_Identity_Check.json" \
    "$p08Docs/review_evidence/libpng_setup/Dependency_Preparation_Context_20261028/Read_Only_Context.json" \
    > "$p08Record/preparation-inputs.sha256"

p08Phase() {
    local p08Name="$1" p08Exit=0
    shift
    printf '%q ' "$@" > "$p08Record/$p08Name-command.txt"
    printf '\n' >> "$p08Record/$p08Name-command.txt"
    if "$@" > "$p08Record/$p08Name-stdout.txt" 2> "$p08Record/$p08Name-stderr.txt"; then
        p08Exit=0
    else
        p08Exit=$?
    fi
    printf '%s\n' "$p08Exit" > "$p08Record/$p08Name-exit-code.txt"
    cat "$p08Record/$p08Name-stdout.txt"
    cat "$p08Record/$p08Name-stderr.txt" >&2
    return "$p08Exit"
}

p08Phase preflight python3 "$p08Helper" preflight "$p08Record/preflight-check.json"
p08Install=(cmake --install "$p08Build" --prefix "$p08Prefix" --component Development --config Debug)
printf '%q ' "${p08Install[@]}" > "$p08Record/install-command.txt"
printf '\n' >> "$p08Record/install-command.txt"
printf '开始准备P08的固定zlib依赖；复用已有静态库，记录：%s\n' "$p08Record"
if LC_ALL=C /usr/bin/time -v -o "$p08Record/install-time.txt" -- "${p08Install[@]}" \
    > "$p08Record/install-stdout.txt" 2> "$p08Record/install-stderr.txt"; then
    p08InstallExit=0
else
    p08InstallExit=$?
fi
printf '%s\n' "$p08InstallExit" > "$p08Record/install-exit-code.txt"
cat "$p08Record/install-stdout.txt"
cat "$p08Record/install-stderr.txt" >&2
printf '依赖安装退出码：%s\n' "$p08InstallExit"
if [[ "$p08InstallExit" -ne 0 ]]; then
    printf '已有部分前缀及原始日志保留，请返回输出，不重复运行同编号。\n' >&2
    exit "$p08InstallExit"
fi
p08Phase verify python3 "$p08Helper" verify "$p08Record/dependency-check.json" "$p08Record/preflight-check.json"
python3 - "$p08Build/install_manifest_Development.txt" "$p08Record/install_manifest_Development.txt" <<'PY'
from pathlib import Path
import sys
with Path(sys.argv[2]).open('xb') as target:
    target.write(Path(sys.argv[1]).read_bytes())
PY
sha256sum "$p08Prefix/include/zlib.h" "$p08Prefix/include/zconf.h" \
    "$p08Prefix/lib/libz.a" "$p08Prefix/lib/pkgconfig/zlib.pc" \
    > "$p08Record/installed-artifacts.sha256"
printf 'ended_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$p08Record/preparation-meta.txt"
printf 'DEP-P08-001完成；请返回输出，由助手验收后继续libpng构建。此步未运行构建或漏洞检测。\n'
