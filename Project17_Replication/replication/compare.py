"""S6: compare the replication with the original study and write output/comparison.csv.

    python replication/compare.py                 compare the runs in output/results
    python replication/compare.py --self-test     run the same comparison on the raw outputs
                                                  saved by the original study; it must
                                                  reproduce all 725 alerts of the review ledger

Checks:
  S1 archive hash        matches Third_Party_Sources.json
  S2 input file hashes   every file scanned by Flawfinder matches the original run
  S3 compilation DBs     the built, filtered and adapted databases match the saved ones entry by entry
  S4 tool commands       the executed command is byte-identical to the frozen original command
  S5 alerts              each tool's alerts (file, line, column, rule) match the review ledger by count
  S6 review outcomes     when the alerts match, the original 648 / 62 / 15 outcomes carry over
  cost                   old and new wall time and maximum RSS are listed side by side, not judged

Uses only the Python standard library and runs on Windows or Linux.
"""
import argparse
import csv
import json
import re
import shlex
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import TOOLS, argv, load_config  # noqa: E402
from parsers import as_counter, parse_codechecker, parse_cppcheck, parse_flawfinder, relative_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = {"FF": "Flawfinder", "CP": "Cppcheck", "CC": "CodeChecker/clangsa"}
# Outcome values as stored (in Chinese) in the original review ledger
LABELS = ("原风险误报", "有依据", "无法判断")
LABEL_TEXT = {"原风险误报": "false_positive", "有依据": "supported", "无法判断": "undetermined"}


class Original:
    """Records of the original study package (Project17_Implementation_and_Data)."""

    def __init__(self, root):
        self.root = Path(root)
        records = self.root / "data" / "records"
        self.records = records
        with open(records / "ten_project_synthesis_20261029" / "Candidate_Review_Combined.csv", encoding="utf-8-sig") as f:
            self.ledger = list(csv.DictReader(f))
        with open(records / "formal_comparison_20261030" / "Final_Matrix.csv", encoding="utf-8-sig") as f:
            self.matrix = {(r["project_id"], r["tool_key"]): r for r in csv.DictReader(f)}
        with open(records / "formal_comparison_20261030" / "Frozen_Configuration.json", encoding="utf-8") as f:
            self.frozen = {r["run_id"]: r for r in json.load(f)["runs"]}
        with open(records / "formal_comparison_20261030" / "Reuse_Assessment.json", encoding="utf-8") as f:
            self.raw_dirs = {r["run_id"]: records / r["raw_directory"].removeprefix("review_evidence/")
                             for r in json.load(f)["rows"]}
        with open(self.root / "data" / "Third_Party_Sources.json", encoding="utf-8") as f:
            self.sources = {s["commit"]: s for s in json.load(f)}

    def raw_dir(self, run_id):
        if run_id.startswith("FORM-"):
            return self.records / "cJSON_cost_supplement_20261030" / "runs" / run_id
        return self.raw_dirs[run_id]

    def command(self, run_id):
        if run_id.startswith("FORM-"):
            name = {"FF": "Flawfinder", "CP": "Cppcheck", "CC": "CodeChecker"}[run_id.split("-")[2]]
            path = self.root / "code/experiment_inputs/cJSON_cost_supplement_20261030" / f"{name}_Profile.json"
            return json.loads(path.read_text(encoding="utf-8"))["analysis_argv"]
        return shlex.split(self.frozen[run_id]["command_verbatim"])

    def alerts(self, run_id):
        rows = [r for r in self.ledger if r["runId"] == run_id]
        return as_counter((r["file"], r["line"], r["column"], r["rule"]) for r in rows), rows


