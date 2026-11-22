#!/usr/bin/env bash
# User-run P08 Flawfinder pretest. Identity checks/display are outside timing.
set -euo pipefail
cd "$HOME/comp5355"
source .venv/bin/activate
docs="/mnt/d/Project/COMP5355 Cyber and Internet Security"
run_id=PRE-P08-FF-001
run="$HOME/comp5355/results/pretest-libpng-1.6.50/$run_id"
ff="$HOME/comp5355/.venv/bin/flawfinder"
database="$HOME/comp5355/build/libpng-1.6.50/compile_commands.json"
manifest="$docs/review_evidence/libpng_setup/flawfinder-inputs.sha256"
if [[ -e "$run" || -L "$run" ]]; then
    printf '运行目录已存在，请保留原件并先核对进度：%s\n' "$run" >&2
    exit 73
fi
[[ -x "$ff" ]] || { printf '未找到实验虚拟环境中的Flawfinder。\n' >&2; exit 69; }
version=$("$ff" --version)
[[ "$version" == '2.0.20' ]] || { printf 'Flawfinder版本不符：%s\n' "$version" >&2; exit 65; }
python - "$docs" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);data=root/'review_evidence/libpng_pretest_20261028'
accepted=json.loads((data/'Build_Identity_Check.json').read_text(encoding='utf-8'))
if accepted.get('acceptanceStatus')!='accepted_build_originals' or accepted.get('compileActions')!=15:
    raise SystemExit('P08构建未验收为15条目标动作。')
profile=json.loads((root/'review_evidence/libpng_setup/Flawfinder_Profile.json').read_text(encoding='utf-8'))
manifest=(root/'review_evidence/libpng_setup/flawfinder-inputs.sha256').read_bytes()
if hashlib.sha256(manifest).hexdigest()!=profile['identityManifestSHA256']:
    raise SystemExit('输入身份清单与准备配置不一致。')
closure=json.loads((data/'Project_Dependency_Manifest.json').read_text(encoding='utf-8'))
expected={x['linuxPath']:x['sha256'] for x in closure}
text={x['file']:x['sha256'] for x in profile['inputs']}
identities={x['file']:x['sha256'] for x in profile['identityFiles']}
if len(closure)!=22 or len(profile['inputs'])!=22 or text!=expected:
    raise SystemExit('22项文本范围与实际P08闭包不一致。')
if len(profile['identityFiles'])!=23 or identities!={**expected,profile['database']:profile['databaseSHA256']}:
    raise SystemExit('23项身份应仅含22文本与原始数据库。')
rows=[line.split(None,1) for line in manifest.decode('utf-8').splitlines()]
if len(rows)!=23 or {file:digest for digest,file in rows}!=identities:
    raise SystemExit('清单路径／哈希与准备配置不一致。')
db=Path(profile['database']);raw=db.read_bytes()
if hashlib.sha256(raw).hexdigest()!=profile['databaseSHA256']:
    raise SystemExit('原始数据库身份改变。')
actions=json.loads(raw)
cfiles={x['file'] for x in profile['inputs'] if x['category']=='translation_unit'}
if len(actions)!=15 or {x['file'] for x in actions}!=cfiles:
    raise SystemExit('原始数据库与15个C文本文件范围不一致。')
print('Flawfinder前置核对通过：22个P08文本输入；23项身份包含原数据库但不扫描它。')
PY
sha256sum -c "$manifest"
inputs=()
while read -r digest file; do
    [[ -n "$digest" && -n "$file" ]] || { printf '输入身份清单存在空项。\n' >&2; exit 65; }
    if [[ "$file" != "$database" ]]; then
        inputs+=("$file")
    fi
done < "$manifest"
[[ ${#inputs[@]} -eq 22 ]] || { printf '文本输入数不是预定22项。\n' >&2; exit 65; }
printf '开始Flawfinder：22个文本输入（15C＋6源码头＋1生成头）；23项身份中的原数据库不作文本扫描。完整输出保存后显示摘要。\n'
if bash "$docs/scripts/measure_run.sh" "$run_id" "$run" -- \
    "$ff" --minlevel=1 --neverignore --columns --context "${inputs[@]}"; then
    analysis_status=0
else
    analysis_status=$?
fi
[[ -f "$run/exit-code.txt" ]] || exit "$analysis_status"
cp -- "$manifest" "$run/input-files.sha256"
printf '%s\n' "${inputs[@]}" > "$run/input-files.txt"
cp -- "$docs/review_evidence/libpng_setup/Flawfinder_Profile.json" "$run/prepared-profile.json"
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
