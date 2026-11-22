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
│   ├── config/  replication/            frozen configuration, pipeline S1–S6
│   ├── analysis/  human_review/         figures and stratified human review
│   └── output/                          replication results
├── ui/                                  web UI — self-contained
│   ├── data/                            bundled copies of all data the UI reads
│   ├── vendor/                          replication parsers (for live-run output)
│   ├── static/                          front end
│   ├── container/                       helpers run inside the replication container
│   ├── tools/                           sync_data.py, build_static.py
│   ├── config.py  server.py ...         backend (FastAPI)
│   ├── runtime/                         source cache + live runs (created automatically, git-ignored)
│   └── Dockerfile
├── reports/                             final reports (EN / CN, PDF + DOCX)
├── .github/workflows/pages.yml          automatic GitHub Pages deployment
├── docker-compose.yml  .env.example     server deployment
└── backup/                              presentations, drafts (local only, git-ignored)
```

The UI only reads files inside `ui/`. After changing the research packages, refresh its copy with `python ui/tools/sync_data.py`.

## Two ways to deploy

| | GitHub Pages | Docker server |
| --- | --- | --- |
| How | push to GitHub — automatic | `docker compose up -d --build` on a server |
| Cost | free (public repository) | needs a Linux server |
| Browse libraries, tools, dashboard, alerts, cases, conclusions | ✅ | ✅ |
| **Live run** (run a tool on a library in Docker) | ❌ needs a backend | ✅ |

GitHub Pages only hosts static files, so it cannot run the Python backend or Docker. The workflow therefore pre-generates every API response as JSON and publishes a static version of the UI; everything works except live runs.

### Option A: GitHub Pages (automatic on push)

1. Push the repository to GitHub.
2. In the repository go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions** (one time).
3. Every push to `main` runs [`.github/workflows/pages.yml`](.github/workflows/pages.yml), which builds the site with `ui/tools/build_static.py` and publishes it at `https://<user>.github.io/<repo>/`. Progress is visible in the **Actions** tab; you can also run it manually there ("Run workflow").

Pages for private repositories requires a paid GitHub plan; on the free plan make the repository public.

Preview the static build locally:

```bash
pip install -r ui/requirements.txt
python ui/tools/build_static.py          # writes ui/dist/
python -m http.server -d ui/dist 8000    # open http://localhost:8000
```

### Option B: Docker server (full features)

Requirements: Linux with Docker Engine 24+ and the Compose plugin, outbound internet access.

```bash
git clone <repo-url> project17 && cd project17
cp .env.example .env              # adjust P17_RUNTIME_DIR (absolute path) and P17_PORT if needed
docker compose up -d --build
```

Open `http://<server>:8000`. This builds two images:

- `project17-ui` — the web UI and API (data bundled from `ui/`).
- `project17-replication:1.0` — the pinned analysis tools used by live runs (5–10 minutes the first time).

Runtime data (written only by live runs) lives in `P17_RUNTIME_DIR`:

```
$P17_RUNTIME_DIR/
├── cache/downloads/   source archives (SHA-256 checked)
├── cache/sources/     extracted library sources
├── cache/build/       build trees + compilation databases, reused across runs
├── cache/deps/        installed dependencies (zlib for libpng)
├── runs/<run_id>/     output and progress log of each live run
└── helpers/           helper script mounted into the replication container
```

**Why it must be an absolute path:** a live run launches a *sibling* replication container through `/var/run/docker.sock`. Docker resolves `-v` paths on the host, so compose mounts the runtime directory at the **same absolute path** inside the UI container; every path the UI hands to Docker is then valid on the host.

```bash
docker compose logs -f ui                       # logs
docker compose run --rm prepare-sources         # optional: pre-fetch all library sources
git pull && docker compose up -d --build        # update
docker compose down                             # stop (runtime data is kept)
```

On a slow network set `UBUNTU_MIRROR` / `PIP_INDEX_URL` in `.env` (see `.env.example`); tool versions are pinned, so mirrors do not change results.

> **Security:** the UI container can use the host Docker socket. Do not expose port 8000 directly to the internet; put it behind an authenticated reverse proxy or restrict it with a firewall.

### UI configuration

All paths are defined in [`ui/config.py`](ui/config.py); every one is optional.

| Variable | Default | Purpose |
| --- | --- | --- |
| `P17_DATA_DIR` | `ui/data` | bundled study data (read-only) |
| `P17_RUNTIME_DIR` | `ui/runtime` | writable runtime data |
| `P17_HOST_RUNTIME_DIR` | same as `P17_RUNTIME_DIR` | the runtime directory as seen by the Docker host |
| `P17_IMAGE` | `project17-replication:1.0` | image used for live runs |

## Local development

```bash
pip install -r ui/requirements.txt
cd ui && uvicorn server:app --reload --port 8000
```

Live runs also need Docker and the image: `docker build -t project17-replication:1.0 Project17_Replication`.

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
