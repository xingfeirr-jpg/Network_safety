#!/usr/bin/env bash
# User-run P08 clangsa pretest. Checks and parsing stay outside analysis timing.
set -euo pipefail
cd "$HOME/comp5355"
source .venv/bin/activate
export CC_ANALYZER_BIN="clangsa:/usr/bin/clang-18"
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P08-CC-001
run="$HOME/comp5355/results/pretest-libpng-1.6.50/$run_id"
database="$HOME/comp5355/build/libpng-1.6.50/compile_commands.json"
cc="$HOME/comp5355/.venv/bin/CodeChecker"
manifest="$docs/review_evidence/libpng_setup/codechecker-inputs.sha256"

if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，保留原件并停止：%s\n' "$run" >&2
    exit 73
fi
version=$(python -c 'import importlib.metadata; print(importlib.metadata.version("codechecker"))')
if [[ "$version" != '6.29.1' ]]; then
    printf 'CodeChecker版本与固定配置不一致：%s\n' "$version" >&2
    exit 69
fi
/usr/bin/clang-18 --version | grep -E 'version 18\.1\.3([[:space:]]|$)'
[[ -s "$docs/review_evidence/libpng_pretest_20261028/Build_Identity_Check.json" ]]
python - "$docs" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);data=root/'review_evidence/libpng_pretest_20261028'
accepted=json.loads((data/'Build_Identity_Check.json').read_text(encoding='utf-8'))
if accepted.get('acceptanceStatus')!='accepted_build_originals' or accepted.get('compileActions')!=15:
    raise SystemExit('P08构建未验收为15条目标动作，请返回输出。')
profile=json.loads((root/'review_evidence/libpng_setup/CodeChecker_Profile.json').read_text(encoding='utf-8'))
manifest=(root/'review_evidence/libpng_setup/codechecker-inputs.sha256').read_bytes()
if hashlib.sha256(manifest).hexdigest()!=profile['identityManifestSHA256']:
    raise SystemExit('输入清单与准备配置不一致。')
closure=json.loads((data/'Project_Dependency_Manifest.json').read_text(encoding='utf-8'))+json.loads((data/'External_Dependency_Manifest.json').read_text(encoding='utf-8'))
prepared={x['file']:x['sha256'] for x in profile['identityFiles']}
if len(closure)!=24 or any(prepared.get(x['linuxPath'])!=x['sha256'] for x in closure):
    raise SystemExit('实际闭包与预备输入不一致。')
PY
sha256sum -c "$manifest"
printf '阶段1：开始clangsa分析；完整输出写入文件，结束后显示摘要。\n'

if bash "$docs/scripts/measure_run.sh" "$run_id" "$run" -- \
    "$cc" analyze "$database" \
    --analyzers clangsa \
    -o "$run/reports" \
    -j 1 \
    --timeout 120 \
    --compile-uniqueing none \
    --capture-analysis-output \
    --z3-refutation off; then
    analysis_status=0
else
    analysis_status=$?
fi
[[ -f "$run/exit-code.txt" ]] || exit "$analysis_status"
cp -- "$manifest" "$run/input-files.sha256"
cp -- "$docs/review_evidence/libpng_setup/CodeChecker_Profile.json" "$run/prepared-profile.json"
printf 'CC_ANALYZER_BIN=%s\nCC_TEST_LABELS_DIR=%s\n' "$CC_ANALYZER_BIN" "${CC_TEST_LABELS_DIR-<unset>}" > "$run/configuration-environment.txt"

