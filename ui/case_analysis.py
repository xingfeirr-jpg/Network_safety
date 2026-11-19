"""Classify the 725 reviewed alerts into explainable case families.

The classification follows the dimensions already used by the replication analysis:
- false positives are grouped by the reason that rules out the original risk;
- supported alerts are grouped by the kind of confirmed issue;
- undetermined alerts are grouped by the evidence that is missing.

Each family includes representative alerts and the original Chinese reasoning. The UI
uses these fields to explain not only what the tool reported, but why the review
reached its verdict.
"""
import re
from collections import Counter, defaultdict

FP = "false_positive"
SUP = "supported"
UND = "undetermined"

RISK_CATEGORY = {
    "buffer": ["memcpy", "strcpy", "strcat", "strncpy", "char", "strlen", "read", "negativeIndex",
               "arrayIndexOutOfBoundsCond", "pointerOutOfBoundsCond"],
    "formatted": ["fprintf", "sprintf", "snprintf", "vsnprintf", "vsprintf", "vfprintf", "_snprintf",
                  "vprintf", "syslog", "invalidPrintfArgType_sint"],
    "null": ["core.NullDereference", "unix.cstring.NullArg", "core.NonNullParamChecker",
             "nullPointerRedundantCheck", "nullPointerArithmeticRedundantCheck", "nullPointerArithmetic",
             "ctunullpointer", "core.CallAndMessage"],
    "integer": ["core.UndefinedBinaryOperatorResult", "core.DivideZero", "core.BitwiseShift",
                "shiftTooManyBitsSigned", "shiftNegativeLHS", "zerodiv", "integerOverflowCond",
                "AssignmentIntegerToAddress"],
    "file": ["open", "fopen", "getenv", "system"],
    "quality": ["deadcode.DeadStores", "uselessAssignmentPtrArg", "legacyUninitvar", "core.uninitialized.Branch"],
}
RULE_TO_RISK = {rule: category for category, rules in RISK_CATEGORY.items() for rule in rules}

SUPPORTED_KIND = [
    ("negative_shift", lambda r: r["rule"] == "shiftTooManyBitsSigned"),
    ("dead_store", lambda r: r["rule"] in ("deadcode.DeadStores", "uselessAssignmentPtrArg")),
    ("redundant_null_check", lambda r: r["rule"] == "nullPointerRedundantCheck"),
    ("null_arithmetic", lambda r: r["rule"].startswith("nullPointerArithmetic")),
    ("conditional_overflow", lambda r: r["tool"] == "Flawfinder" and r["rule"] == "memcpy"),
    ("nonnull_parameter", lambda r: r["rule"] == "core.NonNullParamChecker"),
    ("null_copy_destination", lambda r: r["rule"] == "unix.cstring.NullArg"),
    ("unchecked_environment", lambda r: r["rule"] == "getenv"),
]

UNDETERMINED_GAP = [
    ("caller_context", lambda r: r["tool"] == "Flawfinder" and r["rule"] in ("vsnprintf", "open", "fopen", "getenv")),
    ("int_max_boundary", lambda r: r["tool"] == "Flawfinder" and r["rule"] == "memcpy"),
    ("feasible_copy_path", lambda r: r["rule"] == "unix.cstring.NullArg"),
]

FALSE_POSITIVE_REASON = [
    ("inactive_code", ["未定义", "不活动", "未激活", "不编入", "未编入", "后备分支", "不参与", "未启用", "未选择",
                        "不存在该", "为假", "兼容分支", "调试宏", "本配置为空", "与实际config", "条件不成立", "均不成立", "相反"]),
    ("name_not_call", ["不是调用", "没有调用", "不是strlen", "声明整数", "整数参数", "宏存在性", "参数名", "命中的是",
                       "词法", "标识符", "注释", "不是函数", "并非调用", "没有执行", "名称匹配", "仅为声明", "宏别名",
                       "宏替代", "不是格式化调用", "形参", "#error", "错误文本", "只声明", "宏定义不会", "结构成员", "字段名"]),
    ("noreturn_handler", ["error_exit", "ERREXIT", "不返回", "noreturn", "longjmp"]),
    ("nul_terminated", ["终止字符串", "已终止", "NUL结尾", "NUL 结尾", "以NUL", "NUL终止", "终止符"]),
    ("prior_guard", ["先检查", "已检查", "判空", "之前检查", "前检查", "守卫", "先判", "路径矛盾", "不可达", "检查后",
                     "保证非空", "直接返回", "直接选择返回"]),
    ("constant_argument", ["常量", "字面量", "固定格式", "固定字符串", "常数", "固定的数值"]),
    ("bounded_write", ["容量", "上界", "分配", "长度", "≤", "<=", "足够", "不超过", "范围", "大小", "字节"]),
]

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
        if (test(row) if callable(test) else any(key in (row.get(field) or "") for key in test)):
            return name
    return "other"


def family_for(row):
    outcome = row["outcome"]
    if outcome == FP:
        return classify(row, FALSE_POSITIVE_REASON, "source_evidence")
    if outcome == SUP:
        return classify(row, SUPPORTED_KIND)
    return classify(row, UNDETERMINED_GAP)


def pick_examples(rows, limit=3):
    """Prefer cases discussed in the report, then the clearest rationale. Order is stable."""
    ordered = sorted(rows, key=lambda r: (-len(r.get("source_evidence") or ""), r["key"]))
    chosen = []
    used = set()
    for row in ordered:
        marker = (row["project"], row["rule"], short_path(row["file"]).split("/")[-1], str(row["line"]))
        if marker in REPORT_CASES:
            chosen.append(row)
            used.add(marker)
            if len(chosen) >= limit:
                return chosen
    for row in ordered:
        marker = (row["project"], row["rule"], short_path(row["file"]).split("/")[-1], str(row["line"]))
        if marker not in used:
            chosen.append(row)
            used.add(marker)
            if len(chosen) >= limit:
                break
    return chosen


def public_case(row):
    return {
        "key": row["key"],
        "project": row["project"],
        "version": row["version"],
        "tool": row["tool"],
        "rule": row["rule"],
        "file": short_path(row["file"]),
        "line": row["line"],
        "column": row["column"],
        "outcome": row["outcome"],
        "risk": RULE_TO_RISK.get(row["rule"], "other"),
        "security_meaning": row.get("security_meaning") or "",
        "source_evidence": row.get("source_evidence") or "",
        "missing_conditions": row.get("missing_conditions") or "",
        "root_cause_group": row.get("root_cause_group") or "",
        "cross_tool": row.get("cross_tool") or "",
        "source_code": row.get("source_code") or "",
        "family": family_for(row),
    }


def load_special_cases(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["outcome"], family_for(row))].append(row)

    cases = []
    for (outcome, family), members in groups.items():
        cases.append({
            "id": f"{outcome}-{family}",
            "outcome": outcome,
            "family": family,
            "count": len(members),
            "tools": dict(Counter(row["tool"] for row in members)),
            "libraries": dict(Counter(row["project"] for row in members)),
            "rules": [rule for rule, _ in Counter(row["rule"] for row in members).most_common(6)],
            "examples": [public_case(row) for row in pick_examples(members)],
        })

    outcome_order = {FP: 0, SUP: 1, UND: 2}
    cases.sort(key=lambda item: (outcome_order[item["outcome"]], -item["count"], item["family"]))
    totals = Counter(row["outcome"] for row in rows)
    return {
        "total": len(rows),
        "outcome_totals": dict(totals),
        "family_count": len(cases),
        "cases": cases,
    }
