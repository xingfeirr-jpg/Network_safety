#!/usr/bin/env bash
# 用户执行：只读核对既有对象，保存新记录；不构建、不运行检测分析。
set -euo pipefail
export LC_ALL=C PYTHONDONTWRITEBYTECODE=1
p03Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p03Docs="$(dirname -- "$p03Scripts")"
p03Evidence="$p03Docs/review_evidence/cJSON_cost_supplement_20261030"
p03Base="$HOME/comp5355"
p03Run="$p03Base/results/formal-cJSON-v1.7.19/preparation/CHECK-P03-COST-001"
p03Receipt="$p03Evidence/preflight/CHECK-P03-COST-001"
p03Python="$p03Base/.venv/bin/python"
[[ $# -eq 0 ]] || { printf '用法：bash cjson_cost_preflight.sh\n' >&2; exit 64; }
[[ -x "$p03Python" && -x /usr/bin/time ]] || {
    printf '未找到原Python虚拟环境或GNU time，请返回输出。\n' >&2; exit 69;
}
if [[ -e "$p03Run" || -L "$p03Run" || -e "$p03Receipt" || -L "$p03Receipt" ]]; then
    printf 'CHECK-P03-COST-001记录已存在，保留原件；请返回输出核对进度。\n' >&2
    exit 73
fi
cd -- "$p03Docs"
sha256sum -c "$p03Evidence/preflight-control.sha256"
mkdir -p -- "$(dirname -- "$p03Run")"
mkdir -- "$p03Run"
cd -- "$p03Base"
source "$p03Base/.venv/bin/activate"
export CC_ANALYZER_BIN="clangsa:/usr/bin/clang-18"
printf '开始cJSON成本补测前置检查；尚不运行检测。\n'
if bash "$p03Scripts/capture_environment.sh" "$p03Run/environment" \
    > "$p03Run/environment-capture.stdout.txt" 2> "$p03Run/environment-capture.stderr.txt"; then
    p03EnvironmentStatus=0
else
    p03EnvironmentStatus=$?
fi
printf '%s\n' "$p03EnvironmentStatus" > "$p03Run/environment-exit-code.txt"
if "$p03Python" "$p03Evidence/Verify_Preflight.py" --docs "$p03Docs" --output "$p03Run" \
    > "$p03Run/stdout.txt" 2> "$p03Run/stderr.txt"; then
    p03Status=0
else
    p03Status=$?
fi
if [[ $p03Status -eq 0 && $p03EnvironmentStatus -ne 0 ]]; then p03Status=$p03EnvironmentStatus; fi
printf '%s\n' "$p03Status" > "$p03Run/exit-code.txt"
# 用新目录复制本步记录到课程目录，供助手直接验收；拒绝覆盖。
"$p03Python" - "$p03Run" "$p03Receipt" <<'PY'
from pathlib import Path
import shutil
import sys
source, target = map(Path, sys.argv[1:])
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, target)
PY
cat "$p03Run/stdout.txt" "$p03Run/stderr.txt"
if [[ $p03EnvironmentStatus -ne 0 ]]; then
    cat "$p03Run/environment-capture.stdout.txt" "$p03Run/environment-capture.stderr.txt"
fi
printf '\n环境快照退出码：%s；本步退出码：%s\n' "$p03EnvironmentStatus" "$p03Status"
printf 'Linux记录：%s\n课程目录副本：%s\n' "$p03Run" "$p03Receipt"
printf '请返回完整输出或截图；助手验收后再开始CodeChecker计时分析。\n'
exit "$p03Status"
