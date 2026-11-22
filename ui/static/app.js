const TOOL_LABEL = { FF: "Flawfinder", CP: "Cppcheck", CC: "CodeChecker/clangsa" };
const TOOL_CLASS = { Flawfinder: "b-ff", Cppcheck: "b-cp", "CodeChecker/clangsa": "b-cc" };
const OUTCOME_CLASS = { false_positive: "b-fp", supported: "b-sup", undetermined: "b-und" };
const OUTCOME_COLOR = { false_positive: "#94a3b8", supported: "#1f9d55", undetermined: "#d97706" };
const TOOLS = ["Flawfinder", "Cppcheck", "CodeChecker/clangsa"];
const DOMAIN = { zlib: "compression", LZ4: "compression", cJSON: "JSON", "json-c": "JSON", yyjson: "JSON", libyaml: "YAML", Expat: "XML", libpng: "image", "libjpeg-turbo": "image", utf8proc: "Unicode" };

const PLOT_CFG = { displayModeBar: false, responsive: true };
const PLOT_LAYOUT = { margin: { t: 10, r: 20, b: 50, l: 60 }, font: { family: "Microsoft YaHei, sans-serif", size: 12 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", legend: { orientation: "h", y: -0.2 } };

const $ = (id) => document.getElementById(id);
const fmt = (n) => (n === null || n === undefined || Number.isNaN(n)) ? "-" : Number(n).toLocaleString(LANG === "en" ? "en-US" : "zh-CN");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const outcomeText = (outcome) => ({ false_positive: t("fp"), supported: t("sup"), undetermined: t("und") }[outcome] || outcome);
const toolShort = (tool) => tool === "CodeChecker/clangsa" ? "clangsa" : tool;
const text = (key, vars = {}) => Object.entries(vars).reduce((value, [name, replacement]) => value.replaceAll(`{${name}}`, replacement), t(key));

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

// ---------- tabs ----------
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === name));
  window.scrollTo({ top: 0, behavior: "smooth" });
  window.dispatchEvent(new Event("resize"));
}

document.querySelectorAll(".tab").forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

$("lang-toggle").addEventListener("click", () => setLanguage(LANG === "zh" ? "en" : "zh"));

// ---------- tab 0: overview ----------
const OVERVIEW_MODULES = [
  { tab: "libs", icon: "P17", key: "ov_mod_libs_h", desc: "ov_mod_libs_p" },
  { tab: "tools", icon: "T", key: "ov_mod_tools_h", desc: "ov_mod_tools_p" },
  { tab: "run", icon: "R", key: "ov_mod_run_h", desc: "ov_mod_run_p" },
  { tab: "dash", icon: "D", key: "ov_mod_dash_h", desc: "ov_mod_dash_p" },
  { tab: "cases", icon: "C", key: "ov_mod_cases_h", desc: "ov_mod_cases_p" },
  { tab: "conclusion", icon: "S", key: "ov_mod_concl_h", desc: "ov_mod_concl_p" },
  { tab: "reliability", icon: "R", key: "ov_mod_rel_h", desc: "ov_mod_rel_p" },
];

function renderOverview() {
  $("ov-stats").innerHTML = [
    [t("ov_kpi_libs"), LIBS.length],
    [t("ov_kpi_tools"), TOOLS.length],
    [t("ov_kpi_scans"), MATRIX.length],
    [t("ov_kpi_alerts"), sumCandidatesAll()],
  ].map(([label, value]) => `<div class="ov-stat"><div class="l">${esc(label)}</div><div class="v">${fmt(value)}</div></div>`).join("");

  $("ov-modules").innerHTML = OVERVIEW_MODULES.map((module) => `<button class="ov-module" data-tab="${module.tab}">
    <div class="ov-module-head"><span class="ov-module-icon">${esc(module.icon)}</span><h4>${esc(t(module.key))}</h4></div>
    <p>${esc(t(module.desc))}</p>
    <span class="ov-module-go">${esc(t("ov_go"))} →</span>
  </button>`).join("");

  document.querySelectorAll(".ov-module").forEach((card) => card.addEventListener("click", () => switchTab(card.dataset.tab)));
}

function sumCandidatesAll() {
  return MATRIX.reduce((a, m) => a + (m.candidates || 0), 0);
}

// ---------- tab 1: libraries ----------
let MATRIX = [];
let LIBS = [];

async function loadLibs() {
  const [ov, mx] = await Promise.all([api("/api/overview"), api("/api/matrix")]);
  LIBS = ov.libraries;
  MATRIX = mx;
  const byLib = {};
  MATRIX.forEach((m) => { (byLib[m.project_id] ||= {})[m.tool_key] = m; });

  $("lib-cards").innerHTML = LIBS.map((l) => {
    const cc = byLib[l.id]?.CC || {};
    return `<div class="lib-card" data-id="${esc(l.id)}">
      <div><span class="name">${esc(l.name)}</span><span class="ver">${esc(l.version)}</span></div>
      <span class="domain">${esc(DOMAIN[l.name] || "")}</span>
      <div class="metrics">
        <div>${esc(t("card_src"))}<br><b>${fmt(byLib[l.id]?.FF?.intended)}</b></div>
        <div>${esc(t("card_units"))}<br><b>${fmt(cc.intended)}</b></div>
        <div>${esc(t("card_alerts"))}<br><b>${fmt(sumCandidates(l.id))}</b></div>
        <div>${esc(t("card_cc_time"))}<br><b>${fmt(cc.wall_seconds)} s</b></div>
      </div></div>`;
  }).join("");

  document.querySelectorAll(".lib-card").forEach((el) => el.addEventListener("click", () => selectLibrary(el.dataset.id)));

  const rows = LIBS.map((l) => ({ name: l.name, sz: byLib[l.id]?.FF?.intended || 0, cc: byLib[l.id]?.CC?.intended || 0 }));
  Plotly.newPlot("chart-lib-size", [
    { type: "bar", name: t("s_src"), x: rows.map((r) => r.name), y: rows.map((r) => r.sz), marker: { color: "#2f5bea" }, hovertemplate: `%{x}<br>${t("s_src")}: %{y}<extra></extra>` },
    { type: "bar", name: t("s_units"), x: rows.map((r) => r.name), y: rows.map((r) => r.cc), marker: { color: "#9333ea" }, hovertemplate: `%{x}<br>${t("s_units")}: %{y}<extra></extra>` },
  ], { ...PLOT_LAYOUT, barmode: "group", yaxis: { type: "log", title: t("y_count") } }, PLOT_CFG);

  $("lib-table").innerHTML = `<thead><tr><th>${esc(t("col_lib"))}</th><th>${esc(t("col_version"))}</th><th>${esc(t("col_domain"))}</th><th class="num">${esc(t("col_src"))}</th><th class="num">${esc(t("col_units"))}</th><th class="num">${esc(t("col_ff_alerts"))}</th><th class="num">${esc(t("col_cp_alerts"))}</th><th class="num">${esc(t("col_cc_alerts"))}</th></tr></thead><tbody>` +
    LIBS.map((l) => `<tr class="clickable" data-id="${esc(l.id)}"><td><b>${esc(l.name)}</b></td><td>${esc(l.version)}</td><td>${esc(DOMAIN[l.name] || "")}</td>
      <td class="num">${fmt(byLib[l.id]?.FF?.intended)}</td><td class="num">${fmt(byLib[l.id]?.CC?.intended)}</td>
      <td class="num">${fmt(byLib[l.id]?.FF?.candidates)}</td><td class="num">${fmt(byLib[l.id]?.CP?.candidates)}</td>
      <td class="num">${fmt(byLib[l.id]?.CC?.candidates)}</td></tr>`).join("") + "</tbody>";

  document.querySelectorAll("#lib-table tr.clickable").forEach((row) => row.addEventListener("click", () => selectLibrary(row.dataset.id)));

  setupLibPie(byLib);
  renderOverview();
}

// ---------- library pie chart ----------
const TOOL_COLOR = { Flawfinder: "#2f5bea", Cppcheck: "#0ea5a4", "CodeChecker/clangsa": "#9333ea" };
const OUTCOME_PIE_COLOR = { false_positive: "#94a3b8", supported: "#1f9d55", undetermined: "#d97706" };

let LIB_PIE_LIB = "";
let LIB_PIE_VIEW = "tool";

function setupLibPie(byLib) {
  $("pie-lib").innerHTML = LIBS.map((l) => `<option value="${esc(l.id)}">${esc(l.name)} ${esc(l.version)}</option>`).join("");
  if (!LIB_PIE_LIB || !LIBS.some((l) => l.id === LIB_PIE_LIB)) LIB_PIE_LIB = LIBS[0]?.id || "";
  $("pie-lib").value = LIB_PIE_LIB;
  $("pie-view").value = LIB_PIE_VIEW;

  if (!$("pie-lib").dataset.bound) {
    $("pie-lib").addEventListener("change", () => { LIB_PIE_LIB = $("pie-lib").value; renderLibPie(); });
    $("pie-view").addEventListener("change", () => { LIB_PIE_VIEW = $("pie-view").value; renderLibPie(); });
    $("pie-lib").dataset.bound = "true";
  }
  renderLibPie();
}

// Click on a library card or table row: select it in the pie picker and scroll the pie into view.
function selectLibrary(id) {
  LIB_PIE_LIB = id;
  $("pie-lib").value = id;
  renderLibPie();
  const section = $("lib-pie-section");
  const topbar = document.querySelector(".topbar");
  const offset = (topbar ? topbar.getBoundingClientRect().height : 0) + 16;
  window.scrollTo({ top: section.getBoundingClientRect().top + window.scrollY - offset, behavior: "smooth" });
}

