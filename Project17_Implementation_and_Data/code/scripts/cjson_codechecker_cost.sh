#!/usr/bin/env bash
# 用户执行P03完整clangsa成本补测；助手只准备、核对与整理材料。
set -euo pipefail
export LC_ALL=C PYTHONDONTWRITEBYTECODE=1
p03Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p03Docs="$(dirname -- "$p03Scripts")"
[[ $# -eq 0 ]] || { printf '本脚本不接收额外参数。\n' >&2; exit 64; }
[[ -x "$HOME/comp5355/.venv/bin/python" ]] || { printf '固定虚拟环境不存在。\n' >&2; exit 69; }
cd -- "$p03Docs"
sha256sum -c -- review_evidence/cJSON_cost_supplement_20261030/codechecker-control.sha256
source "$HOME/comp5355/.venv/bin/activate"
export CC_ANALYZER_BIN='clangsa:/usr/bin/clang-18'
if [[ -n ${CC_TEST_LABELS_DIR-} ]]; then
    printf '发现自定义检查器labels目录，请返回输出核对。\n' >&2
    exit 65
fi
unset CC_TEST_LABELS_DIR
exec "$HOME/comp5355/.venv/bin/python" -B \
    "$p03Docs/review_evidence/cJSON_cost_supplement_20261030/Run_CodeChecker.py" --docs "$p03Docs"
