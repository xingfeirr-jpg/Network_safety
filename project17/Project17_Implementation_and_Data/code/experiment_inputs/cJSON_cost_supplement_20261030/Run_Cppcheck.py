"""用户执行完整Cppcheck成本补测；准备、XML提取及复制均在计时外。"""
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
import xml.etree.ElementTree as ET

from Run_CodeChecker import read_json, require_fresh, run_saved, write_json
from Verify_Preflight import file_check, version_matches


BLOCKING_IDS = {"syntaxError", "internalError", "cppcheckError", "preprocessorError",
                "preprocessorErrorDirective", "unknownMacro"}


def extract_xml(data, expected_version):
    """读取原始XML诊断，保留完整位置链和原始块；不判定告警真假。"""
    text = data.decode("utf-8")
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise ValueError("XML包含非预期DTD或实体声明")
    root = ET.fromstring(data)
    tools = root.findall("cppcheck")
    errors_nodes = root.findall("errors")
    if (root.tag != "results" or root.get("version") != "2" or len(tools) != 1
            or tools[0].get("version") != expected_version or len(errors_nodes) != 1):
        raise ValueError("Cppcheck XML结构、格式或版本不符")
    errors = list(errors_nodes[0])
    if any(item.tag != "error" for item in errors):
        raise ValueError("errors节点包含未知子元素")
    raw_blocks = list(re.finditer(r"<error\b[^>]*?/>|<error\b[^>]*>.*?</error>", text, re.S))
    if len(raw_blocks) != len(errors):
        raise ValueError("XML原始诊断块与解析元素数量不一致")
    records = []
    for index, (error, block) in enumerate(zip(errors, raw_blocks), 1):
        if not all(error.get(key) for key in ("id", "severity", "msg")):
            raise ValueError("诊断缺少ID、severity或原消息")
        if ET.fromstring(block[0]).attrib != error.attrib:
            raise ValueError("诊断原始块与解析属性不一致")
        role = "information" if error.get("severity") == "information" else (
            "configuration_blocker" if error.get("id") in BLOCKING_IDS else "source_candidate")
        records.append({"xml_ordinal": index, "record_kind": role,
                        "attributes": dict(error.attrib),
                        "locations": [dict(location.attrib) for location in error.findall("location")],
                        "symbols": [symbol.text or "" for symbol in error.findall("symbol")],
                        "raw_xml_block": block[0],
                        "xml_start_line": text.count("\n", 0, block.start()) + 1,
                        "xml_end_line": text.count("\n", 0, block.end() - 1) + 1})
    return {"xml_format_version": "2", "cppcheck_version": expected_version,
            "xml_diagnostic_count": len(records),
            "source_candidate_count": sum(row["record_kind"] == "source_candidate" for row in records),
            "information_count": sum(row["record_kind"] == "information" for row in records),
            "configuration_blocker_count": sum(row["record_kind"] == "configuration_blocker" for row in records),
            "severity_counts": dict(Counter(row["attributes"]["severity"] for row in records)),
            "rule_counts": dict(Counter(row["attributes"]["id"] for row in records)),
            "blocking_diagnostic_ids": sorted({row["attributes"]["id"] for row in records
                                              if row["attributes"]["id"] in BLOCKING_IDS}),
            "records": records}


def checker_dictionary(text):
    rows = re.findall(r"^(Yes|No)[ \t]+(\S+)", text, re.M)
    result = {name: state == "Yes" for state, name in rows}
    if not rows or len(rows) != len(result):
        raise ValueError("检查器报告没有非空、唯一的Yes/No字典")
    return result