function markSelectedLibrary() {
  document.querySelectorAll(".lib-card, #lib-table tr.clickable").forEach((el) => el.classList.toggle("selected", el.dataset.id === LIB_PIE_LIB));
}

async function renderLibPie() {
  if (!LIB_PIE_LIB) return;
  markSelectedLibrary();
  const detail = await api(`/api/library-detail/${encodeURIComponent(LIB_PIE_LIB)}`);

  let labels = [];
  let values = [];
  let colors = [];

  if (LIB_PIE_VIEW === "tool") {
    labels = TOOLS;
    values = TOOLS.map((tool) => detail.verdict[tool].false_positive + detail.verdict[tool].supported + detail.verdict[tool].undetermined);
    colors = TOOLS.map((tool) => TOOL_COLOR[tool]);
  } else {
    const outcomes = ["false_positive", "supported", "undetermined"];
    labels = outcomes.map(outcomeText);
    values = outcomes.map((outcome) => TOOLS.reduce((sum, tool) => sum + detail.verdict[tool][outcome], 0));
    colors = outcomes.map((outcome) => OUTCOME_PIE_COLOR[outcome]);
  }

  const total = values.reduce((a, b) => a + b, 0);
  const theme = {
    ...PLOT_LAYOUT,
    font: { ...PLOT_LAYOUT.font, family: LANG === "en" ? "Arial, sans-serif" : "Microsoft YaHei, sans-serif" },
    legend: { orientation: "h", y: -0.05, x: 0, xanchor: "left" },
  };

  if (!total) {
    $("lib-pie-side").innerHTML = `<div class="empty">${esc(t("lib_pie_no_data"))}</div>`;
    Plotly.newPlot("chart-lib-pie", [], theme, PLOT_CFG);
    return;
  }

  Plotly.newPlot("chart-lib-pie", [{
    type: "pie",
    labels,
    values,
    marker: { colors, line: { color: "#fff", width: 2 } },
    textinfo: "percent",
    textposition: "outside",
    automargin: true,
    textfont: { size: 12 },
    sort: false,
    hovertemplate: `%{label}<br>%{value} (${LANG === "zh" ? "占" : ""}%{percent})<extra></extra>`,
  }], { ...theme, showlegend: false, margin: { t: 44, r: 44, b: 44, l: 44 } }, PLOT_CFG);

  const rows = labels.map((label, index) => `<div class="lib-pie-row">
    <span class="dot" style="background:${colors[index]}"></span>
    <span class="name">${esc(label)}</span>
    <span class="val">${fmt(values[index])}</span>
    <span class="pct">${(100 * values[index] / total).toFixed(1)}%</span>
  </div>`).join("");

  $("lib-pie-side").innerHTML = `<div class="lib-pie-total"><div class="l">${esc(t("lib_pie_total"))}</div><div class="v">${fmt(total)}</div></div>` + rows;
}

function sumCandidates(id) {
  return MATRIX.filter((m) => m.project_id === id).reduce((a, m) => a + (m.candidates || 0), 0);
}

// ---------- tab 2: live run ----------
let CURRENT_SOURCE = null;
let RUN_ACTIVE = false;

function setupRun() {
  $("run-lib").innerHTML = LIBS.map((l) => `<option value="${esc(l.id)}">${esc(l.id)} · ${esc(l.name)} ${esc(l.version)}</option>`).join("");
  const descriptions = LANG === "zh" ? [
    { n: "Flawfinder", t: "查名字", how: "逐行扫描，看到 memcpy、strcpy、strlen 这类危险函数名就报警。", good: "速度快，能列出所有危险调用。", bad: "分不清函数名和变量名，不知道代码是否真的会执行。", v: "2.0.20" },
    { n: "Cppcheck", t: "推算取值", how: "跟踪变量在赋值和分支中可能取的值，判断是否会出错。", good: "理解整数和指针的取值，代码质量类问题覆盖广。", bad: "需要编译数据库，部分检查依赖真实头文件。", v: "2.13.0" },
    { n: "CodeChecker / clangsa", t: "模拟执行路径", how: "把输入当作未知数，沿每条分支模拟执行，看错误路径能否走到。", good: "空指针、死存储等与路径相关的问题最准确。", bad: "最慢，看不到写在文档里的约定（如函数永不返回）。", v: "6.29.1 · Clang 18.1.3" },
  ] : [
    { n: "Flawfinder", t: "Name matching", how: "Scans line by line and reports calls to risky names such as memcpy, strcpy, and strlen.", good: "Fast and lists every risky call.", bad: "Cannot distinguish names from variables or determine whether the code executes.", v: "2.0.20" },
    { n: "Cppcheck", t: "Value inference", how: "Tracks possible values through assignments and branches to determine whether errors can occur.", good: "Understands integer and pointer values and covers many code-quality problems.", bad: "Needs a compilation database, and some checks require real headers.", v: "2.13.0" },
    { n: "CodeChecker / clangsa", t: "Path simulation", how: "Treats inputs as unknown and simulates each branch to see whether an error path is reachable.", good: "Most accurate for path-related issues such as null pointers and dead stores.", bad: "Slowest, and cannot infer conventions documented in prose, such as a function never returning.", v: "6.29.1 · Clang 18.1.3" },
  ];
  $("tool-compare").innerHTML = descriptions.map((tool, i) => `<div class="tool-box">
      <h4><span class="badge ${["b-ff", "b-cp", "b-cc"][i]}">${esc(tool.n)}</span></h4>
      <p><span class="k">${esc(LANG === "zh" ? "工作方式：" : "How it works:")}</span>${esc(tool.t)}. ${esc(tool.how)}</p>
      <p><span class="k">${esc(LANG === "zh" ? "擅长：" : "Strengths:")}</span>${esc(tool.good)}</p>
      <p><span class="k">${esc(LANG === "zh" ? "短板：" : "Limitations:")}</span>${esc(tool.bad)}</p>
      <p><span class="k">${esc(LANG === "zh" ? "版本：" : "Version:")}</span>${esc(tool.v)}</p></div>`).join("");

  renderToolRules();
  renderWorkflow();
  if (!$("run-start").dataset.bound) {
    $("run-start").addEventListener("click", startRun);
    $("run-start").dataset.bound = "true";
  }
}

