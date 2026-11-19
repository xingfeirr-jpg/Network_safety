"""Derive the project summary and experiment-reliability analysis for the UI.

Both endpoints work from the frozen study records only, so every number shown on the
overview, conclusion, and reliability pages can be traced back to the saved CSVs.

  /api/summary     tool-by-tool evaluation derived from the 725 reviewed alerts
  /api/reliability how the experiment was made trustworthy: independent replication
                   and the AI-assisted stratified review
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "project17" / "Project17_Implementation_and_Data"
REPL = ROOT / "project17" / "Project17_Replication"
RECORDS = IMPL / "data" / "records"

TOOLS = ["Flawfinder", "Cppcheck", "CodeChecker/clangsa"]

TOOL_KEY = {"Flawfinder": "FF", "Cppcheck": "CP", "CodeChecker/clangsa": "CC"}

# What each tool is actually able to see. These statements come from the replication
# README and the observed behaviour of the three tools, not from per-alert data.
TOOL_PROFILE = {
    "Flawfinder": {
        "method": "name_matching",
        "needs_build": False,
        "scale": "textual",
    },
    "Cppcheck": {
        "method": "value_inference",
        "needs_build": True,
        "scale": "compile_action",
    },
    "CodeChecker/clangsa": {
        "method": "path_simulation",
        "needs_build": True,
        "scale": "compile_action",
    },
}


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _matrix_rows():
    path = RECORDS / "formal_comparison_20261030" / "Final_Matrix.csv"
    return _read_csv(path)


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_summary(candidates, matrix):
    """Evaluate each tool from the reviewed alerts and the recorded cost."""
    by_tool = defaultdict(Counter)
    for row in candidates:
        by_tool[row["tool"]][row["outcome"]] += 1

    costs = defaultdict(list)
    rss = defaultdict(list)
    for row in matrix:
        key = row["tool_key"]
        if row["wall_seconds"]:
            costs[key].append(row["wall_seconds"])
        if row["max_rss_kib"]:
            rss[key].append(row["max_rss_kib"])

    tool_rows = []
    for tool in TOOLS:
        counts = by_tool[tool]
        total = sum(counts.values())
        fp = counts["false_positive"]
        sup = counts["supported"]
        und = counts["undetermined"]
        key = TOOL_KEY[tool]
        wall = costs.get(key) or []
        mem = rss.get(key) or []
        tool_rows.append(dict(
            tool=tool,
            tool_key=key,
            total=total,
            false_positive=fp,
            supported=sup,
            undetermined=und,
            precision=round(100.0 * sup / total, 1) if total else 0.0,
            fp_ratio=round(100.0 * fp / total, 1) if total else 0.0,
            cost_per_supported=round(total / sup, 1) if sup else None,
            total_wall_seconds=round(sum(wall), 2),
            median_wall_seconds=round(sorted(wall)[len(wall) // 2], 2) if wall else None,
            peak_rss_kib=max(mem) if mem else None,
            **TOOL_PROFILE[tool],
        ))
    # Which libraries each tool found something on, and how the tools complement
    # each other on the libraries where the finding counts are closest.
    per_project = defaultdict(lambda: defaultdict(int))
    for row in candidates:
        per_project[row["project"]][row["tool"]] += 1
    projects = sorted(per_project)
    coverage = {
        tool: sum(1 for project in projects if per_project[project][tool] > 0)
        for tool in TOOLS
    }
    supported_projects = {
        tool: sorted(project for project in projects if per_project[project][tool] and
                     any(row["tool"] == tool and row["project"] == project and
                         row["outcome"] == "supported" for row in candidates))
        for tool in TOOLS
    }
    # Rule concentration: a tool whose findings are dominated by one rule gives a
    # narrow signal, while a broad spread indicates wider coverage.
    rule_spread = {}
    for tool in TOOLS:
        rules = Counter(row["rule"] for row in candidates if row["tool"] == tool)
        top_rule, top_count = rules.most_common(1)[0] if rules else ("", 0)
        total = sum(rules.values())
        rule_spread[tool] = dict(
            distinct_rules=len(rules),
            top_rule=top_rule,
            top_rule_count=top_count,
            top_rule_share=round(100.0 * top_count / total, 1) if total else 0.0,
            top_rules=[dict(rule=name, count=count) for name, count in rules.most_common(5)],
        )

    # Number of libraries where the tool produced at least one supported alert.
    for row in tool_rows:
        row["supported_projects_count"] = len(supported_projects[row["tool"]])

    return dict(
        total=len(candidates),
        tools=tool_rows,
        coverage=coverage,
        supported_projects=supported_projects,
        project_count=len(projects),
        rule_spread=rule_spread,
    )


def load_reliability(matrix):
    """Describe the two mechanisms that make the experiment trustworthy."""
    import json

    comparison = REPL / "output" / "comparison.csv"
    comparison_rows = _read_csv(comparison) if comparison.exists() else []

    # S1-S5 agreement as recorded by the replication comparison table. Every column
    # below is checked independently, so a step that could not be compared (empty
    # cell) is counted separately instead of being silently treated as a match.
    step_fields = [
        ("s1", "S1_archive_identical"),
        ("s2", "S2_inputs_identical"),
        ("s3", "S3_compile_db_identical"),
        ("s4", "S4_command_identical"),
        ("s5", "S5_alerts_identical"),
    ]

    def _flag(row, field):
        return (row.get(field) or "").strip().lower() in ("true", "1", "yes")

    step_summary = {}
    for key, field in step_fields:
        identical = sum(1 for row in comparison_rows if _flag(row, field))
        comparable = sum(1 for row in comparison_rows if (row.get(field) or "").strip())
        step_summary[key] = dict(identical=identical, comparable=comparable, total=len(comparison_rows))

    alert_identical = sum(1 for row in comparison_rows if _flag(row, "S5_alerts_identical"))
    command_identical = sum(1 for row in comparison_rows if _flag(row, "S4_command_identical"))
    archive_identical = sum(1 for row in comparison_rows if _flag(row, "S1_archive_identical"))

    # The alert counts themselves: the original study and the replication must
    # report the same number of alerts, not merely agree on a verdict flag.
    same_counts = 0
    for row in comparison_rows:
        try:
            if int(float(row.get("original_alerts") or 0)) == int(float(row.get("replicated_alerts") or 0)):
                same_counts += 1
        except ValueError:
            continue

    config = json.loads((REPL / "config" / "libraries.json").read_text(encoding="utf-8"))
    pinned = []
    for lib in config["libraries"]:
        pinned.append(dict(
            id=lib["id"],
            name=lib["name"],
            version=lib["version"],
            commit=lib["commit"],
            sha256=lib["download"]["sha256"],
            has_hash=bool(lib["download"]["sha256"]),
        ))

    # The stratified review plan: important groups are reviewed exhaustively,
    # the large false-positive group is sampled by strata.
    sampling = REPL / "output" / "human_review" / "sampling_plan.csv"
    sampling_rows = _read_csv(sampling) if sampling.exists() else []

    # The plan groups the review ledger into strata. The part before the pipe
    # carries the verdict group; the part after it describes the tool or the
    # exclusion reason. The two important groups are sampled at 100%, the large
    # false-positive group is sampled proportionally inside 19 layers.
    EXHAUSTIVE = ("Supported", "Undetermined")
    strata = []
    group_totals = defaultdict(lambda: dict(population=0, sampled=0))
    for row in sampling_rows:
        name = (row.get("stratum") or "").strip()
        group = name.split("|")[0].strip()
        population = _int(row.get("population"))
        sampled = _int(row.get("sampled"))
        bucket = group_totals[group]
        bucket["population"] += population
        bucket["sampled"] += sampled
        strata.append(dict(
            stratum=name,
            group=group,
            population=population,
            population_size=population,
            sampled=sampled,
            rate=(row.get("sampling_rate") or "").strip(),
        ))

    exhaustive_groups = []
    sampled_groups = []
    for group, totals in group_totals.items():
        entry = dict(
            group=group,
            population=totals["population"],
            sampled=totals["sampled"],
            strata=sum(1 for item in strata if item["group"] == group),
        )
        (exhaustive_groups if group in EXHAUSTIVE else sampled_groups).append(entry)

    population = sum(item["population"] for item in strata)
    sample_size = sum(item["sampled"] for item in strata)

    review_sheet = REPL / "output" / "human_review" / "review_sheet.csv"
    sheet_rows = _read_csv(review_sheet) if review_sheet.exists() else []
    filled = sum(1 for row in sheet_rows if (row.get("reviewer_verdict") or "").strip())

    return dict(
        replication=dict(
            runs_compared=len(comparison_rows),
            alert_groups_identical=alert_identical,
            command_groups_identical=command_identical,
            archive_groups_identical=archive_identical,
            same_alert_counts=same_counts,
            step_summary=step_summary,
            pinned_libraries=pinned,
            hash_coverage=sum(1 for lib in pinned if lib["has_hash"]),
            library_count=len(pinned),
        ),
        review=dict(
            total_alerts=sum(row["candidates"] for row in matrix),
            population=population,
            sample_size=sample_size,
            strata=strata,
            exhaustive_groups=exhaustive_groups,
            sampled_groups=sampled_groups,
            sheet_rows=len(sheet_rows),
            sheet_filled=filled,
            has_review_sheet=review_sheet.exists(),
        ),
    )
