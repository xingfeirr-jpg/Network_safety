#!/usr/bin/env bash
# 用户执行P09 Flawfinder功能预试；身份核对和输出展示均在分析计时外。
set -euo pipefail
cd "$HOME/comp5355"
source .venv/bin/activate
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P09-FF-001
run="$HOME/comp5355/results/pretest-libjpeg-turbo-3.1.1/$run_id"
ff="$HOME/comp5355/.venv/bin/flawfinder"
setup="$docs/review_evidence/libjpeg_turbo_setup"
profile="$setup/Flawfinder_Profile.json"
guard="$setup/Verify_Flawfinder_Inputs.py"
input_list="$docs/review_evidence/libjpeg_turbo_pretest_20261029/analysis_inputs/text-inputs.txt"
manifest="$docs/review_evidence/libjpeg_turbo_pretest_20261029/analysis_inputs/project-inputs.sha256"
expected_profile_sha=34e7c777262096f81218b5097e4c47a07870a027bf7100dfaaf040e962d874c6
expected_guard_sha=8ff8eb7f792e5adb1d806eff5ce78eefad53c1510e4dd180126b88c2a75ada3b

if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，请保留原件并先核对进度：%s\n' "$run" >&2
    exit 73
fi
[[ -x "$ff" ]] || { printf '未找到实验虚拟环境中的Flawfinder。\n' >&2; exit 69; }
version=$("$ff" --version)
[[ "$version" == '2.0.20' ]] || { printf 'Flawfinder版本不符：%s\n' "$version" >&2; exit 65; }
printf '%s  %s\n%s  %s\n' "$expected_profile_sha" "$profile" "$expected_guard_sha" "$guard" | sha256sum -c -
input_guard_json=$(python -B "$guard" --docs "$docs" --json)
mapfile -t inputs < "$input_list"
[[ ${#inputs[@]} -eq 88 ]] || { printf '文本输入数不是预定88项。\n' >&2; exit 65; }
printf '开始Flawfinder：88个项目文本输入（64C＋21项目头＋3生成头）；数据库与84个系统/编译器头不作文本扫描。\n'
if bash "$docs/scripts/measure_run.sh" "$run_id" "$run" -- \
    "$ff" --minlevel=1 --neverignore --columns --context "${inputs[@]}"; then
    analysis_status=0
else
    analysis_status=$?
fi
[[ -f "$run/exit-code.txt" ]] || exit "$analysis_status"
printf '%s\n' "$input_guard_json" > "$run/input-identity-check.json"
printf '%q ' python -B "$guard" --docs "$docs" --json > "$run/input-identity-command.txt"
printf '\n' >> "$run/input-identity-command.txt"
printf '0\n' > "$run/input-identity-exit-code.txt"
cp -- "$manifest" "$run/input-files.sha256"
printf '%s\n' "${inputs[@]}" > "$run/input-files.txt"
cp -- "$profile" "$run/prepared-profile.json"
sha256sum "${BASH_SOURCE[0]}" "$profile" "$guard" "$input_list" "$manifest" \
    "$setup/CodeChecker_Profile.json" "$setup/Verify_CodeChecker_Inputs.py" > "$run/executed-inputs.sha256"
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
printf '文本成功范围、候选和计时仍待按原件核对；本次是功能预试。\n运行记录：%s\n' "$run"
exit "$analysis_status"