// What each tool actually checks, and the dimension in which it reports a finding.
// The dimensions below are the ones the tools themselves emit:
//   Flawfinder  -> risk level [1..5] + category (buffer / format / misc)
//   Cppcheck    -> severity (warning / style / performance / portability / information) + check id
//   CodeChecker -> checker category (Logic error / API / Unused code / Suspicious operation) + checker name
// The rule sets and counts come from the frozen configuration and the saved study output
// (Project17_Replication/config/libraries.json, .../data/records/*/).
const TOOL_RULES = {
  zh: [
    {
      n: "Flawfinder", badge: "b-ff", version: "2.0.20",
      basis: "按函数名匹配",
      basisDetail: "工具内置一张危险函数名表，逐行扫描源码，文本中出现表内的名字即命中；不做数据流与路径分析，因此同一行代码里的注释、宏定义、声明都会一并命中。",
      dimensionLabel: "判定维度",
      dimension: "风险等级 [1]–[5] + 类别（buffer / format / misc / shell）",
      dimensions: [
        ["[1] 低风险", "buffer", "strlen / char 等长度与缓冲区类调用，风险较低", 143],
        ["[2] 中风险", "buffer / misc", "memcpy / fopen 等拷贝与文件类调用", 327],
        ["[3] 中风险", "buffer", "少量中等风险缓冲区命中", 4],
        ["[4] 高风险", "buffer / format / shell", "sprintf / snprintf 等格式化输出与 shell 调用，最容易出问题", 62],
      ],
      dimensionNote: "本实验用 --minlevel=1 保留全部等级，因此 1/2/3/4 四个等级都会出现在结果里；536 条命中中 buffer 类占 455 条。",
      switches: [
        ["--minlevel=1", "报告最低等级设为 1，所有等级命中全部保留"],
        ["--neverignore", "不跳过被注释或条件编译排除的代码"],
        ["--columns --context", "输出列号与上下文，便于定位"],
      ],
      countRule: "输出中每一条命中计为一条告警（与报告 Hits 计数核对一致）",
      examples: ["memcpy", "strlen", "char", "sprintf"],
      exampleLabel: "最常命中的名字",
    },
    {
      n: "Cppcheck", badge: "b-cp", version: "2.13.0",
      basis: "按内置检查器匹配",
      basisDetail: "逐个检查器分析控制流与数据流，只有当检查器定义的触发条件成立时才产生一条诊断；检查器按功能分属不同类，本实验共启用 79 个。",
      dimensionLabel: "判定维度",
      dimension: "严重级别（warning / portability / error）+ 检查器 ID",
      dimensions: [
        ["warning", "nullPointerRedundantCheck", "冗余或重复的空指针检查", 39],
        ["portability", "shiftTooManyBitsSigned", "移位位数超过类型宽度", 21],
        ["warning", "negativeIndex", "数组下标可能为负", 17],
        ["warning", "arrayIndexOutOfBoundsCond", "条件成立时数组越界", 14],
        ["portability / error", "shiftNegativeLHS / zerodiv / legacyUninitvar", "负数左移、除零、未初始化变量", 10],
        ["warning / portability / error", "其他 10 项检查", "指针算术、格式化参数类型、整数溢出等零散命中", 15],
      ],
      dimensionNote: "information 级别（多为缺少头文件提示）在计数时被剔除，116 条告警之外另有 213 条 information 记录。",
      switches: [
        ["--enable=warning,performance,portability,information", "开启四类检查器；information 级在计数时被剔除"],
        ["--project={DB}", "读取编译数据库，按真实宏与包含路径分析"],
        ["--check-level=normal", "只运行 normal 级别检查，不做 exhaustive 全量展开"],
        ["--platform=unix64 --std={STD}", "按目标平台与 C 标准解释代码"],
      ],
      countRule: "severity 不为 information 的 <error> 元素计为一条；多位置诊断只计一次，取首个位置",
      examples: ["nullPointerRedundantCheck", "shiftTooManyBitsSigned", "negativeIndex", "arrayIndexOutOfBoundsCond"],
      exampleLabel: "最常命中的检查器",
    },
    {
      n: "CodeChecker / clangsa", badge: "b-cc", version: "6.29.1 · Clang 18.1.3",
      basis: "按 Clang 分析器匹配",
      basisDetail: "Clang 静态分析器沿每条路径做符号执行，当路径约束不可满足或触发 checker 规则时产生诊断。checker 按缺陷性质归类，本实验在 146 个 checker 中启用 47 个。",
      dimensionLabel: "判定维度",
      dimension: "checker 类别（Logic error / API / Unused code / Suspicious operation）+ checker 名",
      dimensions: [
        ["Logic error", "core.NullDereference", "路径上解引用空指针", 29],
        ["Unused code", "deadcode.DeadStores", "赋值后从未被读取的死存储", 14],
        ["Logic error", "core.UndefinedBinaryOperatorResult", "负数右移等未定义的二进制运算结果", 9],
        ["API", "unix.cstring.NullArg / core.NonNullParamChecker", "向不可为空的参数传入空指针", 11],
        ["Logic error", "core.DivideZero", "除数为零", 6],
        ["Suspicious operation", "core.BitwiseShift", "移位位数越界等可疑运算", 2],
        ["Logic error", "core.uninitialized.Branch / core.CallAndMessage", "未初始化分支读取、调用与消息相关检查", 2],
      ],
      dimensionNote: "73 条诊断中 Logic error 占 52 条；core.uninitialized.Branch 等少量诊断属于路径敏感分析才能给出的结论。",
      switches: [
        ["--analyzers clangsa", "只启用 Clang 静态分析器，不启用其他分析器"],
        ["--timeout 120", "单条诊断分析超时上限（秒）"],
        ["--compile-uniqueing none", "编译命令不做去重，保持与编译数据库一致"],
        ["--z3-refutation off", "关闭 Z3 反证，保留分析器原始判定"],
      ],
      countRule: "reports/ 下 plist 文件中的每条 diagnostic 计为一条告警",
      examples: ["core.NullDereference", "deadcode.DeadStores", "core.UndefinedBinaryOperatorResult", "core.DivideZero"],
      exampleLabel: "最常命中的分析器",
    },
  ],
  en: [
    {
      n: "Flawfinder", badge: "b-ff", version: "2.0.20",
      basis: "Matches by function name",
      basisDetail: "The tool carries a table of risky function names and scans the source line by line. A line matches as soon as a name from the table appears; no data-flow or path analysis is performed, so comments, macro definitions, and declarations on the same line all match.",
      dimensionLabel: "Reporting dimension",
      dimension: "Risk level [1]–[5] + category (buffer / format / misc / shell)",
      dimensions: [
        ["[1] low", "buffer", "Length and buffer calls such as strlen and char; lower risk", 143],
        ["[2] medium", "buffer / misc", "Copy and file calls such as memcpy and fopen", 327],
        ["[3] medium", "buffer", "A small number of medium-risk buffer hits", 4],
        ["[4] high", "buffer / format / shell", "Formatted output such as sprintf and snprintf, plus shell calls; the most error-prone", 62],
      ],
      dimensionNote: "This experiment uses --minlevel=1, so levels 1, 2, 3, and 4 all appear in the results. Of the 536 hits, 455 are buffer calls.",
      switches: [
        ["--minlevel=1", "The lowest reported level is 1, so every severity level is kept"],
        ["--neverignore", "Code excluded by comments or conditional compilation is not skipped"],
        ["--columns --context", "Emits column numbers and context for locating a hit"],
      ],
      countRule: "Every hit line counts as one alert (cross-checked against the reported Hits count)",
      examples: ["memcpy", "strlen", "char", "sprintf"],
      exampleLabel: "Most frequently matched names",
    },
    {
      n: "Cppcheck", badge: "b-cp", version: "2.13.0",
      basis: "Matches by built-in checks",
      basisDetail: "Each checker analyses control flow and data flow, and produces a diagnostic only when the trigger condition defined by that checker holds. Checkers are grouped by function; 79 are enabled in this experiment.",
      dimensionLabel: "Reporting dimension",
      dimension: "Severity (warning / portability / error) + check id",
      dimensions: [
        ["warning", "nullPointerRedundantCheck", "Redundant or duplicated null-pointer checks", 39],
        ["portability", "shiftTooManyBitsSigned", "Shift count exceeds the type width", 21],
        ["warning", "negativeIndex", "Array index may be negative", 17],
        ["warning", "arrayIndexOutOfBoundsCond", "Array out of bounds when a condition holds", 14],
        ["portability / error", "shiftNegativeLHS / zerodiv / legacyUninitvar", "Negative left shift, division by zero, uninitialized variable", 10],
        ["warning / portability / error", "10 other checks", "Pointer arithmetic, printf argument types, integer overflow, and other scattered findings", 15],
      ],
      dimensionNote: "Severity information (mostly missing-header notices) is dropped when counting. The 116 alerts are in addition to 213 information records.",
      switches: [
        ["--enable=warning,performance,portability,information", "Enables four check categories; information severity is dropped when counting"],
        ["--project={DB}", "Reads the compilation database so real macros and include paths are used"],
        ["--check-level=normal", "Runs only normal-level checks instead of an exhaustive expansion"],
        ["--platform=unix64 --std={STD}", "Interprets the code against the target platform and C standard"],
      ],
      countRule: "Every <error> element whose severity is not information counts once; a diagnostic with several locations uses its first location",
      examples: ["nullPointerRedundantCheck", "shiftTooManyBitsSigned", "negativeIndex", "arrayIndexOutOfBoundsCond"],
      exampleLabel: "Most frequently matched checks",
    },
    {
      n: "CodeChecker / clangsa", badge: "b-cc", version: "6.29.1 · Clang 18.1.3",
      basis: "Matches by Clang analyzer checkers",
      basisDetail: "The Clang static analyzer symbolically executes every path and emits a diagnostic when a path constraint becomes unsatisfiable or a checker rule fires. Checkers are grouped by defect nature; 47 of the 146 available checkers are enabled here.",
      dimensionLabel: "Reporting dimension",
      dimension: "Checker category (Logic error / API / Unused code / Suspicious operation) + checker name",
      dimensions: [
        ["Logic error", "core.NullDereference", "Null pointer dereference on a reachable path", 29],
        ["Unused code", "deadcode.DeadStores", "Assigned values that are never read", 14],
        ["Logic error", "core.UndefinedBinaryOperatorResult", "Undefined binary results such as right-shifting a negative value", 9],
        ["API", "unix.cstring.NullArg / core.NonNullParamChecker", "Null pointer passed to a non-null parameter", 11],
        ["Logic error", "core.DivideZero", "Division by zero", 6],
        ["Suspicious operation", "core.BitwiseShift", "Shift-count overflow and similar suspicious operations", 2],
        ["Logic error", "core.uninitialized.Branch / core.CallAndMessage", "Reads through an uninitialized branch, call-and-message checks", 2],
      ],
      dimensionNote: "Logic error accounts for 52 of the 73 diagnostics. A small number of findings such as core.uninitialized.Branch are conclusions only path-sensitive analysis can reach.",
      switches: [
        ["--analyzers clangsa", "Enables only the Clang static analyzer, no other analyzer"],
        ["--timeout 120", "Analysis timeout per diagnostic in seconds"],
        ["--compile-uniqueing none", "Compile commands are not deduplicated, keeping them identical to the compilation database"],
        ["--z3-refutation off", "Keeps Z3 refutation off so the analyzer's original verdict is preserved"],
      ],
      countRule: "Every diagnostic in the plist files under reports/ counts as one alert",
      examples: ["core.NullDereference", "deadcode.DeadStores", "core.UndefinedBinaryOperatorResult", "core.DivideZero"],
      exampleLabel: "Most frequently matched checkers",
    },
  ],
};

function renderToolRules() {
  const rules = TOOL_RULES[LANG] || TOOL_RULES.zh;
  $("tool-rules").innerHTML = rules.map((tool) => `<div class="rule-box">
    <div class="rule-head">
      <span class="badge ${tool.badge}">${esc(tool.n)}</span>
      <span class="rule-basis">${esc(tool.basis)}</span>
    </div>
    <p class="rule-detail">${esc(tool.basisDetail)}</p>
    <div class="rule-block">
      <div class="rule-label">${esc(tool.dimensionLabel)}</div>
      <div class="rule-dimension">${esc(tool.dimension)}</div>
      <table class="rule-table">
        <thead><tr><th>${esc(t("rule_dim_level"))}</th><th>${esc(t("rule_dim_check"))}</th><th>${esc(t("rule_dim_desc"))}</th><th class="num">${esc(t("rule_dim_count"))}</th></tr></thead>
        <tbody>${tool.dimensions.map(([level, check, desc, count]) => `<tr>
          <td><code>${esc(level)}</code></td><td><code>${esc(check)}</code></td><td>${esc(desc)}</td><td class="num">${fmt(count)}</td>
        </tr>`).join("")}</tbody>
      </table>
      <p class="rule-note">${esc(tool.dimensionNote)}</p>
    </div>
    <div class="rule-block">
      <div class="rule-label">${esc(t("rule_switches"))}</div>
      <ul class="rule-switches">${tool.switches.map(([flag, note]) => `<li><code>${esc(flag)}</code><span>${esc(note)}</span></li>`).join("")}</ul>
    </div>
    <div class="rule-block">
      <div class="rule-label">${esc(t("rule_count_rule"))}</div>
      <p class="rule-count">${esc(tool.countRule)}</p>
    </div>
    <div class="rule-block">
      <div class="rule-label">${esc(tool.exampleLabel)}</div>
      <div class="rule-examples">${tool.examples.map((rule) => `<code>${esc(rule)}</code>`).join("")}</div>
    </div>
    <div class="rule-foot"><span>${esc(t("rule_version"))}</span><strong>${esc(tool.version)}</strong></div>
  </div>`).join("");
}

