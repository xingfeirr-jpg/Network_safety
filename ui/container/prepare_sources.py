"""Download and extract the pinned library sources into the shared cache (S1 + S2 only).

The UI shows the source line of every alert, read from <data>/cache/sources. On a fresh
deployment that folder is empty; run this once to fill it:

    docker compose --profile tools run --rm prepare-sources            all ten libraries
    docker compose --profile tools run --rm prepare-sources P01 P08    selected libraries

Libraries whose source folder already exists are skipped. Building and running the tools
is left to live runs from the UI.
"""
import sys

sys.path.insert(0, "/replication/replication")
import pipeline as p  # noqa: E402  (original pipeline, unchanged)


def main():
    wanted = set(sys.argv[1:])
    status = 0
    for lib in p.CONFIG["libraries"]:
        if wanted and lib["id"] not in wanted:
            continue
        source = p.BASE / lib["source_dir"]
        if source.is_dir() and any(source.iterdir()):
            print(f"[{p.now()}] {lib['id']} {lib['name']:<13} source already present, skipped", flush=True)
            continue
        log_dir = p.BASE / "sources" / ".prepare-logs" / lib["id"]
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {}
        try:
            archive = p.s1_download(lib, record)
            p.s2_extract(lib, archive, record, log_dir)
        except Exception as error:  # keep going with the other libraries
            print(f"[{p.now()}] {lib['id']} FAILED: {error}", flush=True)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
