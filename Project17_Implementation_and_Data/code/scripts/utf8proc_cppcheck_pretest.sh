#!/usr/bin/env bash
# 用户执行P10独立Cppcheck功能预试；身份、版本、环境与XML摘要均在分析计时外。
set -euo pipefail
set -C
export PYTHONDONTWRITEBYTECODE=1
p10Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p10Docs="$(dirname -- "$p10Scripts")"
p10Setup="$p10Docs/review_evidence/utf8proc_setup"
p10Base="$HOME/comp5355"
p10Source="$p10Base/sources/utf8proc-2.10.0"
p10Database="$p10Base/build/utf8proc-2.10.0/compile_commands.json"
p10RunId=PRE-P10-CP-001
p10Run="$p10Base/results/pretest-utf8proc-2.10.0/$p10RunId"
p10CP=/usr/bin/cppcheck
p10Manifest="$p10Setup/cppcheck-inputs.sha256"
p10Control="$p10Setup/cppcheck-control.sha256"
p10Profile="$p10Setup/Cppcheck_Profile.json"
p10Session='not supplied; see environment-start.txt for this actual run'
if [[ $# -gt 1 ]]; then
    printf '用法：bash utf8proc_cppcheck_pretest.sh [当前环境快照目录]\n' >&2
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
[[ -x "$p10CP" ]] || { printf '未找到独立Cppcheck。\n' >&2; exit 69; }
command -v python3 >/dev/null || { printf '未找到XML摘要所需的python3。\n' >&2; exit 69; }
cd -- "$p10Base"

p10ExpectedControls=(
    review_evidence/utf8proc_setup/Cppcheck_Profile.json
    review_evidence/utf8proc_setup/cppcheck-inputs.sha256
    scripts/utf8proc_cppcheck_pretest.sh
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

# 四项只用于身份核对；Cppcheck仅导入原始DB，不把头或包含型数据表另造动作。
p10Inputs=()
while read -r p10Digest p10File; do
    [[ "$p10Digest" =~ ^[0-9a-f]{64}$ && -n "$p10File" ]] || {
        printf '输入身份清单格式不符。\n' >&2; exit 65;
    }
    p10Inputs+=("$p10File")
done < "$p10Manifest"
p10ExpectedInputs=("$p10Database" "$p10Source/utf8proc.c" "$p10Source/utf8proc.h" "$p10Source/utf8proc_data.c")
[[ ${#p10Inputs[@]} -eq 4 ]] || { printf '身份输入数不是预定DB＋3文件共4项。\n' >&2; exit 65; }
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
if p10Version="$("$p10CP" --version)"; then
    :
else
    p10VersionExit=$?
    printf 'Cppcheck版本查询失败，退出码%s。\n' "$p10VersionExit" >&2
    exit "$p10VersionExit"
fi
[[ "$p10Version" == 'Cppcheck 2.13.0' ]] || {
    printf 'Cppcheck版本不符：%s\n' "$p10Version" >&2; exit 65;
}

printf '开始Cppcheck：不改原DB的1条utf8proc.c动作，C99／unix64／normal／-j1；不额外注入宏或include路径。\n'
if bash "$p10Scripts/measure_run.sh" "$p10RunId" "$p10Run" -- \
    "$p10CP" \
    --project="$p10Database" \
    --enable=warning,performance,portability,information \
    --check-level=normal \
    --platform=unix64 \
    --std=c99 \
    -j 1 \
    --cppcheck-build-dir="$p10Run/cache" \
    --checkers-report="$p10Run/checkers.txt" \
    --xml --xml-version=2; then
    p10AnalysisStatus=0
else
    p10AnalysisStatus=$?
fi
trap 'p10WrapperExit=$?; if [[ "$p10AnalysisStatus" -ne 0 ]]; then exit "$p10AnalysisStatus"; fi; exit "$p10WrapperExit"' EXIT
if [[ ! -f "$p10Run/exit-code.txt" ]]; then
    printf '记录器未保存分析退出码；保留现有材料，不能认定已完成分析。\n' >&2
    if [[ "$p10AnalysisStatus" -ne 0 ]]; then exit "$p10AnalysisStatus"; else exit 74; fi
fi
cp -- "$p10Manifest" "$p10Run/input-files.sha256"
printf '%s\n' "${p10Inputs[@]}" > "$p10Run/input-files.txt"
cp -- "$p10Profile" "$p10Run/prepared-profile.json"
cp -- "$p10Control" "$p10Run/control-files.sha256"
cp -- "$p10Database" "$p10Run/compile_commands.input.json"
printf '%s\n' "$p10ControlOutput" > "$p10Run/control-identity-stdout.txt"
printf '0\n' > "$p10Run/control-identity-exit-code.txt"
printf '%s\n' "$p10InputOutput" > "$p10Run/input-identity-stdout.txt"
printf '0\n' > "$p10Run/input-identity-exit-code.txt"
printf '%s\n' "$p10Version" > "$p10Run/cppcheck-version.txt"
printf '%q ' "$p10CP" --version > "$p10Run/version-command.txt"
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
printf '\nCppcheck退出码：'; cat "$p10Run/exit-code.txt"
printf '\n进度输出末尾：\n'; tail -n 16 "$p10Run/stdout.txt"
printf '\n外部计时摘要：\n'
sed -n -e '/User time/p' -e '/System time/p' -e '/Elapsed/p' -e '/Maximum resident/p' "$p10Run/time.txt"

python3 -B - "$p10Run" <<'PY'
import collections
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

run = Path(sys.argv[1])
summary = {
    "purpose": "functional pretest",
    "runId": "PRE-P10-CP-001",
    "intendedActions": 1,
    "identityEntries": 4,
    "xmlValid": False,
    "xmlDiagnosticElements": None,
    "informationElements": None,
    "nonInformationElements": None,
    "candidateCount": None,
    "actualSucceededActions": None,
    "actualFailedActions": None,
    "actualSkippedActions": None,
    "coverageValidation": "pending_tool_output_review",
    "sourceReview": "not performed",
    "summaryTiming": "outside analysis measurement"
}
try:
    root = ET.parse(run / "stderr.txt").getroot()
    if root.tag != "results" or root.get("version") != "2":
        raise ValueError("not Cppcheck XML 2")
    error_sections = root.findall("errors")
    if len(error_sections) != 1:
        raise ValueError("Cppcheck XML 2 requires exactly one errors container")
    entries = error_sections[0].findall("error")
    counts = dict(sorted(collections.Counter(e.get("severity", "unknown") for e in entries).items()))
    rules = dict(sorted(collections.Counter(e.get("id", "unknown") for e in entries).items()))
    information = sum(e.get("severity") == "information" for e in entries)
    summary.update(
        xmlValid=True, xmlDiagnosticElements=len(entries),
        informationElements=information, nonInformationElements=len(entries) - information,
        classification="pending assistant review; non-information may include configuration failures",
        bySeverity=counts, byRule=rules)
    print("\nXML 2可解析；原始诊断元素数：", len(entries))
    print("information／非information元素：", information, "/", len(entries) - information)
    print("按severity统计：", json.dumps(counts, ensure_ascii=False))
    print("按规则统计：", json.dumps(rules, ensure_ascii=False))
except (ET.ParseError, OSError, ValueError) as error:
    summary["summaryError"] = str(error)
    print("\nXML摘要未完整生成，不能将失败视为零诊断：", error)
with (run / "xml-summary.json").open("x", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print("1动作实际成功／失败／跳过、缺头、normal限制及源码候选仍待助手核对；XML元素数不是漏洞数。")
PY
printf '\n本次为功能预试；完整记录：%s\n' "$p10Run"
exit "$p10AnalysisStatus"