function renderWorkflow() {
  const steps = I18N[LANG].flow_steps;
  $("workflow").innerHTML = steps.map(([id, title, detail], index) => `
    <div class="flow-step">
      <div class="flow-head">
        <span class="flow-id">${esc(id)}</span>
        <strong>${esc(title)}</strong>
        ${index < steps.length - 1 ? '<span class="flow-arrow">→</span>' : ""}
      </div>
      <p>${esc(detail)}</p>
    </div>`).join("");
}

async function startRun() {
  const lib = $("run-lib").value;
  const tool = $("run-tool").value;
  $("run-start").disabled = true;
  $("run-log").textContent = "";
  $("run-bar").style.width = "5%";
  setStatus(t("running_container"), "running");
  $("run-result").innerHTML = `<div class="empty">${esc(t("running"))}</div>`;

  const { run_id } = await api("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ library: lib, tool }) });
  if (CURRENT_SOURCE) CURRENT_SOURCE.close();
  CURRENT_SOURCE = new EventSource(`/api/runs/${run_id}/events`);
  const log = $("run-log");
  let lines = 0;
  CURRENT_SOURCE.onmessage = (event) => {
    const { line } = JSON.parse(event.data);
    if (!line) return;
    lines += 1;
    log.textContent += line + "\n";
    log.scrollTop = log.scrollHeight;
    $("run-bar").style.width = Math.min(90, 5 + lines * 2) + "%";
    setStatus(line.slice(0, 80), "running");
  };
  CURRENT_SOURCE.addEventListener("done", (event) => {
    CURRENT_SOURCE.close();
    const result = JSON.parse(event.data);
    $("run-bar").style.width = "100%";
    setStatus(result.exit_code === 0 ? t("done_ok") : `${t("done_fail")} ${result.exit_code}`, result.exit_code === 0 ? "ok" : "fail");
    renderResult(result);
    $("run-start").disabled = false;
  });
  CURRENT_SOURCE.onerror = () => {
    $("run-start").disabled = false;
    setStatus(t("load_failed"), "fail");
  };
}

function setStatus(value, cls) {
  const el = $("run-status");
  el.textContent = value;
  el.className = "status " + (cls || "");
}

function renderResult(result) {
  const same = result.matches_reference;
  const verdictLine = same
    ? `<span class="badge b-sup">${esc(t("match"))}</span>`
    : `<span class="badge b-und">${esc(t("mismatch"))}</span>`;
  const rows = (result.alerts || []).slice(0, 300).map((alert) => `<tr><td>${esc(alert.file)}</td><td class="num">${fmt(alert.line)}</td><td class="num">${fmt(alert.column)}</td><td>${esc(alert.rule)}</td><td>${esc(alert.message || "")}</td></tr>`).join("");
  $("run-result").innerHTML = `
    <div class="result-head">
      <div class="stat"><div class="l">${esc(t("tool"))}</div><div class="v">${esc(TOOL_LABEL[result.tool])}</div></div>
      <div class="stat"><div class="l">${esc(t("alerts_this"))}</div><div class="v">${fmt(result.replicated_count)}</div></div>
      <div class="stat"><div class="l">${esc(t("alerts_ref"))}</div><div class="v">${fmt(result.reference_count)}</div></div>
      <div class="stat"><div class="l">${esc(t("duration"))}</div><div class="v">${result.wall_seconds ? result.wall_seconds.toFixed(2) + " s" : "-"}</div></div>
      <div class="stat"><div class="l">${esc(t("peak_mem"))}</div><div class="v">${result.max_rss_kib ? (result.max_rss_kib / 1024).toFixed(1) + " MB" : "-"}</div></div>
    </div>
    <p>${verdictLine}</p>
    <div style="max-height:360px;overflow:auto"><table class="data"><thead><tr><th>${esc(t("col_file"))}</th><th class="num">${esc(t("col_line"))}</th><th class="num">${esc(t("col_col"))}</th><th>${esc(t("col_rule"))}</th><th>${esc(t("col_message"))}</th></tr></thead><tbody>${rows || `<tr><td colspan="5" class="muted">${esc(t("no_alerts"))}</td></tr>`}</tbody></table></div>`;
}

// ---------- tab 3: dashboard ----------
let CANDIDATES = [];
let DASH = null;

// Stacked verdict bars per tool. Drawn both on the overview and the dashboard.
function drawVerdictChart(target, v, outs, chartTheme) {
  Plotly.newPlot(target, outs.map((outcome) => ({
    type: "bar", name: outcomeText(outcome), x: TOOLS, y: TOOLS.map((tool) => v[tool][outcome]),
    marker: { color: OUTCOME_COLOR[outcome] },
    hovertemplate: `%{x}<br>${outcomeText(outcome)}: %{y}<extra></extra>`,
  })), {
    ...chartTheme,
    barmode: "stack",
    margin: { t: 24, r: 20, b: 90, l: 60 },
    automargin: true,
  }, PLOT_CFG);
}

async function loadDashboard() {
  DASH = await api("/api/dashboard");
  const v = DASH.verdict;
  const totalFP = TOOLS.reduce((a, tool) => a + v[tool].false_positive, 0);
  const totalSup = TOOLS.reduce((a, tool) => a + v[tool].supported, 0);
  const totalUnd = TOOLS.reduce((a, tool) => a + v[tool].undetermined, 0);
  const percent = (value) => `${LANG === "zh" ? "占 " : ""}${(100 * value / DASH.total).toFixed(1)}%`;
  $("kpis").innerHTML = [
    [t("k_total"), DASH.total, t("k_sub_all")],
    [t("k_fp"), totalFP, percent(totalFP)],
    [t("k_sup"), totalSup, percent(totalSup)],
    [t("k_und"), totalUnd, percent(totalUnd)],
  ].map(([label, value, sub]) => `<div class="kpi"><div class="label">${esc(label)}</div><div class="value">${fmt(value)}</div><div class="sub">${esc(sub)}</div></div>`).join("");

  const outs = ["false_positive", "supported", "undetermined"];
  const chartTheme = {
    ...PLOT_LAYOUT,
    font: { ...PLOT_LAYOUT.font, family: LANG === "en" ? "Arial, sans-serif" : "Microsoft YaHei, sans-serif" },
    legend: { orientation: "h", y: -0.22, x: 0, xanchor: "left" },
  };
  // No text on the bars: the counts show in the hover tooltip instead, so nothing
  // overlaps the slices or the axis.
  drawVerdictChart("chart-verdict", v, outs, chartTheme);
  drawVerdictChart("chart-overview", v, outs, chartTheme);

  const projects = Object.keys(DASH.by_project);
  Plotly.newPlot("chart-project", outs.map((outcome) => ({
    type: "bar", name: outcomeText(outcome), x: projects, y: projects.map((project) => DASH.by_project[project][outcome]),
    marker: { color: OUTCOME_COLOR[outcome] },
    hovertemplate: `%{x}<br>${outcomeText(outcome)}: %{y}<extra></extra>`,
  })), { ...chartTheme, barmode: "stack", xaxis: { tickangle: -35, automargin: true }, margin: { t: 20, r: 20, b: 100, l: 60 }, automargin: true }, PLOT_CFG);

  const runs = DASH.matrix;
  Plotly.newPlot("chart-cost", TOOLS.map((tool, index) => {
    const key = ["FF", "CP", "CC"][index];
    const rows = runs.filter((row) => row.tool_key === key);
    return {
      type: "bar", name: tool, x: rows.map((row) => row.project), y: rows.map((row) => row.wall_seconds),
      marker: { color: ["#2f5bea", "#0ea5a4", "#9333ea"][index] },
      hovertemplate: `%{x}<br>${tool}: %{y:.2f} s<extra></extra>`,
    };
  }), { ...chartTheme, barmode: "group", yaxis: { type: "log", title: t("y_sec"), automargin: true }, xaxis: { tickangle: -35, automargin: true }, margin: { t: 20, r: 20, b: 100, l: 70 }, automargin: true }, PLOT_CFG);

  const top = DASH.top_rules;
  Plotly.newPlot("chart-rules", [{
    type: "bar", orientation: "h", x: top.map((rule) => rule.count).reverse(), y: top.map((rule) => `${rule.rule} (${toolShort(rule.tool)})`).reverse(),
    marker: { color: "#2f5bea" },
    hovertemplate: `%{y}<br>%{x}<extra></extra>`,
  }], { ...chartTheme, margin: { t: 18, r: 24, b: 70, l: 210 }, automargin: true }, PLOT_CFG);

  $("f-project").innerHTML = `<option value="">${esc(t("all_libs"))}</option>` + LIBS.map((l) => `<option value="${esc(l.id)}">${esc(l.name)}</option>`).join("");
  ["f-project", "f-tool", "f-outcome"].forEach((id) => $(id).addEventListener("change", loadCandidates));
  loadCandidates();
}

async function loadCandidates() {
  const params = new URLSearchParams();
  if ($("f-project").value) params.set("project", $("f-project").value);
  if ($("f-tool").value) params.set("tool", $("f-tool").value);
  if ($("f-outcome").value) params.set("outcome", $("f-outcome").value);
  const data = await api("/api/candidates?" + params.toString() + "&limit=1000");
  CANDIDATES = data.items;
  $("f-count").textContent = `${LANG === "zh" ? "共" : "Total"} ${fmt(data.total)} ${t("alert_count_unit")}`;
  $("cand-table").innerHTML = `<thead><tr><th>${esc(t("col_lib"))}</th><th>${esc(t("col_tool_h"))}</th><th>${esc(t("col_location"))}</th><th>${esc(t("col_rule_h"))}</th><th>${esc(t("col_verdict"))}</th></tr></thead><tbody>` +
    CANDIDATES.map((candidate) => `<tr class="clickable" data-key="${esc(candidate.key)}">
      <td>${esc(candidate.project)} ${esc(candidate.version)}</td>
      <td><span class="badge ${TOOL_CLASS[candidate.tool] || ""}">${esc(candidate.tool)}</span></td>
      <td>${esc(shortPath(candidate.file))}:${fmt(candidate.line)}</td>
      <td>${esc(candidate.rule)}</td>
      <td><span class="badge ${OUTCOME_CLASS[candidate.outcome] || ""}">${esc(outcomeText(candidate.outcome))}</span></td></tr>`).join("") + "</tbody>";
  document.querySelectorAll("#cand-table tr.clickable").forEach((row) => row.addEventListener("click", () => openDetail(row.dataset.key)));
}

function shortPath(path) {
  const parts = String(path).split("/");
  return parts.slice(-2).join("/");
}

async function openDetail(key) {
  const candidate = await api("/api/candidates/" + encodeURIComponent(key));
  const field = (label, value) => value ? `<div class="field"><div class="fl">${esc(label)}</div><div class="fv">${esc(value)}</div></div>` : "";
  const analysisFields = [
    [t("field_meaning"), candidate.security_meaning],
    [t("field_evidence"), candidate.source_evidence],
    [t("field_missing"), candidate.missing_conditions && candidate.missing_conditions !== "[]" ? candidate.missing_conditions : ""],
    [t("field_cross"), candidate.cross_tool],
    [t("field_root"), candidate.root_cause_group],
  ];
  $("drawer-body").innerHTML = `
    <div class="field"><span class="badge ${OUTCOME_CLASS[candidate.outcome]}">${esc(outcomeText(candidate.outcome))}</span>
      <span class="badge ${TOOL_CLASS[candidate.tool]}">${esc(candidate.tool)}</span></div>
    <div class="field"><div class="fl">${esc(t("warn_location"))}</div><div class="code">${esc(candidate.file)}:${fmt(candidate.line)}:${fmt(candidate.column)}</div></div>
    ${field(t("col_lib"), `${candidate.project} ${candidate.version}`)}
    ${field(t("col_rule_h"), candidate.rule)}
    ${field(t("warn_code"), candidate.source_code || "")}
    ${LANG === "en" ? `<p class="muted">${esc(t("warn_chinese_only"))}</p>` : ""}
    ${analysisFields.map(([label, value]) => field(label, value)).join("")}`;
  $("drawer").classList.add("show");
  $("drawer-mask").classList.add("show");
}

function closeDetail() {
  $("drawer").classList.remove("show");
  $("drawer-mask").classList.remove("show");
}
$("drawer-close").addEventListener("click", closeDetail);
$("drawer-mask").addEventListener("click", closeDetail);

function onLanguageChange() {
  applyStaticText();
  if (LIBS.length) loadLibs();
  if (LIBS.length) setupRun();
  if (DASH) loadDashboard();
  if (SPECIAL_CASES) {
    renderCaseSummary();
    renderCaseFilters();
    renderCaseFamilies();
  }
  if (CANDIDATES.length) loadCandidates();
  if (SUMMARY) renderConclusion();
  if (RELIABILITY) renderReliability();
  if (LIBS.length) renderLibPie();
}

// ---------- tab 4: special cases ----------
let SPECIAL_CASES = null;
let CASE_OUTCOME = "";
let CASE_RISK = "";
let CASE_TOOL = "";
let CASE_LIBRARY = "";
let CASE_SEARCH = "";
let CASE_ACTIVE_FAMILY = "";

const CASE_RISK_ORDER = ["buffer", "formatted", "null", "integer", "file", "quality", "other"];

function caseFamilyInfo(family) {
  const definitions = I18N[LANG].case_family_defs;
  return definitions[family] || definitions.other;
}

function caseFamilyTitle(family) {
  return caseFamilyInfo(family)[0];
}

function caseFamilyLogic(family) {
  return caseFamilyInfo(family)[1];
}

function updateCaseNavOffset() {
  const topbar = document.querySelector(".topbar");
  const topbarHeight = topbar ? topbar.getBoundingClientRect().height : 0;
  const navTop = Math.round(topbarHeight + 16);
  document.documentElement.style.setProperty("--case-nav-top", `${navTop}px`);
}

function syncCaseStickyOffsets() {
  updateCaseNavOffset();
  requestAnimationFrame(updateCaseNavOffset);
}

async function loadSpecialCases() {
  SPECIAL_CASES = await api("/api/special-cases");
  renderCaseSummary();
  renderCaseFilters();
  renderCaseFamilies();
  syncCaseStickyOffsets();
}

let CASE_RESIZE_OBSERVER = null;

function observeCaseFilterPanel() {
  const topbar = document.querySelector(".topbar");
  if (!topbar) return;
  if (CASE_RESIZE_OBSERVER) CASE_RESIZE_OBSERVER.disconnect();
  if (typeof ResizeObserver !== "undefined") {
    CASE_RESIZE_OBSERVER = new ResizeObserver(() => updateCaseNavOffset());
    CASE_RESIZE_OBSERVER.observe(topbar);
  }
  window.addEventListener("resize", syncCaseStickyOffsets);
}

function renderCaseSummary() {
  const totals = SPECIAL_CASES.outcome_totals;
  const cards = [
    ["k_total", SPECIAL_CASES.total, `case_family_count`],
    ["k_fp", totals.false_positive || 0, ""],
    ["k_sup", totals.supported || 0, ""],
    ["k_und", totals.undetermined || 0, ""],
    ["case_family_count", SPECIAL_CASES.family_count, ""],
  ];
  $("case-summary").innerHTML = cards.map(([label, value, extra]) => `<div class="case-kpi">
    <div class="label">${esc(t(label))}</div><div class="value">${fmt(value)}</div>
    ${extra ? `<div class="sub">${esc(t(extra))}</div>` : ""}</div>`).join("");
}

function renderCaseFilters() {
  const outcomes = ["false_positive", "supported", "undetermined"];
  $("case-outcome-filter").dataset.label = t("case_filter_verdict");
  $("case-outcome-filter").innerHTML = `<button class="case-filter ${CASE_OUTCOME ? "" : "active"}" data-outcome="">${esc(t("case_all_outcomes"))}</button>` +
    outcomes.map((outcome) => `<button class="case-filter ${outcome === CASE_OUTCOME ? "active" : ""}" data-outcome="${outcome}">${esc(outcomeText(outcome))} <span class="case-filter-count">${fmt(SPECIAL_CASES.outcome_totals[outcome] || 0)}</span></button>`).join("");
  $("case-risk-filter").dataset.label = t("case_filter_risk");
  $("case-risk-filter").innerHTML = `<button class="case-filter ${CASE_RISK ? "" : "active"}" data-risk="">${esc(t("case_all_risks"))}</button>` +
    CASE_RISK_ORDER.map((risk) => `<button class="case-filter ${risk === CASE_RISK ? "active" : ""}" data-risk="${risk}">${esc(caseRiskLabel(risk))}</button>`).join("");

  const tools = [...new Set(SPECIAL_CASES.cases.flatMap((item) => Object.keys(item.tools)))];
  $("case-tool-filter").dataset.label = t("case_filter_tool");
  $("case-tool-filter").innerHTML = `<button class="case-filter ${CASE_TOOL ? "" : "active"}" data-tool="">${esc(t("case_all_tools"))}</button>` +
    tools.map((tool) => `<button class="case-filter ${tool === CASE_TOOL ? "active" : ""}" data-tool="${esc(tool)}">${esc(toolShort(tool))}</button>`).join("");
  const libraries = [...new Set(SPECIAL_CASES.cases.flatMap((item) => Object.keys(item.libraries)))].sort();
  $("case-library-filter").dataset.label = t("case_filter_library");
  $("case-library-filter").innerHTML = `<button class="case-filter ${CASE_LIBRARY ? "" : "active"}" data-library="">${esc(t("case_all_libraries"))}</button>` +
    libraries.map((library) => `<button class="case-filter ${library === CASE_LIBRARY ? "active" : ""}" data-library="${esc(library)}">${esc(library)}</button>`).join("");

  document.querySelectorAll("#case-outcome-filter .case-filter").forEach((button) => button.addEventListener("click", () => {
    CASE_OUTCOME = button.dataset.outcome;
    CASE_ACTIVE_FAMILY = "";
    renderCaseFilters();
    renderCaseFamilies();
  }));
  document.querySelectorAll("#case-risk-filter .case-filter").forEach((button) => button.addEventListener("click", () => {
    CASE_RISK = button.dataset.risk;
    CASE_ACTIVE_FAMILY = "";
    renderCaseFilters();
    renderCaseFamilies();
  }));
  document.querySelectorAll("#case-tool-filter .case-filter").forEach((button) => button.addEventListener("click", () => {
    CASE_TOOL = button.dataset.tool;
    CASE_ACTIVE_FAMILY = "";
    renderCaseFilters();
    renderCaseFamilies();
  }));
  document.querySelectorAll("#case-library-filter .case-filter").forEach((button) => button.addEventListener("click", () => {
    CASE_LIBRARY = button.dataset.library;
    CASE_ACTIVE_FAMILY = "";
    renderCaseFilters();
    renderCaseFamilies();
  }));
  $("case-search").value = CASE_SEARCH;
  $("case-search").oninput = (event) => {
    CASE_SEARCH = event.target.value.trim().toLowerCase();
    CASE_ACTIVE_FAMILY = "";
    renderCaseFamilies();
  };
  requestAnimationFrame(updateCaseNavOffset);
  $("case-reset").onclick = () => {
    CASE_OUTCOME = "";
    CASE_RISK = "";
    CASE_TOOL = "";
    CASE_LIBRARY = "";
    CASE_SEARCH = "";
    CASE_ACTIVE_FAMILY = "";
    renderCaseFilters();
    renderCaseFamilies();
  };
}

function caseRiskLabel(risk) {
  const labels = {
    buffer: LANG === "zh" ? "内存与缓冲区" : "Memory and buffers",
    formatted: LANG === "zh" ? "格式化输出" : "Formatted output",
    null: LANG === "zh" ? "空指针" : "Null pointer",
    integer: LANG === "zh" ? "整数、移位与除法" : "Integer, shift, division",
    file: LANG === "zh" ? "文件、环境与命令" : "File, environment, command",
    quality: LANG === "zh" ? "代码质量" : "Code quality",
    other: LANG === "zh" ? "其他" : "Other",
  };
  return labels[risk] || risk;
}

function filteredCaseFamilies() {
  return SPECIAL_CASES.cases.filter((item) => {
    if (CASE_OUTCOME && item.outcome !== CASE_OUTCOME) return false;
    if (CASE_RISK && !item.examples.some((example) => example.risk === CASE_RISK)) return false;
    if (CASE_TOOL && !item.tools[CASE_TOOL]) return false;
    if (CASE_LIBRARY && !item.libraries[CASE_LIBRARY]) return false;
    if (CASE_SEARCH) {
      const haystack = [
        caseFamilyTitle(item.family), caseFamilyLogic(item.family), item.family,
        ...item.rules, ...Object.keys(item.tools), ...Object.keys(item.libraries),
        ...item.examples.flatMap((example) => [example.security_meaning, example.source_evidence, example.file, example.rule]),
      ].join(" ").toLowerCase();
      if (!haystack.includes(CASE_SEARCH)) return false;
    }
    return true;
  });
}

function renderCaseFamilies() {
  const cases = filteredCaseFamilies();
  const alertCount = cases.reduce((sum, item) => sum + item.count, 0);
  $("case-count").textContent = text("case_count", { n: fmt(cases.length), alerts: fmt(alertCount) });
  renderCaseNav(cases);

  if (!cases.length) {
    $("case-families").innerHTML = `<div class="case-empty">${esc(LANG === "zh" ? "没有符合当前筛选条件的案例族。请调整或重置筛选。" : "No case family matches the current filters. Adjust or reset them.")}</div>`;
    return;
  }

  $("case-families").innerHTML = cases.map((item) => {
    const toolCounts = Object.entries(item.tools).sort((a, b) => b[1] - a[1]);
    const libraryCounts = Object.entries(item.libraries).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const examples = item.examples.map((example, index) => renderCaseExample(example, index)).join("");
    return `<article class="case-family" data-outcome="${item.outcome}" id="family-${esc(item.id)}">
      <div class="case-family-head">
        <div>
          <div class="case-family-meta">
            <span class="badge ${OUTCOME_CLASS[item.outcome]}">${esc(outcomeText(item.outcome))}</span>
            <span class="case-family-count">${fmt(item.count)} ${esc(t("alert_count_unit"))}</span>
            <span class="case-family-risk">${esc(caseRiskLabel(item.examples[0]?.risk || "other"))}</span>
          </div>
          <h3>${esc(caseFamilyTitle(item.family))}</h3>
        </div>
        <div class="case-family-rules"><span class="case-section-label">${esc(t("case_common_rules"))}</span>${item.rules.map((rule) => `<code>${esc(rule)}</code>`).join("")}</div>
      </div>
      <div class="case-analysis-panel">
        <div class="case-analysis-step case-step-why">
          <div class="case-step-head">
            <span class="case-step-number">1</span>
            <span class="case-step-title">${esc(t("case_why_reported"))}</span>
          </div>
          <p>${esc(caseFamilyLogic(item.family))}</p>
        </div>
        <div class="case-analysis-step case-step-verdict">
          <div class="case-step-head">
            <span class="case-step-number">2</span>
            <span class="case-step-title">${esc(t("case_why_verdict"))}</span>
          </div>
          <p>${esc(caseVerdictExplanation(item))}</p>
          <div class="case-step-verdict-tag"><span class="badge ${OUTCOME_CLASS[item.outcome]}">${esc(outcomeText(item.outcome))}</span></div>
        </div>
        <div class="case-analysis-step case-step-evidence">
          <div class="case-step-head">
            <span class="case-step-number">3</span>
            <span class="case-step-title">${esc(t("case_evidence_chain"))}</span>
          </div>
          <p>${esc(caseEvidenceExplanation(item))}</p>
          <div class="case-step-chain">
            <span class="case-chain-node">${esc(t("case_chain_meaning"))}</span>
            <span class="case-chain-arrow">→</span>
            <span class="case-chain-node">${esc(t("case_chain_evidence"))}</span>
            <span class="case-chain-arrow">→</span>
            <span class="case-chain-node">${esc(t("case_chain_missing"))}</span>
            <span class="case-chain-arrow">→</span>
            <span class="case-chain-node">${esc(t("case_chain_root"))}</span>
          </div>
        </div>
      </div>
      <div class="case-distributions">
        <div><div class="case-section-label">${esc(t("case_tool_distribution"))}</div>${toolCounts.map(([tool, count]) => `<span class="case-chip">${esc(toolShort(tool))} <b>${fmt(count)}</b></span>`).join("")}</div>
        <div><div class="case-section-label">${esc(t("case_library_distribution"))}</div>${libraryCounts.map(([library, count]) => `<span class="case-chip">${esc(library)} <b>${fmt(count)}</b></span>`).join("")}</div>
      </div>
      <h4 class="case-examples-title"><span>${esc(t("case_examples"))}</span><small>${esc(t("case_analysis_steps"))}</small></h4>
      <div class="case-examples">${examples}</div>
    </article>`;
  }).join("");
}

function renderCaseNav(cases) {
  const grouped = new Map();
  cases.forEach((item) => {
    if (!grouped.has(item.outcome)) grouped.set(item.outcome, []);
    grouped.get(item.outcome).push(item);
  });
  $("case-nav-list").innerHTML = [...grouped.entries()].map(([outcome, items]) => `
    <div class="case-nav-group">
      <div class="case-nav-title"><span class="badge ${OUTCOME_CLASS[outcome]}">${esc(outcomeText(outcome))}</span><b>${fmt(items.length)}</b></div>
      ${items.map((item) => `<button class="case-nav-item ${CASE_ACTIVE_FAMILY === item.id ? "active" : ""}" data-family="${esc(item.id)}">
        <span>${esc(caseFamilyTitle(item.family))}</span><b>${fmt(item.count)}</b></button>`).join("")}
    </div>`).join("");
  document.querySelectorAll(".case-nav-item").forEach((button) => button.addEventListener("click", () => {
    CASE_ACTIVE_FAMILY = button.dataset.family;
    renderCaseNav(cases);
    const target = document.getElementById(`family-${CASE_ACTIVE_FAMILY}`);
    if (!target) return;
    const topbar = document.querySelector(".topbar");
    const topbarHeight = topbar ? topbar.getBoundingClientRect().height : 0;
    const offset = topbarHeight + 24;
    const top = target.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top, behavior: "smooth" });
  }));
}

