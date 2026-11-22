"""Run steps S1-S5 for the ten libraries inside the Docker container.

S1 download   fetch the pinned source archive and check its SHA-256
S2 extract    unpack into the same directory as the original study and hash every file
S3 build      build the target with the original CMake options and export the compilation
              database; apply the libjpeg-turbo action filter and the libpng Cppcheck
              database adaptation used in the original study
S4 configure  build the three tool commands from config/libraries.json (byte-identical
              to the frozen original commands)
S5 run        run the three tools in turn and record wall time and maximum RSS with GNU time

S6 (comparison with the original results) is done by compare.py on the host.

Usage (inside the container): python3 pipeline.py [--only P01,P08]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from common import TOOLS, analysis_db, argv, build_db, expand, load_config, run_dir

CONFIG = load_config()
BASE = Path(CONFIG["base"])
RESULTS = BASE / "results"
LOG_ROOT = RESULTS / "_replication"
ENV = dict(os.environ, LC_ALL="C", CC_ANALYZER_BIN="clangsa:/usr/bin/clang-18")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def say(lib, step, message):
    print(f"[{now()}] {lib['id']} {lib['name']:<13} {step}  {message}", flush=True)


def run_logged(log_dir, name, command, cwd=None):
    """Run one preparation command, save its command, output and exit code; raise on failure."""
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{name}-command.json").write_text(json.dumps(command, ensure_ascii=False, indent=1) + "\n")
    with open(log_dir / f"{name}-stdout.txt", "wb") as out, open(log_dir / f"{name}-stderr.txt", "wb") as err:
        code = subprocess.run(command, cwd=cwd or BASE, env=ENV, stdout=out, stderr=err).returncode
    (log_dir / f"{name}-exit-code.txt").write_text(f"{code}\n")
    if code != 0:
        raise RuntimeError(f"{name} failed with exit code {code}; see {log_dir}")


# ---------- S1 download ----------
def s1_download(lib, record):
    downloads = BASE / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / f"{Path(lib['source_dir']).name}.tar.gz"
    expected = lib["download"]["sha256"]
    if not (archive.is_file() and (expected is None or sha256(archive) == expected)):
        say(lib, "S1", f"downloading {lib['download']['url']}")
        partial = archive.with_suffix(".part")
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(lib["download"]["url"], timeout=120) as response, open(partial, "wb") as out:
                    shutil.copyfileobj(response, out)
                break
            except OSError as error:
                if attempt == 3:
                    raise
                say(lib, "S1", f"download attempt {attempt} failed ({error}); retrying")
                time.sleep(5 * attempt)
        partial.replace(archive)
    actual = sha256(archive)
    if expected is not None and actual != expected:
        raise RuntimeError(f"archive hash mismatch: expected {expected}, got {actual}")
    record["S1"] = dict(archive=str(archive), sha256=actual, expected_sha256=expected,
                        matches_original=None if expected is None else True)
    say(lib, "S1", f"archive SHA-256 {'matches the original study' if expected else 'recorded (no original value)'}")
    return archive


# ---------- S2 extract ----------
def s2_extract(lib, archive, record, log_dir):
    source = BASE / lib["source_dir"]
    if source.exists():
        shutil.rmtree(source)
    staging = BASE / "sources" / f".extract-{lib['id']}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        tar.extractall(staging, filter="tar")
    roots = list(staging.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise RuntimeError(f"archive should have one top-level directory, found {[p.name for p in roots]}")
    roots[0].rename(source)
    staging.rmdir()
    lines = [f"{sha256(path)}  {path}" for path in sorted(source.rglob("*"))
             if path.is_file() and not path.is_symlink()]
    (log_dir / "source-files.sha256").write_text("\n".join(lines) + "\n")
    record["S2"] = dict(source_dir=str(source), regular_files=len(lines))
    say(lib, "S2", f"extracted to {source}; hashed {len(lines)} files")


# ---------- S3 build ----------
def s3_build(lib, record, log_dir, libraries):
    build = lib["build"]
    if "depends_on" in build:
        dependency = libraries[build["depends_on"]]
        prefix = BASE / "deps" / Path(dependency["build_dir"]).name
        if not (prefix / "include" / "zlib.h").is_file():
            if not Path(build_db(CONFIG, dependency)).is_file():
                say(lib, "S3", f"building dependency {dependency['name']} first")
                prepare(dependency, libraries, run_tools=False)
            say(lib, "S3", f"installing {dependency['name']} into {prefix}")
            run_logged(log_dir, "dependency-install",
                       ["cmake", "--install", str(BASE / dependency["build_dir"]), "--prefix", str(prefix),
                        "--component", "Development", "--config", "Debug"])
    build_dir = BASE / lib["build_dir"]
    if build_dir.exists():
        shutil.rmtree(build_dir)
    source = BASE / lib["source_dir"]
    if build["cmake_subdir"]:
        source = source / build["cmake_subdir"]
    options = [expand(option, CONFIG) for option in build["options"]]
    say(lib, "S3", f"configuring with CMake and building target {build['target']}")
    run_logged(log_dir, "configure", ["cmake", "-S", str(source), "-B", str(build_dir), "-G", "Ninja", *options])
    run_logged(log_dir, "build", ["cmake", "--build", str(build_dir), "--target", build["target"], "--parallel", "1"])
    database = json.loads(Path(build_db(CONFIG, lib)).read_text())
    shutil.copy(build_db(CONFIG, lib), log_dir / "compile_commands.build.json")
    record["S3"] = dict(build_dir=str(build_dir), compile_actions=len(database))

    if "analysis_db" in lib:                      # libjpeg-turbo: keep only the library actions
        keep = tuple(lib["analysis_db"]["keep_output_dirs"])
        selected = [entry for entry in database if entry.get("output", "").startswith(keep)]
        write_json(lib["analysis_db"]["path"], selected)
        shutil.copy(lib["analysis_db"]["path"], log_dir / "compile_commands.analysis.json")
        record["S3"]["analysis_actions"] = len(selected)
    if "database" in lib["cppcheck"]:             # libpng: adapted database used only by Cppcheck
        old, new = (expand(text, CONFIG) for text in lib["cppcheck"]["database"]["replace"])
        adapted = [dict(entry, command=entry["command"].replace(old, new)) for entry in database]
        changed = sum(a["command"] != b["command"] for a, b in zip(adapted, database))
        write_json(lib["cppcheck"]["database"]["path"], adapted)
        shutil.copy(lib["cppcheck"]["database"]["path"], log_dir / "compile_commands.cppcheck.json")
        record["S3"]["cppcheck_adapted_actions"] = changed
    say(lib, "S3", f"compilation database has {len(database)} actions" + (
        f", {record['S3']['analysis_actions']} used for analysis" if "analysis_actions" in record["S3"] else ""))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


# ---------- S4 + S5 build the command and run it ----------
def s5_run(lib, tool_key, record):
    run = Path(run_dir(CONFIG, lib, tool_key))
    if run.exists():
        shutil.rmtree(run)
    run.mkdir(parents=True)
    command = argv(CONFIG, lib, tool_key)                       # S4
    (run / "command.json").write_text(json.dumps(command, ensure_ascii=False, indent=1) + "\n")
    if tool_key == "FF":
        lines = [f"{sha256(item)}  {item}" for item in command[5:]]
        (run / "input-files.sha256").write_text("\n".join(lines) + "\n")
    if tool_key == "CP":
        (run / "cache").mkdir()
    if tool_key in ("CP", "CC"):
        shutil.copy(analysis_db(CONFIG, lib, tool_key), run / "compile_commands.input.json")
    say(lib, "S5", f"running {lib['runs'][tool_key]}")
    started = now()
    with open(run / "stdout.txt", "wb") as out, open(run / "stderr.txt", "wb") as err:
        code = subprocess.run(["/usr/bin/time", "-v", "-o", str(run / "time.txt"), "--", *command],
                              cwd=BASE, env=ENV, stdout=out, stderr=err).returncode
    (run / "exit-code.txt").write_text(f"{code}\n")
    record.setdefault("S5", {})[tool_key] = dict(run_id=lib["runs"][tool_key], exit_code=code,
                                                started_utc=started, ended_utc=now())
    say(lib, "S5", f"{lib['runs'][tool_key]} exit code {code}")


def prepare(lib, libraries, run_tools=True):
    log_dir = LOG_ROOT / lib["id"]
    if log_dir.exists() and run_tools:
        shutil.rmtree(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    record = dict(id=lib["id"], name=lib["name"], version=lib["version"], started_utc=now())
    archive = s1_download(lib, record)
    s2_extract(lib, archive, record, log_dir)
    s3_build(lib, record, log_dir, libraries)
    if run_tools:
        for tool_key, _ in TOOLS:
            s5_run(lib, tool_key, record)
    record["ended_utc"] = now()
    (log_dir / "steps.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def capture_environment():
    queries = [("os-release", ["cat", "/etc/os-release"]), ("cmake", ["cmake", "--version"]),
               ("ninja", ["ninja", "--version"]), ("clang-18", ["clang-18", "--version"]),
               ("cppcheck", ["cppcheck", "--version"]), ("python", [sys.executable, "--version"]),
               ("flawfinder", [str(BASE / ".venv/bin/flawfinder"), "--version"]),
               ("CodeChecker", [str(BASE / ".venv/bin/CodeChecker"), "analyzer-version"]),
               ("glibc", ["ldd", "--version"]),
               ("packages", ["dpkg-query", "-W", "clang-18", "cppcheck", "time", "cmake", "ninja-build", "libc6-dev"]),
               ("cpu", ["nproc"]), ("memory", ["grep", "MemTotal", "/proc/meminfo"])]
    parts = [f"Recorded UTC: {now()}\n"]
    for name, command in queries:
        result = subprocess.run(command, env=ENV, capture_output=True, text=True)
        parts.append(f"[{name}]\n{result.stdout.strip() or result.stderr.strip()}\n")
    (LOG_ROOT / "environment.txt").write_text("\n".join(parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="run only these libraries, e.g. P01,P08")
    args = parser.parse_args()
    libraries = {lib["id"]: lib for lib in CONFIG["libraries"]}
    selected = args.only.split(",") if args.only else list(libraries)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    capture_environment()
    summary, failed = [], []
    for lib_id in selected:
        lib = libraries[lib_id]
        try:
            summary.append(prepare(lib, libraries))
        except Exception as error:                 # one failing library does not stop the others
            say(lib, "!!", f"failed: {error}")
            failed.append(dict(id=lib_id, error=str(error)))
    (LOG_ROOT / "pipeline_summary.json").write_text(
        json.dumps(dict(finished_utc=now(), completed=[r["id"] for r in summary], failed=failed),
                   ensure_ascii=False, indent=2) + "\n")
    print(f"{len(summary)} libraries completed, {len(failed)} failed. Next: run compare.py on the host.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
