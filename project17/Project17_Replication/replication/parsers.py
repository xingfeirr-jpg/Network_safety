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


def parse_flawfinder(text, detail=False):
    """Return (file, line, column, rule) tuples. With detail=True, return dicts that also
    carry the risk level, the category and the indented explanation lines of each hit."""
    hits = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = FLAWFINDER_HIT.match(line)
        if match:
            file, row, col, level, category, rule = match.groups()
            if not detail:
                hits.append((file, int(row), int(col), rule))
                continue
            message = []
            for follow in lines[index + 1:]:
                if not follow.startswith("  ") or FLAWFINDER_HIT.match(follow):
                    break
                message.append(follow.strip())
            hits.append(dict(file=file, line=int(row), column=int(col), rule=rule,
                             level=int(level), category=category, message=" ".join(message)))
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


def parse_codechecker_detail(reports_dir):
    """Same diagnostics as parse_codechecker, plus the description and the path of events
    (the steps the analyzer followed to reach the warning)."""
    diagnostics = []
    for plist in sorted(Path(reports_dir).glob("*.plist")):
        with plist.open("rb") as stream:
            data = plistlib.load(stream)
        files = data.get("files", [])
        for item in data.get("diagnostics", []):
            location = item["location"]
            trace = []
            for step in item.get("path", []):
                step_loc = step.get("location")
                if step_loc is None:
                    continue
                trace.append(dict(file=files[step_loc["file"]], line=int(step_loc["line"]),
                                  column=int(step_loc["col"]), message=step.get("message", "")))
            diagnostics.append(dict(
                file=files[location["file"]], line=int(location["line"]), column=int(location["col"]),
                rule=item["check_name"], category=item.get("category", ""),
                message=item.get("description", ""), trace=trace,
            ))
    return diagnostics


def parse_cppcheck_detail(xml_text):
    """Same diagnostics as parse_cppcheck, with the message, severity, CWE and every location."""
    root = ET.fromstring(xml_text)
    if root.tag != "results" or root.get("version") != "2":
        raise ValueError("not a Cppcheck XML version 2 report")
    diagnostics = []
    for error in root.iter("error"):
        if error.get("severity") == "information":
            continue
        locations = error.findall("location")
        first = locations[0] if locations else None
        diagnostics.append(dict(
            file=first.get("file") if first is not None else "",
            line=int(first.get("line")) if first is not None else 0,
            column=int(first.get("column", 0)) if first is not None else 0,
            rule=error.get("id"), severity=error.get("severity"),
            message=error.get("verbose") or error.get("msg", ""), cwe=error.get("cwe", ""),
            trace=[dict(file=l.get("file"), line=int(l.get("line")), column=int(l.get("column", 0)),
                        message=l.get("info", "")) for l in locations],
        ))
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