def coverage_evidence(progress, checker_text, cache_files, source):
    checking_files = re.findall(r"^Checking ([^:\r\n]+)(?: \.\.\.|:.*)$", progress, re.M)
    mappings = []
    for line in cache_files.splitlines():
        slot, separator, file = line.partition("::")
        if not separator or not slot or not file:
            raise ValueError("Cppcheck cache/files.txt存在无法识别的映射")
        mappings.append({"cache_slot": slot, "source_file": file})
    no_critical = "No critical errors, all files were checked." in checker_text
    return {"intended_database_actions": 1,
            "observed_checking_sources": sorted(set(checking_files)),
            "observed_cache_mappings": mappings,
            "checker_report_no_critical_errors": no_critical,
            "machine_scope_evidence_matches": bool(checking_files) and set(checking_files) == {source}
                and len(mappings) == 1 and mappings[0]["source_file"] == source and no_critical,
            "coverage_acceptance": "pending_assistant_review_of_progress_cache_checkers_and_XML",
            "accepted_succeeded_actions": None, "accepted_failed_actions": None, "accepted_skipped_actions": None,
            "meaning": "观察到的处理证据不是穷尽路径证明；助手验收前不填已验收成功／失败／跳过数。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("实际Cppcheck分析仅由用户在Ubuntu执行")
    docs = args.docs.resolve()
    setup = docs / "review_evidence/cJSON_cost_supplement_20261030"
    profile = read_json(setup / "Cppcheck_Profile.json")
    baseline = read_json(docs / profile["input_baseline"])
    legacy = read_json(docs / profile["historical_summary"])
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
        for key, expected in [("accepted_codechecker", "FORM-P03-CC-001"),
                              ("accepted_flawfinder", "FORM-P03-FF-001")]:
            acceptance = read_json(docs / profile[key])
            if acceptance.get("accepted") is not True or acceptance.get("run_id") != expected:
                raise ValueError("前一步尚无已验收记录：" + expected)
        rows = [file_check(item) for item in baseline["files"]]
        if len(rows) != 7 or not all(row["passed"] for row in rows):
            write_json(prep / "Input_Check.json", {"passed": False, "files": rows})
            raise ValueError("7项现有输入与已验收基准不符")
        expected_arguments = [
            "--cppcheck-build-dir=" + str(run / "cache") if arg == "--cppcheck-build-dir=cache" else
            "--checkers-report=" + str(run / "checkers.txt") if arg == "--checkers-report=checkers.txt" else arg
            for arg in legacy["arguments"]]
        expected_argv = [baseline["executables"]["Cppcheck"], "--project=" + baseline["database"], *expected_arguments]
        if (profile["analysis_argv"] != expected_argv or profile["database"] != baseline["database"]
                or profile["tool_version"] != legacy["toolVersion"]
                or profile["ubuntu_package"] != legacy["ubuntuPackage"]):
            raise ValueError("Cppcheck固定argv或版本与旧配置不符")
        executable = Path(profile["analysis_argv"][0])
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("固定Cppcheck入口不可用")
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
        database = read_json(Path(baseline["database"]))
        if (database != read_json(docs / baseline["database_baseline"]) or len(database) != 1
                or database[0]["file"] != profile["source"]):
            raise ValueError("真实数据库与原1条C89动作不同")
        write_json(prep / "Input_Check.json", {"passed": True, "files": rows, "packages": packages,
                   "database_actions": len(database), "checked_utc": datetime.now(timezone.utc).isoformat()})
        environment = prep / "environment"
        if run_saved(prep, "environment", ["bash", str(docs / "scripts/capture_environment.sh"),
                                             str(environment)], base, env) != 0:
            raise ValueError("当前完整环境快照失败")
        required_environment = [environment / name for name in (
            "system.txt", "tool-versions.txt", "time-version.txt", "time-binary.sha256", "recording-scripts.sha256")]
        if not all(path.is_file() and path.stat().st_size > 0 for path in required_environment):
            raise ValueError("当前完整环境快照缺少必需原件")
        print("前置核对通过；开始FORM-P03-CP-001完整Cppcheck计时分析，原1条C89动作、新缓存。", flush=True)
        analysis_status = subprocess.run([
            "bash", str(docs / "scripts/measure_run.sh"), profile["run_id"], str(run),
            "--", *profile["analysis_argv"]], cwd=base, env=env, check=False).returncode
        after = [file_check(item) for item in baseline["files"]]
        if run.is_dir():
            write_json(run / "Input_After_Check.json", {"passed": all(row["passed"] for row in after), "files": after})
        if not (run / "exit-code.txt").is_file():
            raise ValueError("记录器没有保存实际分析退出码")
        if (run / "exit-code.txt").read_text().strip() != str(analysis_status):
            raise ValueError("记录器返回值与保存退出码不一致")
        shutil.copyfile(setup / "Cppcheck_Profile.json", run / "prepared-profile.json")
        shutil.copyfile(setup / "cppcheck-control.sha256", run / "control-manifest.sha256")
        shutil.copyfile(Path(baseline["database"]), run / "compile_commands.input.json")
        write_json(run / "Environment_Association.json", {
            "current_environment": str(environment), "pre_analysis_checks": str(prep),
            "accepted_preflight": profile["accepted_preflight"],
            "accepted_codechecker": profile["accepted_codechecker"],
            "accepted_flawfinder": profile["accepted_flawfinder"],
            "execution_order": "P03 CC和FF已验收后执行CP",
            "tool_result_cache": profile["policies"]["tool_result_cache"]})
        result = extract_xml((run / "stderr.txt").read_bytes(), profile["tool_version"])
        records = result.pop("records")
        for filename, role in [("Source_Candidates.json", "source_candidate"),
                               ("Information_Only.json", "information"),
                               ("Configuration_Blockers.json", "configuration_blocker")]:
            write_json(run / filename, {"run_id": profile["run_id"],
                       "records": [row for row in records if row["record_kind"] == role],
                       "mapping_status": "pending_assistant_comparison_with_PRE-P03-CP-001"})
        checker_text = (run / "checkers.txt").read_text()
        old_checkers = checker_dictionary((docs / profile["historical_checkers"]).read_text())
        current_checkers = checker_dictionary(checker_text)
        evidence = coverage_evidence((run / "stdout.txt").read_text(), checker_text,
                                     (run / "cache/files.txt").read_text(), profile["source"])
        evidence["cache_slots_exist_nonempty"] = all(
            (run / "cache" / item["cache_slot"]).is_file()
            and (run / "cache" / item["cache_slot"]).stat().st_size > 0
            for item in evidence["observed_cache_mappings"])
        write_json(run / "Coverage_Evidence_Pending.json", evidence)
        checker_matches = current_checkers == old_checkers
        machine_passed = (analysis_status == 0 and all(row["passed"] for row in after)
                          and evidence["machine_scope_evidence_matches"]
                          and evidence["cache_slots_exist_nonempty"] and checker_matches
                          and not result["blocking_diagnostic_ids"])
        result.update({"status": "machine_evidence_ready_pending_assistant_acceptance" if machine_passed else "needs_review",
                       "run_id": profile["run_id"], "analysis_exit_code": analysis_status,
                       "input_after_passed": all(row["passed"] for row in after),
                       "checker_dictionary_matches_old": checker_matches,
                       "enabled_checker_entries": sum(current_checkers.values()),
                       "checker_entry_count": len(current_checkers),
                       "coverage_acceptance": evidence["coverage_acceptance"],
                       "historical_count_is_not_acceptance_gate": True,
                       "meaning": "XML元素和location链分别保留；信息不计源码候选；新旧映射及实际覆盖、成本仍待助手验收。"})
        write_json(run / "Result_Summary_Pending.json", result)
        status = analysis_status if analysis_status != 0 else (0 if machine_passed else 65)
        for title, filename, limit in [("外部计时", "time.txt", 30), ("处理日志", "stdout.txt", 14),
                                       ("检查器报告开头", "checkers.txt", 6)]:
            print("\n" + title + "：")
            print("\n".join((run / filename).read_text(errors="replace").splitlines()[:limit]))
        print("\nXML诊断：", result["xml_diagnostic_count"], "；源码候选：", result["source_candidate_count"],
              "；信息：", result["information_count"], "；配置阻断：", result["configuration_blocker_count"])
        print("分析退出码：", analysis_status, "；实际覆盖、新旧诊断和外部成本待助手验收。")
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, importlib.metadata.PackageNotFoundError) as error:
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
