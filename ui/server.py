"""FastAPI backend for the Project 17 UI.

Endpoints
  GET  /api/overview                 10 libraries (file counts, build info)
  GET  /api/matrix                   30 library-tool rows with counts and cost
  GET  /api/candidates               725 alerts (filterable)
  GET  /api/candidates/{key}         one alert with source evidence
  GET  /api/dashboard                aggregated numbers for the dashboard
  GET  /api/tools                    tool comparison text data
  POST /api/runs                     start one live run (library, tool)
  GET  /api/runs/{id}/events         Server-Sent Events: progress lines and final result
  GET  /api/runs/{id}                final result as JSON
"""
import asyncio
import json
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

UI = Path(__file__).resolve().parent
sys.path.insert(0, str(UI))
sys.path.insert(0, str(UI.parent / "project17" / "Project17_Replication" / "replication"))

import data_loader as dl  # noqa: E402
from case_analysis import load_special_cases  # noqa: E402
from parsers import (  # noqa: E402
    parse_codechecker, parse_codechecker_detail, parse_cppcheck, parse_cppcheck_detail,
    parse_flawfinder,
)
from summary import load_reliability, load_summary  # noqa: E402

RUNS = UI / "runs"
RUNS.mkdir(exist_ok=True)
IMAGE = "project17-replication:1.0"
LIBRARY_IDS = {lib["id"] for lib in dl.load_libraries()}
TOOL_KEYS = {"FF", "CP", "CC"}

app = FastAPI(title="Project 17 UI")
app.mount("/static", StaticFiles(directory=UI / "static"), name="static")

STATE = {}  # run_id -> dict(lines, done, result, process)


# ---------- cached loaders ----------
_cache = {}


def cached(name, loader):
    if name not in _cache:
        _cache[name] = loader()
    return _cache[name]


def matrix():
    return cached("matrix", dl.load_matrix)


def candidates():
    return cached("candidates", dl.load_candidates)


def libraries():
    return cached("libraries", dl.load_libraries)


@app.get("/")
def index():
    return FileResponse(UI / "static" / "index.html")


@app.get("/api/overview")
def overview():
    libs = libraries()
    return dict(libraries=libs, count=len(libs))


@app.get("/api/matrix")
def get_matrix():
    return matrix()


@app.get("/api/candidates")
def get_candidates(project: str = None, tool: str = None, outcome: str = None, limit: int = 1000):
    rows = candidates()
    if project:
        rows = [r for r in rows if r["project_id"] == project]
    if tool:
        rows = [r for r in rows if r["tool"] == tool]
    if outcome:
        rows = [r for r in rows if r["outcome"] == outcome]
    return dict(total=len(rows), items=[strip(r) for r in rows[:limit]])


def strip(row):
    return {k: row[k] for k in ("project_id", "project", "version", "key", "original_id", "tool",
                                "file", "line", "column", "rule", "outcome", "outcome_label")}


@app.get("/api/candidates/{key}")
def get_candidate(key: str):
    for row in candidates():
        if row["key"] == key:
            return row
    raise HTTPException(404, "not found")


@app.get("/api/dashboard")
def dashboard():
    rows = candidates()
    by_tool = Counter((r["tool"], r["outcome"]) for r in rows)
    tools = ["Flawfinder", "Cppcheck", "CodeChecker/clangsa"]
    verdict = {t: {o: by_tool.get((t, o), 0) for o in ("false_positive", "supported", "undetermined")}
               for t in tools}
    by_project = Counter((r["project"], r["outcome"]) for r in rows)
    rules = Counter((r["tool"], r["rule"]) for r in rows).most_common(15)
    return dict(
        total=len(rows),
        verdict=verdict,
        by_project={p: {o: by_project.get((p, o), 0) for o in ("false_positive", "supported", "undetermined")}
                    for p in sorted({r["project"] for r in rows})},
        top_rules=[dict(tool=t, rule=r, count=c) for (t, r), c in rules],
        matrix=matrix(),
    )


@app.get("/api/special-cases")
def special_cases():
    """Classify all reviewed alerts into explainable families with representative cases."""
    rows = candidates()
    for row in rows:
        code = source_line(row["file"], row["line"], row["project_id"])
        if code and not row.get("source_code"):
            row["source_code"] = code
    return load_special_cases(rows)


@app.get("/api/summary")
def summary():
    """Tool-by-tool evaluation derived from the 725 reviewed alerts."""
    return cached("summary", lambda: load_summary(candidates(), matrix()))


