#!/usr/bin/env bash
# User-run P06 Flawfinder pretest. Identity checks/display are outside timing.
set -euo pipefail
cd "$HOME/comp5355"
source .venv/bin/activate
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P06-FF-001
run="$HOME/comp5355/results/pretest-yyjson-0.12.0/$run_id"
ff="$HOME/comp5355/.venv/bin/flawfinder"
manifest="$docs/review_evidence/yyjson_setup/flawfinder-inputs.sha256"
if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，请保留原件并先核对进度：%s\n' "$run" >&2
    exit 73
fi
[[ -x "$ff" ]] || { printf '未找到实验虚拟环境中的Flawfinder。\n' >&2; exit 69; }
version=$("$ff" --version)
[[ "$version" == '2.0.20' ]] || { printf 'Flawfinder版本不符：%s\n' "$version" >&2; exit 65; }
sha256sum -c "$manifest"
inputs=()
while read -r digest file; do
    [[ -n "$digest" && -n "$file" ]] || { printf '输入身份清单存在空项。\n' >&2; exit 65; }
    inputs+=("$file")
done < "$manifest"
[[ ${#inputs[@]} -eq 2 ]] || { printf '文本输入数不是预定2项。\n' >&2; exit 65; }
printf '开始Flawfinder：2个文本输入（1C＋1源码头，无生成C头）；完整输出保存后显示摘要。\n'
if bash "$docs/scripts/measure_run.sh" "$run_id" "$run" -- \
    "$ff" --minlevel=1 --neverignore --columns --context "${inputs[@]}"; then
    analysis_status=0
else
    analysis_status=$?
fi
[[ -f "$run/exit-code.txt" ]] || exit "$analysis_status"
cp -- "$manifest" "$run/input-files.sha256"
printf '%s\n' "${inputs[@]}" > "$run/input-files.txt"
cp -- "$docs/review_evidence/yyjson_setup/Flawfinder_Profile.json" "$run/prepared-profile.json"
printf '\nFlawfinder退出码：'; cat "$run/exit-code.txt"
printf '\n外部计时摘要：\n'
sed -n -e '/User time/p' -e '/System time/p' -e '/Elapsed/p' -e '/Maximum resident/p' "$run/time.txt"
printf '\n检测输出末尾：\n'
tail -n 36 "$run/stdout.txt"
if [[ -s "$run/stderr.txt" ]]; then
    printf '\n工具stderr：\n'
    cat "$run/stderr.txt" >&2
fi
printf '\n显示命中按minlevel=1统计；等级0及累计0+另列，候选数量不是确认漏洞数。\n'
printf '运行记录：%s\n' "$run"
exit "$analysis_status"
