"""P09 Flawfinder只读输入守卫；仅核对身份和文本范围，不调用检测器。"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import stat
import sys

sys.dont_write_bytecode = True
KINDS = {"compiled_c": 58, "included_c": 6, "project_header": 21, "generated_header": 3}


def read_regular(path, digest=None):
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise ValueError("输入不是普通文件：" + str(path))
    data = path.read_bytes()
    if digest is not None and hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("固定输入哈希不一致：" + str(path))
    return data


def verify(docs, local=False):
    setup = docs / "review_evidence/libjpeg_turbo_setup"
    profile = json.loads(read_regular(setup / "Flawfinder_Profile.json").decode("utf-8-sig"))
    if (profile.get("project") != "P09 libjpeg-turbo" or profile.get("projectVersion") != "3.1.1"
            or profile.get("plannedRunId") != "PRE-P09-FF-001" or profile.get("inputCount") != 88
            or profile.get("arguments") != ["--minlevel=1", "--neverignore", "--columns", "--context"]):
        raise ValueError("Flawfinder固定配置不一致")
    shared_profile_path = setup / "CodeChecker_Profile.json"
    shared_profile = json.loads(read_regular(shared_profile_path, profile["sharedCodeCheckerProfileSHA256"]).decode("utf-8-sig"))
    shared_guard_path = setup / "Verify_CodeChecker_Inputs.py"
    read_regular(shared_guard_path, profile["sharedCodeCheckerGuardSHA256"])
    spec = importlib.util.spec_from_file_location("p09_ff_shared_identity_guard", shared_guard_path)
    shared_guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared_guard)
    shared_result = shared_guard.verify(docs, local=local)
    if profile["identityFiles"] != shared_profile["identityFiles"] or len(profile["identityFiles"]) != 90:
        raise ValueError("复用的90项输入身份发生变化")
    wanted = [row for row in shared_profile["identityFiles"] if row["category"] in KINDS]
    if profile["inputs"] != wanted or len(wanted) != 88:
        raise ValueError("文本输入不是已验收88个项目闭包文件")
    if dict(Counter(row["category"] for row in wanted)) != KINDS:
        raise ValueError("文本分类不是58独立C＋6包含C＋21项目头＋3生成头")
    names = [row["file"] for row in wanted]
    if len(set(names)) != 88 or any("\n" in name or "\r" in name for name in names):
        raise ValueError("文本路径重复或包含换行")
    paths = read_regular(docs / profile["textInputList"], profile["textInputListSHA256"]).decode("utf-8").splitlines()
    if paths != names:
        raise ValueError("88项文本清单与固定Profile不一致")
    manifest = read_regular(docs / profile["textIdentityManifest"], profile["textIdentityManifestSHA256"]).decode("utf-8").splitlines()
    rows = [line.split(None, 1) for line in manifest]
    if any(len(row) != 2 for row in rows) or len(rows) != 88:
        raise ValueError("文本哈希清单格式或数量异常")
    if [(row[1], row[0]) for row in rows] != [(row["file"], row["sha256"]) for row in wanted]:
        raise ValueError("88项文本哈希清单与固定Profile不一致")
    if any(Path(name).suffix not in (".c", ".h") for name in names):
        raise ValueError("文本输入包含非C/头文件")
    return dict(status="passed", project="P09 libjpeg-turbo", plannedRunId="PRE-P09-FF-001",
        mode="local_copies" if local else "live_linux_inputs", inputCount=88,
        inputCategories=KINDS, sourceCFiles=64, sourceHeaders=21, generatedHeaders=3,
        textListEqualsAcceptedProjectClosure=True, databasesPassedToScanner=False,
        systemCompilerPathsPassedToScanner=False, repeatedBitDepthActionsNotRepeatedAsText=True,
        sharedIdentity=shared_result, guardExecutedScannerBuildOrReportParse=False,
        actualFlawfinderCoverage="pending user execution and output review")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, required=True)
    parser.add_argument("--local-copies", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.docs, local=args.local_copies)
    except Exception as exc:
        result = dict(status="failed", error=str(exc), guardExecutedScannerBuildOrReportParse=False)
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    if result["status"] != "passed":
        print("P09 Flawfinder输入身份检查失败：" + result["error"], file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("P09 Flawfinder输入身份通过：88文本＝64C＋21项目头＋3生成头；数据库与系统头不作为文本输入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