@app.get("/api/reliability")
def reliability():
    """How the experiment was made trustworthy: independent replication and stratified review."""
    return cached("reliability", lambda: load_reliability(matrix()))


@app.get("/api/library-detail/{library_id}")
def library_detail(library_id: str):
    """Alert breakdown of one library, used by the library cards and the pie charts."""
    rows = candidates()
    libs = {lib["id"]: lib for lib in libraries()}
    if library_id not in libs:
        raise HTTPException(404, "unknown library")
    subset = [row for row in rows if row["project_id"] == library_id]
    by_tool = defaultdict(Counter)
    for row in subset:
        by_tool[row["tool"]][row["outcome"]] += 1
    tools = ["Flawfinder", "Cppcheck", "CodeChecker/clangsa"]
    matrix_rows = {row["tool_key"]: row for row in matrix() if row["project_id"] == library_id}
    return dict(
        library=libs[library_id],
        total=len(subset),
        verdict={tool: {outcome: by_tool[tool][outcome]
                       for outcome in ("false_positive", "supported", "undetermined")}
                 for tool in tools},
        by_tool={tool: {outcome: by_tool[tool][outcome]
                        for outcome in ("false_positive", "supported", "undetermined")}
                 for tool in tools},
        rules=[dict(tool=tool, rule=rule, count=count)
               for (tool, rule), count in Counter((row["tool"], row["rule"]) for row in subset).most_common(10)],
        cost={key: dict(wall_seconds=matrix_rows[key]["wall_seconds"],
                        max_rss_kib=matrix_rows[key]["max_rss_kib"],
                        intended=matrix_rows[key]["intended"])
              for key in ("FF", "CP", "CC") if key in matrix_rows},
    )


# ---------- live runs ----------
class RunRequest(BaseModel):
    library: str
    tool: str


CONTAINER_ROOT = "/home/yhong/comp5355/"
SOURCE_PREFIXES = {
    "P01": "sources/zlib-v1.3.2",
    "P02": "sources/lz4-v1.10.0",
    "P03": "sources/cJSON-v1.7.19",
    "P04": "sources/libyaml-0.2.5",
    "P05": "sources/json-c-0.18",
    "P06": "sources/yyjson-0.12.0",
    "P07": "sources/expat-2.7.1",
    "P08": "sources/libpng-1.6.50",
    "P09": "sources/libjpeg-turbo-3.1.1",
    "P10": "sources/utf8proc-2.10.0",
}


def host_source_path(container_path: str, project_id: str = ""):
    """Map a path recorded inside the container to the matching cached source file."""
    if not container_path:
        return None
    if container_path.startswith(CONTAINER_ROOT):
        relative = container_path[len(CONTAINER_ROOT):]
        host = UI / "cache" / Path(relative)
        if host.is_file():
            return host
    # Some original Flawfinder records, notably libpng, store repository-relative paths.
    prefix = SOURCE_PREFIXES.get(project_id)
    if prefix:
        host = UI / "cache" / prefix / Path(container_path)
        if host.is_file():
            return host
    return None


def source_line(container_path: str, line: int, project_id: str = ""):
    """Return the text of one source line (one-based), or None when the file is unavailable."""
    host = host_source_path(container_path, project_id)
    if host is None or line < 1:
        return None
    try:
        with host.open(encoding="utf-8", errors="replace") as stream:
            for number, text in enumerate(stream, 1):
                if number == line:
                    return text.rstrip("\r\n")
    except OSError:
        return None
    return None


def with_code(alert: dict, project_id: str = ""):
    """Attach the warning line and the code of every trace step to an alert."""
    alert["code"] = source_line(alert["file"], alert["line"], project_id)
    for step in alert.get("trace", []):
        step["code"] = source_line(step["file"], step["line"], project_id)
    return alert


def parse_result(tool_key, run_dir: Path):
    """Parse one tool's saved output. Returns (alerts, information). Each alert carries the
    file, line, column, rule, message, and (for CodeChecker and Cppcheck) the path of steps.
    The first four fields and the count are the same as the replication comparison uses."""
    if tool_key == "FF":
        text = (run_dir / "stdout.txt").read_text(encoding="utf-8", errors="replace")
        alerts = [dict(d) for d in parse_flawfinder(text, detail=True)]
        info = None
    elif tool_key == "CP":
        text = (run_dir / "stderr.txt").read_text(encoding="utf-8")
        alerts = parse_cppcheck_detail(text)
        _, info = parse_cppcheck(text)
    else:
        alerts = parse_codechecker_detail(run_dir / "reports")
        info = None
    return [with_code(a) for a in alerts], info