function caseVerdictExplanation(item) {
  if (item.outcome === "false_positive") {
    return LANG === "zh"
      ? `该案例族的 ${item.count} 条告警均未在当前固定构建与源码路径中形成原报告所描述的风险，因此判为原风险误报。代表案例中的源码证据给出了排除原因。`
      : `None of the ${item.count} alerts in this family establishes the risk described by the original warning under the frozen build and source path, so they are false positives. The representative cases show the evidence used to exclude the risk.`;
  }
  if (item.outcome === "supported") {
    return LANG === "zh"
      ? `该案例族的 ${item.count} 条告警均找到源码依据。结论表示问题在当前实现中成立，但不等同于已经完成动态利用验证。`
      : `All ${item.count} alerts in this family have source-level support. The verdict means the issue is present in the current implementation; it does not imply completed exploit validation.`;
  }
  return LANG === "zh"
    ? `该案例族的 ${item.count} 条告警均缺少决定性上下文。现有证据既不足以确认风险，也不足以排除风险，因此判为无法判断。`
    : `All ${item.count} alerts in this family lack decisive context. The available evidence neither confirms nor excludes the risk, so the verdict remains undetermined.`;
}

function caseEvidenceExplanation(item) {
  const evidence = item.examples[0];
  if (!evidence) return "";
  const source = evidence.source_code ? ` ${LANG === "zh" ? "告警位置已定位到具体源码行。" : "The warning location has been mapped to a concrete source line."}` : "";
  return `${LANG === "zh" ? "每个代表案例按“安全含义 → 源码证据 → 缺失条件 → 跨工具关系”展开。" : "Each representative case follows security meaning → source evidence → missing conditions → cross-tool relation."}${source}`;
}

