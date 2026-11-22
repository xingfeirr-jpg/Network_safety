"""All file-system locations used by the UI, in one place.

Every path can be overridden with an environment variable, so the same code runs on a
developer machine (defaults below) and inside the Docker deployment (see docker-compose.yml).

  P17_IMPL_DIR        original study data (read-only)       default <repo>/Project17_Implementation_and_Data
  P17_REPL_DIR        replication package (read-only)       default <repo>/Project17_Replication
  P17_DATA_DIR        writable runtime data                 default <repo>/data
      cache/downloads   source archives                     (shared with the replication container)
      cache/sources     extracted library sources           (used to show source lines)
      cache/build       build trees and compilation databases
      cache/deps        installed dependencies (zlib for libpng)
      runs/<run_id>/    output of each live run
      runtime/          helper scripts mounted into the replication container
  P17_HOST_DATA_DIR   the same directory as P17_DATA_DIR, seen from the Docker host.
                      Needed only when the UI itself runs in a container and starts the
                      replication container through the host Docker socket. Defaults to
                      P17_DATA_DIR (correct when both paths are identical).
  P17_IMAGE           replication image name                default project17-replication:1.0
"""
import os
from pathlib import Path

UI = Path(__file__).resolve().parent
ROOT = UI.parent


def _path(name, default):
    value = os.environ.get(name)
    return Path(value).resolve() if value else default


IMPL = _path("P17_IMPL_DIR", ROOT / "Project17_Implementation_and_Data")
REPL = _path("P17_REPL_DIR", ROOT / "Project17_Replication")
RECORDS = IMPL / "data" / "records"

DATA = _path("P17_DATA_DIR", ROOT / "data")
CACHE = DATA / "cache"
RUNS = DATA / "runs"
RUNTIME = DATA / "runtime"

# Host-side view of DATA, used for `docker run -v` when the UI runs inside a container.
HOST_DATA = os.environ.get("P17_HOST_DATA_DIR") or str(DATA)

IMAGE = os.environ.get("P17_IMAGE", "project17-replication:1.0")

# Working root inside the replication container (fixed by the original study).
CONTAINER_ROOT = "/home/yhong/comp5355"
CACHE_SUBDIRS = ("downloads", "sources", "build", "deps")


def ensure_dirs():
    for sub in CACHE_SUBDIRS:
        (CACHE / sub).mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)


def host_path(local: Path) -> str:
    """Translate a path under DATA to the same location as seen by the Docker host."""
    relative = Path(local).resolve().relative_to(DATA)
    if HOST_DATA == str(DATA):
        return str(Path(local).resolve())
    return HOST_DATA.rstrip("/\\") + "/" + relative.as_posix()
