# COMP5355 Project 17 — Comparing Three Static Vulnerability Detectors on Ten Open-Source C Libraries

[中文版 README](README.zh-CN.md)

We ran three static analysis tools — **Flawfinder 2.0.20**, **Cppcheck 2.13.0** and **CodeChecker 6.29.1 + Clang Static Analyzer 18.1.3** — on ten pinned open-source C libraries (30 runs in total), reviewed every one of the resulting **725 alerts** against the source code, and compared alert quality and runtime cost.

| Key figures | |
| --- | --- |
| Alerts | 725 (Flawfinder 536 / Cppcheck 116 / clangsa 73) |
| Review outcome | 648 false positives / 62 supported / 15 undetermined |
| Replication | All 30 library-tool runs reproduce the original alert sets |

## Repository layout

```
.
├── Project17_Implementation_and_Data/   original experiment (read-only)
│   ├── code/                            tool scripts, inputs, result rebuild script
│   └── data/                            raw tool output, timing, 725-alert ledger
├── Project17_Replication/               one-step Docker replication + analysis
│   ├── Dockerfile                       Ubuntu 24.04 with the pinned tool versions
│   ├── config/libraries.json            frozen configuration of the ten libraries
│   ├── replication/                     pipeline (S1–S5), parsers, comparison (S6)
│   ├── analysis/  human_review/         figures and stratified human review
│   └── output/                          replication results used by the UI
├── ui/                                  web UI (FastAPI + Plotly)
│   ├── config.py                        all paths, overridable by environment variables
│   ├── server.py                        API + live runs
│   ├── container/                       helpers run inside the replication container
│   ├── static/                          front end
│   └── Dockerfile
├── reports/                             final reports (EN / CN, PDF + DOCX)
├── docker-compose.yml                   deployment
├── .env.example                         deployment settings template
└── data/                                runtime data, created automatically (git-ignored)
```

`backup/` (presentations, report drafts, original archive) is kept locally only and is not tracked by git.

## Deployment (Docker, recommended)

Requirements: a Linux server with Docker Engine 24+ and the Compose plugin, and outbound internet access (Ubuntu/PyPI packages and the library source archives from GitHub).

```bash
git clone <your-repo-url> project17 && cd project17
cp .env.example .env              # edit P17_DATA_DIR (absolute path) and P17_PORT if needed
docker compose up -d --build
```

Then open `http://<server>:8000`.

What `docker compose up` does:

1. **Builds `project17-replication:1.0`** (the analysis image with the pinned tools; 5–10 minutes the first time) and runs `prepare-sources` once, which downloads and extracts the ten pinned library sources into `$P17_DATA_DIR/cache/sources` and then exits. The UI uses these to show the source line of each alert. Libraries already present are skipped on later starts.
2. **Builds and starts `project17-ui`**, which serves the UI and the API on port 8000.

### Data paths

All UI paths are defined in [`ui/config.py`](ui/config.py):

| Variable | Default (local) | Purpose |
| --- | --- | --- |
| `P17_IMPL_DIR` | `<repo>/Project17_Implementation_and_Data` | original study data, read-only (baked into the image) |
| `P17_REPL_DIR` | `<repo>/Project17_Replication` | replication package, read-only (baked into the image) |
| `P17_DATA_DIR` | `<repo>/data` | writable runtime data |
| `P17_HOST_DATA_DIR` | same as `P17_DATA_DIR` | the data directory as seen by the Docker host |
| `P17_IMAGE` | `project17-replication:1.0` | image used for live runs |

Runtime data layout:

```
$P17_DATA_DIR/
├── cache/
│   ├── downloads/   source archives (SHA-256 checked)
│   ├── sources/     extracted library sources
│   ├── build/       build trees + compilation databases (reused across runs)
│   └── deps/        installed dependencies (zlib for libpng)
├── runs/<run_id>/   output and progress log of each live run
└── runtime/         helper script mounted into the replication container
```

**Why `P17_DATA_DIR` must be absolute:** a live run started from the UI launches a *sibling* replication container through `/var/run/docker.sock`. Docker resolves `-v` paths on the host, so compose mounts the data directory at the **same absolute path** inside the UI container. That way every path the UI hands to Docker is valid on the host.

### Operations

```bash
docker compose logs -f ui                              # UI logs
docker compose run --rm prepare-sources P01 P08        # (re)fetch selected library sources
docker compose up -d --build                           # update after git pull
docker compose down                                    # stop (data in P17_DATA_DIR is kept)
```

On a slow network, set `UBUNTU_MIRROR` and `PIP_INDEX_URL` in `.env` (examples are in `.env.example`); tool versions are pinned, so mirrors do not change results.

> **Security note:** the UI container has access to the host Docker socket in order to start analysis containers. Do not expose port 8000 directly to the public internet; put it behind a reverse proxy with authentication or restrict it by firewall.

## Local development (without Docker for the UI)

```bash
pip install -r ui/requirements.txt
cd ui && uvicorn server:app --reload --port 8000
```

Runtime data goes to `<repo>/data`. Live runs still need Docker and the replication image: `docker build -t project17-replication:1.0 Project17_Replication`.

## Full replication from the command line

```bash
cd Project17_Replication
bash run_replication.sh          # all ten libraries
bash run_replication.sh P01      # zlib only (about 2 minutes)
```

See [Project17_Replication/README.md](Project17_Replication/README.md) for the pipeline, data formats, review procedure and full analysis, and [Project17_Implementation_and_Data/README.md](Project17_Implementation_and_Data/README.md) for the original experiment records.

## Reports

- [reports/Project17_Report.pdf](reports/Project17_Report.pdf) (English)
- [reports/Project17_Report_CN.pdf](reports/Project17_Report_CN.pdf) (Chinese)
