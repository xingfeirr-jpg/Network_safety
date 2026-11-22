#!/usr/bin/env bash
# User-run P02 Flawfinder pretest; identity checks and display stay outside timing.
set -euo pipefail
cd "$HOME/comp5355"
source .venv/bin/activate
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P02-FF-001
run="$HOME/comp5355/results/pretest-lz4-v1.10.0/$run_id"
ff="$HOME/comp5355/.venv/bin/flawfinder"
manifest="$docs/review_evidence/lz4_setup/flawfinder-inputs.sha256"
input_list="$docs/review_evidence/lz4_setup/flawfinder-inputs.txt"
if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，请保留原件并先核对进度：%s\n' "$run" >&2
    exit 73
fi
[[ "$("$ff" --version)" == '2.0.20' ]]
sha256sum -c "$manifest"
mapfile -t inputs < "$input_list"
[[ ${#inputs[@]} -eq 11 ]]
printf '开始Flawfinder：11个文本输入（5C＋6头）；完整输出保存后显示摘要。\n'
if bash "$docs/scripts/measure_run.sh" "$run_id" "$run" -- \
    "$ff" --minlevel=1 --neverignore --columns --context "${inputs[@]}"; then
    analysis_status=0
else
    analysis_status=$?
fi
[[ -f "$run/exit-code.txt" ]] || exit "$analysis_status"
cp -- "$manifest" "$run/input-files.sha256"
cp -- "$input_list" "$run/input-files.txt"
cp -- "$docs/review_evidence/lz4_setup/Flawfinder_Profile.json" "$run/prepared-profile.json"
printf '\nFlawfinder退出码：'; cat "$run/exit-code.txt"
printf '\n外部计时摘要：\n'
grep -E 'User time|System time|Elapsed|Maximum resident' "$run/time.txt" || true
printf '\n检测输出末尾：\n'
tail -n 36 "$run/stdout.txt"
if [[ -s "$run/stderr.txt" ]]; then
    printf '\n工具stderr：\n'
    cat "$run/stderr.txt" >&2
fi
printf '\n显示命中按minlevel=1统计；等级0及累计0+另列，候选数量不是确认漏洞数。\n'
printf '运行记录：%s\n' "$run"
exit "$analysis_status"
