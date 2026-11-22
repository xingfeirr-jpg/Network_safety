"""Copy every file the UI reads from the two research packages into ui/data/.

The UI then depends only on the ui/ folder. Run this again whenever the research
packages change:

    python ui/tools/sync_data.py

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

    write_source_lines()


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
