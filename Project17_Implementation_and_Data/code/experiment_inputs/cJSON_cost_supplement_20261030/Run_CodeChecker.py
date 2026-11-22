"""User-run complete CodeChecker measurement; setup and parse are outside timing."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys

from Verify_Preflight import file_check, version_matches


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_fresh(path):
    if path.exists() or path.is_symlink():
        raise ValueError("保留已存在的记录，请先返回输出核对：" + str(path))
    for parent in path.parents:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError("输出父目录状态不符：" + str(parent))


def run_saved(directory, prefix, argv, cwd, env):
    (directory / (prefix + "-command.txt")).write_text(shlex.join(argv) + "\n", encoding="utf-8")
    with (directory / (prefix + "-stdout.txt")).open("xb") as out, \
            (directory / (prefix + "-stderr.txt")).open("xb") as err:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=out, stderr=err, check=False)
    (directory / (prefix + "-exit-code.txt")).write_text(str(result.returncode) + "\n")
    return result.returncode


def checker_dictionary(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("checkers查询不是非空数组")
    result = {}
    for row in rows:
        if row.get("analyzer") != "clangsa" or row.get("status") not in {"enabled", "disabled"}:
            raise ValueError("检查器后端或状态不符")
        name = row["name"]
        if name in result:
            raise ValueError("检查器名称重复")
        result[name] = row["status"] == "enabled"
    return result


def summarize(run, profile):
    tool_list = read_json(run / "reports/metadata.json")["tools"]
    if len(tool_list) != 1 or tool_list[0]["name"] != "codechecker":
        raise ValueError("结果元数据工具集合不符")
    tool = tool_list[0]
    if set(tool["analyzers"]) != {"clangsa"}:
        raise ValueError("结果分析器集合不符")
    analyzer = tool["analyzers"]["clangsa"]
    stats = analyzer["analyzer_statistics"]
    if (tool["command"] != profile["analysis_argv"]
            or tool["version"] != profile["metadata_version"]
            or analyzer["checkers"] != profile["checker_dictionary"]
            or stats["version"] != "18.1.3"):
        raise ValueError("实际命令、版本或完整检查器字典与固定配置不符")
    if (tool["action_num"] != 1 or tool["skipped"] != 0
            or stats["successful"] != 1 or stats["failed"] != 0
            or stats["successful_sources"] != [profile["source"]]
            or stats["failed_sources"] != []):
        raise ValueError("实际成功／失败／跳过范围不是预定1／0／0")
    plists = sorted((run / "reports").rglob("*.plist"))
    mapping = tool["result_source_files"]
    if len(plists) != 1 or set(mapping) != {str(plists[0])} or set(mapping.values()) != {profile["source"]}:
        raise ValueError("plist数量或源码映射不符")
    payload = plistlib.loads(plists[0].read_bytes())
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list) or not all(isinstance(item, dict) for item in diagnostics):
        raise ValueError("plist的diagnostics字段不合法")
    return {"status": "machine_checks_passed_pending_assistant_acceptance",
            "successful_actions": 1, "failed_actions": 0, "skipped_actions": 0,
            "legal_plist_files": 1, "saved_diagnostics": len(diagnostics),
            "enabled_checkers": sum(analyzer["checkers"].values()),
            "checker_dictionary_matches_old": True,
            "meaning": "保存诊断数不是漏洞数；普通parse展示数量与旧输出映射待助手核对。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("实际检测仅由用户在Ubuntu执行")
    docs = args.docs.resolve()
    setup = docs / "review_evidence/cJSON_cost_supplement_20261030"
    profile = read_json(setup / "CodeChecker_Profile.json")
    baseline = read_json(setup / "Preflight_Profile.json")
    run = Path(profile["run_directory"])
    prep = Path(profile["preparation_directory"])
    copies = [(prep, setup / "execution_preparation" / profile["run_id"]),
              (run, setup / "runs" / profile["run_id"])]
    for path in [prep, run] + [dest for _, dest in copies]:
        require_fresh(path)
    if Path(sys.prefix) != Path(baseline["venv"]) or Path.home() != Path("/home/yhong"):
        raise ValueError("用户目录或Python虚拟环境不同")
    env = dict(os.environ, LC_ALL="C", CC_ANALYZER_BIN="clangsa:/usr/bin/clang-18")
    if env.get("CC_TEST_LABELS_DIR"):
        raise ValueError("自定义labels覆盖未清除")
    env.pop("CC_TEST_LABELS_DIR", None)
    base = Path.home() / "comp5355"
    prep.mkdir(parents=True)
    status = 65
    analysis_status = None
    try:
        rows = [file_check(item) for item in baseline["files"]]
        if not all(item["passed"] for item in rows):
            write_json(prep / "Input_Check.json", {"passed": False, "files": rows})
            raise ValueError("现有输入与已验收基准不符")
        os_release = platform.freedesktop_os_release()
        if platform.machine() != "x86_64" or os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID") != "24.04":
            raise ValueError("系统不符Ubuntu24.04/x86_64")
        versions = {name: importlib.metadata.version(name) for name in baseline["python_packages"]}
        if versions != baseline["python_packages"]:
            raise ValueError("固定Python工具版本不符")
        for name, spec in baseline["version_queries"].items():
            prefix = "version-" + name.lower().replace(" ", "-")
            code = run_saved(prep, prefix, spec["argv"], base, env)
            result = {"exit_code": code, "stdout": (prep / (prefix + "-stdout.txt")).read_text(),
                      "stderr": (prep / (prefix + "-stderr.txt")).read_text()}
            if not version_matches(result, spec):
                raise ValueError(name + "版本不符")
        if read_json(Path(baseline["database"])) != read_json(docs / baseline["database_baseline"]):
            raise ValueError("真实数据库与旧验收基准不同")
        write_json(prep / "Input_Check.json", {"passed": True, "files": rows, "packages": versions,
                   "database_actions": 1, "checked_utc": datetime.now(timezone.utc).isoformat()})
        if run_saved(prep, "environment", ["bash", str(docs / "scripts/capture_environment.sh"),
                                             str(prep / "environment")], base, env) != 0:
            raise ValueError("当前完整环境快照失败")
        cc = profile["analysis_argv"][0]
        if run_saved(prep, "codechecker-version", [cc, "version"], base, env) != 0:
            raise ValueError("CodeChecker版本查询失败")
        version_output = (prep / "codechecker-version-stdout.txt").read_text()
        if profile["codechecker_commit"] not in version_output:
            raise ValueError("CodeChecker提交版本不符")
        if run_saved(prep, "checkers", [cc, "checkers", "--analyzers", "clangsa", "--details", "--output", "json"], base, env) != 0:
            raise ValueError("检查器快照失败")
        if checker_dictionary(read_json(prep / "checkers-stdout.txt")) != profile["checker_dictionary"]:
            raise ValueError("当前完整检查器字典与旧实验不同，请返回输出核对")
        print("前置核对通过；开始FORM-P03-CC-001完整clangsa计时分析，1条C89动作。", flush=True)
        analysis_status = subprocess.run(["bash", str(docs / "scripts/measure_run.sh"), profile["run_id"],
                                         str(run), "--", *profile["analysis_argv"]],
                                        cwd=base, env=env, check=False).returncode
        if not (run / "exit-code.txt").is_file():
            raise ValueError("记录器没有保存实际分析退出码")
        shutil.copyfile(setup / "CodeChecker_Profile.json", run / "prepared-profile.json")
        shutil.copyfile(Path(baseline["database"]), run / "compile_commands.input.json")
        write_json(run / "Environment_Association.json", {"current_environment": str(prep / "environment"),
                   "pre_analysis_checks": str(prep), "accepted_preflight": profile["accepted_preflight"]})
        print("分析结束；状态和诊断parse在计时区间外执行。", flush=True)
        statuses = {}
        for name, argv in [("status", [cc, "parse", "--status", "--detailed", str(run / "reports")]),
                           ("findings", [cc, "parse", str(run / "reports")])]:
            statuses[name] = run_saved(run, name, argv, base, env)
        after = [file_check(item) for item in baseline["files"]]
        write_json(run / "Input_After_Check.json", {"passed": all(row["passed"] for row in after), "files": after})
        summary = summarize(run, profile)
        summary["auxiliary_exit_codes"] = statuses
        summary["analysis_exit_code"] = analysis_status
        write_json(run / "Result_Summary_Pending.json", summary)
        status = analysis_status if analysis_status != 0 else (0 if statuses["status"] == 0
                 and statuses["findings"] in {0, 2} and all(row["passed"] for row in after) else 65)
        for title, filename, limit in [("分析日志", "stdout.txt", 18), ("分析stderr", "stderr.txt", 12),
                                       ("外部计时", "time.txt", 30), ("诊断展示", "findings-stdout.txt", 32)]:
            print("\n" + title + "：")
            print("\n".join((run / filename).read_text(errors="replace").splitlines()[-limit:]))
        print("\n成功／失败／跳过：1／0／0；合法plist：1；保存诊断：", summary["saved_diagnostics"])
        print("分析退出码：", analysis_status, "；辅助退出码：", statuses)
        print("普通parse返回2表示有报告。新成本及新旧输出对应关系待助手验收。")
    except (OSError, ValueError, KeyError, TypeError, importlib.metadata.PackageNotFoundError) as error:
        print("需要核对：" + str(error), file=sys.stderr)
        write_json(prep / "Failure.json", {"error": str(error), "analysis_exit_code": analysis_status})
        status = analysis_status if analysis_status not in {None, 0} else 65
    finally:
        write_json(prep / "Execution_Status.json", {"wrapper_exit_code": status,
                   "analysis_exit_code": analysis_status, "run_id": profile["run_id"],
                   "status": "pending_assistant_acceptance", "not_a_completed_comparison": True})
        for source, dest in copies:
            if source.is_dir():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, dest)
                print("已保存课程目录副本：", dest)
    return status


if __name__ == "__main__":
    sys.exit(main())
