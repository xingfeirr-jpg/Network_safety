#!/usr/bin/env bash
# One-step replication: build the image -> run S1-S5 in the container -> compare (S6) and analyze on the host.
#
#   bash run_replication.sh            run all ten libraries
#   bash run_replication.sh P01        run zlib only (trial run, about 2 minutes)
#   bash run_replication.sh P01,P08    run several libraries
#
# Requires Docker (start Docker Desktop first on Windows) and Python 3.10 or later.
set -euo pipefail
cd "$(dirname "$0")"

image=project17-replication:1.0
only=${1:-}
mkdir -p output/results output/downloads

# Git Bash on Windows rewrites arguments that start with /, which breaks container paths
export MSYS_NO_PATHCONV=1
host_path() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
results=$(host_path "$PWD/output/results")
downloads=$(host_path "$PWD/output/downloads")

printf '\n== Building the replication image (5-10 minutes the first time)\n'
# On a slow network, use mirrors, for example:
#   UBUNTU_MIRROR=http://mirrors.ustc.edu.cn/ubuntu PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple bash run_replication.sh
docker build -t "$image" \
    --build-arg UBUNTU_MIRROR="${UBUNTU_MIRROR:-}" \
    --build-arg PIP_INDEX_URL="${PIP_INDEX_URL:-}" .

printf '\n== Running S1-S5 in the container\n'
status=0
docker run --rm \
    -v "$results:/home/yhong/comp5355/results" \
    -v "$downloads:/home/yhong/comp5355/downloads" \
    "$image" ${only:+--only "$only"} || status=$?

printf '\n== Running the S6 comparison on the host\n'
# On Windows, python3 may be only the Microsoft Store stub, so pick one that actually runs
python_bin=""
for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null && "$candidate" -c "import sys; sys.exit(sys.version_info < (3, 10))" 2>/dev/null; then
        python_bin=$candidate; break
    fi
done
if [[ -z "$python_bin" ]]; then
    printf 'Python 3.10 or later not found; install it and run: python replication/compare.py\n' >&2
    exit 1
fi
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 "$python_bin" replication/compare.py || status=$?

printf '\n== Analysis (requires matplotlib)\n'
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 "$python_bin" analysis/analyze.py \
    || printf 'Analysis did not finish; install matplotlib and run analysis/analyze.py\n'

printf '\nComparison table: %s\nFigures: %s\n' "$PWD/output/comparison.csv" "$PWD/output/analysis/figures"
exit "$status"
