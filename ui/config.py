"""All file-system locations used by the UI, in one place.

The UI is self-contained: everything it reads lives under ui/.

  ui/data/       bundled study data (read-only, tracked in git; refresh with tools/sync_data.py)
  ui/vendor/     replication parsers used to read live-run output
  ui/runtime/    writable runtime data (git-ignored), created automatically
      cache/downloads   source archives            (shared with the replication container)
      cache/sources     extracted library sources  (used to show source lines of live runs)
      cache/build       build trees and compilation databases
      cache/deps        installed dependencies (zlib for libpng)
      runs/<run_id>/    output of each live run
      helpers/          helper scripts mounted into the replication container

Environment variables (all optional):

  P17_DATA_DIR          bundled data directory            default ui/data
  P17_RUNTIME_DIR       writable runtime directory        default ui/runtime
  P17_HOST_RUNTIME_DIR  the runtime directory as seen by the Docker host. Needed only when
                        the UI runs in a container and starts replication containers through
                        the host Docker socket. Defaults to P17_RUNTIME_DIR.
  P17_IMAGE             replication image for live runs   default project17-replication:1.0
"""
import os
from pathlib import Path

UI = Path(__file__).resolve().parent


def _path(name, default):
    value = os.environ.get(name)
    return Path(value).resolve() if value else default


DATA = _path("P17_DATA_DIR", UI / "data")
VENDOR = UI / "vendor"

RUNTIME = _path("P17_RUNTIME_DIR", UI / "runtime")
CACHE = RUNTIME / "cache"
RUNS = RUNTIME / "runs"
HELPERS = RUNTIME / "helpers"

# Host-side view of RUNTIME, used for `docker run -v` when the UI runs inside a container.
HOST_RUNTIME = os.environ.get("P17_HOST_RUNTIME_DIR") or str(RUNTIME)

IMAGE = os.environ.get("P17_IMAGE", "project17-replication:1.0")

# Working root inside the replication container (fixed by the original study).
CONTAINER_ROOT = "/home/yhong/comp5355"
CACHE_SUBDIRS = ("downloads", "sources", "build", "deps")


def ensure_dirs():
    for sub in CACHE_SUBDIRS:
        (CACHE / sub).mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    HELPERS.mkdir(parents=True, exist_ok=True)


def host_path(local: Path) -> str:
    """Translate a path under RUNTIME to the same location as seen by the Docker host."""
    local = Path(local).resolve()
    if HOST_RUNTIME == str(RUNTIME):
        return str(local)
    return HOST_RUNTIME.rstrip("/\\") + "/" + local.relative_to(RUNTIME).as_posix()
