"""P09 accepted release preflight and extracted-tree verification; never extracts."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True
PIN_SHA = "aadc97ea91f6ef078b0ae3a62bba69e008d9a7db19b34e4ac973b19b71b4217c"
PIN_COMMIT = "7723f50f3f66b9da74376e6d8badb6162464212c"
PIN_BYTES = 2506010
PIN_PROFILE_SHA = "847dcf76333d9a2013349e7276cf1f86967797a02989a2538013df263c7b1bf9"
PIN_INSPECTOR_SHA = "69f500a25f2ad343c296ae01c69d795a79369f86a0c4e7ab8fdf23c0fb42c906"
# Actual DL-P09-001 member table and final local acceptance, frozen 2026-10-29.
PIN_ARCHIVE_CHECK_SHA = "711fac89e3cc5556933414baf5c57910864966826059beede52d829b0b51c0c8"
PIN_ACCEPTANCE_SHA = "be58cd1b202f17105b860c6f599220144e77b7a1c23fab87c5c2d6ed8738ad99"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular_input(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise ValueError("input is not an ordinary file: " + str(path))
    return path.read_bytes()


def pinned_input(path, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("DL-P09-001 acceptance baseline is not yet frozen")
    data = regular_input(path)
    if sha(data) != expected:
        raise ValueError("pinned input SHA-256 mismatch: " + str(path))
    return data


def member_map(rows):
    found = {}
    for row in rows:
        name = row.get("path")
        if not isinstance(name, str):
            raise ValueError("member path missing")
        parts = PurePosixPath(name).parts
        if (name.startswith("/") or "\\" in name or name.endswith("/") or name == "."
                or any(x in (".", "..") for x in parts)
                or (name and PurePosixPath(name).as_posix() != name)
                or name in found):
            raise ValueError("unsafe or duplicate member path: " + name)
        if row.get("type") not in ("file", "directory"):
            raise ValueError("unsupported member type: " + name)
        if not isinstance(row.get("mode"), int) or row["mode"] & ~0o777:
            raise ValueError("unsupported member mode: " + name)
        if not isinstance(row.get("size"), int) or row["size"] < 0:
            raise ValueError("invalid member size: " + name)
        if row["type"] == "file":
            if not name or not re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")):
                raise ValueError("invalid file identity: " + name)
        elif row["size"] != 0:
            raise ValueError("nonzero directory size in archive: " + name)
        found[name] = dict(row)
    if "" not in found or found[""]["type"] != "directory":
        raise ValueError("archive root directory missing")
    for name in found:
        for parent in PurePosixPath(name).parents:
            rel = "" if parent.as_posix() == "." else parent.as_posix()
            if rel not in found or found[rel]["type"] != "directory":
                raise ValueError("missing or non-directory parent: " + name)
    return found


def collect_source(source):
    """Use lstat and scandir so links and special files cannot masquerade as files."""
    found = {}

    def visit(path, name):
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            raise ValueError("unexpected symlink in source: " + name)
        if stat.S_ISDIR(info.st_mode):
            found[name] = dict(path=name, type="directory", mode=mode, size=0)
            with os.scandir(path) as entries:
                children = sorted(entries, key=lambda x: x.name)
            for child in children:
                relative = name + "/" + child.name if name else child.name
                visit(Path(child.path), relative)
        elif stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                raise ValueError("unexpected hardlink in source: " + name)
            data = path.read_bytes()
            if len(data) != info.st_size:
                raise ValueError("file size changed while reading source: " + name)
            found[name] = dict(path=name, type="file", mode=mode,
                               size=len(data), sha256=sha(data))
        else:
            raise ValueError("unexpected source entry type: " + name)

    visit(source, "")
    if found[""]["type"] != "directory":
        raise ValueError("source root is not a directory")
    return found


def compare_members(observed, expected):
    if set(observed) != set(expected):
        raise ValueError("source member set mismatch: " + json.dumps({
            "missing": sorted(set(expected) - set(observed)),
            "extra": sorted(set(observed) - set(expected))}))
    for name, ref in expected.items():
        actual = observed[name]
        if actual["type"] != ref["type"]:
            raise ValueError("source member type mismatch: " + name)
        if actual["mode"] != ref["mode"]:
            raise ValueError("source mode mismatch (including execution bits): " + name)
        if ref["type"] == "file" and (actual["size"] != ref["size"]
                or actual["sha256"] != ref["sha256"]):
            raise ValueError("source content size/SHA-256 mismatch: " + name)


def validate_inputs(profile_path, archive, archive_check, acceptance):
    pinned_input(profile_path, PIN_PROFILE_SHA)
    inspector_path = Path(__file__).with_name("Inspect_Release_Archive.py")
    pinned_input(inspector_path, PIN_INSPECTOR_SHA)
    original_bytes = pinned_input(archive_check, PIN_ARCHIVE_CHECK_SHA)
    accepted_bytes = pinned_input(acceptance, PIN_ACCEPTANCE_SHA)
    original = json.loads(original_bytes.decode("utf-8-sig"))
    accepted = json.loads(accepted_bytes.decode("utf-8-sig"))
    if (accepted.get("accepted") is not True or accepted.get("archiveSHA256") != PIN_SHA
            or accepted.get("archiveBytes") != PIN_BYTES or accepted.get("runId") != "DL-P09-001"
            or accepted.get("commit") != PIN_COMMIT or accepted.get("version") != "3.1.1"
            or accepted.get("regularFiles") != 546
            or accepted.get("directoriesIncludingArchiveRoot") != 42
            or accepted.get("subdirectories") != 41
            or accepted.get("symlinks") != 0 or accepted.get("hardlinks") != 0
            or accepted.get("archiveRootModeOctal") != "0775" or accepted.get("failed") != 0):
        raise ValueError("archive acceptance record does not accept this fixed release")
    if (original.get("commit") != PIN_COMMIT or original.get("version") != "3.1.1"
            or original.get("archiveSHA256") != PIN_SHA
            or original.get("archiveBytes") != PIN_BYTES
            or original.get("matchedOfficialReleaseAssetDigest") is not True
            or original.get("officialAssetId") != 262668412
            or original.get("regularFiles") != 546 or original.get("directories") != 42
            or original.get("symlinks") != 0 or original.get("hardlinks") != 0):
        raise ValueError("original DL-P09-001 archive check identity/count mismatch")
    expected = member_map(original["members"])
    if (len(expected) != 588
            or sum(x["type"] == "file" for x in expected.values()) != 546
            or sum(x["type"] == "directory" for x in expected.values()) != 42):
        raise ValueError("archive member table is incomplete")
    spec = importlib.util.spec_from_file_location("p09_pinned_archive_inspector", inspector_path)
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    profile = inspector.load_profile(profile_path)
    archive_data = regular_input(archive)
    if len(archive_data) != PIN_BYTES or sha(archive_data) != PIN_SHA:
        raise ValueError("actual archive size/official release digest mismatch")
    reread = inspector.inspect_members(archive, profile)
    for key in ("members", "regularFiles", "directories", "symlinks", "hardlinks",
                "fixedCommitReferenceFiles", "version"):
        if reread.get(key) != original.get(key):
            raise ValueError("actual archive differs from original member check: " + key)
    return profile, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "source"))
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-check", type=Path, required=True)
    parser.add_argument("--accepted", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reserve the output first; a repeated invocation cannot overwrite evidence.
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        try:
            profile, expected = validate_inputs(args.profile, args.archive, args.archive_check, args.accepted)
            result = dict(status="passed", mode=args.mode, project="P09 libjpeg-turbo",
                          version="3.1.1", commit=PIN_COMMIT, archiveSHA256=PIN_SHA,
                          archiveBytes=PIN_BYTES, archiveCheckSHA256=PIN_ARCHIVE_CHECK_SHA,
                          acceptanceRecordSHA256=PIN_ACCEPTANCE_SHA,
                          regularFiles=546, directoriesIncludingRoot=42,
                          directoriesExcludingRoot=41, symlinks=0, hardlinks=0,
                          wholeArchiveEqualsGitTree="not asserted: official release may include generated files",
                          digitalSignatureVerified=False, configured=False, built=False, scanned=False)
            if args.mode == "source":
                if args.source is None:
                    raise ValueError("--source is required for source verification")
                observed = collect_source(args.source)
                compare_members(observed, expected)
                fixed = {}
                for ref in profile["referenceFiles"]:
                    row = observed[ref["file"]]
                    if row["size"] != ref["bytes"] or row["sha256"] != ref["sha256"]:
                        raise ValueError("extracted fixed commit reference mismatch: " + ref["file"])
                    fixed[ref["file"]] = row["sha256"]
                cmake = (args.source / "CMakeLists.txt").read_text(encoding="utf-8")
                if not re.search(r"^set\(VERSION\s+3\.1\.1\)", cmake, re.M):
                    raise ValueError("extracted CMake version mismatch")
                result.update(sourceRoot=str(args.source), sourceExtracted=True,
                              allMembersMatchAcceptedArchive=True,
                              allPermissionsIncludingExecutionBitsMatch=True,
                              fixedCommitReferenceFiles=fixed,
                              members=[observed[name] for name in sorted(observed)])
            else:
                result.update(sourceExtracted=False, expectedRootMode=oct(expected[""]["mode"]),
                              actualArchiveRereadMatchesOriginalMemberTable=True)
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        except Exception as exc:
            json.dump(dict(status="failed", mode=args.mode, error=str(exc),
                           configured=False, built=False, scanned=False),
                      stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            print("P09前置／源码核对失败：" + str(exc), file=sys.stderr)
            return 1
    if args.mode == "preflight":
        print("已验收发布包前置复核通过：2,506,010字节，固定官方SHA-256、原成员表及4个固定参考文本一致。")
        print("普通文件546；目录含根42／不含根41；符号链接0／硬链接0。尚未解压。")
    else:
        print("解压源码核对通过：546普通文件、41子目录（含根42）；完整集合、类型、权限／执行位、大小及SHA-256均与已验收发布包一致。")
        print("CMake版本3.1.1及4个固定commit构建／许可文本一致；尚未配置、构建或运行检测工具。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("P09核对入口失败：" + str(exc), file=sys.stderr)
        raise SystemExit(1)
