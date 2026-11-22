"""仅从已保存证据生成最终比较表；不调用WSL、编译器、检测器或CodeChecker。"""
import csv
import hashlib
import io
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path, PurePosixPath

PACKAGE = Path(__file__).resolve().parents[1]
CODE = PACKAGE / "code"
RECORDS = PACKAGE / "data" / "records"
OUT = RECORDS / "formal_comparison_20261030"
SUPPLEMENT = RECORDS / "cJSON_cost_supplement_20261030"
SYNTHESIS = RECORDS / "ten_project_synthesis_20261029"


# Historical source-review notes are stored with the local submission checks.
LOCAL_REVIEW_RECORDS = {
    "Project17_Experiment_Protocol.md",
    "review_evidence/Expat_Pretest_Record.md",
    "review_evidence/Json_C_Pretest_Record.md",
    "review_evidence/LZ4_Pretest_Record.md",
    "review_evidence/Libjpeg_Turbo_Pretest_Record.md",
    "review_evidence/Libpng_Pretest_Record.md",
    "review_evidence/Libyaml_Pretest_Record.md",
    "review_evidence/Utf8proc_Pretest_Record.md",
    "review_evidence/YYJSON_Pretest_Record.md",
    "review_evidence/cJSON_Pretest_Record.md",
    "review_evidence/zlib_Pretest_Record.md",
    "review_evidence/cJSON_review/Review_Ledger.csv",
    "review_evidence/cJSON_review/Review_Summary.json",
    "review_evidence/expat_review/Review_Ledger.csv",
    "review_evidence/expat_review/Review_Summary.json",
    "review_evidence/json_c_review/Review_Ledger.csv",
    "review_evidence/json_c_review/Review_Summary.json",
    "review_evidence/libjpeg_turbo_review/Review_Ledger.csv",
    "review_evidence/libjpeg_turbo_review/Review_Summary.json",
    "review_evidence/libpng_review/Review_Ledger.csv",
    "review_evidence/libpng_review/Review_Summary.json",
    "review_evidence/libyaml_review/Review_Ledger.csv",
    "review_evidence/libyaml_review/Review_Summary.json",
    "review_evidence/lz4_review/Review_Ledger.csv",
    "review_evidence/lz4_review/Review_Summary.json",
    "review_evidence/utf8proc_review/Review_Ledger.csv",
    "review_evidence/utf8proc_review/Review_Summary.json",
    "review_evidence/yyjson_review/Review_Ledger.csv",
    "review_evidence/yyjson_review/Review_Summary.json",
    "review_evidence/zlib_review/Review_Ledger.csv",
    "review_evidence/zlib_review/Review_Summary.json",
}


def input_path(name):
    if name.startswith("review_evidence/"):
        relative = name.removeprefix("review_evidence/")
        record = RECORDS / relative
        return record if record.is_file() else CODE / "experiment_inputs" / relative
    return PACKAGE / "data" / name


def check_available_record(name):
    path = PurePosixPath(name)
    archived_cache = (
        path.parent.name == "cache"
        and path.name != "files.txt"
        and not (
            path.parent.as_posix() == "review_evidence/libjpeg_turbo_pretest_20261029/Cppcheck/cache"
            and path.suffix == ".a1"
        )
    )
    is_local_record = name in LOCAL_REVIEW_RECORDS or archived_cache
    return not is_local_record or input_path(name).is_file()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stamp(path, name=None):
    return {"path": name or "review_evidence/" + path.relative_to(RECORDS).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest(path)}


