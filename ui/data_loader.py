"""Load the saved study data for the UI.

Only read-only sources are used. Manual review fields (humanReview, reviewer verdicts,
review reports and ledger paths) are deliberately not loaded: the manual review has not
been carried out, so these fields are never shown.
"""
import csv
from collections import Counter
from pathlib import Path

from config import IMPL, RECORDS, REPL  # noqa: F401  (paths are configured in config.py)

LABEL_EN = {
    "原风险误报": "false_positive",
    "有依据": "supported",
    "无法判断": "undetermined",
}
TOOL_KEY = {"Flawfinder": "FF", "Cppcheck": "CP", "CodeChecker/clangsa": "CC"}
TOOL_NAME = {"FF": "Flawfinder", "CP": "Cppcheck", "CC": "CodeChecker/clangsa"}


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _source_context_map():
    """Map (project, original alert id) to the source line captured by the tool."""
    contexts = {}
    root = RECORDS.parent
    for path in root.glob("**/diagnostics.csv"):
        try:
            rows = _read_csv(path)
        except OSError:
            continue
        for row in rows:
            if not row.get("originalId") and not row.get("candidateId"):
                continue
            original_id = row.get("originalId") or row.get("candidateId")
            context = row.get("sourceContext", "").strip()
            if context and original_id not in contexts:
                contexts[original_id] = context
    return contexts


def load_matrix():
    """30 rows: one per library and tool, with counts, verdicts and cost."""
    rows = _read_csv(RECORDS / "formal_comparison_20261030" / "Final_Matrix.csv")
    result = []
    for r in rows:
        result.append(dict(
            project_id=r["project_id"], project=r["project"], version=r["version"],
            tool=r["tool"], tool_key=r["tool_key"], run_id=r["result_run_id"],
            intended=_int(r["intended_count"]), examined=_int(r["succeeded_or_examined"]),
            failed=_int(r["failed"]), candidates=_int(r["candidate_count"]),
            false_positive=_int(r["original_risk_false_positive"]),
            supported=_int(r["supported_diagnoses"]), undetermined=_int(r["undetermined"]),
            wall_seconds=_float(r["wall_seconds"]), max_rss_kib=_int(r["max_rss_kib"]),
        ))
    return result


def load_libraries():
    """Ten libraries: one row per library from the file counts in the replication package."""
    import json
    config = json.loads((REPL / "config" / "libraries.json").read_text(encoding="utf-8"))
    libs = []
    for lib in config["libraries"]:
        libs.append(dict(
            id=lib["id"], name=lib["name"], version=lib["version"],
            commit=lib["commit"], source_dir=lib["source_dir"],
            build_target=lib["build"]["target"], cppcheck_std=lib["cppcheck"]["std"],
            flawfinder_inputs=len(lib["flawfinder"]["inputs"]),
            analysis_db=bool("analysis_db" in lib),
        ))
    return libs


def load_candidates():
    """725 alerts with location, rule, outcome and source-code evidence.

    Manual review columns are omitted on purpose.
    """
    rows = _read_csv(RECORDS / "ten_project_synthesis_20261029" / "Candidate_Review_Combined.csv")
    contexts = cached_contexts()
    out = []
    for r in rows:
        out.append(dict(
            project_id=r["projectId"], project=r["project"], version=r["version"],
            key=r["candidateKey"], original_id=r["originalId"],
            tool=r["tool"], run_id=r["runId"],
            file=r["file"], line=_int(r["line"]), column=_int(r["column"]),
            rule=r["rule"], outcome=LABEL_EN.get(r["normalizedFinalLabel"], "unknown"),
            outcome_label=r["normalizedFinalLabel"],
            security_meaning=r["securityMeaning"], source_evidence=r["sourceEvidence"],
            missing_conditions=r["missingConditions"], cross_tool=r["crossToolRelation"],
            root_cause_group=r["rootCauseGroup"],
            source_code=contexts.get(r["originalId"], ""),
        ))
    return out


_CONTEXT_CACHE = None


def cached_contexts():
    global _CONTEXT_CACHE
    if _CONTEXT_CACHE is None:
        _CONTEXT_CACHE = _source_context_map()
    return _CONTEXT_CACHE


def summary_counts(candidates):
    by_tool = Counter((c["tool"], c["outcome"]) for c in candidates)
    return by_tool


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
