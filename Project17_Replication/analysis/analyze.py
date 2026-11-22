"""Multi-dimensional analysis of the 725 alerts; writes figures and tables.

    python analysis/analyze.py

Reads only the original review ledger and final matrix (plus the replication comparison
table) and writes to output/analysis/:
    figures/*.png   charts
    tables/*.csv    one data table per dimension
    examples.csv    one representative example per category

Dimensions:
    1 tool x outcome        alerts, false positives, supported and undetermined per tool, and the
                            number of alerts reviewed per supported alert
    2 library x tool        alerts and supported alerts per tool on each library
    3 risk class x outcome  rules grouped into six risk classes (see RISK_CATEGORY)
    4 rule                  alerts and supported share per rule
    5 supported kinds       the 62 supported alerts grouped into eight kinds of issue
    6 undetermined gaps     the 15 undetermined alerts grouped by the missing evidence
    7 false-positive basis  the 648 false positives grouped by keywords in the review
                            rationale (approximate, for reading only)
    8 cross-tool overlap    locations reported by more than one tool
    9 cost                  wall time and maximum RSS (original, and replication if present)
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT.parent / "Project17_Implementation_and_Data" / "data" / "records"
LEDGER = ORIGINAL / "ten_project_synthesis_20261029" / "Candidate_Review_Combined.csv"
MATRIX = ORIGINAL / "formal_comparison_20261030" / "Final_Matrix.csv"
REPLICATION = ROOT / "output" / "comparison.csv"
OUT = ROOT / "output" / "analysis"

TOOLS = ["Flawfinder", "Cppcheck", "CodeChecker/clangsa"]
TOOL_SHORT = {"Flawfinder": "Flawfinder", "Cppcheck": "Cppcheck", "CodeChecker/clangsa": "clangsa"}
LIBRARIES = ["zlib", "LZ4", "cJSON", "libyaml", "json-c", "yyjson", "Expat", "libpng", "libjpeg-turbo", "utf8proc"]
# Outcome values exactly as stored (in Chinese) in the original review ledger
FP, SUP, UND = "原风险误报", "有依据", "无法判断"
LABELS = [FP, SUP, UND]
LABEL_TEXT = {FP: "False positive", SUP: "Supported", UND: "Undetermined"}
COLORS = {FP: "#9aa5b1", SUP: "#2f80c1", UND: "#e0a33b"}
TOOL_COLORS = {"Flawfinder": "#e0a33b", "Cppcheck": "#2f80c1", "CodeChecker/clangsa": "#5aa469"}

# Dimension 3: each rule belongs to exactly one risk class
RISK_CATEGORY = {
    "Buffer and memory access": ["memcpy", "strcpy", "strcat", "strncpy", "char", "strlen", "read", "negativeIndex",
                  "arrayIndexOutOfBoundsCond", "pointerOutOfBoundsCond"],
    "Formatted output": ["fprintf", "sprintf", "snprintf", "vsnprintf", "vsprintf", "vfprintf", "_snprintf", "vprintf",
              "syslog", "invalidPrintfArgType_sint"],
    "Null pointer": ["core.NullDereference", "unix.cstring.NullArg", "core.NonNullParamChecker", "nullPointerRedundantCheck",
            "nullPointerArithmeticRedundantCheck", "nullPointerArithmetic", "ctunullpointer", "core.CallAndMessage"],
    "Integer, shift and division": ["core.UndefinedBinaryOperatorResult", "core.DivideZero", "core.BitwiseShift",
                  "shiftTooManyBitsSigned", "shiftNegativeLHS", "zerodiv", "integerOverflowCond",
                  "AssignmentIntegerToAddress"],
    "File, environment and command": ["open", "fopen", "getenv", "system"],
    "Code quality (dead store, uninitialized)": ["deadcode.DeadStores", "uselessAssignmentPtrArg", "legacyUninitvar",
                        "core.uninitialized.Branch"],
}
RULE_TO_RISK = {rule: category for category, rules in RISK_CATEGORY.items() for rule in rules}

# Dimension 5: kinds of supported alerts, decided by tool and rule
SUPPORTED_KIND = [
    ("Right shift of negative values", lambda r: r["rule"] == "shiftTooManyBitsSigned"),
    ("Dead store or ineffective assignment", lambda r: r["rule"] in ("deadcode.DeadStores", "uselessAssignmentPtrArg")),
    ("Redundant null check", lambda r: r["rule"] == "nullPointerRedundantCheck"),
    ("Arithmetic on a null pointer", lambda r: r["rule"].startswith("nullPointerArithmetic")),
    ("Conditional buffer overflow", lambda r: r["tool"] == "Flawfinder" and r["rule"] == "memcpy"),
    ("Null passed to a non-null parameter", lambda r: r["rule"] == "core.NonNullParamChecker"),
    ("Copy to a null destination", lambda r: r["rule"] == "unix.cstring.NullArg"),
    ("Unchecked environment value", lambda r: r["rule"] == "getenv"),
]

# Dimension 6: undetermined alerts grouped by the missing evidence
UNDETERMINED_GAP = [
    ("Caller and deployment context",
     lambda r: r["tool"] == "Flawfinder" and r["rule"] in ("vsnprintf", "open", "fopen", "getenv")),
    ("Copy path at the INT_MAX boundary",
     lambda r: r["tool"] == "Flawfinder" and r["rule"] == "memcpy"),
    ("Feasible path to the copy",
     lambda r: r["rule"] == "unix.cstring.NullArg"),
]

# Dimension 7: basis for ruling out a false positive. The keywords match the Chinese review
# rationale (sourceEvidence) in the original ledger; the first matching class wins.
FALSE_POSITIVE_REASON = [
    ("Code not compiled in this build",
     ["未定义", "不活动", "未激活", "不编入", "未编入", "后备分支", "不参与", "未启用", "未选择", "不存在该", "为假",
      "兼容分支", "调试宏", "本配置为空", "与实际config", "条件不成立", "均不成立", "相反"]),
    ("Name match, not a call",
     ["不是调用", "没有调用", "不是strlen", "声明整数", "整数参数", "宏存在性", "参数名", "命中的是", "词法", "标识符",
      "注释", "不是函数", "并非调用", "没有执行", "名称匹配", "仅为声明", "宏别名", "宏替代", "不是格式化调用", "形参",
      "#error", "错误文本", "只声明", "宏定义不会", "结构成员", "字段名"]),
    ("Error handler does not return", ["error_exit", "ERREXIT", "不返回", "noreturn", "longjmp"]),
    ("String known to be NUL-terminated", ["终止字符串", "已终止", "NUL结尾", "NUL 结尾", "以NUL", "NUL终止", "终止符"]),
    ("Earlier null or range check",
     ["先检查", "已检查", "判空", "之前检查", "前检查", "守卫", "先判", "路径矛盾", "不可达", "检查后", "保证非空",
      "直接返回", "直接选择返回"]),
    ("Constant format or argument", ["常量", "字面量", "固定格式", "固定字符串", "常数", "固定的数值"]),
    ("Write length bounded by capacity",
     ["容量", "上界", "分配", "长度", "≤", "<=", "足够", "不超过", "范围", "大小", "字节"]),
]

# Preferred examples: cases discussed in the report, then the clearest cases (library, rule, file, line)
REPORT_CASES = {
    ("libyaml", "sprintf", "dumper.c", "254"), ("libyaml", "strlen", "emitter.c", "1475"),
    ("zlib", "core.DivideZero", "gzwrite.c", "303"),
    ("utf8proc", "strlen", "utf8proc.c", "126"), ("cJSON", "strcpy", "cJSON.c", "456"),
    ("zlib", "memcpy", "gzwrite.c", "217"), ("libpng", "memcpy", "pngrutil.c", "3942"),
    ("libjpeg-turbo", "memcpy", "jdatadst.c", "134"), ("libjpeg-turbo", "core.NullDereference", "jdapistd.c", "211"),
    ("libjpeg-turbo", "nullPointerRedundantCheck", "jdapistd.c", "211"), ("LZ4", "unix.cstring.NullArg", "lz4hc.c", "1753"),
    ("LZ4", "unix.cstring.NullArg", "lz4.c", "2179"), ("libyaml", "memcpy", "api.c", "854"),
    ("Expat", "getenv", "xmlparse.c", "8826"), ("cJSON", "uselessAssignmentPtrArg", "cJSON.c", "3190"),
    ("libjpeg-turbo", "deadcode.DeadStores", "jclhuff.c", "364"), ("libjpeg-turbo", "shiftTooManyBitsSigned", "jchuff.c", "584"),
    ("yyjson", "nullPointerArithmeticRedundantCheck", "yyjson.c", "2498"), ("libpng", "core.NonNullParamChecker", "pngset.c", "1076"),
    ("cJSON", "nullPointerRedundantCheck", "cJSON.c", "1497"), ("zlib", "vsnprintf", "gzwrite.c", "467"),
    ("libjpeg-turbo", "getenv", "jinclude.h", "96"), ("libpng", "fprintf", "pngdebug.h", "87"),
}


def short_path(path):
    return re.sub(r"^/home/[^/]+/comp5355/(?:sources|build)/[^/]+/", "", path)


def classify(row, table, field=None):
    for name, test in table:
        if (test(row) if callable(test) else any(key in row[field] for key in test)):
            return name
    return "Other"


def fp_reason(row):
    return classify(row, FALSE_POSITIVE_REASON, "sourceEvidence")


def pick_example(rows):
    """Prefer a listed case; otherwise take the longest rationale (ties broken by key, so the choice is stable)."""
    for row in rows:
        key = (row["project"], row["rule"], short_path(row["file"]).split("/")[-1], row["line"])
        if key in REPORT_CASES:
            return row
    return sorted(rows, key=lambda r: (-len(r["sourceEvidence"]), r["candidateKey"]))[0]


def write_table(name, header, rows):
    path = OUT / "tables" / f"{name}.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def setup_fonts():
    plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    for side in ("top", "right"):
        plt.rcParams[f"axes.spines.{side}"] = False


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / "figures" / f"{name}.png", bbox_inches="tight")
    plt.close(fig)


def stacked_bars(ax, categories, counts, horizontal=False):
    """counts[category][label] -> stacked bar chart with a number on each segment."""
    base = [0] * len(categories)
    largest = max(sum(counts[c].get(label, 0) for label in LABELS) for c in categories)
    for label in LABELS:
        values = [counts[c].get(label, 0) for c in categories]
        if horizontal:
            bars = ax.barh(categories, values, left=base, color=COLORS[label], label=LABEL_TEXT[label])
        else:
            bars = ax.bar(categories, values, bottom=base, color=COLORS[label], label=LABEL_TEXT[label])
        for bar, value in zip(bars, values):
            if value >= largest * 0.04:          # skip labels on thin segments to avoid overlap
                x = bar.get_x() + bar.get_width() / 2
                y = bar.get_y() + bar.get_height() / 2
                ax.text(x, y, str(value), ha="center", va="center", fontsize=8,
                        color="white" if label != FP else "#222")
        base = [b + v for b, v in zip(base, values)]
    ax.legend(frameon=False)


def main():
    if not LEDGER.exists():
        sys.exit(f"review ledger not found: {LEDGER}")
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    setup_fonts()
    with open(LEDGER, encoding="utf-8-sig") as stream:
        ledger = list(csv.DictReader(stream))
    with open(MATRIX, encoding="utf-8-sig") as stream:
        matrix = list(csv.DictReader(stream))
    for row in ledger:
        row["risk"] = RULE_TO_RISK.get(row["rule"], "Other")
    examples = []

    def add_example(dimension, category, rows):
        row = pick_example(rows)
        examples.append([dimension, category, len(rows), row["project"], row["tool"], row["rule"],
                         f'{short_path(row["file"])}:{row["line"]}', LABEL_TEXT[row["normalizedFinalLabel"]],
                         row["sourceEvidence"]])

    # 1 tool x outcome
    by_tool = {t: Counter(r["normalizedFinalLabel"] for r in ledger if r["tool"] == t) for t in TOOLS}
    rows = []
    for tool in TOOLS:
        c = by_tool[tool]
        total = sum(c.values())
        per = f'{total / c[SUP]:.1f}' if c[SUP] else ""
        rows.append([tool, total, c[FP], c[SUP], c[UND],
                     f'{100 * c[SUP] / total:.1f}%', per])
    write_table("1_tool_verdict", ["tool", "alerts", "false_positive", "supported", "undetermined", "supported_share", "alerts_per_supported"], rows)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    stacked_bars(axes[0], [TOOL_SHORT[t] for t in TOOLS], {TOOL_SHORT[t]: by_tool[t] for t in TOOLS})
    axes[0].set_title("Review outcomes by tool")
    axes[0].set_ylabel("Alerts")
    per_supported = [sum(by_tool[t].values()) / by_tool[t][SUP] for t in TOOLS]
    bars = axes[1].bar([TOOL_SHORT[t] for t in TOOLS], per_supported, color=[TOOL_COLORS[t] for t in TOOLS])
    axes[1].bar_label(bars, fmt="%.1f")
    axes[1].set_title("Alerts reviewed per supported alert")
    save(fig, "1_tool_verdict")
    for tool in TOOLS:
        for label in LABELS:
            subset = [r for r in ledger if r["tool"] == tool and r["normalizedFinalLabel"] == label]
            if subset:
                add_example("1 tool x outcome", f"{tool} / {LABEL_TEXT[label]}", subset)

    # 2 library x tool
    raw = {(lib, t): 0 for lib in LIBRARIES for t in TOOLS}
    supported = dict(raw)
    for r in ledger:
        raw[(r["project"], r["tool"])] += 1
        supported[(r["project"], r["tool"])] += r["normalizedFinalLabel"] == SUP
    write_table("2_library_tool", ["library"] + [f"{TOOL_SHORT[t]}_alerts" for t in TOOLS] + [f"{TOOL_SHORT[t]}_supported" for t in TOOLS],
                [[lib] + [raw[(lib, t)] for t in TOOLS] + [supported[(lib, t)] for t in TOOLS] for lib in LIBRARIES])
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, data, title, cmap in ((axes[0], raw, "Raw alerts", "Oranges"), (axes[1], supported, "Supported alerts", "Blues")):
        grid = [[data[(lib, t)] for t in TOOLS] for lib in LIBRARIES]
        ax.imshow(grid, cmap=cmap, aspect="auto")
        ax.set_xticks(range(len(TOOLS)), [TOOL_SHORT[t] for t in TOOLS])
        ax.set_yticks(range(len(LIBRARIES)), LIBRARIES)
        for i, line in enumerate(grid):
            for j, value in enumerate(line):
                ax.text(j, i, value, ha="center", va="center", fontsize=9,
                        color="white" if value > max(map(max, grid)) * 0.6 else "#222")
        ax.set_title(title)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
    save(fig, "2_library_tool")

    # 3 risk class x outcome
    risks = list(RISK_CATEGORY)
    by_risk = {k: Counter(r["normalizedFinalLabel"] for r in ledger if r["risk"] == k) for k in risks}
    write_table("3_risk_verdict", ["risk_class", "rules", "alerts", "false_positive", "supported", "undetermined"],
                [[k, " ".join(RISK_CATEGORY[k]), sum(by_risk[k].values()), by_risk[k][FP], by_risk[k][SUP],
                  by_risk[k][UND]] for k in risks])
    fig, ax = plt.subplots(figsize=(10, 4))
    order = sorted(risks, key=lambda k: sum(by_risk[k].values()))
    stacked_bars(ax, order, by_risk, horizontal=True)
    ax.set_title("Review outcomes by risk class")
    ax.set_xlabel("Alerts")
    save(fig, "3_risk_verdict")
    for k in risks:
        for label in LABELS:
            subset = [r for r in ledger if r["risk"] == k and r["normalizedFinalLabel"] == label]
            if subset:
                add_example("3 risk class", f"{k} / {LABEL_TEXT[label]}", subset)

    # 4 rule
    by_rule = defaultdict(Counter)
    for r in ledger:
        by_rule[(r["tool"], r["rule"])][r["normalizedFinalLabel"]] += 1
    rule_rows = sorted(by_rule.items(), key=lambda kv: -sum(kv[1].values()))
    write_table("4_rule", ["tool", "rule", "risk_class", "alerts", "false_positive", "supported", "undetermined", "supported_share"],
                [[t, rule, RULE_TO_RISK.get(rule, "Other"), sum(c.values()), c[FP], c[SUP], c[UND],
                  f'{100 * c[SUP] / sum(c.values()):.0f}%'] for (t, rule), c in rule_rows])
    fig, ax = plt.subplots(figsize=(10, 6))
    top = rule_rows[:15][::-1]
    names = [f"{rule} ({TOOL_SHORT[t]})" for (t, rule), _ in top]
    stacked_bars(ax, names, {n: c for n, (_, c) in zip(names, top)}, horizontal=True)
    ax.set_title("Fifteen rules with the most alerts")
    ax.set_xlabel("Alerts")
    save(fig, "4_rule_top15")

    # 5 kinds of supported alerts
    support_rows = [r for r in ledger if r["normalizedFinalLabel"] == SUP]
    kinds = defaultdict(list)
    for r in support_rows:
        kinds[classify(r, SUPPORTED_KIND)].append(r)
    write_table("5_supported_kind", ["kind", "alerts", "tools", "libraries"],
                [[k, len(v), " ".join(f"{TOOL_SHORT[t]}={n}" for t, n in Counter(r["tool"] for r in v).items()),
                  " ".join(f"{p}={n}" for p, n in Counter(r["project"] for r in v).items())]
                 for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1]))])
    for k, v in kinds.items():
        add_example("5 supported kind", k, v)
    fig, ax = plt.subplots(figsize=(9, 4))
    order = sorted(kinds, key=lambda k: len(kinds[k]))
    base = [0] * len(order)
    for tool in TOOLS:
        values = [sum(r["tool"] == tool for r in kinds[k]) for k in order]
        ax.barh(order, values, left=base, color=TOOL_COLORS[tool], label=TOOL_SHORT[tool])
        base = [b + v for b, v in zip(base, values)]
    for i, total in enumerate(base):
        ax.text(total + 0.3, i, str(total), va="center", fontsize=9)
    ax.legend(frameon=False)
    ax.set_title("Kinds of the 62 supported alerts")
    save(fig, "5_supported_kind")

    # 6 undetermined gaps
    gaps = defaultdict(list)
    for r in ledger:
        if r["normalizedFinalLabel"] == UND:
            gaps[classify(r, UNDETERMINED_GAP)].append(r)
    write_table("6_undetermined_gap", ["missing_evidence", "alerts", "locations"],
                [[k, len(v), "; ".join(f'{r["project"]} {r["rule"]} {short_path(r["file"])}:{r["line"]}' for r in v)]
                 for k, v in gaps.items()])
    for k, v in gaps.items():
        add_example("6 undetermined gap", k, v)

    # 7 false-positive basis (approximate)
    fp_rows = [r for r in ledger if r["normalizedFinalLabel"] == FP]
    reasons = defaultdict(list)
    for r in fp_rows:
        reasons[fp_reason(r)].append(r)
    write_table("7_false_positive_reason", ["basis_keyword_approximation", "alerts", "Flawfinder", "Cppcheck", "clangsa", "main_rules"],
                [[k, len(v)] + [sum(r["tool"] == t for r in v) for t in TOOLS]
                 + [" ".join(f"{rule}={n}" for rule, n in Counter(r["rule"] for r in v).most_common(4))]
                 for k, v in sorted(reasons.items(), key=lambda kv: -len(kv[1]))])
    for k, v in reasons.items():
        add_example("7 false-positive basis", k, v)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    order = sorted(reasons, key=lambda k: len(reasons[k]))
    base = [0] * len(order)
    for tool in TOOLS:
        values = [sum(r["tool"] == tool for r in reasons[k]) for k in order]
        ax.barh(order, values, left=base, color=TOOL_COLORS[tool], label=TOOL_SHORT[tool])
        base = [b + v for b, v in zip(base, values)]
    for i, total in enumerate(base):
        ax.text(total + 2, i, str(total), va="center", fontsize=9)
    ax.legend(frameon=False)
    ax.set_title("Basis for ruling out the 648 false positives (keyword approximation)")
    save(fig, "7_false_positive_reason")

    # 8 cross-tool overlap
    locations = defaultdict(list)
    for r in ledger:
        locations[(r["project"], short_path(r["file"]), r["line"])].append(r)
    multi = {k: v for k, v in locations.items() if len({r["tool"] for r in v}) > 1}
    write_table("8_cross_tool_overlap", ["library", "location", "tool_rule_outcome"],
                [[k[0], f"{k[1]}:{k[2]}", "; ".join(f'{TOOL_SHORT[r["tool"]]} {r["rule"]} ({LABEL_TEXT[r["normalizedFinalLabel"]]})'
                                                  for r in v)] for k, v in sorted(multi.items())])

    # 9 cost
    replicated = {}
    if REPLICATION.exists():
        with open(REPLICATION, encoding="utf-8-sig") as stream:
            for r in csv.DictReader(stream):
                replicated[(r["project"], r["tool"])] = r
    cost_rows = []
    for r in matrix:
        rep = replicated.get((r["project"], r["tool"]), {})
        cost_rows.append([r["project"], r["tool"], r["wall_seconds"], r["max_rss_kib"],
                          rep.get("replicated_wall_seconds", ""), rep.get("replicated_max_rss_kib", "")])
    write_table("9_cost", ["library", "tool", "original_wall_s", "original_max_rss_kib", "replicated_wall_s", "replicated_max_rss_kib"], cost_rows)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    x = range(len(LIBRARIES))
    width = 0.27
    for offset, tool in zip((-width, 0, width), TOOLS):
        rows = {r["project"]: r for r in matrix if r["tool"] == tool}
        axes[0].bar([i + offset for i in x], [float(rows[lib]["wall_seconds"]) for lib in LIBRARIES], width,
                    color=TOOL_COLORS[tool], label=TOOL_SHORT[tool])
        axes[1].bar([i + offset for i in x], [int(rows[lib]["max_rss_kib"]) / 1024 for lib in LIBRARIES], width,
                    color=TOOL_COLORS[tool], label=TOOL_SHORT[tool])
    for ax, title, unit in ((axes[0], "Wall time per run (log scale)", "Seconds"), (axes[1], "Maximum RSS", "MiB")):
        ax.set_xticks(list(x), LIBRARIES, rotation=40, ha="right")
        ax.set_title(title)
        ax.set_ylabel(unit)
    axes[0].set_yscale("log")
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.06))
    save(fig, "9_cost")

    # original vs replication wall time
    if replicated:
        fig, ax = plt.subplots(figsize=(5.5, 5))
        for tool in TOOLS:
            pairs = [(float(r["wall_seconds"]), float(replicated[(r["project"], r["tool"])]["replicated_wall_seconds"]))
                     for r in matrix if r["tool"] == tool and replicated.get((r["project"], r["tool"]), {}).get("replicated_wall_seconds")]
            ax.scatter([p[0] for p in pairs], [p[1] for p in pairs], color=TOOL_COLORS[tool], label=TOOL_SHORT[tool], s=28)
        ax.plot([0.03, 400], [0.03, 400], color="#999", linestyle="--", linewidth=1, label="Equal time")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Original wall time (s)")
        ax.set_ylabel("Replication wall time (s)")
        ax.set_title("Wall time: original study vs replication")
        ax.legend(frameon=False)
        save(fig, "10_replication_wall_time")

    with open(OUT / "examples.csv", "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["dimension", "category", "alerts_in_category", "library", "tool", "rule", "location", "outcome", "source_evidence_original_chinese"])
        writer.writerows(examples)

    print(f"{len(ledger)} alerts; {len(list((OUT / 'figures').glob('*.png')))} figures; "
          f"{len(list((OUT / 'tables').glob('*.csv')))} tables; {len(examples)} examples")
    print(f"output: {OUT}")


if __name__ == "__main__":
    main()
