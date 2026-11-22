"""P09独立Cppcheck只读输入守卫；不运行检测器、构建或报告parse。"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shlex
import stat
import sys

sys.dont_write_bytecode = True


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
    profile = json.loads(read_regular(setup / "Cppcheck_Profile.json").decode("utf-8-sig"))
    if (profile.get("project") != "P09 libjpeg-turbo" or profile.get("projectVersion") != "3.1.1"
            or profile.get("plannedRunId") != "PRE-P09-CP-001" or profile.get("databaseActions") != 101
            or profile.get("analysisCStandard") != "C11, explicitly --std=c11"
            or profile.get("extraPreprocessorDefinitions") != []):
        raise ValueError("Cppcheck固定配置或额外宏不一致")
    shared_path = setup / "CodeChecker_Profile.json"
    shared = json.loads(read_regular(shared_path, profile["sharedCodeCheckerProfileSHA256"]).decode("utf-8-sig"))
    shared_guard_path = setup / "Verify_CodeChecker_Inputs.py"
    read_regular(shared_guard_path, profile["sharedCodeCheckerGuardSHA256"])
    spec = importlib.util.spec_from_file_location("p09_cp_shared_identity_guard", shared_guard_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identity = module.verify(docs, local=local)
    if profile["identityFiles"] != shared["identityFiles"] or len(profile["identityFiles"]) != 90:
        raise ValueError("共享90项身份发生变化")
    if profile["database"] != shared["database"] or profile["databaseSHA256"] != shared["databaseSHA256"]:
        raise ValueError("Cppcheck必须直接使用未改写的原选101动作数据库")
    row = next(item for item in shared["identityFiles"] if item["file"] == profile["database"])
    path = docs / row["localFile"] if local else Path(row["file"])
    actions = json.loads(read_regular(path, row["sha256"]).decode("utf-8-sig"))
    groups = Counter()
    macro_groups = Counter()
    contexts = []
    for index, action in enumerate(actions):
        argv = shlex.split(action["command"])
        target, output, _ = module.action_identity(action)
        expected_includes = ["-I" + shared["buildRoot"], "-I" + shared["sourceRoot"] + "/src"]
        includes = [token for token in argv if token.startswith("-I")]
        definitions = [token for token in argv if token.startswith("-D")]
        expected_definitions = {"jpeg-static": [], "jpeg12-static": ["-DBITS_IN_JSAMPLE=12"],
                                "jpeg16-static": ["-DBITS_IN_JSAMPLE=16"]}[target]
        if includes != expected_includes or definitions != expected_definitions:
            raise ValueError("原动作-I或-D上下文不一致，索引：" + str(index))
        if any(token.startswith(("-U", "-std", "-isystem")) for token in argv):
            raise ValueError("发现未准备的宏取消／标准／系统include参数")
        groups[target] += 1
        macro_groups[";".join(definitions) or "8-bit header default"] += 1
        contexts.append(dict(databaseIndex=index, source=action["file"], target=target,
                             object=output, includeArguments=includes, defineArguments=definitions))
    if dict(groups) != {"jpeg-static": 58, "jpeg12-static": 28, "jpeg16-static": 15}:
        raise ValueError("101条多位深动作没有完整保留")
    return dict(status="passed", project="P09 libjpeg-turbo", plannedRunId="PRE-P09-CP-001",
        mode="local_copies" if local else "live_linux_inputs", databaseActions=101,
        uniqueCompiledSourceFiles=58, targetActionCounts=dict(groups), macroContextCounts=dict(macro_groups),
        originalSelectedDatabaseUnchanged=True, databaseImportContextAudit=contexts,
        extraPreprocessorDefinitions=[], importedIncludePolicy="retain original two -I paths;no -isystem conversion or extra-I",
        sharedIdentity=identity, guardExecutedScannerBuildOrReportParse=False,
        actualCppcheckCoverage="pending user execution,101 processed-action evidence and raw-output review")


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
        print("P09 Cppcheck输入身份检查失败：" + result["error"], file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("P09 Cppcheck输入通过：101原始动作＝58／28／15，原-I/-D保持，90项身份和完整源码一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