def read_alerts(tool_key, run):
    """Read the alerts of one run directory; also accepts the file names of the early cJSON pretest."""
    if tool_key == "FF":
        path = run / "stdout.txt" if (run / "stdout.txt").exists() else run / "report.txt"
        return parse_flawfinder(path.read_text(encoding="utf-8", errors="replace")), None
    if tool_key == "CP":
        path = run / "stderr.txt" if (run / "stderr.txt").exists() else run / "report.xml"
        return parse_cppcheck(path.read_text(encoding="utf-8"))
    return parse_codechecker(run / "reports"), None


def read_time(run):
    path = run / "time.txt"
    if not path.exists():
        return None, None
    text = path.read_text(encoding="utf-8", errors="replace")
    wall = re.search(r"Elapsed \(wall clock\) time .*: (?:(\d+):)?(\d+):([\d.]+)", text)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", text)
    seconds = None
    if wall:
        hours, minutes, secs = wall.groups()
        seconds = int(hours or 0) * 3600 + int(minutes) * 60 + float(secs)
    return seconds, int(rss.group(1)) if rss else None


def read_hashes(path):
    if not path.exists():
        return None
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            result[relative_path(name.strip().lstrip("*"))] = digest
    return result


def same_database(new_path, saved_path):
    if not new_path.exists():
        return None
    load = lambda p: sorted(json.dumps(e, sort_keys=True) for e in json.loads(p.read_text(encoding="utf-8")))
    return load(new_path) == load(saved_path)


def check(results, original, config, self_test):
    rows, steps = [], []
    for lib in config["libraries"]:
        prep = results / "_replication" / lib["id"]
        step = dict(id=lib["id"], name=lib["name"])
        if not self_test:
            record = json.loads((prep / "steps.json").read_text(encoding="utf-8")) if (prep / "steps.json").exists() else {}
            s1 = record.get("S1", {})
            step["S1"] = s1.get("matches_original") if s1 else None
            step["S1_note"] = "no archive hash in the original study" if lib["download"]["sha256"] is None else ""
            checks = [same_database(prep / "compile_commands.build.json", original.root / lib["build"]["saved_compile_db"])]
            if "analysis_db" in lib:
                checks.append(same_database(prep / "compile_commands.analysis.json", original.root / lib["analysis_db"]["saved"]))
            if "database" in lib["cppcheck"]:
                checks.append(same_database(prep / "compile_commands.cppcheck.json",
                                            original.root / lib["cppcheck"]["database"]["saved"]))
            step["S3"] = None if None in checks else all(checks)
        steps.append(step)

        for tool_key, _ in TOOLS:
            run_id, ledger_id = lib["runs"][tool_key], lib["ledger_runs"][tool_key]
            run = original.raw_dir(run_id) if self_test else results / lib["results_dir"].removeprefix("results/") / run_id
            orig_row = original.matrix[(lib["id"], tool_key)]
            row = dict(project_id=lib["id"], project=lib["name"], tool=TOOL_NAMES[tool_key], run_id=run_id)
            if not run.exists():
                row.update(status="missing run output")
                rows.append(row)
                continue
            if not self_test:
                ran = json.loads((run / "command.json").read_text(encoding="utf-8")) if (run / "command.json").exists() else None
                row["S4_command_identical"] = ran == original.command(run_id) == argv(config, lib, tool_key)
                row["exit_code"] = (run / "exit-code.txt").read_text(encoding="utf-8", errors="replace").strip() if (run / "exit-code.txt").exists() else ""
                if tool_key == "FF":
                    new_hashes = read_hashes(run / "input-files.sha256")
                    old_hashes = read_hashes(original.raw_dir(run_id) / "input-files.sha256")
                    # the original manifest may also list the compilation database; compare only scanned inputs
                    scanned = {relative_path(f"{config['base']}/{item}") for item in lib["flawfinder"]["inputs"]}
                    if old_hashes:
                        old_hashes = {k: v for k, v in old_hashes.items() if k in scanned}
                    row["S2_inputs_identical"] = None if not (new_hashes and old_hashes) else new_hashes == old_hashes
            alerts, information = read_alerts(tool_key, run)
            got = as_counter(alerts)
            expected, ledger_rows = original.alerts(ledger_id)
            row.update(original_alerts=sum(expected.values()), replicated_alerts=sum(got.values()),
                       S5_alerts_identical=got == expected,
                       only_in_replication=sum((got - expected).values()),
                       only_in_original=sum((expected - got).values()))
            if information is not None:
                row["original_information"] = int(orig_row["information_items"] or 0)
                row["replicated_information"] = information
            if got == expected:
                labels = Counter(r["normalizedFinalLabel"] for r in ledger_rows)
                for label in LABELS:
                    row[LABEL_TEXT[label]] = labels.get(label, 0)
            wall, rss = read_time(run)
            row.update(original_wall_seconds=orig_row["wall_seconds"], replicated_wall_seconds=wall,
                       original_max_rss_kib=orig_row["max_rss_kib"], replicated_max_rss_kib=rss)
            row["differences"] = [list(k) + [v, "replication only"] for k, v in (got - expected).items()] + \
                                 [list(k) + [v, "original only"] for k, v in (expected - got).items()]
            rows.append(row)
    return rows, steps


