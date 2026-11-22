"""Read-only P09 clangsa input guard; never configures, builds, analyzes or parses reports."""
from collections import Counter
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import importlib.util
import json
import re
import shlex
import stat
import sys

sys.dont_write_bytecode = True
PROJECT = "P09 libjpeg-turbo"
COMMIT = "7723f50f3f66b9da74376e6d8badb6162464212c"
TARGETS = {"jpeg-static": 58, "jpeg12-static": 28, "jpeg16-static": 15}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path, expected_sha=None, expected_bytes=None):
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise ValueError("input is not an ordinary file: " + str(path))
    data = path.read_bytes()
    if expected_bytes is not None and len(data) != expected_bytes:
        raise ValueError("input byte length differs: " + str(path))
    if expected_sha is not None and (not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
                                     or sha(data) != expected_sha):
        raise ValueError("pinned input SHA-256 differs: " + str(path))
    return data


def load_identity(docs, row, local):
    path = docs / row["localFile"] if local else Path(row["file"])
    return read_regular(path, row["sha256"], row["bytes"])


def action_identity(action):
    """Keep action semantics; repeated source files remain separate actions."""
    if not isinstance(action, dict) or not isinstance(action.get("file"), str):
        raise ValueError("malformed compilation action")
    if "arguments" in action:
        argv = action["arguments"]
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError("malformed compilation argv")
    else:
        argv = shlex.split(action["command"])
    if argv.count("-o") != 1 or argv.index("-o") + 1 >= len(argv):
        raise ValueError("action does not have exactly one object output")
    output = argv[argv.index("-o") + 1]
    directory = PurePosixPath(action["directory"])
    obj = PurePosixPath(output)
    if obj.is_absolute():
        try:
            output = obj.relative_to(directory).as_posix()
        except ValueError:
            raise ValueError("object outside original build directory") from None
    groups = [target for target in TARGETS if output.startswith("CMakeFiles/" + target + ".dir/")]
    return (groups[0] if len(groups) == 1 else None), output, argv


def verify_database(raw, selected, source_root, expected_macro_values, build_root=None):
    if not isinstance(raw, list) or not isinstance(selected, list):
        raise ValueError("database is not a JSON action array")
    wanted = [row for row in raw if action_identity(row)[0] in TARGETS]
    if selected != wanted:
        raise ValueError("selected DB is not the exact ordered target-action subset of raw DB")
    if len(selected) != 101:
        raise ValueError("selected database must retain all101 actual library actions")
    counts, macro_values, outputs, sources = Counter(), {}, [], []
    for row in selected:
        if build_root is not None and row.get("directory") != build_root:
            raise ValueError("action build directory differs from accepted original context")
        group, output, argv = action_identity(row)
        counts[group] += 1
        outputs.append(output)
        src = PurePosixPath(row["file"])
        if src.suffix != ".c" or not src.is_relative_to(PurePosixPath(source_root)):
            raise ValueError("target action is not an accepted project C translation unit")
        sources.append(str(src))
        bits = [x for x in argv if x.startswith("-DBITS_IN_JSAMPLE=")]
        macro_values.setdefault(group, set()).add(tuple(bits))
    if dict(counts) != TARGETS or len(set(outputs)) != 101:
        raise ValueError("target action counts or101 distinct object outputs differ")
    macros = {key: sorted([list(x) for x in value]) for key, value in macro_values.items()}
    if macros != expected_macro_values:
        raise ValueError("original 8/12/16-bit macro contexts differ")
    return dict(rawActions=len(raw), selectedActions=len(selected), targetActionCounts=dict(counts),
                uniqueObjectOutputs=len(set(outputs)), independentSourceFiles=len(set(sources)),
                repeatedSourceActions=len(sources) - len(set(sources)), bitDepthMacroContexts=macros,
                exactOrderedSubsetOfRawDatabase=True, compileUniqueing="none")


