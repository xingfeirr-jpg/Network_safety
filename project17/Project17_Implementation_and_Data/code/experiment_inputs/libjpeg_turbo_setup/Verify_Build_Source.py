"""P09 build-phase source identity guard. It never configures, builds or scans."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import stat
import sys

sys.dont_write_bytecode = True
PIN_EXTRACT_VERIFIER_SHA = "8cfefe4aea515ba87fff3b6a437b13f6c90e680a7f5cd23b3b4b9ad496d23f63"
PIN_SOURCE_ACCEPTANCE_SHA = "5fbf3fab9f20556267cc8fd83cad3e06d2fc1cf139076d632a0da0cd4aa0492d"
PIN_SOURCE_CHECK_SHA = "f0bd826d4947555a41a6aacced439c762b1dd44996cf0bd86d25a1f7b5d7ff6e"
PIN_COMMIT = "7723f50f3f66b9da74376e6d8badb6162464212c"
PIN_ARCHIVE_SHA = "aadc97ea91f6ef078b0ae3a62bba69e008d9a7db19b34e4ac973b19b71b4217c"
PHASES = ("before-build", "after-build", "after-configure-failure", "after-build-failure")


def read_pinned(path, digest):
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("source acceptance baseline is not yet frozen")
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise ValueError("input is not an ordinary file: " + str(path))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("pinned input SHA-256 mismatch: " + str(path))
    return data


def verify(source, archive, archive_check, accepted_archive, accepted_source, source_record):
    # This loader invokes functions only. The historical SRC __main__ messages
    # and its configured/built/scanned fields are not reused after a build.
    verifier_path = Path(__file__).with_name("Verify_Extracted_Source.py")
    read_pinned(verifier_path, PIN_EXTRACT_VERIFIER_SHA)
    spec = importlib.util.spec_from_file_location("p09_pinned_source_verifier", verifier_path)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    accepted = json.loads(read_pinned(accepted_source, PIN_SOURCE_ACCEPTANCE_SHA).decode("utf-8-sig"))
    previous = json.loads(read_pinned(source_record, PIN_SOURCE_CHECK_SHA).decode("utf-8-sig"))
    if accepted.get("accepted") is not True or accepted.get("runId") != "SRC-P09-001":
        raise ValueError("local acceptance does not accept SRC-P09-001")
    if accepted.get("commit") != PIN_COMMIT or accepted.get("version") != "3.1.1":
        raise ValueError("local source acceptance fixed identity mismatch")
    if (accepted.get("sourceDirectory") != str(source)
            or accepted.get("archiveSHA256") != PIN_ARCHIVE_SHA
            or accepted.get("rawSourceCheckSHA256") != PIN_SOURCE_CHECK_SHA
            or accepted.get("regularFiles") != 546
            or accepted.get("directoriesIncludingRoot") != 42
            or accepted.get("subdirectories") != 41
            or accepted.get("symlinks") != 0 or accepted.get("hardlinks") != 0
            or accepted.get("allPermissionsIncludingExecutionBitsMatch") is not True
            or accepted.get("failed") != 0):
        raise ValueError("local source acceptance baseline/coverage mismatch")
    if (previous.get("status") != "passed" or previous.get("mode") != "source"
            or previous.get("commit") != PIN_COMMIT or previous.get("version") != "3.1.1"
            or previous.get("sourceRoot") != str(source)
            or previous.get("archiveSHA256") != PIN_ARCHIVE_SHA
            or previous.get("allMembersMatchAcceptedArchive") is not True
            or previous.get("allPermissionsIncludingExecutionBitsMatch") is not True):
        raise ValueError("original SRC-P09-001 did not accept the requested source")
    profile_path = verifier_path.with_name("Download_Profile.json")
    profile, expected = verifier.validate_inputs(profile_path, archive, archive_check, accepted_archive)
    prior_members = verifier.member_map(previous["members"])
    verifier.compare_members(prior_members, expected)
    observed = verifier.collect_source(source)
    verifier.compare_members(observed, expected)
    verifier.compare_members(observed, prior_members)
    fixed = {}
    for ref in profile["referenceFiles"]:
        row = observed[ref["file"]]
        if row["size"] != ref["bytes"] or row["sha256"] != ref["sha256"]:
            raise ValueError("fixed commit reference mismatch: " + ref["file"])
        fixed[ref["file"]] = row["sha256"]
    return dict(status="passed", project="P09 libjpeg-turbo", version="3.1.1", commit=PIN_COMMIT,
                sourceRoot=str(source), archiveSHA256=PIN_ARCHIVE_SHA,
                sourceAcceptanceSHA256=PIN_SOURCE_ACCEPTANCE_SHA,
                sourceRecordSHA256=PIN_SOURCE_CHECK_SHA,
                completeMemberSetTypesModesSizesSHA256MatchAcceptedSourceAndArchive=True,
                regularFiles=sum(row["type"] == "file" for row in observed.values()),
                directoriesIncludingRoot=sum(row["type"] == "directory" for row in observed.values()),
                fixedCommitReferenceFiles=fixed,
                members=[observed[name] for name in sorted(observed)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "archive", "archive-check", "accepted-archive", "accepted-source", "source-record", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--phase", choices=PHASES, required=True)
    args = parser.parse_args()
    # Reserve a fresh record even on verification failure; never overwrite it.
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        try:
            result = verify(args.source, args.archive, args.archive_check, args.accepted_archive,
                            args.accepted_source, args.source_record)
        except Exception as exc:
            result = dict(status="failed", project="P09 libjpeg-turbo", error=str(exc))
        result.update(callerPhase=args.phase, guardExecutedConfigureBuildOrAnalysis=False,
                      phaseMeaning="caller phase only; actual configure/build status is recorded separately")
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    if result["status"] != "passed":
        print("P09完整源码身份检查失败：" + result["error"], file=sys.stderr)
        return 1
    print(args.phase + "：546普通文件／41子目录（含根42）的完整集合、类型、权限／执行位、大小及SHA-256与已验收SRC和原包保持一致。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("P09构建源码守卫入口失败：" + str(exc), file=sys.stderr)
        raise SystemExit(1)