def write_results(rows, steps, out, self_test):
    """Write comparison.csv (30 rows) and, if any alert differs, alert_differences.csv."""
    by_id = {s["id"]: s for s in steps}
    for row in rows:
        step = by_id.get(row["project_id"], {})
        row["S1_archive_identical"] = step.get("S1")
        row["S3_compile_db_identical"] = step.get("S3")
    total = sum(r.get("replicated_alerts", 0) for r in rows)
    identical = sum(bool(r.get("S5_alerts_identical")) for r in rows)
    tally = Counter()
    for r in rows:
        for text in LABEL_TEXT.values():
            tally[text] += r.get(text, 0)
    fields = ["project_id", "project", "tool", "run_id", "S1_archive_identical", "S2_inputs_identical",
              "S3_compile_db_identical", "S4_command_identical", "exit_code", "original_alerts", "replicated_alerts",
              "S5_alerts_identical", "only_in_replication", "only_in_original", "original_information",
              "replicated_information", "false_positive", "supported", "undetermined", "original_wall_seconds",
              "replicated_wall_seconds", "original_max_rss_kib", "replicated_max_rss_kib", "status"]
    name = "self_test_comparison.csv" if self_test else "comparison.csv"
    with open(out / name, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    differences = [[r["project"], r["tool"], *d] for r in rows for d in r.get("differences", [])]
    diff_path = out / ("self_test_alert_differences.csv" if self_test else "alert_differences.csv")
    if differences:
        with open(diff_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["library", "tool", "file", "line", "column", "rule", "count", "found_in"])
            writer.writerows(differences)
    elif diff_path.exists():
        diff_path.unlink()
    if not self_test:
        failed = [f"{r['project']} {r['tool']} {k}" for r in rows
                  for k in ("S1_archive_identical", "S2_inputs_identical", "S3_compile_db_identical", "S4_command_identical")
                  if r.get(k) is False]
        print("S1-S4 mismatches: " + (", ".join(failed) if failed else "none"))
    print(f"S5 alerts identical: {identical}/{len(rows)}; total alerts {total}; "
          f"false positive {tally['false_positive']} / supported {tally['supported']} / undetermined {tally['undetermined']}")
    print("comparison table:", out / name, "; alert differences:", len(differences) if differences else "none")
    return identical, len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--original", default=ROOT.parent / "Project17_Implementation_and_Data", type=Path)
    parser.add_argument("--output", default=ROOT / "output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    config = load_config()
    original = Original(args.original)
    results = args.output / "results"
    rows, steps = check(results, original, config, args.self_test)
    args.output.mkdir(parents=True, exist_ok=True)
    identical, count = write_results(rows, steps, args.output, args.self_test)
    return 0 if identical == count else 1


if __name__ == "__main__":
    sys.exit(main())
