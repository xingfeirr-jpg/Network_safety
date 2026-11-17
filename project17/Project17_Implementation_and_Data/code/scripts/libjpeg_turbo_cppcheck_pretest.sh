#!/usr/bin/env bash
# 用户执行P09独立Cppcheck功能预试；身份核对和XML摘要均在分析计时外。
set -euo pipefail
cd "$HOME/comp5355"
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P09-CP-001
run="$HOME/comp5355/results/pretest-libjpeg-turbo-3.1.1/$run_id"
setup="$docs/review_evidence/libjpeg_turbo_setup"
profile="$setup/Cppcheck_Profile.json"
guard="$setup/Verify_Cppcheck_Inputs.py"
database="$docs/review_evidence/libjpeg_turbo_pretest_20261029/analysis_inputs/compile_commands.json"
expected_profile_sha=461274fc6fa018c27ad3d8e190c4f4844ac69340f3713d7d3b82ff1a3afa189f
expected_guard_sha=23ad89f17a6b49573fe0ccd5cd7b0d43292df9676b164b33952860fcddae1cc4

if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，保留原件并先核对进度：%s\n' "$run" >&2
    exit 73
fi
version=$(/usr/bin/cppcheck --version)
[[ "$version" == 'Cppcheck 2.13.0' ]] || { printf 'Cppcheck版本不符：%s\n' "$version" >&2; exit 65; }
printf '%s  %s\n%s  %s\n' "$expected_profile_sha" "$profile" "$expected_guard_sha" "$guard" | sha256sum -c -
input_guard_json=$(python3 -B "$guard" --docs "$docs" --json)
printf '开始Cppcheck：原选101条主库动作（58／28／15）保持；C11分析模型，实际构建为GNU C17；不额外注入宏。\n'
if bash "$docs/scripts/measure_run.sh" "$run_id" "$run" -- \
    /usr/bin/cppcheck \
    --project="$database" \
    --enable=warning,performance,portability,information \
    --check-level=normal \
    --platform=unix64 \
    --std=c11 \
    -j 1 \
    --cppcheck-build-dir="$run/cache" \
    --checkers-report="$run/checkers.txt" \
    --xml --xml-version=2; then
    analysis_status=0
else
    analysis_status=$?
fi
[[ -f "$run/exit-code.txt" ]] || exit "$analysis_status"
printf '%s\n' "$input_guard_json" > "$run/input-identity-check.json"
printf '%q ' python3 -B "$guard" --docs "$docs" --json > "$run/input-identity-command.txt"
printf '\n' >> "$run/input-identity-command.txt"
printf '0\n' > "$run/input-identity-exit-code.txt"
cp -- "$profile" "$run/prepared-profile.json"
cp -- "$database" "$run/compile_commands.input.json"
sha256sum "${BASH_SOURCE[0]}" "$profile" "$guard" "$database" \
    "$setup/CodeChecker_Profile.json" "$setup/Verify_CodeChecker_Inputs.py" > "$run/executed-inputs.sha256"
printf '\nCppcheck退出码：'; cat "$run/exit-code.txt"
printf '\n进度输出末尾：\n'; tail -n 16 "$run/stdout.txt"
printf '\n外部计时摘要：\n'
sed -n -e '/User time/p' -e '/System time/p' -e '/Elapsed/p' -e '/Maximum resident/p' "$run/time.txt"
python3 - "$run" <<'PY'
import collections
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

run = pathlib.Path(sys.argv[1])
summary = {"purpose": "functional pretest", "runId": "PRE-P09-CP-001", "intendedActions": 101,
           "candidateCount": None, "coverageValidation": "pending_tool_output_review",
           "sourceReview": "not performed", "summaryTiming": "outside analysis measurement"}
try:
    root = ET.parse(run / "stderr.txt").getroot()
    if root.tag != "results" or root.get("version") != "2":
        raise ValueError("not Cppcheck XML 2")
    entries = root.findall("errors/error")
    counts = dict(sorted(collections.Counter(e.get("severity", "unknown") for e in entries).items()))
    rules = dict(sorted(collections.Counter(e.get("id", "unknown") for e in entries).items()))
    summary.update(xmlValid=True, xmlDiagnosticElements=len(entries),
        informationElements=sum(e.get("severity") == "information" for e in entries),
        nonInformationElements=sum(e.get("severity") != "information" for e in entries),
        classification="pending assistant review;non-information may include configuration failures",
        bySeverity=counts, byRule=rules)
    print("\nXML 2可解析；原始诊断元素数：", len(entries))
    print("按severity统计：", json.dumps(counts, ensure_ascii=False))
    print("按规则统计：", json.dumps(rules, ensure_ascii=False))
except (ET.ParseError, OSError, ValueError) as exc:
    summary.update(xmlValid=False, summaryError=str(exc))
    print("\nXML摘要未完整生成，请保留原件核查：", exc)
(run / "xml-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("101动作覆盖、失败/跳过和源码判断待助手核对；XML元素含信息项，数量不是已确认漏洞数。")
PY
printf '\n运行记录：%s\n' "$run"
exit "$analysis_status"
