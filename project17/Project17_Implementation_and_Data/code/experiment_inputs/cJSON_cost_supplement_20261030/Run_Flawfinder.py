"""用户执行完整Flawfinder成本补测；所有准备、摘要和复制均在计时外。"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

from Run_CodeChecker import read_json, require_fresh, run_saved, write_json
from Verify_Preflight import file_check, version_matches


def parse_report(text, expected_inputs):
    """提取实际显示条目及原始块；历史26条不作为验收常量。"""
    examined = re.findall(r"^Examining ([^\r\n]+)\r?$", text, re.M)
    if examined != expected_inputs:
        raise ValueError("实际Examining文件与两项固定输入不符")
    if not re.search(r"^Flawfinder version 2\.0\.20,", text, re.M):
        raise ValueError("分析报告版本不是2.0.20")
    summary_headers = list(re.finditer(r"^ANALYSIS SUMMARY:\r?$", text, re.M))
    if len(summary_headers) != 1:
        raise ValueError("报告缺少唯一ANALYSIS SUMMARY")
    summary_start = summary_headers[0].start()
    header_pattern = r"^(/home/[^:\n]+):(\d+):(\d+):[ \t]+\[(\d+)\] \(([^)]+)\) (\w+):\r?$"
    headers = list(re.finditer(header_pattern, text, re.M))
    if any(item.start() >= summary_start for item in headers):
        raise ValueError("摘要后出现候选头，报告结构需核对")
    findings = []
    for index, item in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else summary_start
        raw_block = text[item.start():end]
        if item[1] not in expected_inputs or not 1 <= int(item[4]) <= 5:
            raise ValueError("显示条目的位置或风险等级不在固定范围")
        body = raw_block.splitlines()[1:]
        message = " ".join(line.strip() for line in body
                           if line.startswith("  ") and not line.startswith("    "))
        if not message:
            raise ValueError("显示条目没有可提取的诊断消息")
        findings.append({"display_ordinal": index + 1, "file": item[1],
                         "line": int(item[2]), "column": int(item[3]),
                         "risk_level": int(item[4]), "category": item[5], "rule": item[6],
                         "message": message, "raw_report_block": raw_block,
                         "report_start_line": text.count("\n", 0, item.start()) + 1,
                         "report_end_line": text.count("\n", 0, end - 1) + 1})
    summary = text[summary_start:]
    hits = re.search(r"^Hits = (\d+)\r?$", summary, re.M)
    levels = re.search(r"^Hits@level = (.+)\r?$", summary, re.M)
    cumulative = re.search(r"^Hits@level\+ = (.+)\r?$", summary, re.M)
    minimum = re.search(r"^Minimum risk level = (\d+)\r?$", summary, re.M)
    lines = re.search(r"^Lines analyzed = (\d+) in approximately ([0-9.]+) seconds", summary, re.M)
    sloc = re.search(r"^Physical Source Lines of Code \(SLOC\) = (\d+)\r?$", summary, re.M)
    if any(value is None for value in (hits, levels, cumulative, minimum, lines, sloc)):
        raise ValueError("分析摘要字段不完整")
    per_level = {int(key): int(value) for key, value in re.findall(r"\[(\d)\]\s+(\d+)", levels[1])}
    at_least = {int(key): int(value) for key, value in re.findall(r"\[(\d)\+\]\s+(\d+)", cumulative[1])}
    displayed_levels = Counter(row["risk_level"] for row in findings)
    if (set(per_level) != set(range(6)) or set(at_least) != set(range(6))
            or int(minimum[1]) != 1 or int(hits[1]) != len(findings)
            or any(displayed_levels[level] != per_level[level] for level in range(1, 6))
            or any(at_least[level] != sum(per_level[i] for i in range(level, 6)) for level in range(6))):
        raise ValueError("显示命中、等级摘要或累计计数不一致")
    if int(lines[1]) <= 0 or int(sloc[1]) <= 0:
        raise ValueError("工具报告没有非空文本处理证据")
    return {"examined_files": examined, "displayed_hits": len(findings),
            "displayed_risk_level_counts": dict(sorted(displayed_levels.items())),
            "summary_risk_level_counts_including_filtered": per_level,
            "summary_cumulative_level_counts": at_least,
            "filtered_level_zero_count": per_level[0], "minimum_risk_level": 1,
            "tool_reported_lines_analyzed": int(lines[1]), "tool_reported_sloc": int(sloc[1]),
            "tool_reported_approximate_seconds": lines[2], "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("实际扫描仅由用户在Ubuntu执行")
    docs = args.docs.resolve()
    setup = docs / "review_evidence/cJSON_cost_supplement_20261030"
    profile = read_json(setup / "Flawfinder_Profile.json")
    baseline = read_json(docs / profile["input_baseline"])
    run = Path(profile["run_directory"])
    prep = Path(profile["preparation_directory"])
    copies = [(prep, setup / "execution_preparation" / profile["run_id"]),
              (run, setup / "runs" / profile["run_id"])]
    for path in [prep, run] + [destination for _, destination in copies]:
        require_fresh(path)
    if Path(sys.prefix) != Path(baseline["venv"]) or Path.home() != Path("/home/yhong"):
        raise ValueError("用户目录或Python虚拟环境不同")
    base = Path.home() / "comp5355"
    env = dict(os.environ, LC_ALL="C")
    prep.mkdir(parents=True)
    status = 65
    analysis_status = None
    try:
        accepted_cc = read_json(docs / profile["accepted_codechecker"])
        if accepted_cc.get("run_id") != "FORM-P03-CC-001" or accepted_cc.get("accepted") is not True:
            raise ValueError("前一步CodeChecker补测尚无已验收记录")
        rows = [file_check(item) for item in baseline["files"]]
        if len(rows) != 7 or not all(row["passed"] for row in rows):
            write_json(prep / "Input_Check.json", {"passed": False, "files": rows})
            raise ValueError("7项现有输入与已验收基准不符")
        if (profile["analysis_argv"][1:5] != ["--minlevel=1", "--neverignore", "--columns", "--context"]
                or profile["analysis_argv"][5:] != profile["input_files"]
                or profile["input_files"] != [item["path"] for item in baseline["files"][:2]]):
            raise ValueError("FF固定参数、输入或顺序不符")
        ff = Path(profile["analysis_argv"][0])
        if str(ff) != baseline["executables"]["Flawfinder"] or not ff.is_file() or not os.access(ff, os.X_OK):
            raise ValueError("固定Flawfinder入口不可用")
        os_release = platform.freedesktop_os_release()
        if (platform.machine() != "x86_64" or os_release.get("ID") != "ubuntu"
                or os_release.get("VERSION_ID") != "24.04"):
            raise ValueError("系统不符Ubuntu24.04/x86_64")
        packages = {name: importlib.metadata.version(name) for name in baseline["python_packages"]}
        if packages != baseline["python_packages"]:
            raise ValueError("固定Python工具包版本不符")
        for name, spec in baseline["version_queries"].items():
            prefix = "version-" + name.lower().replace(" ", "-")
            code = run_saved(prep, prefix, spec["argv"], base, env)
            query_result = {"exit_code": code, "stdout": (prep / (prefix + "-stdout.txt")).read_text(),
                            "stderr": (prep / (prefix + "-stderr.txt")).read_text()}
            if not version_matches(query_result, spec):
                raise ValueError(name + "版本不符")
        if run_saved(prep, "flawfinder-version", [str(ff), "--version"], base, env) != 0:
            raise ValueError("Flawfinder版本查询失败")
        if (prep / "flawfinder-version-stdout.txt").read_text().strip() != profile["tool_version"]:
            raise ValueError("Flawfinder实际入口版本不符")
        if read_json(Path(baseline["database"])) != read_json(docs / baseline["database_baseline"]):
            raise ValueError("真实数据库与旧验收基准不同")
        write_json(prep / "Input_Check.json", {"passed": True, "files": rows,
                   "packages": packages, "checked_utc": datetime.now(timezone.utc).isoformat()})
        environment = prep / "environment"
        if run_saved(prep, "environment", ["bash", str(docs / "scripts/capture_environment.sh"),
                                             str(environment)], base, env) != 0:
            raise ValueError("当前完整环境快照失败")
        required_environment = [environment / name for name in (
            "system.txt", "tool-versions.txt", "time-version.txt", "time-binary.sha256", "recording-scripts.sha256")]
        if not all(path.is_file() and path.stat().st_size > 0 for path in required_environment):
            raise ValueError("当前完整环境快照缺少必需原件")
        print("前置核对通过；开始FORM-P03-FF-001完整Flawfinder计时扫描，2个文本输入。", flush=True)
        analysis_status = subprocess.run([
            "bash", str(docs / "scripts/measure_run.sh"), profile["run_id"], str(run),
            "--", *profile["analysis_argv"]], cwd=base, env=env, check=False).returncode
        if not (run / "exit-code.txt").is_file():
            raise ValueError("记录器没有保存实际扫描退出码")
        if (run / "exit-code.txt").read_text().strip() != str(analysis_status):
            raise ValueError("记录器返回值与保存退出码不一致")
        shutil.copyfile(setup / "Flawfinder_Profile.json", run / "prepared-profile.json")
        shutil.copyfile(setup / "flawfinder-control.sha256", run / "control-manifest.sha256")
        (run / "input-files.txt").write_text("\n".join(profile["input_files"]) + "\n", encoding="utf-8")
        (run / "input-files.sha256").write_text("".join(
            item["sha256"] + "  " + item["path"] + "\n" for item in baseline["files"][:2]), encoding="utf-8")
        write_json(run / "Environment_Association.json", {
            "current_environment": str(environment), "pre_analysis_checks": str(prep),
            "accepted_preflight": profile["accepted_preflight"],
            "accepted_codechecker": profile["accepted_codechecker"],
            "execution_order": "P03 CC已验收后执行FF；CP尚未由本入口执行",
            "tool_result_cache": profile["policies"]["tool_result_cache"]})
        after = [file_check(item) for item in baseline["files"]]
        write_json(run / "Input_After_Check.json", {"passed": all(row["passed"] for row in after), "files": after})
        result = parse_report((run / "stdout.txt").read_bytes().decode("utf-8"), profile["input_files"])
        findings = result.pop("findings")
        write_json(run / "Displayed_Findings.json", {"run_id": profile["run_id"], "findings": findings,
                   "mapping_status": "pending_assistant_comparison_with_PRE-P03-FF-001"})
        result.update({"status": "machine_checks_passed_pending_assistant_acceptance",
                       "run_id": profile["run_id"], "analysis_exit_code": analysis_status,
                       "stderr_bytes": (run / "stderr.txt").stat().st_size,
                       "input_after_passed": all(row["passed"] for row in after),
                       "historical_count_is_not_acceptance_gate": True,
                       "meaning": "命中不是漏洞；旧核查判断只在诊断实质匹配后复用；新外部成本待助手验收。"})
        status = analysis_status if analysis_status != 0 else (0 if all(row["passed"] for row in after) else 65)
        if status != 0:
            result["status"] = "needs_review"
        write_json(run / "Result_Summary_Pending.json", result)
        for title, filename, limit in [("外部计时", "time.txt", 30), ("扫描摘要", "stdout.txt", 30),
                                       ("扫描stderr", "stderr.txt", 12)]:
            print("\n" + title + "：")
            print("\n".join((run / filename).read_text(errors="replace").splitlines()[-limit:]))
        print("\n实际文本文件：2；显示命中：", result["displayed_hits"], "；扫描退出码：", analysis_status)
        print("等级0、累计0+及工具自报时间另列；新旧条目映射和成本待助手验收。")
    except (OSError, ValueError, KeyError, TypeError, importlib.metadata.PackageNotFoundError) as error:
        print("需要核对：" + str(error), file=sys.stderr)
        write_json(prep / "Failure.json", {"error": str(error), "analysis_exit_code": analysis_status})
        status = analysis_status if analysis_status not in {None, 0} else 65
    finally:
        write_json(prep / "Execution_Status.json", {"wrapper_exit_code_before_receipt_copy": status,
                   "analysis_exit_code": analysis_status, "run_id": profile["run_id"],
                   "status": "pending_assistant_acceptance", "not_a_completed_comparison": True})
        copy_errors = []
        for source, destination in copies:
            if source.is_dir():
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source, destination)
                    print("已保存课程目录副本：", destination)
                except OSError as error:
                    copy_errors.append({"source": str(source), "destination": str(destination), "error": str(error)})
                    print("课程副本复制失败，Linux原件已保留：" + str(error), file=sys.stderr)
        if copy_errors:
            write_json(prep / "Receipt_Copy_Failure.json", {"errors": copy_errors})
            status = status or 74
    return status


if __name__ == "__main__":
    sys.exit(main())
