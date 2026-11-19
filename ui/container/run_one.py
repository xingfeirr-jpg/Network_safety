"""Run one tool on one library inside the replication container.

Reuses the functions of the original pipeline (download, extract, build, run) without
changing them. Only the chosen tool is run. Results go to the mounted directory given by
the UI, never to the original output folder.

Usage (inside the container):
    python3 run_one.py P01 FF        FF = Flawfinder, CP = Cppcheck, CC = CodeChecker/clangsa
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/replication/replication")
import pipeline as p  # noqa: E402  (original pipeline, unchanged)

TOOL_NAMES = {"FF": "Flawfinder", "CP": "Cppcheck", "CC": "CodeChecker/clangsa"}


def source_ready(lib):
    """True when this library was already extracted and built by an earlier run.

    The source tree, the build directory and the compilation database live in the mounted
    cache, so they survive between runs. A completed build writes a marker file there.
    """
    source = p.BASE / lib["source_dir"]
    marker = p.BASE / lib["build_dir"] / ".p17-ready"
    return marker.is_file() and source.is_dir() and any(source.iterdir())


def say_reuse(lib):
    print(f"[{p.now()}] {lib['id']} reuse existing source and build (skip S1-S3)", flush=True)


def main():
    lib_id, tool_key = sys.argv[1], sys.argv[2]
    if tool_key not in TOOL_NAMES:
        print(f"unknown tool {tool_key}", file=sys.stderr)
        return 2
    libraries = {lib["id"]: lib for lib in p.CONFIG["libraries"]}
    lib = libraries[lib_id]
    log_dir = p.LOG_ROOT / lib["id"]
    log_dir.mkdir(parents=True, exist_ok=True)
    record = dict(id=lib["id"], name=lib["name"], version=lib["version"], tool=tool_key,
                  started_utc=p.now())
    print(f"[{p.now()}] {lib['id']} {lib['name']} {lib['version']} tool={TOOL_NAMES[tool_key]}", flush=True)

    # Reuse the source tree and build from earlier runs when they are complete.
    # Those folders are mounted from the host (ui/cache), so they persist across runs.
    if not source_ready(lib):
        archive = p.s1_download(lib, record)
        p.s2_extract(lib, archive, record, log_dir)
        p.s3_build(lib, record, log_dir, libraries)
        (p.BASE / lib["build_dir"] / ".p17-ready").write_text(p.now() + "\n")
    else:
        say_reuse(lib)
    p.s5_run(lib, tool_key, record)

    record["ended_utc"] = p.now()
    (log_dir / f"steps-{tool_key}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    code = record["S5"][tool_key]["exit_code"]
    print(f"[{p.now()}] DONE exit={code}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
