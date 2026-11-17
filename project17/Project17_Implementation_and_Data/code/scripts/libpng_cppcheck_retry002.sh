#!/usr/bin/env bash
# User-run P08 Cppcheck pretest. Input checks and summary are outside timing.
set -euo pipefail
cd "$HOME/comp5355"
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P08-CP-002
run="$HOME/comp5355/results/pretest-libpng-1.6.50/$run_id"
database="$docs/review_evidence/libpng_setup/Cppcheck_Retry002/compile_commands.json"
manifest="$docs/review_evidence/libpng_setup/Cppcheck_Retry002/cppcheck-inputs.sha256"

if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，保留原件并停止：%s\n' "$run" >&2
    exit 73
fi
[[ "$(/usr/bin/cppcheck --version)" == 'Cppcheck 2.13.0' ]]
[[ -s "$docs/review_evidence/libpng_pretest_20261028/Build_Identity_Check.json" ]]
python3 - "$docs" <<'PY'
from pathlib import Path
import hashlib,json,sys,shlex
root=Path(sys.argv[1]);data=root/'review_evidence/libpng_pretest_20261028'
accepted=json.loads((data/'Build_Identity_Check.json').read_text(encoding='utf-8'))
if accepted.get('acceptanceStatus')!='accepted_build_originals' or accepted.get('compileActions')!=15:
    raise SystemExit('P08构建未验收为15条目标动作，请返回输出。')
profile=json.loads((root/'review_evidence/libpng_setup/Cppcheck_Retry002/Cppcheck_Profile.json').read_text(encoding='utf-8'))
manifest=(root/'review_evidence/libpng_setup/Cppcheck_Retry002/cppcheck-inputs.sha256').read_bytes()
if hashlib.sha256(manifest).hexdigest()!=profile['identityManifestSHA256']:
    raise SystemExit('输入清单与准备配置不一致。')
closure=json.loads((data/'Project_Dependency_Manifest.json').read_text(encoding='utf-8'))+json.loads((data/'External_Dependency_Manifest.json').read_text(encoding='utf-8'))
prepared={x['file']:x['sha256'] for x in profile['identityFiles']}
if len(closure)!=24 or any(prepared.get(x['linuxPath'])!=x['sha256'] for x in closure):
    raise SystemExit('实际闭包与预备输入不一致。')
original=json.loads(Path(profile['originalDatabase']).read_text(encoding='utf-8'))
derived=json.loads(Path(profile['database']).read_text(encoding='utf-8'))
dep='/home/yhong/comp5355/deps/zlib-v1.3.2/include'
if len(original)!=15 or len(derived)!=15:
    raise SystemExit('原始与派生数据库动作数不一致。')
for old,new in zip(original,derived):
    before=shlex.split(old['command']);expected=list(before)
    pos=expected.index('-isystem')
    if expected[pos+1]!=dep:
        raise SystemExit('原zlib依赖目录不一致。')
    expected[pos:pos+2]=['-I'+dep]
    if {k:v for k,v in old.items() if k!='command'}!={k:v for k,v in new.items() if k!='command'} or shlex.split(new['command'])!=expected:
        raise SystemExit('派生数据库有额外改动。')
PY
sha256sum -c "$manifest"
printf '开始Cppcheck重试002：派生数据库保留15条目标C动作并补齐固定zlib头路径；C11分析配置（实际构建为GNU C17）；完整输出写入记录目录，结束后显示摘要。\n'

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
cp -- "$manifest" "$run/input-files.sha256"
cp -- "$database" "$run/compile_commands.cppcheck.json"
cp -- "$docs/review_evidence/libpng_setup/Cppcheck_Retry002/Database_Adaptation_Audit.json" "$run/database-adaptation-audit.json"
cp -- "$docs/review_evidence/libpng_setup/Cppcheck_Retry002/Cppcheck_Profile.json" "$run/prepared-profile.json"
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
        "runId": "PRE-P08-CP-002",
        "xmlValid": True,
        "xmlDiagnosticElements": len(entries),
        "informationElements": sum(e.get("severity") == "information" for e in entries),
        "nonInformationElements": sum(e.get("severity") != "information" for e in entries),
        "candidateCount": None,
        "classification": "pending assistant review;non-information may include configuration failures",
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
print("覆盖情况和源码判断待助手核对；XML元素含信息项，以上数量不是已确认漏洞数。")
PY
printf '\n运行记录：%s\n' "$run"
exit "$analysis_status"