def verify(docs, local=False):
    setup = docs / "review_evidence/libjpeg_turbo_setup"
    profile = json.loads(read_regular(setup / "CodeChecker_Profile.json").decode("utf-8-sig"))
    if (profile.get("project") != PROJECT or profile.get("version") != "3.1.1"
            or profile.get("commit") != COMMIT or profile.get("intendedActions") != 101
            or profile.get("inputFreezeStatus") != "frozen_from_accepted_build"):
        raise ValueError("CodeChecker profile is not frozen from the accepted P09 build")
    rows = profile["identityFiles"]
    if len({x["file"] for x in rows}) != len(rows):
        raise ValueError("duplicate identity path")
    blobs = {row["file"]: load_identity(docs, row, local) for row in rows}
    evidence = {}
    for label, row in profile["evidencePins"].items():
        evidence[label] = json.loads(read_regular(docs / row["file"], row["sha256"]).decode("utf-8-sig"))
    accepted = evidence["buildAcceptance"]
    for assertion in profile["buildAcceptanceAssertions"]:
        node = accepted
        for key in assertion["path"]:
            node = node[key]
        if node != assertion["equals"]:
            raise ValueError("accepted build assertion differs: " + ".".join(assertion["path"]))
    closure_doc = evidence["scopeClosure"]
    closure_all = closure_doc["files"]
    closure = [row for row in closure_all if row["kind"] != "system_or_compiler"]
    system = [row for row in closure_all if row["kind"] == "system_or_compiler"]
    if (len(closure) != profile["scopeClosureFiles"] or len(system) != 84
            or len(closure_all) != 172 or closure_doc["counts"] != profile["dependencyKindCounts"]):
        raise ValueError("actual project/system target dependency closure count differs")
    prepared = {row["file"]: row for row in rows}
    closure_paths = []
    for item in closure:
        name = item["linuxPath"]
        closure_paths.append(name)
        if name not in prepared or prepared[name]["sha256"] != item["sha256"]:
            raise ValueError("closure file missing/different in prepared identities: " + name)
    if len(closure_paths) != len(set(closure_paths)):
        raise ValueError("duplicate dependency closure path")
    database = verify_database(json.loads(blobs[profile["rawDatabase"]].decode("utf-8-sig")),
                               json.loads(blobs[profile["database"]].decode("utf-8-sig")),
                               profile["sourceRoot"], profile["bitDepthMacroContexts"], profile["buildRoot"])
    if local:
        # Local Windows copies cannot establish original POSIX modes; live mode does.
        source = dict(status="local_identity_copies_only", posixSourceTreeNotReinspected=True)
    else:
        helper = setup / "Verify_Build_Source.py"
        read_regular(helper, profile["sourceGuardHelperSHA256"])
        spec = importlib.util.spec_from_file_location("p09_cc_source_guard", helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = module.verify(Path(profile["sourceRoot"]), Path(profile["archive"]),
                               Path(profile["archiveCheck"]), docs / profile["acceptedArchive"],
                               docs / profile["acceptedSource"], Path(profile["sourceRecord"]))
    return dict(status="passed", project=PROJECT, purpose="functional pretest input identity only",
                mode="local_copies" if local else "live_linux_inputs", intendedActions=101,
                identityFiles=len(rows), scopeClosureFiles=len(closure), database=database,
                systemOrCompilerDependencyFiles=len(system),
                systemHeaderIdentityBoundary="84 paths retained as environment/context provenance;no content SHA was collected by build acceptance;not missing project hashes",
                sourceIdentity=source, guardExecutedConfigureBuildOrAnalysis=False,
                coverageValidation="pending_user_analysis_and_result_review")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, required=True)
    parser.add_argument("--local-copies", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true", help="emit the full identity result on stdout")
    args = parser.parse_args()
    try:
        result = verify(args.docs, args.local_copies)
    except Exception as exc:
        result = dict(status="failed", project=PROJECT, error=str(exc),
                      guardExecutedConfigureBuildOrAnalysis=False)
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    if result["status"] != "passed":
        print("P09 clangsa输入身份检查失败：" + result["error"], file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print("P09输入身份通过：101条原始主库动作（58／28／15），保留相同源文件不同位深动作；源码与实际闭包身份保持。")
    if args.local_copies:
        print("本次仅核对本地副本；POSIX源码树身份须另用live Linux模式核对。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