function renderCaseExample(example, index) {
  const evidenceBlocks = [
    [t("case_security_meaning"), example.security_meaning, "meaning"],
    [t("case_source_evidence"), example.source_evidence, "evidence"],
    ...(example.missing_conditions && example.missing_conditions !== "[]" ? [[t("case_missing"), example.missing_conditions, "missing"]] : []),
    ...(example.root_cause_group ? [[t("case_root_cause"), example.root_cause_group, "root"]] : []),
    ...(example.cross_tool ? [[t("case_cross_tool"), example.cross_tool, "cross"]] : []),
  ];
  const codeBlock = example.source_code ? `<div class="case-code-block">
      <div class="case-code-head"><span class="case-code-dot"></span><span>${esc(t("case_code_line"))}</span><code>${esc(example.file)}:${fmt(example.line)}</code></div>
      <pre><code>${esc(example.source_code)}</code></pre>
    </div>` : `<div class="case-code-missing">${esc(t("warn_no_code"))}</div>`;
  return `<div class="case-example">
    <div class="case-example-head">
      <span class="case-example-number">${index + 1}</span>
      <div>
        <strong>${esc(example.project)} ${esc(example.version)} · ${esc(example.rule)}</strong>
        <div class="case-location"><span class="case-location-pin">●</span>${esc(example.file)}:${fmt(example.line)}:${fmt(example.column)}</div>
      </div>
      <span class="badge ${TOOL_CLASS[example.tool] || ""}">${esc(toolShort(example.tool))}</span>
    </div>
    ${codeBlock}
    <div class="case-evidence">
      ${evidenceBlocks.map(([label, value, kind], blockIndex) => `<div class="case-evidence-item case-evidence-${kind}">
        <div class="case-evidence-label"><span>${blockIndex + 1}</span>${esc(label)}</div>
        <p>${esc(value)}</p>
      </div>`).join("")}
    </div>
    <div class="case-conclusion"><span class="badge ${OUTCOME_CLASS[example.outcome]}">${esc(outcomeText(example.outcome))}</span><span>${esc(caseFamilyTitle(example.family || ""))}</span></div>
  </div>`;
}