def read_csv(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


def main():
    baseline_path = OUT / "Reuse_Assessment.json"
    baseline = read_json(baseline_path)
    protected = {
        name: expected
        for name, expected in read_json(OUT / "Before_Integrity.json")["files"].items()
        if check_available_record(name)
    }
    for name, expected in protected.items():
        actual = stamp(input_path(name), name)
        assert actual["sha256"] == expected["sha256"], name
        assert actual["bytes"] == expected["bytes"], name
    candidates = read_csv(SYNTHESIS / "Candidate_Review_Combined.csv")
    projects = read_csv(SYNTHESIS / "Project_Summary.csv")
    tools = read_csv(SYNTHESIS / "Tool_Summary.csv")
    assert len(candidates) == len({r["candidateKey"] for r in candidates}) == 725
    assert Counter(r["normalizedFinalLabel"] for r in candidates) == {
        "原风险误报": 648, "有依据": 62, "无法判断": 15}
    acceptances = {}
    raw_count = 0
    for key, filename in (("FF", "Flawfinder"), ("CP", "Cppcheck"), ("CC", "CodeChecker")):
        path = SUPPLEMENT / (filename + "_Acceptance.json")
        acceptance = read_json(path)
        assert acceptance["accepted"] is True
        assert acceptance["old_new_mapping"]["new_candidates_requiring_review"] == 0
        for name, expected in acceptance["raw_receipt_manifest"].items():
            if not check_available_record("review_evidence/cJSON_cost_supplement_20261030/" + name):
                continue
            file = SUPPLEMENT / name
            assert digest(file) == expected["sha256"], name
            assert file.stat().st_size == expected["bytes"], name
            raw_count += 1
        acceptances[key] = (acceptance, path)

    rows = []
    for ordinal, source in enumerate(baseline["rows"], 1):
        assert source["result_decision"] == "可复用"
        selected = [r for r in candidates if r["projectId"] == source["project_id"]
                    and r["tool"] == source["tool"]]
        assert len(selected) == source["output"]["candidate_count"]
        for evidence in source["evidence"]:
            if check_available_record(evidence["path"]):
                assert digest(input_path(evidence["path"])) == evidence["sha256"], evidence["path"]
        resource = deepcopy(source["external_resources"])
        cost_run = source["run_id"]
        cost_acceptance = None
        cost_coverage = None
        if source["project_id"] == "P03":
            acceptance, path = acceptances[source["tool_key"]]
            measurement = acceptance["measurement"]
            cost_run = acceptance["run_id"]
            time_path = SUPPLEMENT / "runs" / cost_run / "time.txt"
            resource = {
                "wall_seconds": measurement["wall_seconds"],
                "user_seconds": measurement["user_seconds"],
                "system_seconds": measurement["system_seconds"],
                "max_rss_kib": measurement.get("max_rss_kib", measurement.get("maximum_rss_kib")),
                "timed_invocation_exit_code": acceptance["analysis_exit_code"]
                if source["tool_key"] != "FF" else 0,
                "source_file": "review_evidence/" + time_path.relative_to(RECORDS).as_posix(),
                "source_sha256": digest(time_path),
                "boundary": measurement["timing_boundary"],
                "sample_count": 1,
                "os_page_cache": measurement["os_page_cache"],
                "rss_meaning": "GNU time最大RSS，Linux KiB；不是全进程树RSS总峰值",
            }
            cost_acceptance = stamp(path)
            cost_coverage = deepcopy(acceptance.get("coverage", {
                "successful_actions": acceptance.get("successful_actions"),
                "failed_actions": acceptance.get("failed_actions"),
                "skipped_actions": acceptance.get("skipped_actions"),
                "actual_text_inputs": acceptance.get("actual_text_inputs")
            }))
        assert all(resource[k] is not None for k in
                   ("wall_seconds", "user_seconds", "system_seconds", "max_rss_kib"))
        assert digest(input_path(resource["source_file"])) == resource["source_sha256"]
        labels = Counter(r["normalizedFinalLabel"] for r in selected)
        rows.append({
            "cell": ordinal, "project_id": source["project_id"], "project": source["project"],
            "version": source["version"], "tool": source["tool"], "tool_key": source["tool_key"],
            "policy": "comparison-v1", "adopted_date": "2026-10-30",
            "result_status": "已按声明范围验收并采用", "result_run_id": source["run_id"],
            "result_original_phase": source["original_phase"],
            "cost_status": "已验收；单次描述性成本", "cost_run_id": cost_run,
            "cost_source_kind": "新完整分析及旧输出映射" if cost_acceptance else "已验收旧预试外部记录",
            "input": deepcopy(source["input"]), "result_coverage": deepcopy(source["coverage"]),
            "output": deepcopy(source["output"]), "configuration": deepcopy(source["configuration"]),
            "result_runtime_metadata": deepcopy(source["runtime_metadata"]),
            "external_resources": resource, "new_cost_acceptance": cost_acceptance,
            "new_cost_coverage": cost_coverage,
            "judgments": {"reviewed_candidate_entries": len(selected),
                          "original_risk_false_positive": labels["原风险误报"],
                          "supported_diagnoses": labels["有依据"],
                          "undetermined": labels["无法判断"], "unreviewed": 0},
            "result_evidence": deepcopy(source["evidence"]),
            "limits": deepcopy(source["limits"]),
            "baseline_assessment_row": ordinal,
        })
    assert len(rows) == len({(r["project_id"], r["tool_key"]) for r in rows}) == 30
    assert sum(r["output"]["candidate_count"] for r in rows) == 725
    assert sum(r["output"]["information_items"] or 0 for r in rows) == 213
    for project in projects:
        selected = [r for r in candidates if r["projectId"] == project["projectId"]]
        counts = Counter(r["normalizedFinalLabel"] for r in selected)
        assert len(selected) == int(project["registeredCandidates"])
        assert counts["原风险误报"] == int(project["originalRiskFalsePositive"])
        assert counts["有依据"] == int(project["supportedDiagnoses"])
        assert counts["无法判断"] == int(project["undetermined"])
    summary = {
        "projects": 10, "accepted_result_cells": 30, "accepted_external_cost_cells": 30,
        "reused_external_cost_cells": 27, "new_complete_analysis_runs": 3,
        "new_complete_analysis_runs_are_not_30": True, "candidate_entries": 725,
        "original_risk_false_positive": 648, "supported_diagnoses": 62,
        "undetermined": 15, "unreviewed": 0, "cppcheck_information_items": 213,
        "codechecker_saved_diagnostics": 73, "codechecker_displayed_reports": 71,
        "globally_deduplicated_bug_count": None, "global_cross_tool_overlap_rate": None,
    }
    sources = [baseline_path, OUT / "Frozen_Configuration.json",
               OUT / "Before_Integrity.json", SYNTHESIS / "Candidate_Review_Combined.csv",
               SYNTHESIS / "Project_Summary.csv", SYNTHESIS / "Tool_Summary.csv"]
    sources += [p for _, p in acceptances.values()]
    data = {
        "schema": "project17-final-comparison-v1", "date": "2026-10-30",
        "meaning": "已批准旧检测结果的回顾性采用；27旧成本加3新完整分析成本。PRE原目的和原件保持。",
        "summary": summary, "sources": [stamp(p) for p in sources],
        "counting_boundary": "FF显示hit／CP非information XML元素／CC保存plist诊断；不是独立bug或安全漏洞数。",
        "review_boundary": "同一助手体系AI全量源码核查；限定用户阅读另列；不称独立人工复核。",
        "timing_boundary": "完整工具分析进程；准备、版本/哈希检查、独立parse和AI核查在外；每格单次自然页缓存。",
        "coverage_boundary": "成功文本或编译动作仅说明实际分析范围，不是程序路径覆盖率；旧FF失败/跳过未单独记录的null保持。",
        "overlap_boundary": "尚未完成全局独立问题的统一跨工具匹配；不按行号、规则、hash或未分组占位值推算重合/独有漏洞数。",
        "rows": rows,
    }
    (OUT / "Final_Matrix.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    flat = []
    for row in rows:
        flat.append({k: row[k] for k in
                     ("project_id", "project", "version", "tool", "tool_key", "result_run_id", "cost_run_id")})
        target = flat[-1]
        target.update(input_unit=row["input"]["unit"], intended_count=row["input"]["intended_count"],
                      succeeded_or_examined=row["result_coverage"]["succeeded_or_examined"],
                      failed=row["result_coverage"]["failed"], skipped=row["result_coverage"]["skipped"])
        target.update(row["output"])
        target.update(row["judgments"])
        target.update({k: row["external_resources"][k] for k in
                       ("wall_seconds", "user_seconds", "system_seconds", "max_rss_kib", "source_file", "source_sha256")})
        target["result_status"] = row["result_status"]
        target["cost_status"] = row["cost_status"]
    with (OUT / "Final_Matrix.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    lines = ["# 十项目最终比较数据（2026-10-30）", "",
             "30组结果已按comparison-v1采用；30组外部成本＝27组旧记录＋3组cJSON新完整分析。实际新增FORM分析为3次，旧PRE原阶段保持。",
             "", "数据入口：[逐组JSON](./Final_Matrix.json)、[30行CSV](./Final_Matrix.csv)、[最终核验](./Final_Verification.json)、[主报告第4章](../../Project17_Report_Framework.md#4-实验结果)。",
             "", "## 候选及核查汇总", "",
             "| 工具 | 原始候选条目 | 原风险误报 | 有依据诊断 | 无法判断 | 未审 |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for tool in tools:
        lines.append("| " + " | ".join(tool[k] for k in ("tool", "registeredCandidates", "originalRiskFalsePositive", "supportedDiagnoses", "undetermined", "unreviewed")) + " |")
    lines += ["| 合计 | 725 | 648 | 62 | 15 | 0 |", "",
              "725为原始登记候选，非去重漏洞数；62有据包括质量、可移植性与条件性风险。CP的213信息另列；CC保存73／普通展示71，P09保存48／展示46。全局跨工具独立根因匹配及总体召回率未计算。",
              "", "## 30组合分析成本与输入范围", "",
              "| 项目 | 工具 | 实际文本／动作数 | 结果运行 | 成本运行 | wall秒 | user秒 | sys秒 | 最大RSS KiB |",
              "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: |"]
    for row in rows:
        cost = row["external_resources"]
        lines.append(f"| {row['project_id']} {row['project']} | {row['tool']} | {row['result_coverage']['succeeded_or_examined']} | {row['result_run_id']} | {row['cost_run_id']} | {cost['wall_seconds']:.2f} | {cost['user_seconds']:.2f} | {cost['system_seconds']:.2f} | {cost['max_rss_kib']} |")
    lines += ["", "成本为单次完整分析命令外部记录，准备／构建／独立parse及核查在外；自然系统页缓存，GNU time最大RSS不称进程树内存总峰值。不能据本表推出稳定速度倍数或总体排名。每行配置、缓存、环境关联与原始time SHA见JSON；C11/GNU C17及P06/P08输入适配差异保留。",
              "", "P09的101动作为8/12/16位58/28/15，58个唯一C路径；FF只扫去重项目文本。旧FF未独立记录失败／跳过计数保持null，不能当成零。P06 CP001和P08 CP001等未采用尝试保留，不填入有效结果计数。",
              "", "## cJSON本次映射", "",
              "[CC验收](../cJSON_cost_supplement_20261030/CodeChecker_Acceptance.md)：1动作、合法plist1、0诊断，新旧plist相同。",
              "[FF验收](../cJSON_cost_supplement_20261030/Flawfinder_Acceptance.md)：2文本、26命中逐块对应旧表；等级0另1、累计27另列。",
              "[CP验收](../cJSON_cost_supplement_20261030/Cppcheck_Acceptance.md)：1动作、26XML＝16候选＋10信息；新旧XML字节一致。沿用15质量诊断有据及1误报。",
              "", "三次新分析不新增725候选分母，也不重记AI核查次数。新图[FIG-P03-18](../screenshots/P03/FIG-P03-18_cost_cppcheck-summary.png)与[153图索引](../screenshots/Screenshot_Index.md)已关联。",
              "", "后续集中完善讨论、全局问题匹配说明、代表案例与10分钟展示；15未决的证据缺口继续如实保留。课程原创声明、签名、贡献、提交日期及TurnItIn按最终要求核对。", ""]
    (OUT / "Final_Results.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "raw_new_receipts_checked": raw_count,
                      "protected_old_files_checked": len(protected), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
