"""Read existing cJSON inputs and tool versions; never build or analyze code."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone


def file_check(item):
    path = Path(item["path"])
    row = dict(item, passed=False)
    if path.is_symlink() or not path.is_file():
        row["reason"] = "缺少预期普通文件，或文件已变为符号链接"
        return row
    data = path.read_bytes()
    row["actual_sha256"] = hashlib.sha256(data).hexdigest()
    row["actual_bytes"] = len(data)
    row["passed"] = row["actual_sha256"] == item["sha256"]
    if "bytes" in item:
        row["passed"] &= len(data) == item["bytes"]
    if not row["passed"]:
        row["reason"] = "大小或SHA-256与旧验收基准不同；不自动改写文件"
    return row


def query(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=30, check=False)
        return {"argv": argv, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"argv": argv, "exit_code": None, "error": str(error)}


def version_matches(result, spec):
    if result["exit_code"] != 0:
        return False
    stdout = result.get("stdout", "").strip()
    if "exact_stdout" in spec:
        return stdout == spec["exact_stdout"]
    match = re.search(spec["version_pattern"], stdout + result.get("stderr", ""))
    return match is not None and match.group(1) == spec["expected_version"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("实际前置检查仅由用户在Ubuntu运行")
    profile_path = args.docs / "review_evidence/cJSON_cost_supplement_20261030/Preflight_Profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    rows = [file_check(item) for item in profile["files"]]
    for row in rows:
        print(("通过" if row["passed"] else "不通过") + "：" + row["label"])

    checks = []
    def add(label, passed, details):
        checks.append({"label": label, "passed": bool(passed), "details": details})
        print(("通过" if passed else "不通过") + "：" + label)

    try:
        environment_status = (args.output / "environment-exit-code.txt").read_text().strip()
    except OSError as error:
        environment_status = str(error)
    environment_files = [args.output / "environment" / name for name in
                         ("system.txt", "tool-versions.txt", "time-version.txt",
                          "time-binary.sha256", "recording-scripts.sha256")]
    add("本次完整环境快照", environment_status == "0"
        and all(path.is_file() and path.stat().st_size > 0 for path in environment_files),
        {"exit_code": environment_status, "required_files": list(map(str, environment_files))})

    database_path = Path(profile["database"])
    try:
        database = json.loads(database_path.read_text())
        baseline = json.loads((args.docs / profile["database_baseline"]).read_text())
        add("真实数据库保持原1条C89动作", database == baseline and len(database) == 1,
            {"current": database, "baseline": profile["database_baseline"]})
    except (OSError, ValueError, TypeError) as error:
        add("真实数据库保持原1条C89动作", False, str(error))

    add("Ubuntu 24.04 / x86_64环境", platform.machine() == "x86_64"
        and platform.freedesktop_os_release().get("ID") == "ubuntu"
        and platform.freedesktop_os_release().get("VERSION_ID") == "24.04",
        {"machine": platform.machine(), "os": platform.freedesktop_os_release()})
    add("固定Python虚拟环境", sys.prefix == profile["venv"], sys.prefix)
    for package, expected in profile["python_packages"].items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = "NOT FOUND"
        add(package + "版本", actual == expected, {"expected": expected, "actual": actual})

    queries = {}
    for name, spec in profile["version_queries"].items():
        result = query(spec["argv"])
        queries[name] = result
        add(name + "版本", version_matches(result, spec), result)
    for name, path in profile["executables"].items():
        add(name + "固定入口", Path(path).is_file() and os.access(path, os.X_OK), path)
    add("CodeChecker默认labels未被覆盖", not os.environ.get("CC_TEST_LABELS_DIR"),
        os.environ.get("CC_TEST_LABELS_DIR", "unset"))
    add("clangsa路径显式固定", os.environ.get("CC_ANALYZER_BIN") == "clangsa:/usr/bin/clang-18",
        os.environ.get("CC_ANALYZER_BIN", "unset"))

    for item in profile["planned_runs"]:
        path = Path(item["directory"])
        add(item["run_id"] + "目录未占用", not path.exists() and not path.is_symlink(), str(path))

    passed = all(row["passed"] for row in rows + checks)
    summary = {"record_id": "CHECK-P03-COST-001",
               "checked_utc": datetime.now(timezone.utc).isoformat(),
               "purpose": "cJSON成本补测前只读检查；未构建、未运行检测器或parse",
               "status": "machine_checks_passed_pending_assistant_acceptance" if passed else "needs_review",
               "passed": passed, "files": rows, "checks": checks,
               "planned_runs": profile["planned_runs"],
               "profile_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
               "environment_directory": str(args.output / "environment")}
    with (args.output / "Preflight_Check.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("\n" + ("前置检查通过，待助手验收。" if passed else "存在差异，请返回输出，由助手核对。"))
    print("本步未配置、构建、安装、运行三工具分析或解析旧报告。")
    return 0 if passed else 65


if __name__ == "__main__":
    sys.exit(main())
