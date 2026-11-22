"""Export the UI as a static website (for GitHub Pages or any static host).

Every read-only API response is written to a JSON file, and the front end switches to
reading those files (window.P17_STATIC). Live runs need a server with Docker and are
disabled in the static version.

    python ui/tools/build_static.py            writes ui/dist/
    python ui/tools/build_static.py --out DIR
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

UI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UI))

import server  # noqa: E402  (reuses the same endpoint functions as the live server)


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=UI / "dist")
    out = parser.parse_args().out.resolve()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(UI / "static", out / "static")

    api = out / "api"
    write(api / "overview.json", server.overview())
    write(api / "matrix.json", server.get_matrix())
    write(api / "dashboard.json", server.dashboard())
    write(api / "summary.json", server.summary())
    write(api / "reliability.json", server.reliability())
    write(api / "special-cases.json", server.special_cases())
    for lib in server.libraries():
        write(api / "library-detail" / f"{lib['id']}.json", server.library_detail(lib["id"]))
    # All alerts with full detail in one file; the front end filters it in the browser.
    write(api / "candidates.json", server.candidates())

    # Root-relative links become relative so the site works under /<repo>/ on GitHub Pages.
    html = (UI / "static" / "index.html").read_text(encoding="utf-8")
    html = html.replace('"/static/', '"static/')
    html = html.replace("<head>", "<head>\n<script>window.P17_STATIC = true;</script>", 1)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"static site written to {out} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
