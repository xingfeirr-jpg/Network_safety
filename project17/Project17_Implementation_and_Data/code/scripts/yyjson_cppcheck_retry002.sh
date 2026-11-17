#!/usr/bin/env bash
# User-run P06 Cppcheck pretest. Identity checks and XML summary are outside timing.
set -euo pipefail
cd "$HOME/comp5355"
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P06-CP-002
run="$HOME/comp5355/results/pretest-yyjson-0.12.0/$run_id"
database="$HOME/comp5355/build/yyjson-0.12.0/compile_commands.json"
manifest="$docs/review_evidence/yyjson_setup/cppcheck-inputs.sha256"

if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，保留原件并停止：%s\n' "$run" >&2
    exit 73
fi
version=$(/usr/bin/cppcheck --version)
[[ "$version" == 'Cppcheck 2.13.0' ]] || { printf 'Cppcheck版本不符：%s\n' "$version" >&2; exit 65; }
sha256sum -c "$manifest"
printf '开始Cppcheck重试002：补齐__STDC__=1；真实数据库1条C动作，完整输出保存后显示摘要。\n'

if bash "$docs/scripts/measure_run.sh" "$run_id" "$run" -- \
    /usr/bin/cppcheck \
    -D__STDC__=1 \
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
cp -- "$manifest" "$run/input-files.sha256"
cp -- "$docs/review_evidence/yyjson_setup/Cppcheck_Retry002_Profile.json" "$run/prepared-profile.json"
printf '\nCppcheck退出码：'
cat "$run/exit-code.txt"
printf '\n进度输出末尾：\n'
tail -n 12 "$run/stdout.txt"
printf '\n外部计时摘要：\n'
sed -n -e '/User time/p' -e '/System time/p' -e '/Elapsed/p' -e '/Maximum resident/p' "$run/time.txt"

python3 - "$run" <<'PY'
import collections
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

run = pathlib.Path(sys.argv[1])
try:
    root = ET.parse(run / "stderr.txt").getroot()
    if root.tag != "results" or root.get("version") != "2":
        raise ValueError("not Cppcheck XML 2")
    entries = root.findall("errors/error")
    counts = dict(sorted(collections.Counter(e.get("severity", "unknown") for e in entries).items()))
    rules = dict(sorted(collections.Counter(e.get("id", "unknown") for e in entries).items()))
    summary = {
        "purpose": "functional pretest",
        "runId": "PRE-P06-CP-002",
        "xmlValid": True,
        "xmlDiagnosticElements": len(entries),
        "bySeverity": counts,
        "byRule": rules,
        "coverageValidation": "pending_tool_output_review",
        "sourceReview": "not performed",
        "summaryTiming": "outside analysis measurement"
    }
    (run / "xml-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nXML 2可解析；原始诊断元素数：", len(entries))
    print("按severity统计：", json.dumps(counts, ensure_ascii=False))
    print("按规则统计：", json.dumps(rules, ensure_ascii=False))
except (ET.ParseError, OSError, ValueError) as exc:
    print("\nXML摘要未生成，请保留原件核查：", exc)
print("覆盖情况和源码判断待助手核对；XML诊断元素含信息项，以上数量不是已确认漏洞数。")
PY
printf '\n运行记录：%s\n' "$run"
exit "$analysis_status"