# Keep each auxiliary command and its real status; no auxiliary work is timed.
record_aux() {
    local prefix=$1
    local stdout_file=$2
    shift 2
    printf '%q ' "$@" > "$run/$prefix-command.txt"
    printf '\n' >> "$run/$prefix-command.txt"
    if LC_ALL=C "$@" > "$run/$stdout_file" 2> "$run/$prefix-stderr.txt"; then
        aux_status=0
    else
        aux_status=$?
    fi
    printf '%s\n' "$aux_status" > "$run/$prefix-exit-code.txt"
}
record_aux checkers checkers.json "$cc" checkers --analyzers clangsa --details --output json
checkers_status=$aux_status
printf '阶段2：检查已保存结果的状态（分析计时之外）。\n'
record_aux parse-status parse-status.txt "$cc" parse --status --detailed "$run/reports"
status_parse_status=$aux_status
printf '阶段3：解析并展示诊断（分析计时之外）。\n'
record_aux findings findings.txt "$cc" parse "$run/reports"
findings_status=$aux_status

printf '\n分析退出码：'; cat "$run/exit-code.txt"
printf '检查器快照退出码：%s\n状态检查退出码：%s\n普通parse退出码：%s\n' \
    "$checkers_status" "$status_parse_status" "$findings_status"
printf '普通parse返回2表示有可展示报告；不是分析失败。\n'
printf '\n分析日志末尾：\n'; tail -n 16 "$run/stdout.txt"
if [[ -s "$run/stderr.txt" ]]; then
    printf '\n分析stderr末尾：\n'; tail -n 8 "$run/stderr.txt"
fi
printf '\n外部计时摘要：\n'
sed -n -e '/User time/p' -e '/System time/p' -e '/Elapsed/p' -e '/Maximum resident/p' "$run/time.txt"

python - "$run" <<'PY'
import json
import pathlib
import plistlib
import sys

run = pathlib.Path(sys.argv[1])
summary = {"runId": "PRE-P08-CC-001", "purpose": "functional pretest",
           "coverageValidation": "pending_tool_output_review", "sourceReview": "not performed",
           "auxiliaryTiming": "checkers and both parse commands outside analysis timing; not measured"}
try:
    data = json.loads((run / "reports/metadata.json").read_text(encoding="utf-8"))
    tools = [t for t in data.get("tools", []) if t.get("name") == "codechecker"]
    summary["metadataTools"] = []
    for tool in tools:
        stats = tool.get("analyzers", {}).get("clangsa", {}).get("analyzer_statistics", {})
        summary["metadataTools"].append({"actionNum": tool.get("action_num"),
                                        "clangsaStatistics": stats, "skipped": tool.get("skipped")})
        print("\n元数据clangsa成功／失败／跳过：", stats.get("successful"), stats.get("failed"), tool.get("skipped"))
    plists = []
    for path in sorted((run / "reports").rglob("*.plist")):
        with path.open("rb") as f:
            result = plistlib.load(f)
        plists.append({"file": str(path.relative_to(run)), "savedDiagnostics": len(result.get("diagnostics", []))})
    summary["plistResults"] = plists
    summary["plistFileCount"] = len(plists)
    summary["savedPlistDiagnostics"] = sum(p["savedDiagnostics"] for p in plists)
    print("可解析plist文件数：", len(plists))
    print("CodeChecker保存的plist诊断总数：", summary["savedPlistDiagnostics"])
except (OSError, ValueError, plistlib.InvalidFileException, TypeError) as exc:
    summary["summaryError"] = str(exc)
    print("\n结果摘要未完整生成，请保留原始日志核对：", exc)
(run / "result-summary-pending.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("成功范围、解析过滤和源码判断待助手核对；诊断数量不是已确认漏洞数。")
PY
printf '\n普通parse展示末尾（完整内容保存在findings.txt）：\n'
tail -n 22 "$run/findings.txt"
printf '\n运行记录：%s\n' "$run"

[[ "$analysis_status" -eq 0 ]] || exit "$analysis_status"
[[ "$checkers_status" -eq 0 ]] || exit "$checkers_status"
[[ "$status_parse_status" -eq 0 ]] || exit "$status_parse_status"
if [[ "$findings_status" -ne 0 && "$findings_status" -ne 2 ]]; then
    exit "$findings_status"
fi
exit 0