// ---------- tab 6: conclusion ----------
let SUMMARY = null;

async function loadSummary() {
  SUMMARY = await api("/api/summary");
  renderConclusion();
}

function conclVerdictTag(row) {
  const best = Math.max(...SUMMARY.tools.map((item) => item.precision));
  if (row.precision >= best) return ["concl-verdict-best", LANG === "zh" ? "最有效" : "Most effective"];
  if (row.precision >= 10) return ["concl-verdict-mid", LANG === "zh" ? "部分有效" : "Partly effective"];
  return ["concl-verdict-worst", LANG === "zh" ? "基本无效" : "Largely ineffective"];
}

function renderConclusion() {
  const rows = SUMMARY.tools;

  $("concl-cards").innerHTML = rows.map((row) => {
    const [tagClass, tagText] = conclVerdictTag(row);
    const spread = SUMMARY.rule_spread[row.tool];
    return `<div class="concl-card" data-tool="${esc(row.tool)}">
      <div class="concl-card-head">
        <h3>${esc(row.tool)}</h3>
        <span class="concl-verdict-tag ${tagClass}">${esc(tagText)}</span>
      </div>
      <div class="concl-score">
        <div class="concl-score-item"><div class="l">${esc(t("concl_col_volume"))}</div><div class="v">${fmt(row.total)}</div></div>
        <div class="concl-score-item"><div class="l">${esc(t("concl_col_accuracy"))}</div><div class="v">${row.precision}%</div></div>
        <div class="concl-score-item"><div class="l">${esc(t("concl_col_cost"))}</div><div class="v">${fmt(row.total_wall_seconds)}s</div></div>
      </div>
      <h4>${esc(t("concl_strengths"))}</h4>
      <ul>${conclStrengths(row, spread).map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
      <h4>${esc(t("concl_weaknesses"))}</h4>
      <ul>${conclWeaknesses(row, spread).map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
    </div>`;
  }).join("");

  $("concl-table").innerHTML = `<thead><tr>
      <th>${esc(t("col_tool_h"))}</th>
      <th class="num">${esc(t("concl_col_volume"))}</th>
      <th class="num">${esc(t("concl_col_accuracy"))}</th>
      <th class="num">${esc(t("concl_col_precision"))}</th>
      <th class="num">${esc(t("concl_col_cost"))}</th>
      <th class="num">${esc(t("concl_col_cost_per_hit"))}</th>
      <th class="num">${esc(t("concl_col_coverage"))}</th>
    </tr></thead><tbody>` +
    rows.map((row) => `<tr>
      <td><span class="badge ${TOOL_CLASS[row.tool] || ""}">${esc(row.tool)}</span></td>
      <td class="num">${fmt(row.total)}</td>
      <td class="num">${row.precision}%</td>
      <td class="num">${row.fp_ratio}%</td>
      <td class="num">${fmt(row.total_wall_seconds)} s</td>
      <td class="num">${row.cost_per_supported ? fmt(row.cost_per_supported) : "-"}</td>
      <td class="num">${fmt(SUMMARY.coverage[row.tool])} / ${fmt(SUMMARY.project_count)}</td>
    </tr>`).join("") + "</tbody>";

  const chartTheme = {
    ...PLOT_LAYOUT,
    font: { ...PLOT_LAYOUT.font, family: LANG === "en" ? "Arial, sans-serif" : "Microsoft YaHei, sans-serif" },
    legend: { orientation: "h", y: -0.2, x: 0, xanchor: "left" },
  };
  Plotly.newPlot("chart-concl", [
    {
      type: "bar", name: t("concl_col_volume"), x: rows.map((r) => r.tool),
      y: rows.map((r) => r.total), marker: { color: rows.map((r) => TOOL_COLOR[r.tool]) },
      hovertemplate: `%{x}<br>${t("concl_col_volume")}: %{y}<extra></extra>`,
    },
    {
      type: "bar", name: t("concl_col_accuracy"), x: rows.map((r) => r.tool),
      y: rows.map((r) => r.precision), marker: { color: "#1f9d55" }, yaxis: "y2",
      hovertemplate: `%{x}<br>${t("concl_col_accuracy")}: %{y}%<extra></extra>`,
    },
  ], {
    ...chartTheme,
    barmode: "group",
    margin: { t: 20, r: 20, b: 90, l: 60 },
    automargin: true,
    yaxis: { title: t("concl_col_volume") },
    yaxis2: { title: t("concl_col_accuracy"), overlaying: "y", side: "right", range: [0, 100], showgrid: false },
  }, PLOT_CFG);

  $("concl-verdicts").innerHTML = rows.map((row) => `<div class="concl-verdict">
    <h3><span class="badge ${TOOL_CLASS[row.tool] || ""}">${esc(row.tool)}</span></h3>
    <p>${esc(conclVerdictText(row))}</p>
    <p class="muted">${esc(LANG === "zh" ? "找到有效问题的库" : "Libraries with useful findings")}: ${
      SUMMARY.supported_projects[row.tool].length
        ? SUMMARY.supported_projects[row.tool].map((p) => esc(p)).join("、")
        : (LANG === "zh" ? "无" : "none")
    }</p>
  </div>`).join("");

  const scenarios = ["concl_sc_llm", "concl_sc_ci", "concl_sc_deep", "concl_sc_combo"];
  const scenarioTools = ["Flawfinder", "Cppcheck", "CodeChecker/clangsa", "Flawfinder + Cppcheck + clangsa"];
  $("concl-scenarios").innerHTML = scenarios.map((key, index) => `<div class="concl-scenario">
    <h4>${esc(t(key))}</h4>
    <p><span class="tool">${esc(scenarioTools[index])}</span></p>
    <p>${esc(t(`${key}_d`))}</p>
  </div>`).join("");
}

function conclStrengths(row, spread) {
  const items = [];
  if (LANG === "zh") {
    if (row.supported >= 30) items.push(`找到 ${row.supported} 条有依据的告警，有效率 ${row.precision}%，三款工具中最高。`);
    if (row.total >= 300) items.push(`覆盖全部 ${SUMMARY.coverage[row.tool]} 个库，告警总量 ${row.total} 条，风险位置不容易漏。`);
    if (row.total_wall_seconds < 60) items.push(`十次扫描总耗时仅 ${row.total_wall_seconds} 秒，日常使用负担最小。`);
    if (!row.needs_build) items.push("不需要先编译，直接读文本就能用，接入成本最低。");
    if (spread.distinct_rules >= 15) items.push(`命中 ${spread.distinct_rules} 种不同规则，信号分布较广。`);
    if (row.supported_projects_count >= 2) items.push(`在 ${row.supported_projects_count} 个库中找到了有效问题。`);
  } else {
    if (row.supported >= 30) items.push(`Found ${row.supported} supported alerts, a ${row.precision}% usefulness rate, the highest of the three.`);
    if (row.total >= 300) items.push(`Covered all ${SUMMARY.coverage[row.tool]} libraries with ${row.total} alerts, so risky locations are unlikely to be missed.`);
    if (row.total_wall_seconds < 60) items.push(`All ten scans took only ${row.total_wall_seconds} seconds in total, the smallest burden for routine use.`);
    if (!row.needs_build) items.push("Needs no prior build; it reads the text directly, so integration cost is the lowest.");
    if (spread.distinct_rules >= 15) items.push(`Matched ${spread.distinct_rules} distinct rules, giving a broad signal.`);
    if (row.supported_projects_count >= 2) items.push(`Produced useful findings in ${row.supported_projects_count} libraries.`);
  }
  return items;
}

