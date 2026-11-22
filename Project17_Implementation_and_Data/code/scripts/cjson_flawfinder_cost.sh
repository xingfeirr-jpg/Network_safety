#!/usr/bin/env bash
# 用户执行P03完整Flawfinder成本补测；前后核对及摘要均在计时外。
set -euo pipefail
export LC_ALL=C PYTHONDONTWRITEBYTECODE=1
p03Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p03Docs="$(dirname -- "$p03Scripts")"
[[ $# -eq 0 ]] || { printf '本脚本不接收额外参数。\n' >&2; exit 64; }
[[ -x "$HOME/comp5355/.venv/bin/python" ]] || { printf '固定虚拟环境不存在。\n' >&2; exit 69; }
cd -- "$p03Docs"
sha256sum -c -- review_evidence/cJSON_cost_supplement_20261030/flawfinder-control.sha256
source "$HOME/comp5355/.venv/bin/activate"
exec "$HOME/comp5355/.venv/bin/python" -B \
    "$p03Docs/review_evidence/cJSON_cost_supplement_20261030/Run_Flawfinder.py" --docs "$p03Docs"