def read_time(run_dir: Path):
    path = run_dir / "time.txt"
    if not path.exists():
        return None, None
    import re
    text = path.read_text(encoding="utf-8", errors="replace")
    wall = re.search(r"Elapsed \(wall clock\) time .*: (?:(\d+):)?(\d+):([\d.]+)", text)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", text)
    seconds = None
    if wall:
        h, m, s = wall.groups()
        seconds = (int(h or 0) * 3600) + int(m) * 60 + float(s)
    return seconds, int(rss.group(1)) if rss else None


@app.post("/api/runs")
def start_run(req: RunRequest):
    if req.library not in LIBRARY_IDS or req.tool not in TOOL_KEYS:
        raise HTTPException(400, "unknown library or tool")
    run_id = uuid.uuid4().hex[:12]
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True)
    cache = UI / "cache"
    for sub in ("sources", "build", "deps", "downloads"):
        (cache / sub).mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "-e", "MSYS_NO_PATHCONV=1",
        "-v", f"{out_dir / 'results'}:/home/yhong/comp5355/results",
        "-v", f"{cache / 'downloads'}:/home/yhong/comp5355/downloads",
        "-v", f"{cache / 'sources'}:/home/yhong/comp5355/sources",
        "-v", f"{cache / 'build'}:/home/yhong/comp5355/build",
        "-v", f"{cache / 'deps'}:/home/yhong/comp5355/deps",
        "-v", f"{UI / 'container' / 'run_one.py'}:/replication/run_one.py:ro",
        "--entrypoint", "python3",
        IMAGE, "/replication/run_one.py", req.library, req.tool,
    ]
    lines_file = out_dir / "progress.log"
    proc = subprocess.Popen(cmd, stdout=open(lines_file, "w", encoding="utf-8"),
                            stderr=subprocess.STDOUT, text=True)
    STATE[run_id] = dict(library=req.library, tool=req.tool, process=proc, out=out_dir,
                         started=time.time(), finished=None)
    return dict(run_id=run_id)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    state = STATE.get(run_id)
    if not state:
        raise HTTPException(404, "run not found")

    async def stream():
        log = state["out"] / "progress.log"
        position = 0
        while True:
            if log.exists():
                with open(log, encoding="utf-8", errors="replace") as f:
                    f.seek(position)
                    chunk = f.read()
                    position = f.tell()
                for line in chunk.splitlines():
                    yield f"data: {json.dumps({'line': line}, ensure_ascii=False)}\n\n"
            if state["process"].poll() is not None:
                result = finalize(run_id)
                yield f"event: done\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
                return
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")


def finalize(run_id):
    state = STATE[run_id]
    if state["finished"] is None:
        state["finished"] = time.time()
    run_root = state["out"]
    lib_id, tool_key = state["library"], state["tool"]
    lib = next(l for l in dl.load_libraries() if l["id"] == lib_id)
    project_id = lib["id"]
    # run directory name comes from the frozen configuration
    frozen = json.loads((dl.REPL / "config" / "libraries.json").read_text(encoding="utf-8"))
    item = next(x for x in frozen["libraries"] if x["id"] == lib_id)
    run_name = item["runs"][tool_key]
    run_dir = run_root / item["results_dir"] / run_name
    exit_code = None
    code_file = run_dir / "exit-code.txt"
    if code_file.exists():
        exit_code = int(code_file.read_text().strip() or -1)
    alerts, info = ([], None)
    if run_dir.exists():
        alerts, info = parse_result(tool_key, run_dir)
        alerts = [with_code(alert, project_id) for alert in alerts]
    seconds, rss = read_time(run_dir)
    reference = [r for r in candidates()
                 if r["project_id"] == lib["id"] and r["tool"] == dl.TOOL_NAME[tool_key]]
    return dict(
        run_id=run_id, library=lib_id, tool=tool_key, exit_code=exit_code,
        alerts=alerts, information=info, wall_seconds=seconds, max_rss_kib=rss,
        reference_count=len(reference), replicated_count=len(alerts),
        matches_reference=len(alerts) == len(reference),
    )


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    state = STATE.get(run_id)
    if not state:
        raise HTTPException(404, "run not found")
    return finalize(run_id)
