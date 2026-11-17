"""Parse the raw output of the three tools into one alert format.

Counting rules follow the original study (report Section 2.4):
- Flawfinder: every hit displayed with --minlevel=1;
- Cppcheck: every <error> element whose severity is not "information"; an element with
  several locations counts once and uses its first location;
- CodeChecker/clangsa: every diagnostic saved in the plist files under reports/.

Each alert becomes (file, line, column, rule).
"""
import plistlib
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# Example: /home/yhong/comp5355/sources/zlib-v1.3.2/gzguts.h:91:15:  [4] (format) vsnprintf:
FLAWFINDER_HIT = re.compile(r"^(/[^:]+):(\d+):(\d+):\s+\[(\d)\]\s+\(([^)]+)\)\s+([^:\s]+):")
FLAWFINDER_TOTAL = re.compile(r"^Hits = (\d+)$", re.M)


def parse_flawfinder(text):
    hits = []
    for line in text.splitlines():
        match = FLAWFINDER_HIT.match(line)
        if match:
            file, row, col, _level, _category, rule = match.groups()
            hits.append((file, int(row), int(col), rule))
    total = FLAWFINDER_TOTAL.search(text)
    if total and int(total.group(1)) != len(hits):
        raise ValueError(f"Flawfinder summary says Hits={total.group(1)} but {len(hits)} hits were parsed")
    return hits


def parse_cppcheck(xml_text):
    """Return (source diagnostics, number of information items)."""
    root = ET.fromstring(xml_text)
    if root.tag != "results" or root.get("version") != "2":
        raise ValueError("not a Cppcheck XML version 2 report")
    diagnostics, information = [], 0
    for error in root.iter("error"):
        if error.get("severity") == "information":
            information += 1
            continue
        location = error.find("location")
        if location is None:
            diagnostics.append(("", 0, 0, error.get("id")))
        else:
            diagnostics.append((location.get("file"), int(location.get("line")),
                                int(location.get("column", 0)), error.get("id")))
    return diagnostics, information


def parse_codechecker(reports_dir):
    diagnostics = []
    for plist in sorted(Path(reports_dir).glob("*.plist")):
        with plist.open("rb") as stream:
            data = plistlib.load(stream)
        files = data.get("files", [])
        for item in data.get("diagnostics", []):
            location = item["location"]
            diagnostics.append((files[location["file"]], int(location["line"]),
                                int(location["col"]), item["check_name"]))
    return diagnostics


LIBRARY_ROOT = re.compile(r"^/home/[^/]+/comp5355/(?:sources|build)/[^/]+/")


def relative_path(path):
    """Strip the .../comp5355/sources/<lib>/ or .../build/<lib>/ prefix.

    The original review ledger stores absolute paths for most libraries and relative
    paths for libpng, so both sides are reduced to library-relative paths.
    """
    return LIBRARY_ROOT.sub("", str(path))


def as_counter(alerts):
    """Compare by count: one location can be reported once per build configuration
    (for example libjpeg-turbo at 8, 12 and 16 bits)."""
    return Counter((relative_path(f), int(l), int(c), str(r)) for f, l, c, r in alerts)
