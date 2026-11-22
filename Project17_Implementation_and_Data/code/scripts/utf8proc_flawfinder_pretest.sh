#!/usr/bin/env bash
# 用户执行P10功能预试；控制、版本、输入身份与展示均在分析计时外。
set -euo pipefail
set -C
export PYTHONDONTWRITEBYTECODE=1
p10Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p10Docs="$(dirname -- "$p10Scripts")"
p10Setup="$p10Docs/review_evidence/utf8proc_setup"
p10Base="$HOME/comp5355"
p10Source="$p10Base/sources/utf8proc-2.10.0"
p10RunId=PRE-P10-FF-001
p10Run="$p10Base/results/pretest-utf8proc-2.10.0/$p10RunId"
p10FF="$p10Base/.venv/bin/flawfinder"
p10Manifest="$p10Setup/flawfinder-inputs.sha256"
p10Control="$p10Setup/flawfinder-control.sha256"
p10Profile="$p10Setup/Flawfinder_Profile.json"
p10Session='not supplied; see environment-start.txt for this actual run'
if [[ $# -gt 1 ]]; then
    printf '用法：bash utf8proc_flawfinder_pretest.sh [当前环境快照目录]\n' >&2
    exit 64
fi
if [[ $# -eq 1 ]]; then
    [[ -s "$1/system.txt" && -s "$1/tool-versions.txt" ]] || {
        printf '传入的当前环境快照缺少system.txt或tool-versions.txt。\n' >&2; exit 65;
    }
    p10Session="$(cd -- "$1" && pwd -P)"
fi
if [[ -e "$p10Run" || -L "$p10Run" ]]; then
    printf '运行目录已存在，请保留原件并先核对进度：%s\n' "$p10Run" >&2
    exit 73
fi
p10Parent="$(dirname -- "$p10Run")"
while [[ "$p10Parent" != / ]]; do
    if [[ -L "$p10Parent" || ( -e "$p10Parent" && ! -d "$p10Parent" ) ]]; then
        printf '结果父目录状态不符：%s\n' "$p10Parent" >&2; exit 73
    fi
    p10Parent="$(dirname -- "$p10Parent")"
done
[[ -x "$p10FF" && -s "$p10Base/.venv/bin/activate" ]] || {
    printf '未找到实验虚拟环境中的Flawfinder。\n' >&2; exit 69;
}
cd -- "$p10Base"
source "$p10Base/.venv/bin/activate"

# 控制清单只允许本次六项；相对路径在已解析的课程目录内核对。
p10ExpectedControls=(
    review_evidence/utf8proc_setup/Flawfinder_Profile.json
    review_evidence/utf8proc_setup/flawfinder-inputs.sha256
    scripts/utf8proc_flawfinder_pretest.sh
    scripts/measure_run.sh
    review_evidence/utf8proc_pretest_20261029/Build_Identity_Check.json
    review_evidence/utf8proc_pretest_20261029/Project_Dependency_Manifest.json
)
p10Controls=()
while read -r p10Digest p10File; do
    [[ "$p10Digest" =~ ^[0-9a-f]{64}$ && -n "$p10File" ]] || {
        printf '控制身份清单格式不符。\n' >&2; exit 65;
    }
    p10Controls+=("$p10File")
done < "$p10Control"
[[ ${#p10Controls[@]} -eq 6 ]] || { printf '控制清单不是预定6项。\n' >&2; exit 65; }
for p10Index in "${!p10ExpectedControls[@]}"; do
    [[ "${p10Controls[$p10Index]}" == "${p10ExpectedControls[$p10Index]}" ]] || {
        printf '控制清单路径或顺序不符。\n' >&2; exit 65;
    }
done
if p10ControlOutput="$(cd -- "$p10Docs" && sha256sum -c -- "$p10Control")"; then
    printf '%s\n' "$p10ControlOutput"
else
    p10ControlExit=$?
    printf '%s\n' "$p10ControlOutput"
    exit "$p10ControlExit"
fi

p10Inputs=()
while read -r p10Digest p10File; do
    [[ "$p10Digest" =~ ^[0-9a-f]{64}$ && -n "$p10File" ]] || {
        printf '输入身份清单格式不符。\n' >&2; exit 65;
    }
    p10Inputs+=("$p10File")
done < "$p10Manifest"
p10ExpectedInputs=("$p10Source/utf8proc.c" "$p10Source/utf8proc.h" "$p10Source/utf8proc_data.c")
[[ ${#p10Inputs[@]} -eq 3 ]] || { printf '文本输入数不是预定3项。\n' >&2; exit 65; }
for p10Index in "${!p10ExpectedInputs[@]}"; do
    [[ "${p10Inputs[$p10Index]}" == "${p10ExpectedInputs[$p10Index]}" &&
       -f "${p10Inputs[$p10Index]}" && -s "${p10Inputs[$p10Index]}" &&
       ! -L "${p10Inputs[$p10Index]}" ]] || {
        printf '输入路径、顺序、类型或非空条件不符：%s\n' "${p10Inputs[$p10Index]}" >&2; exit 65;
    }
done
if p10InputOutput="$(sha256sum -c -- "$p10Manifest")"; then
    printf '%s\n' "$p10InputOutput"
else
    p10InputExit=$?
    printf '%s\n' "$p10InputOutput"
    exit "$p10InputExit"
fi
if p10Version="$("$p10FF" --version)"; then
    :
else
    p10VersionExit=$?
    printf 'Flawfinder版本查询失败，退出码%s。\n' "$p10VersionExit" >&2
    exit "$p10VersionExit"
fi
[[ "$p10Version" == '2.0.20' ]] || {
    printf 'Flawfinder版本不符：%s\n' "$p10Version" >&2; exit 65;
}

printf '开始Flawfinder：3文本＝1主C＋1项目头＋1包含型数据表；对应1条语义动作。\n'
if bash "$p10Scripts/measure_run.sh" "$p10RunId" "$p10Run" -- \
    "$p10FF" --minlevel=1 --neverignore --columns --context "${p10Inputs[@]}"; then
    p10AnalysisStatus=0
else
    p10AnalysisStatus=$?
fi
# 若后续复制或展示失败，已经发生的非零分析状态仍作为最终退出码。
trap 'p10WrapperExit=$?; if [[ "$p10AnalysisStatus" -ne 0 ]]; then exit "$p10AnalysisStatus"; fi; exit "$p10WrapperExit"' EXIT
if [[ ! -f "$p10Run/exit-code.txt" ]]; then
    printf '记录器未保存分析退出码；保留现有材料，不能认定已完成分析。\n' >&2
    if [[ "$p10AnalysisStatus" -ne 0 ]]; then exit "$p10AnalysisStatus"; else exit 74; fi
fi
cp -- "$p10Manifest" "$p10Run/input-files.sha256"
printf '%s\n' "${p10Inputs[@]}" > "$p10Run/input-files.txt"
cp -- "$p10Profile" "$p10Run/prepared-profile.json"
cp -- "$p10Control" "$p10Run/control-files.sha256"
printf '%s\n' "$p10ControlOutput" > "$p10Run/control-identity-stdout.txt"
printf '0\n' > "$p10Run/control-identity-exit-code.txt"
printf '%s\n' "$p10InputOutput" > "$p10Run/input-identity-stdout.txt"
printf '0\n' > "$p10Run/input-identity-exit-code.txt"
printf '%s\n' "$p10Version" > "$p10Run/flawfinder-version.txt"
printf '%q ' "$p10FF" --version > "$p10Run/version-command.txt"
printf '\n' >> "$p10Run/version-command.txt"
printf '0\n' > "$p10Run/version-exit-code.txt"
sha256sum "$p10Control" > "$p10Run/control-manifest.sha256"
{
    printf 'build_environment_session\t/home/yhong/comp5355/environment/session-20261029T085446-p10-22994\n'
    printf 'execution_environment_session\t%s\n' "$p10Session"
    printf 'actual_run_snapshot\tenvironment-start.txt\ncoverage_validation\tpending_tool_output_review\n'
} > "$p10Run/execution-environment.tsv"
if [[ $# -eq 1 ]]; then
    cp -- "$p10Session/system.txt" "$p10Run/current-session-system.txt"
    cp -- "$p10Session/tool-versions.txt" "$p10Run/current-session-tool-versions.txt"
    sha256sum "$p10Session/system.txt" "$p10Session/tool-versions.txt" > "$p10Run/current-session-inputs.sha256"
fi
printf '\nFlawfinder退出码：'; cat "$p10Run/exit-code.txt"
printf '\n外部计时摘要：\n'
sed -n -e '/User time/p' -e '/System time/p' -e '/Elapsed/p' -e '/Maximum resident/p' "$p10Run/time.txt"
printf '\n检测输出末尾：\n'
tail -n 36 "$p10Run/stdout.txt"
if [[ -s "$p10Run/stderr.txt" ]]; then
    printf '\n工具stderr：\n'; cat "$p10Run/stderr.txt" >&2
fi
printf '\n显示命中按minlevel=1统计；等级0及累计0+另列，候选数量不是确认漏洞数。\n'
printf '实际成功范围、失败／跳过、候选与成本仍待按原件验收；本次为功能预试。\n运行记录：%s\n' "$p10Run"
exit "$p10AnalysisStatus"
