#!/usr/bin/env bash
# 用户执行P10 clangsa功能预试；版本、身份、checkers和两次parse均在分析计时外。
set -euo pipefail
set -C
export LC_ALL=C PYTHONDONTWRITEBYTECODE=1
p10Scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
p10Docs="$(dirname -- "$p10Scripts")"
p10Setup="$p10Docs/review_evidence/utf8proc_setup"
p10Base="$HOME/comp5355"
p10Source="$p10Base/sources/utf8proc-2.10.0"
p10Database="$p10Base/build/utf8proc-2.10.0/compile_commands.json"
p10RunId=PRE-P10-CC-001
p10Run="$p10Base/results/pretest-utf8proc-2.10.0/$p10RunId"
p10CC="$p10Base/.venv/bin/CodeChecker"
p10Python="$p10Base/.venv/bin/python"
p10Clang=/usr/bin/clang-18
p10Manifest="$p10Setup/codechecker-inputs.sha256"
p10Control="$p10Setup/codechecker-control.sha256"
p10Profile="$p10Setup/CodeChecker_Profile.json"
p10Session='not supplied; see environment-start.txt for this actual run'
if [[ $# -gt 1 ]]; then
    printf '用法：bash utf8proc_codechecker_pretest.sh [当前环境快照目录]\n' >&2
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
[[ -x "$p10CC" && -x "$p10Python" && -x "$p10Clang" ]] || {
    printf '未找到固定CodeChecker虚拟环境或clang-18。\n' >&2; exit 69;
}
cd -- "$p10Base"
source "$p10Base/.venv/bin/activate"
export CC_ANALYZER_BIN="clangsa:$p10Clang"
if [[ -n ${CC_TEST_LABELS_DIR-} ]]; then
    printf '发现自定义CC_TEST_LABELS_DIR，与本次默认检查器政策不同，停止并返回输出。\n' >&2
    exit 69
fi
# CodeChecker按变量是否存在读取labels目录；移除已导出的空值以保持默认。
unset CC_TEST_LABELS_DIR

p10ExpectedControls=(
    review_evidence/utf8proc_setup/CodeChecker_Profile.json
    review_evidence/utf8proc_setup/codechecker-inputs.sha256
    scripts/utf8proc_codechecker_pretest.sh
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

# 四项用于身份核对；analyze仅接收原DB，依赖不另造编译动作。
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
p10Version="$("$p10Python" -B -c 'import importlib.metadata; print(importlib.metadata.version("codechecker"))')"
[[ "$p10Version" == '6.29.1' ]] || {
    printf 'CodeChecker版本不符：%s\n' "$p10Version" >&2; exit 65;
}
p10ClangVersion="$("$p10Clang" --version)"
[[ "$p10ClangVersion" =~ version[[:space:]]18\.1\.3([[:space:]]|$) ]] || {
    printf 'Clang版本不符：%s\n' "$p10ClangVersion" >&2; exit 65;
}

printf '阶段1：开始clangsa；原DB的1条C99动作、-j1、每动作120秒，完整输出写入新目录。\n'
if bash "$p10Scripts/measure_run.sh" "$p10RunId" "$p10Run" -- \
    "$p10CC" analyze "$p10Database" \
    --analyzers clangsa \
    -o "$p10Run/reports" \
    -j 1 \
    --timeout 120 \
    --compile-uniqueing none \
    --capture-analysis-output \
    --z3-refutation off; then
    p10AnalysisStatus=0
else
    p10AnalysisStatus=$?
fi
# 后续保存、展示或摘要失败不能覆盖已经发生的非零分析状态。
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
printf '%s\n' "$p10Version" > "$p10Run/codechecker-version.txt"
printf '%s\n' "$p10ClangVersion" > "$p10Run/clang-version.txt"
printf '%q ' "$p10Python" -B -c 'import importlib.metadata; print(importlib.metadata.version("codechecker"))' > "$p10Run/codechecker-version-command.txt"
printf '\n' >> "$p10Run/codechecker-version-command.txt"
printf '0\n' > "$p10Run/codechecker-version-exit-code.txt"
printf '%q ' "$p10Clang" --version > "$p10Run/clang-version-command.txt"
printf '\n' >> "$p10Run/clang-version-command.txt"
printf '0\n' > "$p10Run/clang-version-exit-code.txt"
sha256sum "$p10Control" > "$p10Run/control-manifest.sha256"
printf 'CC_ANALYZER_BIN=%s\nCC_TEST_LABELS_DIR=%s\nLC_ALL=%s\n' "$CC_ANALYZER_BIN" "${CC_TEST_LABELS_DIR-<unset>}" "$LC_ALL" > "$p10Run/configuration-environment.txt"
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

record_aux() {
    local prefix=$1 stdout_file=$2
    shift 2
    printf '%q ' "$@" > "$p10Run/$prefix-command.txt"
    printf '\n' >> "$p10Run/$prefix-command.txt"
    if LC_ALL=C "$@" > "$p10Run/$stdout_file" 2> "$p10Run/$prefix-stderr.txt"; then
        p10AuxStatus=0
    else
        p10AuxStatus=$?
    fi
    printf '%s\n' "$p10AuxStatus" > "$p10Run/$prefix-exit-code.txt"
}
record_aux checkers checkers.json "$p10CC" checkers --analyzers clangsa --details --output json
p10CheckersStatus=$p10AuxStatus
printf '阶段2：读取状态与详细成功／失败／跳过范围（分析计时之外）。\n'
record_aux parse-status parse-status.txt "$p10CC" parse --status --detailed "$p10Run/reports"
p10ParseStatus=$p10AuxStatus
printf '阶段3：普通parse展示诊断（分析计时之外）。\n'
record_aux findings findings.txt "$p10CC" parse "$p10Run/reports"
p10FindingsStatus=$p10AuxStatus

# 只派生已保存原件摘要；实际动作覆盖及展示数量仍由助手验收。
if "$p10Python" -B - "$p10Run" <<'PY'
import json
from pathlib import Path
import plistlib
import sys
from xml.parsers.expat import ExpatError

run = Path(sys.argv[1])
summary = {
    "purpose": "functional pretest", "runId": "PRE-P10-CC-001", "intendedActions": 1,
    "actualSucceededActions": None, "actualFailedActions": None, "actualSkippedActions": None,
    "coverageValidation": "pending_tool_output_review", "sourceReview": "not performed",
    "metadataTools": [], "rawPlistFileCount": None, "parsedPlistFileCount": None,
    "parsedSubsetDiagnostics": None, "savedPlistDiagnostics": None,
    "displayedDiagnosticCount": None, "candidateCount": None,
    "summaryTiming": "outside analysis measurement", "summaryValid": False
}
errors = []
try:
    data = json.loads((run / "reports/metadata.json").read_text(encoding="utf-8"))
    tools = [t for t in data.get("tools", []) if isinstance(t, dict) and t.get("name") == "codechecker"]
    if len(tools) != 1:
        raise ValueError("metadata does not contain exactly one codechecker tool record")
    for tool in tools:
        stats = tool.get("analyzers", {}).get("clangsa", {}).get("analyzer_statistics", {})
        values = [tool.get("action_num"), tool.get("skipped"), stats.get("successful"), stats.get("failed")]
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("metadata lacks nonnegative action/skipped/clangsa successful/failed counts")
        summary["metadataTools"].append({"actionNum": tool.get("action_num"),
                                        "clangsaStatistics": stats, "skipped": tool.get("skipped")})
        print("元数据clangsa成功／失败／跳过：", stats.get("successful"), stats.get("failed"), tool.get("skipped"))
except (OSError, ValueError, TypeError, AttributeError) as exc:
    errors.append("metadata: " + str(exc))
paths = sorted((run / "reports").rglob("*.plist"))
summary["rawPlistFileCount"] = len(paths)
plists, invalid = [], []
for path in paths:
    try:
        with path.open("rb") as handle:
            result = plistlib.load(handle)
        if not isinstance(result, dict) or not isinstance(result.get("diagnostics"), list):
            raise ValueError("not a plist dictionary with a diagnostics array")
        if not all(isinstance(d, dict) for d in result["diagnostics"]):
            raise ValueError("diagnostics array contains a non-dictionary entry")
        plists.append({"file": str(path.relative_to(run)), "savedDiagnostics": len(result["diagnostics"])})
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException, ExpatError, OverflowError) as exc:
        invalid.append({"file": str(path.relative_to(run)), "error": str(exc)})
summary["plistResults"] = plists
summary["parsedPlistFileCount"] = len(plists)
summary["invalidPlistFiles"] = invalid
summary["parsedSubsetDiagnostics"] = sum(p["savedDiagnostics"] for p in plists) if plists else None
if not paths:
    errors.append("no plist results; cannot infer successful zero diagnostics")
elif invalid:
    errors.append("invalid plist results; only parsedSubsetDiagnostics is available, total remains null")
else:
    summary["savedPlistDiagnostics"] = summary["parsedSubsetDiagnostics"]
summary["auxiliaryExitCodes"] = {}
for name in ("checkers", "parse-status", "findings"):
    try:
        summary["auxiliaryExitCodes"][name] = int((run / (name + "-exit-code.txt")).read_text().strip())
    except (OSError, ValueError) as exc:
        errors.append(name + " exit status: " + str(exc))
summary["summaryValidationErrors"] = errors
summary["summaryValid"] = not errors
with (run / "result-summary-pending.json").open("x", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print("原始plist／合法plist／保存诊断：", summary["rawPlistFileCount"], summary["parsedPlistFileCount"], summary["savedPlistDiagnostics"])
if errors:
    print("摘要有待核对问题，不能按零诊断验收：", errors)
print("实际覆盖、默认过滤与parse展示数量待验收；诊断数不是漏洞数。")
sys.exit(65 if errors else 0)
PY
then
    p10SummaryStatus=0
else
    p10SummaryStatus=$?
fi
printf '%s\n' "$p10SummaryStatus" > "$p10Run/summary-exit-code.txt"
printf '\n分析退出码：'; cat "$p10Run/exit-code.txt"
printf 'checkers／状态parse／普通parse／摘要退出码：%s／%s／%s／%s\n' "$p10CheckersStatus" "$p10ParseStatus" "$p10FindingsStatus" "$p10SummaryStatus"
printf '普通parse返回2表示有报告；未选后端Missing不直接等于clangsa失败。\n'
printf '\n分析日志末尾：\n'; tail -n 16 "$p10Run/stdout.txt"
if [[ -s "$p10Run/stderr.txt" ]]; then
    printf '\n分析stderr末尾：\n'; tail -n 8 "$p10Run/stderr.txt"
fi
printf '\n外部计时摘要：\n'
sed -n -e '/User time/p' -e '/System time/p' -e '/Elapsed/p' -e '/Maximum resident/p' "$p10Run/time.txt"
printf '\n普通parse展示末尾（完整内容在findings.txt）：\n'; tail -n 22 "$p10Run/findings.txt"
printf '\n功能预试记录：%s\n' "$p10Run"
[[ "$p10AnalysisStatus" -eq 0 ]] || exit "$p10AnalysisStatus"
[[ "$p10CheckersStatus" -eq 0 ]] || exit "$p10CheckersStatus"
[[ "$p10ParseStatus" -eq 0 ]] || exit "$p10ParseStatus"
if [[ "$p10FindingsStatus" -ne 0 && "$p10FindingsStatus" -ne 2 ]]; then
    exit "$p10FindingsStatus"
fi
exit "$p10SummaryStatus"
