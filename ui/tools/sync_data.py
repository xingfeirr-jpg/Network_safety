"""Copy every file the UI reads from the two research packages into ui/data/.

The UI then depends only on the ui/ folder. Run this again whenever the research
packages change:

    python ui/tools/sync_data.py

It also writes ui/data/replay/<library>-<tool>.json: the recorded output of each of the 30
replication runs (S1-S6), which the UI can replay step by step without Docker.

It also writes ui/data/source_lines.json: the source line of each of the 725 alerts,
taken from the local source cache (ui/runtime/cache/sources). That file lets the UI show
code without downloading the libraries, e.g. on GitHub Pages. If the cache is missing,
the existing source_lines.json is kept.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

UI = Path(__file__).resolve().parents[1]
ROOT = UI.parent
IMPL = ROOT / "Project17_Implementation_and_Data"
REPL = ROOT / "Project17_Replication"
OUT = UI / "data"
RECORDS = IMPL / "data" / "records"

FILES = {
    RECORDS / "formal_comparison_20261030" / "Final_Matrix.csv": "Final_Matrix.csv",
    RECORDS / "ten_project_synthesis_20261029" / "Candidate_Review_Combined.csv": "Candidate_Review_Combined.csv",
    REPL / "config" / "libraries.json": "libraries.json",
    REPL / "output" / "comparison.csv": "comparison.csv",
    REPL / "output" / "human_review" / "sampling_plan.csv": "human_review/sampling_plan.csv",
    REPL / "output" / "human_review" / "review_sheet.csv": "human_review/review_sheet.csv",
    # Parsers used to read live-run output (same code as the replication comparison).
    REPL / "replication" / "parsers.py": "../vendor/parsers.py",
}


def copy(src: Path, rel: str):
    dst = (OUT / rel).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"  {src.relative_to(ROOT)}  ->  {dst.relative_to(ROOT)}")


def main():
    if not IMPL.is_dir() or not REPL.is_dir():
        sys.exit("research packages not found next to ui/")
    print("copying data files")
    for src, rel in FILES.items():
        copy(src, rel)

    # Per-project diagnostics tables (source context captured by the tools).
    diag = OUT / "diagnostics"
    if diag.exists():
        shutil.rmtree(diag)
    for path in sorted((IMPL / "data").glob("**/diagnostics.csv")):
        name = "__".join(path.relative_to(IMPL / "data").parts[:-1]) + ".csv"
        copy(path, f"diagnostics/{name}")

    write_replay()
    write_source_lines()


# ---------- replay of the recorded replication runs ----------
TOOL_KEYS = ("FF", "CP", "CC")
TOOL_NAMES = {"FF": "Flawfinder", "CP": "Cppcheck", "CC": "CodeChecker/clangsa"}
HOME = "/home/yhong/comp5355/"


def _short(text: str) -> str:
    return text.replace(HOME, "~/")


def _lines(path: Path, head: int, tail: int = 0):
    """First `head` and last `tail` lines of a log, with a marker for the omitted part."""
    if not path.is_file():
        return []
    rows = [_short(line.rstrip()) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if len(rows) <= head + tail:
        return rows
    skipped = len(rows) - head - tail
    return rows[:head] + [f"... ({skipped} lines)"] + (rows[-tail:] if tail else [])


def _command(path: Path, keep: int = 14):
    if not path.is_file():
        return []
    args = [_short(a) for a in json.loads(path.read_text(encoding="utf-8"))]
    shown = args[:keep]
    rest = len(args) - len(shown)
    return ["$ " + " ".join(shown) + (f" ... (+{rest} args)" if rest else "")]


def write_replay():
    """Recorded replication output per library and tool, trimmed for display.

    Everything shown comes from Project17_Replication/output (logs, commands, tool output,
    timing) and output/comparison.csv (the S6 comparison against the original study)."""
    sys.path.insert(0, str(UI))
    from server import parse_result, read_time  # same parsing as a live run

    frozen = json.loads((REPL / "config" / "libraries.json").read_text(encoding="utf-8"))
    with open(REPL / "output" / "comparison.csv", encoding="utf-8-sig", newline="") as stream:
        comparison = {(row["project_id"], row["run_id"]): row for row in csv.DictReader(stream)}
    replication = REPL / "output" / "results" / "_replication"
    out = OUT / "replay"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    written = 0
    for lib in frozen["libraries"]:
        steps_file = replication / lib["id"] / "steps.json"
        steps = json.loads(steps_file.read_text(encoding="utf-8")) if steps_file.is_file() else {}
        for key in TOOL_KEYS:
            run_name = lib["runs"][key]
            run_dir = REPL / "output" / lib["results_dir"] / run_name
            row = comparison.get((lib["id"], run_name), {})
            if not run_dir.is_dir():
                print(f"  missing {run_dir.relative_to(ROOT)}; no replay for {lib['id']}-{key}")
                continue
            alerts, info = parse_result(key, run_dir)
            seconds, rss = read_time(run_dir)
            s1, s2, s3 = steps.get("S1", {}), steps.get("S2", {}), steps.get("S3", {})
            exit_file = run_dir / "exit-code.txt"
            exit_code = int(exit_file.read_text().strip() or -1) if exit_file.is_file() else None
            stdout = run_dir / ("stderr.txt" if key == "CP" and not (run_dir / "stdout.txt").is_file() else "stdout.txt")
            build = replication / lib["id"]
            stages = [
                dict(id="S1", lines=[
                    f"archive  {Path(s1.get('archive', '')).name}",
                    f"sha256   {s1.get('sha256', '')}",
                    f"expected {s1.get('expected_sha256', '')}",
                    f"archive matches original: {row.get('S1_archive_identical') or s1.get('matches_original')}",
                ]),
                dict(id="S2", lines=[
                    f"extract -> {_short(s2.get('source_dir', ''))}",
                    f"regular files: {s2.get('regular_files', '')}",
                    f"scan inputs match original: {row.get('S2_inputs_identical') or 'n/a'}",
                ]),
                dict(id="S3", lines=[
                    *_command(build / "configure-command.json"),
                    *_lines(build / "configure-stdout.txt", 4, 3),
                    *_lines(build / "build-stdout.txt", 4, 2),
                    f"compile actions: {s3.get('compile_actions', '')}",
                    f"compile database matches original: {row.get('S3_compile_db_identical') or 'n/a'}",
                ]),
                dict(id="S4", lines=[
                    *_command(run_dir / "command.json"),
                    f"command matches original: {row.get('S4_command_identical') or 'n/a'}",
                ]),
                dict(id="S5", lines=[
                    *_lines(stdout, 14, 8),
                    f"exit code {exit_code} · wall {seconds} s · max rss {rss} KiB",
                ]),
                dict(id="S6", lines=[
                    f"alerts: original {row.get('original_alerts', '?')} · replicated {row.get('replicated_alerts', '?')}",
                    f"alert set identical: {row.get('S5_alerts_identical', '?')}"
                    f" (only in replication {row.get('only_in_replication', 0)}, only in original {row.get('only_in_original', 0)})",
                    f"verdicts carried over: false positive {row.get('false_positive') or 0}"
                    f" · supported {row.get('supported') or 0} · undetermined {row.get('undetermined') or 0}",
                ]),
            ]
            reference = int(row["original_alerts"]) if row.get("original_alerts") else None
            data = dict(
                library=lib["id"], name=lib["name"], version=lib["version"], tool=key, tool_name=TOOL_NAMES[key],
                run_id=run_name, recorded_utc=steps.get("started_utc"), stages=stages,
                result=dict(
                    tool=key, exit_code=exit_code, information=info, wall_seconds=seconds, max_rss_kib=rss,
                    alerts=[{k: a.get(k) for k in ("file", "line", "column", "rule", "message")} for a in alerts],
                    replicated_count=len(alerts), reference_count=reference,
                    matches_reference=row.get("S5_alerts_identical") == "True",
                ),
            )
            (out / f"{lib['id']}-{key}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            written += 1
    print(f"wrote {written} replay files to {out.relative_to(ROOT)}")


def write_source_lines():
    sys.path.insert(0, str(UI))
    import config as cfg

    sources = cfg.CACHE / "sources"
    target = OUT / "source_lines.json"
    if not sources.is_dir() or not any(sources.iterdir()):
        print(f"source cache {sources} is empty; keeping existing {target.name}")
        return
    from server import source_line  # same lookup the live server uses

    with open(OUT / "Candidate_Review_Combined.csv", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    lines = {}
    for row in rows:
        try:
            number = int(float(row["line"]))
        except ValueError:
            continue
        key = f'{row["projectId"]}|{row["file"]}|{number}'
        text = source_line(row["file"], number, row["projectId"], use_bundle=False)
        if text is not None:
            lines[key] = text
    target.write_text(json.dumps(lines, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)} ({len(lines)} of {len(rows)} alert lines)")


if __name__ == "__main__":
    main()