function conclWeaknesses(row, spread) {
  const items = [];
  if (LANG === "zh") {
    if (row.fp_ratio >= 80) items.push(`${row.fp_ratio}% 的告警是误报，${row.cost_per_supported} 条告警里只有 1 条站得住，人工筛除成本高。`);
    if (row.precision > 0 && row.precision < 10) items.push(`有效率只有 ${row.precision}%，大部分命中来自危险函数名而不是真实缺陷。`);
    if (spread.top_rule_share >= 40) items.push(`${spread.top_rule_share}% 的告警集中在同一条规则（${spread.top_rule}），信息量有限。`);
    if (row.total_wall_seconds >= 200) items.push(`十次扫描总耗时 ${row.total_wall_seconds} 秒，是最快工具的数倍，不适合全库频繁运行。`);
    if (row.undetermined > 0) items.push(`有 ${row.undetermined} 条告警依赖调用方上下文，仅凭库内源码无法定论。`);
    if (row.needs_build) items.push("需要先生成编译数据库，接入比纯文本扫描复杂。");
  } else {
    if (row.fp_ratio >= 80) items.push(`${row.fp_ratio}% of its alerts are false positives; only 1 in ${row.cost_per_supported} holds up, so triage cost is high.`);
    if (row.precision > 0 && row.precision < 10) items.push(`A usefulness rate of only ${row.precision}%; most hits come from risky names rather than real defects.`);
    if (spread.top_rule_share >= 40) items.push(`${spread.top_rule_share}% of its alerts fall in a single rule (${spread.top_rule}), which limits the information it carries.`);
    if (row.total_wall_seconds >= 200) items.push(`All ten scans took ${row.total_wall_seconds} seconds, several times the fastest tool, so it does not suit frequent whole-codebase runs.`);
    if (row.undetermined > 0) items.push(`${row.undetermined} alerts depend on caller context and cannot be settled from library source alone.`);
    if (row.needs_build) items.push("Requires a compilation database first, which makes integration more involved than plain text scanning.");
  }
  return items;
}

function conclVerdictText(row) {
  const lib = LANG === "zh" ? "库" : "libraries";
  if (LANG === "zh") {
    if (row.precision >= 30) {
      return `综合来看，${row.tool} 是三款工具里最有效的：${row.total} 条告警中 ${row.supported} 条经核查成立，有效率 ${row.precision}%。代价是 ${row.total_wall_seconds} 秒的总耗时和 ${row.fp_ratio}% 的误报比例，但每 ${row.cost_per_supported} 条告警就能找到 1 条真问题，比另外两款划算得多。在 ${SUMMARY.supported_projects[row.tool].length} 个 ${lib}中给出了有效结论，是本实验中最值得单独依赖的一款。`;
    }
    if (row.precision >= 10) {
      return `${row.tool} 处在中间位置：${row.total} 条告警中 ${row.supported} 条成立，有效率 ${row.precision}%，在 ${SUMMARY.supported_projects[row.tool].length} 个 ${lib}中有有效发现。它既不像 Flawfinder 那样几乎全是误报，也不像 clangsa 那样定位到精确的路径条件。作为常规质量检查工具，它的覆盖范围和运行代价比较均衡。`;
    }
    return `${row.tool} 在本实验中表现最弱：${row.total} 条告警里只有 ${row.supported} 条成立，有效率 ${row.precision}%，${row.fp_ratio}% 是误报。它${row.total_wall_seconds > 60 ? "同时是最慢的工具，十次扫描要 " + row.total_wall_seconds + " 秒" : "命中规则比较单一"}，${spreadSummary(row)}，适合当作快速摸底的线索来源，不适合作为判断依据。`;
  }
  if (row.precision >= 30) {
    return `Overall, ${row.tool} is the most effective of the three: ${row.supported} of ${row.total} alerts hold up under review, a usefulness rate of ${row.precision}%. The cost is ${row.total_wall_seconds} seconds of total runtime and a ${row.fp_ratio}% false-positive share, but it yields 1 real finding per ${row.cost_per_supported} alerts, far better value than the alternatives. It produced useful conclusions across ${SUMMARY.supported_projects[row.tool].length} ${lib} and is the one worth relying on by itself.`;
  }
  if (row.precision >= 10) {
    return `${row.tool} sits in the middle: ${row.supported} of ${row.total} alerts hold up, a usefulness rate of ${row.precision}%, with useful findings in ${SUMMARY.supported_projects[row.tool].length} ${lib}. It is neither almost entirely false positives like Flawfinder nor as precise about path conditions as clangsa. As a routine quality gate, its coverage and runtime cost are well balanced.`;
  }
  return `${row.tool} performed worst in this experiment: only ${row.supported} of ${row.total} alerts hold up, a usefulness rate of ${row.precision}%, with ${row.fp_ratio}% false positives. It ${row.total_wall_seconds > 60 ? "is also the slowest, needing " + row.total_wall_seconds + " seconds for ten scans" : "matches a fairly narrow set of rules"}; ${spreadSummary(row)}. It works as a quick source of leads rather than as a basis for decisions.`;
}

function spreadSummary(row) {
  const spread = SUMMARY.rule_spread[row.tool];
  return LANG === "zh"
    ? `命中的规则集中在 ${spread.distinct_rules} 种，其中 ${spread.top_rule} 占 ${spread.top_rule_share}%`
    : `matches ${spread.distinct_rules} rules, of which ${spread.top_rule} accounts for ${spread.top_rule_share}%`;
}

// ---------- tab 7: reliability ----------
let RELIABILITY = null;

async function loadReliability() {
  RELIABILITY = await api("/api/reliability");
  renderReliability();
}

function renderReliability() {
  const rep = RELIABILITY.replication;
  const rev = RELIABILITY.review;

  $("rel-pillars").innerHTML = [
    { n: "1", h: "rel_pillar1_h", p: "rel_pillar1_p" },
    { n: "2", h: "rel_pillar2_h", p: "rel_pillar2_p" },
  ].map((item) => `<div class="rel-pillar">
    <h3><span class="rel-pillar-num">${esc(item.n)}</span>${esc(t(item.h))}</h3>
    <p>${esc(t(item.p))}</p>
  </div>`).join("");

  const steps = [
    ["rel_step1", "rel_step1_d"], ["rel_step2", "rel_step2_d"],
    ["rel_step3", "rel_step3_d"], ["rel_step4", "rel_step4_d"],
  ];
  $("rel-steps").innerHTML = steps.map(([h, d], index) => `<div class="rel-step">
    <h4><span class="rel-pillar-num">${index + 1}</span> ${esc(t(h))}</h4>
    <p>${esc(t(d))}</p>
  </div>`).join("");

  $("rel-pinned-table").innerHTML = `<thead><tr>
      <th>${esc(t("rel_col_lib"))}</th><th>${esc(t("rel_col_version"))}</th>
      <th>${esc(t("rel_col_commit"))}</th><th>${esc(t("rel_col_hash"))}</th>
    </tr></thead><tbody>` +
    rep.pinned_libraries.map((lib) => `<tr>
      <td><b>${esc(lib.name)}</b></td>
      <td>${esc(lib.version)}</td>
      <td><code class="rel-hash">${esc(String(lib.commit).slice(0, 12))}</code></td>
      <td>${lib.has_hash
        ? `<span class="badge b-sup">${esc(t("rel_hash_yes"))}</span> <code class="rel-hash">${esc(String(lib.sha256).slice(0, 16))}…</code>`
        : `<span class="badge b-und">${esc(t("rel_hash_no"))}</span>`}</td>
    </tr>`).join("") + "</tbody>";

  const exhaustive = rev.exhaustive_groups.reduce((a, item) => a + item.sampled, 0);
  const sampled = rev.sampled_groups.reduce((a, item) => a + item.sampled, 0);
  $("rel-review-grid").innerHTML = [
    [t("rel_kpi_total"), rev.total_alerts],
    [t("rel_kpi_exhaustive"), exhaustive],
    [t("rel_kpi_sampled"), sampled],
    [t("rel_kpi_runs"), rep.runs_compared],
    [t("rel_kpi_identical"), rep.alert_groups_identical],
  ].map(([label, value]) => `<div class="rel-kpi"><div class="l">${esc(label)}</div><div class="v">${fmt(value)}</div></div>`).join("");

  const strata = [...rev.exhaustive_groups, ...rev.sampled_groups];
  $("rel-strata-table").innerHTML = `<thead><tr>
      <th>${esc(t("rel_col_stratum"))}</th><th>${esc(t("rel_col_population"))}</th>
      <th class="num">${esc(t("rel_col_pop_size"))}</th><th class="num">${esc(t("rel_col_sampled"))}</th>
      <th class="num">${esc(t("rel_col_rate"))}</th>
    </tr></thead><tbody>` +
    strata.map((item) => `<tr>
      <td><b>${esc(item.stratum)}</b></td>
      <td>${esc(item.population)}</td>
      <td class="num">${fmt(item.population_size)}</td>
      <td class="num">${fmt(item.sampled)}</td>
      <td class="num">${esc(item.rate)}</td>
    </tr>`).join("") + "</tbody>" +
    `<tfoot><tr><td colspan="2"><b>${esc(LANG === "zh" ? "合计" : "Total")}</b></td>
      <td class="num"><b>${fmt(rev.population)}</b></td>
      <td class="num"><b>${fmt(rev.sample_size)}</b></td>
      <td class="num"><b>${rev.population ? ((100 * rev.sample_size / rev.population).toFixed(1)) : "0"}%</b></td>
    </tr></tfoot>`;

}

// ---------- boot ----------
(async function boot() {
  try {
    applyStaticText();
    await loadLibs();
    setupRun();
    await loadDashboard();
    await loadSpecialCases();
    await loadSummary();
    await loadReliability();
    observeCaseFilterPanel();
    syncCaseStickyOffsets();
  } catch (err) {
    document.body.insertAdjacentHTML("afterbegin", `<div style="padding:12px;background:#fee;color:#900">${esc(t("load_failed"))}: ${esc(err.message)}</div>`);
  }
})();
