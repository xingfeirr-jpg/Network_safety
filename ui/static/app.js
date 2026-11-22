const TOOL_LABEL = { FF: "Flawfinder", CP: "Cppcheck", CC: "CodeChecker/clangsa" };
const TOOL_CLASS = { Flawfinder: "b-ff", Cppcheck: "b-cp", "CodeChecker/clangsa": "b-cc" };
const OUTCOME_CLASS = { false_positive: "b-fp", supported: "b-sup", undetermined: "b-und" };
const TOOLS = ["Flawfinder", "Cppcheck", "CodeChecker/clangsa"];
const DOMAIN = { zlib: "compression", LZ4: "compression", cJSON: "JSON", "json-c": "JSON", yyjson: "JSON", libyaml: "YAML", Expat: "XML", libpng: "image", "libjpeg-turbo": "image", utf8proc: "Unicode" };

// Design tokens shared with style.css (keep the two in sync).
const DS = {
  ink: "#0e1116", muted: "#5d6672", faint: "#9aa3ae", line: "#e3e6eb", panel: "#ffffff",
  sans: '-apple-system, BlinkMacSystemFont, "Inter", "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif',
  mono: 'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
  outcome: { false_positive: "#d9dde3", supported: "#f0601a", undetermined: "#6b7a90" },
  tool: { Flawfinder: "#3e63dd", Cppcheck: "#12a594", "CodeChecker/clangsa": "#8e4ec6" },
  neutral: ["#3b4452", "#b4bdc9"],
};
const OUTCOME_COLOR = DS.outcome;
const TOOL_COLOR = DS.tool;
// Display order for verdicts: the rare, important ones first.
const OUTCOMES = ["supported", "undetermined", "false_positive"];

const PLOT_CFG = { displayModeBar: false, responsive: true };

// One Plotly theme for every chart: transparent background, hairline grid, mono ticks.
function plotLayout(extra = {}) {
  const axis = { gridcolor: DS.line, zeroline: false, linecolor: DS.line, tickfont: { family: DS.mono, size: 10.5, color: DS.faint }, fixedrange: true, automargin: true };
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: DS.sans, size: 12, color: DS.muted },
    margin: { t: 8, r: 16, b: 36, l: 48 },
    showlegend: false,
    hoverlabel: { bgcolor: DS.ink, bordercolor: DS.ink, font: { family: DS.sans, color: "#fff", size: 12 } },
    ...extra,
    xaxis: { ...axis, ...(extra.xaxis || {}) },
    yaxis: { ...axis, ...(extra.yaxis || {}) },
  };
}
// Category axis with readable labels (tool / library names).
const CATEGORY_AXIS = { showgrid: false, linecolor: "rgba(0,0,0,0)", tickfont: { family: DS.sans, size: 12.5, color: DS.ink }, ticksuffix: "  " };

function outcomeMarker(outcome) {
  return outcome === "undetermined"
    ? { color: DS.panel, line: { color: DS.outcome[outcome], width: 1 }, pattern: { shape: "/", fgcolor: DS.outcome[outcome], size: 5, solidity: 0.35 } }
    : { color: DS.outcome[outcome], line: { width: 0 } };
}

function renderLegend(id, items) {
  $(id).innerHTML = items.map(([label, cls, color]) => `<span class="lg"><i class="sw ${cls || ""}"${color ? ` style="background:${color}"` : ""}></i>${esc(label)}</span>`).join("");
}
const outcomeLegend = (id) => renderLegend(id, OUTCOMES.map((o) => [outcomeText(o), `sw-${o}`]));
const toolLegend = (id) => renderLegend(id, TOOLS.map((tool) => [toolShort(tool), "", TOOL_COLOR[tool]]));

const $ = (id) => document.getElementById(id);
const fmt = (n) => (n === null || n === undefined || Number.isNaN(n)) ? "-" : Number(n).toLocaleString(LANG === "en" ? "en-US" : "zh-CN");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const outcomeText = (outcome) => ({ false_positive: t("fp"), supported: t("sup"), undetermined: t("und") }[outcome] || outcome);
const toolShort = (tool) => tool === "CodeChecker/clangsa" ? "clangsa" : tool;
const text = (key, vars = {}) => Object.entries(vars).reduce((value, [name, replacement]) => value.replaceAll(`{${name}}`, replacement), t(key));

// Static mode (GitHub Pages build, see ui/tools/build_static.py): the API responses are
// pre-generated JSON files next to index.html and filtering happens in the browser.
const STATIC = Boolean(window.P17_STATIC);
let STATIC_CANDIDATES = null;

async function fetchJson(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

async function staticApi(path) {
  const url = new URL(path, "http://x");
  const route = url.pathname.replace(/^\/api\//, "");
  if (route === "candidates" || route.startsWith("candidates/")) {
    if (!STATIC_CANDIDATES) STATIC_CANDIDATES = await fetchJson("api/candidates.json");
    if (route.startsWith("candidates/")) {
      const key = decodeURIComponent(route.slice("candidates/".length));
      const row = STATIC_CANDIDATES.find((r) => r.key === key);
      if (!row) throw new Error(`404 ${path}`);
      return row;
    }
    const q = url.searchParams;
    const rows = STATIC_CANDIDATES.filter((r) =>
      (!q.get("project") || r.project_id === q.get("project")) &&
      (!q.get("tool") || r.tool === q.get("tool")) &&
      (!q.get("outcome") || r.outcome === q.get("outcome")));
    return { total: rows.length, items: rows.slice(0, Number(q.get("limit") || 1000)) };
  }
  if (route.startsWith("replay/")) return fetchJson(`api/replay/${route.slice("replay/".length).replace("/", "-")}.json`);
  if (route.startsWith("runs")) throw new Error(t("run_static"));
  return fetchJson(`api/${route}.json`);
}

async function api(path, opts) {
  return STATIC ? staticApi(path) : fetchJson(path, opts);
}

// ---------- tabs ----------
// Highlight a page in the stage navigation without changing what is shown.
function setNavState(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  const current = Number(document.querySelector(`.tab[data-tab="${name}"]`)?.closest(".stage")?.dataset.stage || 1);
  document.querySelectorAll(".stage").forEach((st) => {
    const n = Number(st.dataset.stage);
    st.classList.toggle("is-done", n < current);
    st.classList.toggle("is-current", n === current);
  });
  // On phones the stage bar scrolls sideways; keep the current page in view.
  const stages = $("stages");
  const activeTab = document.querySelector(`.tab[data-tab="${name}"]`);
  if (stages && activeTab && stages.scrollWidth > stages.clientWidth + 1) {
    stages.scrollTo({ left: activeTab.closest(".stage").offsetLeft - 14, behavior: "smooth" });
  }
}

function switchTab(name) {
  if (PRESENTING) exitDeck();
  setNavState(name);
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === name));
  window.scrollTo({ top: 0, behavior: "smooth" });
  window.dispatchEvent(new Event("resize"));
}

// Height covered by the navigation at the top of the page: only on phones, where the
// sidebar turns into a sticky top bar. On wider screens it sits on the left.
function stickyTop() {
  const bar = $("sidebar");
  if (!bar || getComputedStyle(bar).position !== "sticky") return 0;
  return Math.max(0, bar.getBoundingClientRect().bottom);
}

// Narrow rail on medium screens and during the talk; full sidebar on wide screens.
function updateRail() {
  const wide = window.innerWidth >= 900;
  document.body.classList.toggle("is-rail", wide && (window.innerWidth < 1280 || PRESENTING));
}
window.addEventListener("resize", updateRail);

document.querySelectorAll(".tab").forEach((btn) => btn.addEventListener("click", () => {
  if (PRESENTING && deckJumpToPage(btn.dataset.tab)) return;
  switchTab(btn.dataset.tab);
}));
// A stage heading opens the first page of that stage (or its first slide during the talk).
document.querySelectorAll(".stage-head").forEach((head) => head.addEventListener("click", () => {
  const stage = Number(head.closest(".stage").dataset.stage);
  if (PRESENTING) return deckJumpToStage(stage);
  switchTab(head.closest(".stage").querySelector(".tab").dataset.tab);
}));
$("mode-toggle").addEventListener("click", () => (PRESENTING ? exitDeck() : enterDeck()));

$("lang-toggle").addEventListener("click", () => setLanguage(LANG === "zh" ? "en" : "zh"));

// ---------- tab 0: overview ----------
// Overview flow: the pages after the overview, grouped by research stage (same grouping
// as the top navigation).
const OVERVIEW_FLOW = [
  { stage: 2, modules: [["libs", "ov_mod_libs_h", "ov_mod_libs_p"], ["tools", "ov_mod_tools_h", "ov_mod_tools_p"]] },
  { stage: 3, modules: [["run", "ov_mod_run_h", "ov_mod_run_p"]] },
  { stage: 4, modules: [["dash", "ov_mod_dash_h", "ov_mod_dash_p"], ["cases", "ov_mod_cases_h", "ov_mod_cases_p"]] },
  { stage: 5, modules: [["conclusion", "ov_mod_concl_h", "ov_mod_concl_p"], ["reliability", "ov_mod_rel_h", "ov_mod_rel_p"]] },
];

function renderOverview() {
  $("ov-stats").innerHTML = [
    [t("ov_kpi_libs"), LIBS.length],
    [t("ov_kpi_tools"), TOOLS.length],
    [t("ov_kpi_scans"), MATRIX.length],
    [t("ov_kpi_alerts"), sumCandidatesAll()],
  ].map(([label, value], i) => `<div class="ov-kpi${i === 3 ? " is-key" : ""}"><div class="l">${esc(label)}</div><div class="v">${fmt(value)}</div></div>`).join("");

  $("ov-modules").innerHTML = OVERVIEW_FLOW.map((col, i) => `${i ? '<div class="ov-flow-arrow" aria-hidden="true"></div>' : ""}
    <div class="ov-flow-col">
      <div class="ov-flow-col-head"><span class="stage-tag-no">0${col.stage}</span><span>${esc(t(`stage_${col.stage}`))}</span></div>
      ${col.modules.map(([tab, title, desc]) => `<button class="ov-module" data-tab="${tab}">
        <span class="ov-module-title">${esc(t(title))}<span class="ov-module-go" aria-hidden="true">→</span></span>
        <span class="ov-module-desc">${esc(t(desc))}</span>
        <span class="sr-only">${esc(t("ov_go"))}</span>
      </button>`).join("")}
    </div>`).join("");

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
    const m = byLib[l.id] || {};
    const counts = ["FF", "CP", "CC"].map((key) => m[key]?.candidates || 0);
    return `<button class="lib-card" data-id="${esc(l.id)}">
      <span class="lib-card-head"><span class="name">${esc(l.name)}</span><span class="ver">${esc(l.version)}</span><span class="domain">${esc(DOMAIN[l.name] || "")}</span></span>
      <span class="metrics">
        <span><span>${esc(t("card_src"))}</span><b>${fmt(m.FF?.intended)}</b></span>
        <span><span>${esc(t("card_units"))}</span><b>${fmt(m.CC?.intended)}</b></span>
        <span><span>${esc(t("card_alerts"))}</span><b>${fmt(sumCandidates(l.id))}</b></span>
        <span><span>${esc(t("card_cc_time"))}</span><b>${fmt(m.CC?.wall_seconds)} s</b></span>
      </span>
      <span class="mini-stack">${counts.map((c, i) => c ? `<i style="flex:${c};background:${TOOL_COLOR[TOOLS[i]]}" title="${esc(TOOLS[i])}: ${c}"></i>` : "").join("")}</span>
    </button>`;
  }).join("");

  document.querySelectorAll(".lib-card").forEach((el) => el.addEventListener("click", () => selectLibrary(el.dataset.id)));

  // Library size: plain grouped bars on a linear axis, values printed on the bars.
  const rows = LIBS.map((l) => ({ name: l.name, sz: byLib[l.id]?.FF?.intended || 0, cc: byLib[l.id]?.CC?.intended || 0 }));
  renderLegend("lg-lib-size", [[t("s_src"), "", DS.neutral[0]], [t("s_units"), "", DS.neutral[1]]]);
  const sizeTrace = (key, label, color) => ({
    type: "bar", name: label, x: rows.map((r) => r.name), y: rows.map((r) => r[key]), marker: { color },
    text: rows.map((r) => r[key]), textposition: "outside", cliponaxis: false, textfont: { family: DS.mono, size: 10.5, color: DS.muted },
    hovertemplate: `%{x}<br>${label}: %{y}<extra></extra>`,
  });
  Plotly.newPlot("chart-lib-size", [sizeTrace("sz", t("s_src"), DS.neutral[0]), sizeTrace("cc", t("s_units"), DS.neutral[1])],
    plotLayout({ barmode: "group", bargap: 0.38, bargroupgap: 0.1, margin: { t: 22, r: 8, b: 30, l: 36 }, xaxis: CATEGORY_AXIS }), PLOT_CFG);

  const toolCell = (value, tool) => `<td class="num"><span class="tool-num" style="--c:${TOOL_COLOR[tool]}">${fmt(value)}</span></td>`;
  $("lib-table").innerHTML = `<thead><tr><th>${esc(t("col_lib"))}</th><th>${esc(t("col_version"))}</th><th>${esc(t("col_domain"))}</th><th class="num">${esc(t("col_src"))}</th><th class="num">${esc(t("col_units"))}</th><th class="num">${esc(t("col_ff_alerts"))}</th><th class="num">${esc(t("col_cp_alerts"))}</th><th class="num">${esc(t("col_cc_alerts"))}</th></tr></thead><tbody>` +
    LIBS.map((l) => `<tr class="clickable" data-id="${esc(l.id)}"><td><b>${esc(l.name)}</b></td><td class="mono">${esc(l.version)}</td><td><span class="tag">${esc(DOMAIN[l.name] || "")}</span></td>
      <td class="num">${fmt(byLib[l.id]?.FF?.intended)}</td><td class="num">${fmt(byLib[l.id]?.CC?.intended)}</td>
      ${toolCell(byLib[l.id]?.FF?.candidates, "Flawfinder")}${toolCell(byLib[l.id]?.CP?.candidates, "Cppcheck")}${toolCell(byLib[l.id]?.CC?.candidates, "CodeChecker/clangsa")}</tr>`).join("") + "</tbody>";

  document.querySelectorAll("#lib-table tr.clickable").forEach((row) => row.addEventListener("click", () => selectLibrary(row.dataset.id)));

  setupLibPie(byLib);
  renderOverview();
}

// ---------- library pie chart ----------

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
// Click on a library card or table row: show it in the detail panel. On wide screens the
// panel is sticky beside the cards, so only scroll when it is out of view (table clicks).
function selectLibrary(id) {
  LIB_PIE_LIB = id;
  $("pie-lib").value = id;
  renderLibPie();
  const section = $("lib-pie-section");
  const rect = section.getBoundingClientRect();
  if (rect.top < 0 || rect.top > window.innerHeight * 0.6) {
    window.scrollTo({ top: rect.top + window.scrollY - stickyTop() - 16, behavior: "smooth" });
  }
}

function markSelectedLibrary() {
  document.querySelectorAll(".lib-card, #lib-table tr.clickable").forEach((el) => el.classList.toggle("selected", el.dataset.id === LIB_PIE_LIB));
}

async function renderLibPie() {
  if (!LIB_PIE_LIB) return;
  markSelectedLibrary();
  const detail = await api(`/api/library-detail/${encodeURIComponent(LIB_PIE_LIB)}`);
  const lib = LIBS.find((l) => l.id === LIB_PIE_LIB);

  let labels, values, colors;
  if (LIB_PIE_VIEW === "tool") {
    labels = TOOLS;
    values = TOOLS.map((tool) => detail.verdict[tool].false_positive + detail.verdict[tool].supported + detail.verdict[tool].undetermined);
    colors = TOOLS.map((tool) => TOOL_COLOR[tool]);
  } else {
    labels = OUTCOMES.map(outcomeText);
    values = OUTCOMES.map((outcome) => TOOLS.reduce((sum, tool) => sum + detail.verdict[tool][outcome], 0));
    colors = OUTCOMES.map((outcome) => DS.outcome[outcome]);
  }
  const total = values.reduce((a, b) => a + b, 0);

  if (!total) {
    $("lib-pie-side").innerHTML = `<div class="empty">${esc(t("lib_pie_no_data"))}</div>`;
    Plotly.newPlot("chart-lib-pie", [], plotLayout(), PLOT_CFG);
    return;
  }

  // Donut with the total in the middle; the breakdown sits beside it.
  Plotly.newPlot("chart-lib-pie", [{
    type: "pie", hole: 0.64, labels, values, sort: false, direction: "clockwise", textinfo: "none",
    marker: { colors, line: { color: "#fff", width: 2 } },
    hovertemplate: `%{label}<br>%{value} (%{percent})<extra></extra>`,
  }], plotLayout({
    margin: { t: 6, r: 6, b: 6, l: 6 },
    annotations: [
      { text: `<b>${fmt(total)}</b>`, x: 0.5, y: 0.55, xref: "paper", yref: "paper", showarrow: false, font: { family: DS.mono, size: 30, color: DS.ink } },
      { text: esc(t("lib_pie_total")), x: 0.5, y: 0.38, xref: "paper", yref: "paper", showarrow: false, font: { family: DS.sans, size: 12, color: DS.muted } },
    ],
  }), PLOT_CFG);

  $("lib-pie-side").innerHTML = `<div class="lib-pie-title">${esc(lib?.name || "")} <span>${esc(lib?.version || "")}</span></div>` +
    labels.map((label, index) => `<div class="lib-pie-row">
      <span class="dot" style="background:${colors[index]}"></span>
      <span class="name">${esc(label)}</span>
      <span class="val">${fmt(values[index])}</span>
      <span class="pct">${(100 * values[index] / total).toFixed(1)}%</span>
      <span class="lib-pie-bar"><i style="width:${100 * values[index] / total}%;background:${colors[index]}"></i></span>
    </div>`).join("");
}

function sumCandidates(id) {
  return MATRIX.filter((m) => m.project_id === id).reduce((a, m) => a + (m.candidates || 0), 0);
}

function toolDescriptions() {
  return LANG === "zh" ? [
    { n: "Flawfinder", t: "查名字", how: "逐行扫描，看到 memcpy、strcpy、strlen 这类危险函数名就报警。", good: "速度快，能列出所有危险调用。", bad: "分不清函数名和变量名，不知道代码是否真的会执行。", v: "2.0.20" },
    { n: "Cppcheck", t: "推算取值", how: "跟踪变量在赋值和分支中可能取的值，判断是否会出错。", good: "理解整数和指针的取值，代码质量类问题覆盖广。", bad: "需要编译数据库，部分检查依赖真实头文件。", v: "2.13.0" },
    { n: "CodeChecker / clangsa", t: "模拟执行路径", how: "把输入当作未知数，沿每条分支模拟执行，看错误路径能否走到。", good: "空指针、死存储等与路径相关的问题最准确。", bad: "最慢，看不到写在文档里的约定（如函数永不返回）。", v: "6.29.1 · Clang 18.1.3" },
  ] : [
    { n: "Flawfinder", t: "Name matching", how: "Scans line by line and reports calls to risky names such as memcpy, strcpy, and strlen.", good: "Fast and lists every risky call.", bad: "Cannot distinguish names from variables or determine whether the code executes.", v: "2.0.20" },
    { n: "Cppcheck", t: "Value inference", how: "Tracks possible values through assignments and branches to determine whether errors can occur.", good: "Understands integer and pointer values and covers many code-quality problems.", bad: "Needs a compilation database, and some checks require real headers.", v: "2.13.0" },
    { n: "CodeChecker / clangsa", t: "Path simulation", how: "Treats inputs as unknown and simulates each branch to see whether an error path is reachable.", good: "Most accurate for path-related issues such as null pointers and dead stores.", bad: "Slowest, and cannot infer conventions documented in prose, such as a function never returning.", v: "6.29.1 · Clang 18.1.3" },
  ];
}

// ---------- tab 2: live run ----------
let CURRENT_SOURCE = null;
let RUN_ACTIVE = false;

function setupRun() {
  $("run-lib").innerHTML = LIBS.map((l) => `<option value="${esc(l.id)}">${esc(l.id)} · ${esc(l.name)} ${esc(l.version)}</option>`).join("");
  const descriptions = toolDescriptions();
  const L = LANG === "zh"
    ? { how: "工作方式", good: "擅长", bad: "短板" }
    : { how: "How it works", good: "Strengths", bad: "Limitations" };
  // The depth meter mirrors the page's point: the three tools differ in how deeply they read code.
  $("tool-compare").innerHTML = descriptions.map((tool, i) => `<section class="box tool-box" style="--tool:${TOOL_COLOR[TOOLS[i]]}">
      <header class="tool-box-head"><span class="tool-dot"></span><b>${esc(tool.n)}</b><code>${esc(tool.v)}</code></header>
      <div class="tool-method"><span>${esc(tool.t)}</span><span class="depth" title="${i + 1} / 3">${[0, 1, 2].map((k) => `<i class="${k <= i ? "on" : ""}"></i>`).join("")}</span></div>
      <dl class="tool-facts">
        <dt>${esc(L.how)}</dt><dd>${esc(tool.how)}</dd>
        <dt>${esc(L.good)}</dt><dd>${esc(tool.good)}</dd>
        <dt>${esc(L.bad)}</dt><dd>${esc(tool.bad)}</dd>
      </dl>
    </section>`).join("");

  renderToolRules();
  renderWorkflow();
  if (!$("run-replay").dataset.bound) {
    $("run-replay").addEventListener("click", replayRun);
    $("run-replay").dataset.bound = "true";
  }
  if (STATIC) {
    // Live runs need the server deployment (Docker); the static site only shows the data.
    $("run-start").disabled = true;
    $("run-status").dataset.i18n = "run_static";
    setStatus(t("run_static"), "info");
  } else if (!$("run-start").dataset.bound) {
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

let RULE_TOOL = 0;

// One tool at a time, full width, so the rule tables have room to breathe.
function renderToolRules() {
  const rules = TOOL_RULES[LANG] || TOOL_RULES.zh;
  $("tool-rules-tabs").innerHTML = rules.map((tool, i) => `<button class="seg-btn ${i === RULE_TOOL ? "active" : ""}" data-i="${i}" role="tab" aria-selected="${i === RULE_TOOL}"><i class="tool-dot" style="background:${TOOL_COLOR[TOOLS[i]]}"></i>${esc(tool.n)}</button>`).join("");
  document.querySelectorAll("#tool-rules-tabs .seg-btn").forEach((button) => button.addEventListener("click", () => {
    RULE_TOOL = Number(button.dataset.i);
    renderToolRules();
  }));

  const tool = rules[RULE_TOOL];
  const max = Math.max(...tool.dimensions.map((d) => d[3]));
  $("tool-rules").innerHTML = `<div class="rule-panel" style="--tool:${TOOL_COLOR[TOOLS[RULE_TOOL]]}">
    <div class="rule-main">
      <div class="rule-basis"><span class="tool-dot"></span>${esc(tool.basis)}</div>
      <p class="rule-detail">${esc(tool.basisDetail)}</p>
      <div class="rule-label">${esc(tool.dimensionLabel)}</div>
      <div class="rule-dimension">${esc(tool.dimension)}</div>
      <table class="data rule-table">
        <thead><tr><th>${esc(t("rule_dim_level"))}</th><th>${esc(t("rule_dim_check"))}</th><th>${esc(t("rule_dim_desc"))}</th><th class="num">${esc(t("rule_dim_count"))}</th></tr></thead>
        <tbody>${tool.dimensions.map(([level, check, desc, count]) => `<tr>
          <td><code>${esc(level)}</code></td><td><code>${esc(check)}</code></td><td>${esc(desc)}</td>
          <td class="num bar-cell"><span class="bar" style="width:${(100 * count / max).toFixed(1)}%"></span><b>${fmt(count)}</b></td>
        </tr>`).join("")}</tbody>
      </table>
      <p class="rule-note">${esc(tool.dimensionNote)}</p>
    </div>
    <aside class="rule-side">
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
      <div class="rule-foot"><span>${esc(t("rule_version"))}</span><code>${esc(tool.version)}</code></div>
    </aside>
  </div>`;
}

function renderWorkflow() {
  const steps = I18N[LANG].flow_steps;
  $("workflow").innerHTML = steps.map(([id, title, detail]) => `<div class="pipe-step">
      <div class="pipe-head"><span class="pipe-id">${esc(id)}</span><strong>${esc(title)}</strong></div>
      <p>${esc(detail)}</p>
    </div>`).join('<div class="pipe-arrow" aria-hidden="true"></div>');
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

// ---------- replay of a recorded replication run ----------
// Plays back the saved output of one replication run (logs, command, tool output, S6
// comparison) stage by stage. Nothing is executed; the page says so while it plays.
async function replayRun() {
  if (RUN_ACTIVE) return;
  let data;
  try {
    data = await api(`/api/replay/${encodeURIComponent($("run-lib").value)}/${encodeURIComponent($("run-tool").value)}`);
  } catch (err) {
    setStatus(t("load_failed"), "fail");
    return;
  }
  RUN_ACTIVE = true;
  $("run-replay").disabled = true;
  const startWasDisabled = $("run-start").disabled;
  $("run-start").disabled = true;
  const log = $("run-log");
  log.textContent = "";
  $("run-bar").style.width = "0%";
  $("run-result").innerHTML = `<div class="empty">${esc(t("running"))}</div>`;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const write = (line) => { log.textContent += line + "\n"; log.scrollTop = log.scrollHeight; };
  const steps = [...document.querySelectorAll("#workflow .pipe-step")];

  write(`# ${text("replay_note", { date: (data.recorded_utc || "").replace("T", " ").replace("Z", " UTC") })}`);
  write(`# ${data.name} ${data.version} · ${data.tool_name} · ${data.run_id}`);
  for (const [index, stage] of data.stages.entries()) {
    steps.forEach((el, k) => { el.classList.toggle("is-active", k === index); el.classList.toggle("is-done", k < index); });
    const title = (I18N[LANG].flow_steps[index] || [])[1] || stage.id;
    setStatus(`${t("replay_running")} · ${stage.id} ${title}`, "running");
    write(`\n== ${stage.id} ${title} ==`);
    for (const line of stage.lines) {
      write(line);
      await sleep(stage.id === "S5" ? 40 : 70);
    }
    $("run-bar").style.width = `${Math.round(100 * (index + 1) / data.stages.length)}%`;
    await sleep(320);
  }
  steps.forEach((el) => { el.classList.remove("is-active"); el.classList.add("is-done"); });
  setStatus(t("replay_done"), "ok");
  renderResult({ ...data.result, replay: true });
  RUN_ACTIVE = false;
  $("run-replay").disabled = false;
  $("run-start").disabled = startWasDisabled;
}

function setStatus(value, cls) {
  const el = $("run-status");
  el.textContent = value;
  el.className = "status " + (cls || "");
}

function renderResult(result) {
  const same = result.matches_reference;
  const verdictLine = (same
    ? `<span class="badge b-ok">${esc(t("match"))}</span>`
    : `<span class="badge b-und">${esc(t("mismatch"))}</span>`) +
    (result.replay ? ` <span class="badge b-fp">${esc(t("replay_badge"))}</span>` : "");
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



// Overview figure: one horizontal stacked bar per tool, so the share of false positives
// in each tool's output is readable at a glance. Totals and supported counts are labelled
// at the bar ends instead of relying on hover.
function drawOverviewChart(v) {
  const outs = ["supported", "undetermined", "false_positive"];
  const tools = [...TOOLS].reverse();
  const total = (tool) => outs.reduce((a, o) => a + v[tool][o], 0);
  const maxTotal = Math.max(...TOOLS.map(total));

  $("ov-legend").innerHTML = outs.map((o) => `<span class="ov-legend-item"><i class="sw sw-${o}"></i>${esc(outcomeText(o))}</span>`).join("");

  const traces = outs.map((o) => ({
    type: "bar", orientation: "h", name: outcomeText(o),
    y: tools.map(toolShort), x: tools.map((tool) => v[tool][o]),
    marker: o === "undetermined"
      ? { color: DS.panel, line: { color: DS.outcome[o], width: 1 }, pattern: { shape: "/", fgcolor: DS.outcome[o], size: 5, solidity: 0.35 } }
      : { color: DS.outcome[o], line: { width: 0 } },
    hovertemplate: `%{y} · ${outcomeText(o)}: %{x}<extra></extra>`,
  }));

  const annotations = tools.flatMap((tool) => {
    const n = total(tool), sup = v[tool].supported;
    const pct = n ? (100 * sup / n).toFixed(1) : "0.0";
    return [{
      x: n, y: toolShort(tool), xanchor: "left", xshift: 10, yshift: 7, showarrow: false,
      text: `<b>${fmt(n)}</b>`, font: { family: DS.mono, size: 16, color: DS.ink },
    }, {
      x: n, y: toolShort(tool), xanchor: "left", xshift: 10, yshift: -12, showarrow: false,
      text: `${esc(outcomeText("supported"))} ${sup} · ${pct}%`, font: { family: DS.mono, size: 11, color: DS.outcome.supported },
    }];
  });

  Plotly.newPlot("chart-overview", traces, {
    barmode: "stack", bargap: 0.48, showlegend: false, annotations,
    margin: { t: 6, r: 120, b: 30, l: 112 },
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: DS.sans, size: 12, color: DS.muted },
    xaxis: { range: [0, maxTotal * 1.02], showgrid: true, gridcolor: DS.line, zeroline: false, tickfont: { family: DS.mono, size: 10, color: DS.faint }, fixedrange: true },
    yaxis: { showgrid: false, ticks: "", tickfont: { family: DS.sans, size: 13, color: DS.ink }, ticksuffix: "   ", fixedrange: true },
    hoverlabel: { bgcolor: DS.ink, bordercolor: DS.ink, font: { family: DS.sans, color: "#fff", size: 12 } },
  }, PLOT_CFG);
}

async function loadDashboard() {
  DASH = await api("/api/dashboard");
  const v = DASH.verdict;
  const totals = Object.fromEntries(OUTCOMES.map((o) => [o, TOOLS.reduce((a, tool) => a + v[tool][o], 0)]));
  const percent = (value) => `${LANG === "zh" ? "占 " : ""}${(100 * value / DASH.total).toFixed(1)}%`;
  $("kpis").innerHTML = [
    ["k_total", DASH.total, t("k_sub_all"), ""],
    ["k_fp", totals.false_positive, percent(totals.false_positive), "false_positive"],
    ["k_sup", totals.supported, percent(totals.supported), "supported"],
    ["k_und", totals.undetermined, percent(totals.undetermined), "undetermined"],
  ].map(([key, value, sub, o]) => `<div class="stat${o ? ` stat-${o}` : ""}">
    <div class="l">${o ? `<i class="sw sw-${o}"></i>` : ""}${esc(t(key))}</div>
    <div class="v">${fmt(value)}</div><div class="s">${esc(sub)}</div></div>`).join("");
  // One bar for the whole study: how the 725 alerts split across verdicts.
  $("dash-share").innerHTML = OUTCOMES.map((o) => `<i class="share-${o}" style="flex:${totals[o]}" title="${esc(outcomeText(o))}: ${totals[o]}"></i>`).join("");

  drawOverviewChart(v);

  // Verdict mix per tool, normalised to 100% so the three tools compare directly.
  const tools = [...TOOLS].reverse();
  outcomeLegend("lg-verdict");
  Plotly.newPlot("chart-verdict", OUTCOMES.map((o) => ({
    type: "bar", orientation: "h", name: outcomeText(o), y: tools.map(toolShort),
    x: tools.map((tool) => 100 * v[tool][o] / OUTCOMES.reduce((a, k) => a + v[tool][k], 0)),
    customdata: tools.map((tool) => v[tool][o]), marker: outcomeMarker(o),
    texttemplate: "%{x:.1f}%", textposition: "inside", insidetextanchor: "middle", textangle: 0,
    textfont: { family: DS.mono, size: 11, color: o === "supported" ? "#fff" : DS.ink },
    hovertemplate: `%{y} · ${outcomeText(o)}: %{customdata} (%{x:.1f}%)<extra></extra>`,
  })), plotLayout({
    barmode: "stack", bargap: 0.42, uniformtext: { mode: "hide", minsize: 10 },
    margin: { t: 8, r: 16, b: 30, l: 10 }, xaxis: { range: [0, 100], ticksuffix: "%" }, yaxis: CATEGORY_AXIS,
  }), PLOT_CFG);

  // Alerts per library, largest first, with the total printed at the end of each bar.
  const projects = Object.keys(DASH.by_project);
  const projectTotal = (p) => OUTCOMES.reduce((a, o) => a + DASH.by_project[p][o], 0);
  projects.sort((a, b) => projectTotal(a) - projectTotal(b));
  outcomeLegend("lg-project");
  Plotly.newPlot("chart-project", OUTCOMES.map((o) => ({
    type: "bar", orientation: "h", name: outcomeText(o), y: projects, x: projects.map((p) => DASH.by_project[p][o]),
    marker: outcomeMarker(o), hovertemplate: `%{y} · ${outcomeText(o)}: %{x}<extra></extra>`,
  })), plotLayout({
    barmode: "stack", bargap: 0.32, margin: { t: 8, r: 40, b: 30, l: 10 }, yaxis: CATEGORY_AXIS,
    annotations: projects.map((p) => ({ x: projectTotal(p), y: p, text: fmt(projectTotal(p)), xanchor: "left", xshift: 6, showarrow: false, font: { family: DS.mono, size: 11, color: DS.ink } })),
  }), PLOT_CFG);

  // Runtime per library: one dot per tool on a log axis, joined by a range line.
  const runs = DASH.matrix.filter((row) => row.wall_seconds > 0);
  const libs = [...new Set(DASH.matrix.map((row) => row.project))];
  const ranges = libs.flatMap((lib) => {
    const secs = runs.filter((row) => row.project === lib).map((row) => row.wall_seconds);
    return secs.length ? [[Math.min(...secs), Math.max(...secs), lib]] : [];
  });
  toolLegend("lg-cost");
  Plotly.newPlot("chart-cost", [{
    type: "scatter", mode: "lines", hoverinfo: "skip", line: { color: DS.line, width: 3 },
    x: ranges.flatMap(([lo, hi]) => [lo, hi, null]), y: ranges.flatMap(([, , lib]) => [lib, lib, null]),
  }, ...TOOLS.map((tool, index) => {
    const rows = runs.filter((row) => row.tool_key === ["FF", "CP", "CC"][index]);
    return {
      type: "scatter", mode: "markers", name: tool, x: rows.map((row) => row.wall_seconds), y: rows.map((row) => row.project),
      marker: { color: TOOL_COLOR[tool], size: 11, line: { color: "#fff", width: 1.5 } },
      hovertemplate: `%{y} · ${toolShort(tool)}: %{x:.2f} s<extra></extra>`,
    };
  })], plotLayout({
    margin: { t: 8, r: 16, b: 30, l: 10 },
    xaxis: { type: "log", tickvals: [0.01, 0.1, 1, 10, 100], ticktext: ["0.01 s", "0.1 s", "1 s", "10 s", "100 s"] },
    yaxis: { ...CATEGORY_AXIS, categoryorder: "array", categoryarray: [...libs].reverse() },
  }), PLOT_CFG);

  // Top rules coloured by the tool that raised them; full rule names on the axis.
  const top = [...DASH.top_rules].reverse();
  toolLegend("lg-rules");
  Plotly.newPlot("chart-rules", [{
    type: "bar", orientation: "h", x: top.map((rule) => rule.count), y: top.map((_, i) => i),
    customdata: top.map((rule) => `${rule.rule} · ${toolShort(rule.tool)}`),
    marker: { color: top.map((rule) => TOOL_COLOR[rule.tool]) },
    text: top.map((rule) => rule.count), textposition: "outside", cliponaxis: false, textfont: { family: DS.mono, size: 10.5, color: DS.muted },
    hovertemplate: `%{customdata}<br>%{x}<extra></extra>`,
  }], plotLayout({
    bargap: 0.28, margin: { t: 8, r: 34, b: 30, l: 10 },
    yaxis: { showgrid: false, linecolor: "rgba(0,0,0,0)", tickvals: top.map((_, i) => i), ticktext: top.map((rule) => rule.rule), tickfont: { family: DS.mono, size: 11, color: DS.ink }, ticksuffix: "  " },
  }), PLOT_CFG);

  $("f-project").innerHTML = `<option value="">${esc(t("all_libs"))}</option>` + LIBS.map((l) => `<option value="${esc(l.id)}">${esc(l.name)}</option>`).join("");
  if (!$("f-project").dataset.bound) {
    ["f-project", "f-tool", "f-outcome"].forEach((id) => $(id).addEventListener("change", loadCandidates));
    $("f-project").dataset.bound = "true";
  }
  loadCandidates();
}

let CAND_PAGE = 0;
const CAND_PAGE_SIZE = 15;

async function loadCandidates() {
  const params = new URLSearchParams();
  if ($("f-project").value) params.set("project", $("f-project").value);
  if ($("f-tool").value) params.set("tool", $("f-tool").value);
  if ($("f-outcome").value) params.set("outcome", $("f-outcome").value);
  const data = await api("/api/candidates?" + params.toString() + "&limit=1000");
  CANDIDATES = data.items;
  CAND_PAGE = 0;
  $("f-count").textContent = `${LANG === "zh" ? "共" : "Total"} ${fmt(data.total)} ${t("alert_count_unit")}`;
  renderCandidates();
}

// The list is paged so the dashboard stays one screen of charts plus a short table.
function renderCandidates() {
  const pages = Math.max(1, Math.ceil(CANDIDATES.length / CAND_PAGE_SIZE));
  CAND_PAGE = Math.min(Math.max(CAND_PAGE, 0), pages - 1);
  const rows = CANDIDATES.slice(CAND_PAGE * CAND_PAGE_SIZE, (CAND_PAGE + 1) * CAND_PAGE_SIZE);
  $("cand-table").innerHTML = `<thead><tr><th>${esc(t("col_lib"))}</th><th>${esc(t("col_tool_h"))}</th><th>${esc(t("col_location"))}</th><th>${esc(t("col_rule_h"))}</th><th>${esc(t("col_verdict"))}</th></tr></thead><tbody>` +
    rows.map((candidate) => `<tr class="clickable" data-key="${esc(candidate.key)}">
      <td>${esc(candidate.project)} <span class="muted mono">${esc(candidate.version)}</span></td>
      <td><span class="badge ${TOOL_CLASS[candidate.tool] || ""}">${esc(toolShort(candidate.tool))}</span></td>
      <td class="mono">${esc(shortPath(candidate.file))}:${fmt(candidate.line)}</td>
      <td class="mono">${esc(candidate.rule)}</td>
      <td><span class="badge ${OUTCOME_CLASS[candidate.outcome] || ""}">${esc(outcomeText(candidate.outcome))}</span></td></tr>`).join("") + "</tbody>";
  document.querySelectorAll("#cand-table tr.clickable").forEach((row) => row.addEventListener("click", () => openDetail(row.dataset.key)));

  const from = CANDIDATES.length ? CAND_PAGE * CAND_PAGE_SIZE + 1 : 0;
  const to = CAND_PAGE * CAND_PAGE_SIZE + rows.length;
  $("cand-pager").innerHTML = `<span class="pager-info mono">${from}–${to} / ${fmt(CANDIDATES.length)}</span>
    <span class="pager-btns">
      <button class="ghost" data-p="0" ${CAND_PAGE === 0 ? "disabled" : ""} aria-label="first">«</button>
      <button class="ghost" data-p="${CAND_PAGE - 1}" ${CAND_PAGE === 0 ? "disabled" : ""} aria-label="previous">‹</button>
      <span class="pager-page mono">${CAND_PAGE + 1} / ${pages}</span>
      <button class="ghost" data-p="${CAND_PAGE + 1}" ${CAND_PAGE >= pages - 1 ? "disabled" : ""} aria-label="next">›</button>
      <button class="ghost" data-p="${pages - 1}" ${CAND_PAGE >= pages - 1 ? "disabled" : ""} aria-label="last">»</button>
    </span>`;
  document.querySelectorAll("#cand-pager button[data-p]").forEach((button) => button.addEventListener("click", () => {
    CAND_PAGE = Number(button.dataset.p);
    renderCandidates();
  }));
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
  renderPageNav();
  setModeLabel();
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
  if (PRESENTING) renderSlide();
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
  const navTop = Math.round(stickyTop() + 16);
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
  const bar = $("sidebar");
  if (!bar) return;
  if (CASE_RESIZE_OBSERVER) CASE_RESIZE_OBSERVER.disconnect();
  if (typeof ResizeObserver !== "undefined") {
    CASE_RESIZE_OBSERVER = new ResizeObserver(() => updateCaseNavOffset());
    CASE_RESIZE_OBSERVER.observe(bar);
  }
  window.addEventListener("resize", syncCaseStickyOffsets);
}

function renderCaseSummary() {
  const totals = SPECIAL_CASES.outcome_totals;
  $("case-summary").innerHTML = [
    ["k_total", SPECIAL_CASES.total, ""],
    ["k_fp", totals.false_positive || 0, "false_positive"],
    ["k_sup", totals.supported || 0, "supported"],
    ["k_und", totals.undetermined || 0, "undetermined"],
    ["case_family_count", SPECIAL_CASES.family_count, ""],
  ].map(([label, value, o]) => `<div class="stat${o ? ` stat-${o}` : ""}">
    <div class="l">${o ? `<i class="sw sw-${o}"></i>` : ""}${esc(t(label))}</div><div class="v">${fmt(value)}</div></div>`).join("");
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
    const [first, ...rest] = item.examples;
    // Only the first representative alert is open; the others fold away to keep the page scannable.
    const examples = (first ? renderCaseExample(first, 0) : "") + (rest.length ? `<details class="case-more">
        <summary>${esc(t("case_examples"))} +${rest.length}</summary>
        <div class="case-examples">${rest.map((example, index) => renderCaseExample(example, index + 1)).join("")}</div>
      </details>` : "");
    return `<article class="box case-family" data-outcome="${item.outcome}" id="family-${esc(item.id)}">
      <header class="case-family-head">
        <div class="case-family-meta">
          <span class="badge ${OUTCOME_CLASS[item.outcome]}">${esc(outcomeText(item.outcome))}</span>
          <span class="case-family-count mono">${fmt(item.count)} ${esc(t("alert_count_unit"))}</span>
          <span class="tag">${esc(caseRiskLabel(item.examples[0]?.risk || "other"))}</span>
        </div>
        <h3>${esc(caseFamilyTitle(item.family))}</h3>
      </header>
      <div class="case-family-body">
        <div class="case-analysis-panel">
          <div class="case-analysis-step">
            <div class="case-step-head"><span class="case-step-number">1</span><span class="case-step-title">${esc(t("case_why_reported"))}</span></div>
            <p>${esc(caseFamilyLogic(item.family))}</p>
          </div>
          <div class="case-step-arrow" aria-hidden="true"></div>
          <div class="case-analysis-step">
            <div class="case-step-head"><span class="case-step-number">2</span><span class="case-step-title">${esc(t("case_why_verdict"))}</span></div>
            <p>${esc(caseVerdictExplanation(item))}</p>
          </div>
          <div class="case-step-arrow" aria-hidden="true"></div>
          <div class="case-analysis-step case-step-evidence">
            <div class="case-step-head"><span class="case-step-number">3</span><span class="case-step-title">${esc(t("case_evidence_chain"))}</span></div>
            <p>${esc(caseEvidenceExplanation(item))}</p>
            <div class="case-step-chain">
              <span class="case-chain-node">${esc(t("case_chain_meaning"))}</span><span class="case-chain-arrow">→</span>
              <span class="case-chain-node">${esc(t("case_chain_evidence"))}</span><span class="case-chain-arrow">→</span>
              <span class="case-chain-node">${esc(t("case_chain_missing"))}</span><span class="case-chain-arrow">→</span>
              <span class="case-chain-node">${esc(t("case_chain_root"))}</span>
            </div>
          </div>
        </div>
        <div class="case-distributions">
          <div><div class="case-section-label">${esc(t("case_tool_distribution"))}</div>${toolCounts.map(([tool, count]) => `<span class="case-chip"><i class="tool-dot" style="background:${TOOL_COLOR[tool] || DS.faint}"></i>${esc(toolShort(tool))} <b>${fmt(count)}</b></span>`).join("")}</div>
          <div><div class="case-section-label">${esc(t("case_library_distribution"))}</div>${libraryCounts.map(([library, count]) => `<span class="case-chip">${esc(library)} <b>${fmt(count)}</b></span>`).join("")}</div>
          <div><div class="case-section-label">${esc(t("case_common_rules"))}</div>${item.rules.map((rule) => `<code class="case-rule">${esc(rule)}</code>`).join("")}</div>
        </div>
        <h4 class="case-examples-title"><span>${esc(t("case_examples"))}</span><small>${esc(t("case_analysis_steps"))}</small></h4>
        ${examples}
      </div>
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
    const top = target.getBoundingClientRect().top + window.scrollY - stickyTop() - 24;
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

// Long evidence paragraphs are clamped; a toggle reveals the full text.
const CLAMP_CHARS = 180;

function renderCaseExample(example, index) {
  const evidenceBlocks = [
    [t("case_security_meaning"), example.security_meaning, "meaning"],
    [t("case_source_evidence"), example.source_evidence, "evidence"],
    ...(example.missing_conditions && example.missing_conditions !== "[]" ? [[t("case_missing"), example.missing_conditions, "missing"]] : []),
    ...(example.root_cause_group ? [[t("case_root_cause"), example.root_cause_group, "root"]] : []),
    ...(example.cross_tool ? [[t("case_cross_tool"), example.cross_tool, "cross"]] : []),
  ];
  const codeBlock = example.source_code ? `<div class="code-block">
      <div class="code-head"><span class="code-dots"><i></i><i></i><i></i></span><span>${esc(t("case_code_line"))}</span><code>${esc(example.file)}:${fmt(example.line)}</code></div>
      <pre><code>${esc(example.source_code)}</code></pre>
    </div>` : `<div class="case-code-missing">${esc(t("warn_no_code"))}</div>`;
  return `<div class="case-example">
    <div class="case-example-head">
      <span class="case-example-number">${index + 1}</span>
      <div>
        <strong>${esc(example.project)} ${esc(example.version)} · <span class="mono">${esc(example.rule)}</span></strong>
        <div class="case-location mono">${esc(example.file)}:${fmt(example.line)}:${fmt(example.column)}</div>
      </div>
      <span class="badge ${TOOL_CLASS[example.tool] || ""}">${esc(toolShort(example.tool))}</span>
    </div>
    ${codeBlock}
    <div class="case-evidence">
      ${evidenceBlocks.map(([label, value, kind], blockIndex) => {
        const long = String(value).length > CLAMP_CHARS;
        return `<div class="case-evidence-item case-evidence-${kind}${long ? " is-clamped" : ""}">
          <div class="case-evidence-label"><span>${blockIndex + 1}</span>${esc(label)}</div>
          <p>${esc(value)}</p>
          ${long ? `<button class="clamp-toggle" type="button">${esc(t("case_show_detail"))}</button>` : ""}
        </div>`;
      }).join("")}
    </div>
    <div class="case-conclusion"><span class="badge ${OUTCOME_CLASS[example.outcome]}">${esc(outcomeText(example.outcome))}</span><span>${esc(caseFamilyTitle(example.family || ""))}</span></div>
  </div>`;
}

$("case-families").addEventListener("click", (event) => {
  const button = event.target.closest(".clamp-toggle");
  if (!button) return;
  const item = button.closest(".case-evidence-item");
  const open = item.classList.toggle("is-open");
  button.textContent = t(open ? "case_hide_detail" : "case_show_detail");
});

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
  const bar = (pct) => `<span class="cell-bar"><i style="width:${Math.min(100, pct)}%"></i></span>`;

  $("concl-cards").innerHTML = rows.map((row) => {
    const [tagClass, tagText] = conclVerdictTag(row);
    const spread = SUMMARY.rule_spread[row.tool];
    return `<article class="concl-card" style="--tool:${TOOL_COLOR[row.tool]}">
      <header class="concl-card-head"><span class="tool-dot"></span><h3>${esc(row.tool)}</h3><span class="concl-verdict-tag ${tagClass}">${esc(tagText)}</span></header>
      <div class="concl-score">
        <div class="concl-score-item"><div class="l">${esc(t("concl_col_volume"))}</div><div class="v">${fmt(row.total)}</div></div>
        <div class="concl-score-item is-key"><div class="l">${esc(t("concl_col_accuracy"))}</div><div class="v">${row.precision}%</div>${bar(row.precision)}</div>
        <div class="concl-score-item"><div class="l">${esc(t("concl_col_total_time"))}</div><div class="v">${fmt(row.total_wall_seconds)}<small>s</small></div></div>
      </div>
      <div class="concl-lists">
        <div class="pros"><h4>${esc(t("concl_strengths"))}</h4><ul>${conclStrengths(row, spread).map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>
        <div class="cons"><h4>${esc(t("concl_weaknesses"))}</h4><ul>${conclWeaknesses(row, spread).map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>
      </div>
    </article>`;
  }).join("");

  $("concl-table").innerHTML = `<thead><tr>
      <th>${esc(t("col_tool_h"))}</th>
      <th class="num">${esc(t("concl_col_volume"))}</th>
      <th class="num">${esc(t("concl_col_accuracy"))}</th>
      <th class="num">${esc(t("concl_col_precision"))}</th>
      <th class="num">${esc(t("concl_col_total_time"))}</th>
      <th class="num">${esc(t("concl_col_cost_per_hit"))}</th>
      <th class="num">${esc(t("concl_col_coverage"))}</th>
    </tr></thead><tbody>` +
    rows.map((row) => `<tr>
      <td><span class="tool-name" style="--c:${TOOL_COLOR[row.tool]}">${esc(toolShort(row.tool))}</span></td>
      <td class="num">${fmt(row.total)}</td>
      <td class="num bar-num is-good">${bar(row.precision)}${row.precision}%</td>
      <td class="num bar-num">${bar(row.fp_ratio)}${row.fp_ratio}%</td>
      <td class="num">${fmt(row.total_wall_seconds)} s</td>
      <td class="num">${row.cost_per_supported ? fmt(row.cost_per_supported) : "-"}</td>
      <td class="num">${fmt(SUMMARY.coverage[row.tool])} / ${fmt(SUMMARY.project_count)}</td>
    </tr>`).join("") + "</tbody>";

  // Three dimensions in one picture: volume (x), usefulness (y) and total runtime (bubble area).
  const maxSeconds = Math.max(...rows.map((r) => r.total_wall_seconds));
  const maxTotal = Math.max(...rows.map((r) => r.total));
  $("concl-chart-note").textContent = `○ = ${t("concl_col_total_time")}`;
  Plotly.newPlot("chart-concl", rows.map((row) => ({
    type: "scatter", mode: "markers+text", name: row.tool, x: [row.total], y: [row.precision],
    marker: { size: [16 + 64 * Math.sqrt(row.total_wall_seconds / maxSeconds)], color: TOOL_COLOR[row.tool], opacity: 0.88, line: { color: "#fff", width: 2 } },
    text: [`<b>${esc(toolShort(row.tool))}</b><br>${fmt(row.total)} · ${row.precision}% · ${fmt(row.total_wall_seconds)} s`],
    textposition: row.total > maxTotal * 0.6 ? "top left" : "middle right",
    textfont: { family: DS.mono, size: 11, color: DS.ink },
    hovertemplate: `${esc(row.tool)}<br>${t("concl_col_volume")}: %{x}<br>${t("concl_col_accuracy")}: %{y}%<br>${t("concl_col_total_time")}: ${row.total_wall_seconds} s<extra></extra>`,
  })), plotLayout({
    margin: { t: 16, r: 20, b: 50, l: 56 },
    xaxis: { range: [0, maxTotal * 1.18], title: { text: t("concl_col_volume"), font: { family: DS.sans, size: 12, color: DS.muted } } },
    yaxis: { range: [-4, 44], ticksuffix: "%", title: { text: t("concl_col_accuracy"), font: { family: DS.sans, size: 12, color: DS.muted } } },
  }), PLOT_CFG);

  $("concl-verdicts").innerHTML = rows.map((row) => `<article class="concl-verdict" style="--tool:${TOOL_COLOR[row.tool]}">
    <header><span class="tool-dot"></span><b>${esc(row.tool)}</b></header>
    <p>${esc(conclVerdictText(row))}</p>
    <div class="concl-libs"><span class="case-section-label">${esc(LANG === "zh" ? "找到有效问题的库" : "Libraries with useful findings")}</span>${
      SUMMARY.supported_projects[row.tool].length
        ? SUMMARY.supported_projects[row.tool].map((p) => `<span class="tag">${esc(p)}</span>`).join("")
        : `<span class="muted">${LANG === "zh" ? "无" : "none"}</span>`
    }</div>
  </article>`).join("");

  const scenarios = ["concl_sc_llm", "concl_sc_ci", "concl_sc_deep", "concl_sc_combo"];
  const scenarioTools = [["Flawfinder"], ["Cppcheck"], ["CodeChecker/clangsa"], ["Flawfinder", "Cppcheck", "CodeChecker/clangsa"]];
  $("concl-scenarios").innerHTML = scenarios.map((key, index) => `<article class="concl-scenario">
    <div class="concl-scenario-no mono">0${index + 1}</div>
    <h4>${esc(t(key))}</h4>
    <div class="concl-scenario-tools">${scenarioTools[index].map((tool) => `<span class="tool-name" style="--c:${TOOL_COLOR[tool]}">${esc(toolShort(tool))}</span>`).join(index === 3 ? '<span class="plus">+</span>' : "")}</div>
    <p>${esc(t(`${key}_d`))}</p>
  </article>`).join("");
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

const GROUP_OUTCOME = { Supported: "supported", Undetermined: "undetermined", "False positive": "false_positive" };

function renderReliability() {
  const rep = RELIABILITY.replication;
  const rev = RELIABILITY.review;

  // The two mechanisms, each linking down to its section.
  $("rel-pillars").innerHTML = [
    { n: "1", h: "rel_pillar1_h", p: "rel_pillar1_p", target: "rel-repl" },
    { n: "2", h: "rel_pillar2_h", p: "rel_pillar2_p", target: "rel-review" },
  ].map((item) => `<button class="box rel-pillar" data-target="${item.target}">
    <span class="rel-pillar-num mono">0${esc(item.n)}</span>
    <span class="rel-pillar-body"><b>${esc(t(item.h))}</b><span>${esc(t(item.p))}</span></span>
    <span class="rel-pillar-go" aria-hidden="true">↓</span>
  </button>`).join("");
  document.querySelectorAll(".rel-pillar").forEach((button) => button.addEventListener("click", () => {
    const target = $(button.dataset.target);
    window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - stickyTop() - 16, behavior: "smooth" });
  }));

  const steps = [["rel_step1", "rel_step1_d"], ["rel_step2", "rel_step2_d"], ["rel_step3", "rel_step3_d"], ["rel_step4", "rel_step4_d"]];
  $("rel-steps").innerHTML = steps.map(([h, d], index) => `<div class="pipe-step">
      <div class="pipe-head"><span class="pipe-id">${index + 1}</span><strong>${esc(t(h))}</strong></div>
      <p>${esc(t(d))}</p>
    </div>`).join('<div class="pipe-arrow" aria-hidden="true"></div>');

  const exhaustive = rev.exhaustive_groups.reduce((a, item) => a + item.sampled, 0);
  const sampled = rev.sampled_groups.reduce((a, item) => a + item.sampled, 0);
  $("rel-review-grid").innerHTML = [
    [t("rel_kpi_total"), fmt(rev.total_alerts)],
    [t("rel_kpi_exhaustive"), fmt(exhaustive)],
    [t("rel_kpi_sampled"), fmt(sampled)],
    [t("rel_kpi_runs"), fmt(rep.runs_compared)],
    [t("rel_kpi_identical"), `${fmt(rep.alert_groups_identical)}<small> / ${fmt(rep.runs_compared)}</small>`],
  ].map(([label, value], i) => `<div class="stat${i === 4 ? " stat-ok" : ""}"><div class="l">${esc(label)}</div><div class="v">${value}</div></div>`).join("");

  $("rel-pinned-table").innerHTML = `<thead><tr>
      <th>${esc(t("rel_col_lib"))}</th><th>${esc(t("rel_col_version"))}</th>
      <th>${esc(t("rel_col_commit"))}</th><th>${esc(t("rel_col_hash"))}</th>
    </tr></thead><tbody>` +
    rep.pinned_libraries.map((lib) => `<tr>
      <td><b>${esc(lib.name)}</b></td>
      <td class="mono">${esc(lib.version)}</td>
      <td><code class="rel-hash">${esc(String(lib.commit).slice(0, 12))}</code></td>
      <td>${lib.has_hash
        ? `<span class="badge b-ok">${esc(t("rel_hash_yes"))}</span> <code class="rel-hash">${esc(String(lib.sha256).slice(0, 16))}…</code>`
        : `<span class="badge b-und">${esc(t("rel_hash_no"))}</span>`}</td>
    </tr>`).join("") + "</tbody>";

  // How much of each verdict group was reviewed by hand.
  $("rel-groups").innerHTML = [...rev.exhaustive_groups, ...rev.sampled_groups].map((group) => {
    const o = GROUP_OUTCOME[group.group] || "false_positive";
    const pct = group.population ? 100 * group.sampled / group.population : 0;
    return `<div class="rel-group">
      <div class="rel-group-head"><span><i class="sw sw-${o}"></i>${esc(outcomeText(o))}</span><span class="mono">${fmt(group.sampled)} / ${fmt(group.population)} · ${pct.toFixed(0)}%</span></div>
      <div class="rel-group-bar"><i class="fill-${o}" style="width:${pct}%"></i></div>
    </div>`;
  }).join("");

  // One row per stratum (the sampling plan), grouped by verdict.
  let lastGroup = "";
  $("rel-strata-table").innerHTML = `<thead><tr>
      <th>${esc(t("rel_col_stratum"))}</th><th>${esc(t("rel_col_population"))}</th>
      <th class="num">${esc(t("rel_col_pop_size"))}</th><th class="num">${esc(t("rel_col_sampled"))}</th>
      <th class="num">${esc(t("rel_col_rate"))}</th>
    </tr></thead><tbody>` +
    rev.strata.map((item) => {
      const o = GROUP_OUTCOME[item.group] || "false_positive";
      const first = item.group !== lastGroup;
      lastGroup = item.group;
      const name = String(item.stratum).split(" | ").slice(1).join(" · ") || item.stratum;
      return `<tr class="${first ? "group-start" : ""}">
        <td>${first ? `<span class="badge ${OUTCOME_CLASS[o]}">${esc(outcomeText(o))}</span>` : ""}</td>
        <td class="mono small">${esc(name)}</td>
        <td class="num">${fmt(item.population_size)}</td>
        <td class="num">${fmt(item.sampled)}</td>
        <td class="num">${esc(item.rate)}</td>
      </tr>`;
    }).join("") + "</tbody>" +
    `<tfoot><tr><td colspan="2"><b>${esc(LANG === "zh" ? "合计" : "Total")}</b></td>
      <td class="num"><b>${fmt(rev.population)}</b></td>
      <td class="num"><b>${fmt(rev.sample_size)}</b></td>
      <td class="num"><b>${rev.population ? ((100 * rev.sample_size / rev.population).toFixed(1)) : "0"}%</b></td>
    </tr></tfoot>`;
}

// ---------- presentation mode ----------
// One idea per screen for the talk. Slide titles state the finding; every number is
// computed from the same data the explore pages use. The order differs from the page
// order on purpose: core finding first, credibility before the recommendations.
let PRESENTING = false;
let SLIDE = 0;

const DECK_TEXT = {
  zh: {
    finding: "核心发现",
    scope: (n) => `${n.libs} 个库 × ${n.tools} 款工具 = ${n.scans} 次扫描，${fmt(n.alerts)} 条告警逐条核查`,
    libs: (n, d) => `${n} 个固定版本的开源 C 库，覆盖 ${d} 个领域`,
    tools: "三款工具读代码的深度不同",
    process: "从固定源码到逐条核查：S1–S6 每一步都可核对",
    verdict: (r) => `${r.tool} 的 ${fmt(r.total)} 条告警中，只有 ${r.supported} 条成立（${r.precision}%）`,
    cost: (best, worst) => `${toolShort(best.tool)} 每看 ${fmt(best.cost_per_supported)} 条告警就能找到 1 条真问题，${toolShort(worst.tool)} 要看 ${fmt(worst.cost_per_supported)} 条`,
    cases: (name, n) => `最常见的误报原因：${name}（${fmt(n)} 条）`,
    trust: (same, runs, sample) => `${same} / ${runs} 组复现运行与原实验完全一致，${fmt(sample)} 条告警进入人工复核`,
    verdicts: (rows) => rows.map((r) => `${toolShort(r.tool)} ${conclVerdictTag(r)[1]}`).join(" · "),
    rate: "有效率", supportedOf: (s, n) => `${s} / ${fmt(n)} 条成立`, costUnit: "条告警 / 1 条真问题",
    families: "案例族（按告警数）",
  },
  en: {
    finding: "Core finding",
    scope: (n) => `${n.libs} libraries × ${n.tools} tools = ${n.scans} scans; all ${fmt(n.alerts)} alerts checked one by one`,
    libs: (n, d) => `${n} open-source C libraries at fixed versions, across ${d} domains`,
    tools: "The three tools read code at different depths",
    process: "From pinned source to reviewed alerts: every step S1–S6 can be checked",
    verdict: (r) => `Only ${r.supported} of ${r.tool}'s ${fmt(r.total)} alerts hold up (${r.precision}%)`,
    cost: (best, worst) => `${toolShort(best.tool)} yields 1 real finding per ${fmt(best.cost_per_supported)} alerts; ${toolShort(worst.tool)} needs ${fmt(worst.cost_per_supported)}`,
    cases: (name, n) => `Most common false-positive cause: ${name.charAt(0).toLowerCase() + name.slice(1)} (${fmt(n)} alerts)`,
    trust: (same, runs, sample) => `${same} / ${runs} replication runs match the original exactly; ${fmt(sample)} alerts go to human review`,
    verdicts: (rows) => rows.map((r) => `${toolShort(r.tool)}: ${conclVerdictTag(r)[1].toLowerCase()}`).join(" · "),
    rate: "Usefulness", supportedOf: (s, n) => `${s} of ${fmt(n)} hold up`, costUnit: "alerts per real finding",
    families: "Case families (by alerts)",
  },
};
const D = () => DECK_TEXT[LANG] || DECK_TEXT.zh;

// Larger type for the projector.
function deckLayout(extra = {}) {
  const base = plotLayout(extra);
  base.font = { ...base.font, size: 15 };
  ["xaxis", "yaxis"].forEach((axis) => {
    base[axis].tickfont = { ...base[axis].tickfont, size: Math.max(13, (base[axis].tickfont || {}).size || 0) };
  });
  return base;
}

const deckBox = (label, inner, legend = "") => `<section class="box s-box">
  <header class="box-head"><span class="box-label">${label}</span>${legend ? `<span class="chart-legend">${legend}</span>` : ""}</header>
  <div class="s-box-body">${inner}</div></section>`;
const legendHtml = (items) => items.map(([label, cls, color]) => `<span class="lg"><i class="sw ${cls || ""}"${color ? ` style="background:${color}"` : ""}></i>${esc(label)}</span>`).join("");
const outcomeLegendHtml = () => legendHtml(OUTCOMES.map((o) => [outcomeText(o), `sw-${o}`]));
const byPrecision = () => [...SUMMARY.tools].sort((a, b) => b.precision - a.precision);

function deckSlides() {
  const rows = SUMMARY.tools;
  const v = DASH.verdict;
  const rep = RELIABILITY.replication;
  const rev = RELIABILITY.review;
  const domains = new Set(LIBS.map((l) => DOMAIN[l.name]).filter(Boolean)).size;
  const worst = [...rows].sort((a, b) => a.precision - b.precision)[0];
  const cheap = [...rows].sort((a, b) => a.cost_per_supported - b.cost_per_supported)[0];
  const dear = [...rows].sort((a, b) => b.cost_per_supported - a.cost_per_supported)[0];
  const topFalse = [...SPECIAL_CASES.cases].filter((c) => c.outcome === "false_positive").sort((a, b) => b.count - a.count)[0];

  const rateCallouts = byPrecision().map((r) => `<div class="s-callout" style="--tool:${TOOL_COLOR[r.tool]}">
      <div class="s-callout-head"><span class="tool-dot"></span>${esc(toolShort(r.tool))}</div>
      <div class="s-callout-v">${r.precision}<small>%</small></div>
      <div class="s-callout-s">${esc(D().supportedOf(r.supported, r.total))}</div>
    </div>`).join("");

  return [
    { stage: 1, page: "overview", kicker: "COMP5355 · Project 17", title: esc(t("title")), sub: esc(t("ov_hero_p")),
      body: () => `<div class="s-split">${deckBox(`<span class="fig-no">FIG.1</span>${esc(t("ov_hero_chart"))}`, '<div class="s-chart" id="deck-chart"></div>', outcomeLegendHtml())}
        <div class="s-callouts"><div class="s-callouts-label">${esc(D().finding)} · ${esc(D().rate)}</div>${rateCallouts}</div></div>`,
      draw: () => drawVerdictBars("deck-chart", v, false) },

    { stage: 1, page: "overview", kicker: t("tab_overview"), title: esc(D().scope({ libs: LIBS.length, tools: TOOLS.length, scans: MATRIX.length, alerts: sumCandidatesAll() })),
      body: () => `<div class="s-kpis">${[[t("ov_kpi_libs"), LIBS.length], [t("ov_kpi_tools"), TOOLS.length], [t("ov_kpi_scans"), MATRIX.length], [t("ov_kpi_alerts"), sumCandidatesAll()]]
          .map(([l, n], i) => `<div class="box s-kpi${i === 3 ? " is-key" : ""}"><div class="l">${esc(l)}</div><div class="v">${fmt(n)}</div></div>`).join("")}</div>
        <ul class="s-checks">${["ov_point1", "ov_point2", "ov_point3"].map((k) => `<li class="box"><span class="tick"></span>${esc(t(k))}</li>`).join("")}</ul>` },

    { stage: 2, page: "libs", kicker: t("tab_libs"), title: esc(D().libs(LIBS.length, domains)),
      body: () => `<div class="s-libs">${LIBS.map((l) => {
          const m = MATRIX.filter((x) => x.project_id === l.id);
          const c = (k) => m.find((x) => x.tool_key === k)?.candidates || 0;
          return `<div class="box s-lib"><div class="s-lib-head"><b>${esc(l.name)}</b><span class="mono">${esc(l.version)}</span></div>
            <span class="tag">${esc(DOMAIN[l.name] || "")}</span>
            <div class="s-lib-n"><span class="mono">${fmt(sumCandidates(l.id))}</span><small>${esc(t("card_alerts"))}</small></div>
            <span class="mini-stack">${["FF", "CP", "CC"].map((k, i) => c(k) ? `<i style="flex:${c(k)};background:${TOOL_COLOR[TOOLS[i]]}"></i>` : "").join("")}</span></div>`;
        }).join("")}</div><div class="s-legend">${legendHtml(TOOLS.map((tool) => [toolShort(tool), "", TOOL_COLOR[tool]]))}</div>` },

    { stage: 2, page: "tools", kicker: t("tab_tools"), title: esc(D().tools), sub: esc(t("tools_p")),
      body: () => `<div class="s-tools">${toolDescriptions().map((tool, i) => `<section class="box s-tool" style="--tool:${TOOL_COLOR[TOOLS[i]]}">
          <header><span class="tool-dot"></span><b>${esc(tool.n)}</b></header>
          <div class="s-tool-method"><span>${esc(tool.t)}</span><span class="depth">${[0, 1, 2].map((k) => `<i class="${k <= i ? "on" : ""}"></i>`).join("")}</span></div>
          <p>${esc(tool.how)}</p></section>`).join("")}</div>` },

    { stage: 3, page: "run", kicker: t("tab_run"), title: esc(D().process), sub: esc(t("flow_p")),
      body: () => `<div class="pipeline s-pipeline">${I18N[LANG].flow_steps.map(([id, title, detail]) => `<div class="pipe-step">
          <div class="pipe-head"><span class="pipe-id">${esc(id)}</span><strong>${esc(title)}</strong></div><p>${esc(detail)}</p></div>`).join('<div class="pipe-arrow" aria-hidden="true"></div>')}</div>
        <div><button class="primary s-action" id="deck-replay" type="button">▶ ${esc(t("deck_replay"))}</button></div>`,
      draw: () => $("deck-replay").addEventListener("click", () => { switchTab("run"); replayRun(); }) },

    { stage: 4, page: "dash", kicker: t("tab_dash"), title: esc(D().verdict(worst)),
      body: () => `<div class="s-split">${deckBox(esc(t("chart_verdict")), '<div class="s-chart" id="deck-chart"></div>', outcomeLegendHtml())}
        <div class="s-callouts"><div class="s-callouts-label">${esc(D().rate)}</div>${rateCallouts}</div></div>`,
      draw: () => drawVerdictBars("deck-chart", v, true) },

    { stage: 4, page: "conclusion", kicker: t("tab_conclusion"), title: esc(D().cost(cheap, dear)),
      body: () => `<div class="s-split">${deckBox(esc(t("concl_col_cost_per_hit")), '<div class="s-chart" id="deck-chart"></div>')}
        <div class="s-callouts"><div class="s-callouts-label">${esc(t("concl_col_total_time"))}</div>${rows.map((r) => `<div class="s-callout" style="--tool:${TOOL_COLOR[r.tool]}">
          <div class="s-callout-head"><span class="tool-dot"></span>${esc(toolShort(r.tool))}</div>
          <div class="s-callout-v">${fmt(r.total_wall_seconds)}<small>s</small></div></div>`).join("")}</div></div>`,
      draw: () => {
        const order = [...rows].sort((a, b) => a.cost_per_supported - b.cost_per_supported).reverse();
        Plotly.newPlot("deck-chart", [{
          type: "bar", orientation: "h", y: order.map((r) => toolShort(r.tool)), x: order.map((r) => r.cost_per_supported),
          marker: { color: order.map((r) => TOOL_COLOR[r.tool]) }, text: order.map((r) => `${fmt(r.cost_per_supported)} ${D().costUnit}`),
          textposition: "outside", cliponaxis: false, textfont: { family: DS.mono, size: 15, color: DS.ink },
          hovertemplate: "%{y}: %{x}<extra></extra>",
        }], deckLayout({ bargap: 0.45, margin: { t: 10, r: 220, b: 36, l: 10 }, yaxis: { ...CATEGORY_AXIS, tickfont: { family: DS.sans, size: 16, color: DS.ink } } }), PLOT_CFG);
      } },

    { stage: 4, page: "cases", kicker: t("tab_cases"), title: esc(D().cases(caseFamilyTitle(topFalse.family), topFalse.count)),
      body: () => deckBox(esc(D().families), '<div class="s-chart s-chart-tall" id="deck-chart"></div>', outcomeLegendHtml()),
      draw: () => {
        const fam = [...SPECIAL_CASES.cases].sort((a, b) => a.count - b.count);
        Plotly.newPlot("deck-chart", [{
          type: "bar", orientation: "h", y: fam.map((_, i) => i), x: fam.map((c) => c.count),
          marker: { color: fam.map((c) => c.outcome === "false_positive" ? "#c3c9d2" : DS.outcome[c.outcome]) },
          text: fam.map((c) => c.count), textposition: "outside", cliponaxis: false, textfont: { family: DS.mono, size: 12, color: DS.muted },
          customdata: fam.map((c) => caseFamilyTitle(c.family)), hovertemplate: "%{customdata}: %{x}<extra></extra>",
        }], deckLayout({ bargap: 0.25, margin: { t: 6, r: 40, b: 30, l: 10 },
          yaxis: { showgrid: false, linecolor: "rgba(0,0,0,0)", tickvals: fam.map((_, i) => i), ticktext: fam.map((c) => caseFamilyTitle(c.family)), tickfont: { family: DS.sans, size: 13, color: DS.ink }, ticksuffix: "  " } }), PLOT_CFG);
      } },

    { stage: 5, page: "reliability", kicker: t("tab_reliability"), title: esc(D().trust(rep.alert_groups_identical, rep.runs_compared, rev.sample_size)),
      body: () => `<div class="pipeline pipeline-4 s-pipeline">${[1, 2, 3, 4].map((n) => `<div class="pipe-step">
          <div class="pipe-head"><span class="pipe-id">${n}</span><strong>${esc(t(`rel_step${n}`))}</strong></div><p>${esc(t(`rel_step${n}_d`))}</p></div>`).join('<div class="pipe-arrow" aria-hidden="true"></div>')}</div>
        <div class="rel-groups s-groups">${[...rev.exhaustive_groups, ...rev.sampled_groups].map((group) => {
          const o = GROUP_OUTCOME[group.group] || "false_positive";
          const pct = group.population ? 100 * group.sampled / group.population : 0;
          return `<div class="rel-group"><div class="rel-group-head"><span><i class="sw sw-${o}"></i>${esc(outcomeText(o))}</span><span class="mono">${fmt(group.sampled)} / ${fmt(group.population)}</span></div>
            <div class="rel-group-bar"><i class="fill-${o}" style="width:${pct}%"></i></div></div>`;
        }).join("")}</div>` },

    { stage: 5, page: "conclusion", kicker: t("tab_conclusion"), title: esc(D().verdicts(byPrecision())),
      body: () => `<div class="s-tools">${byPrecision().map((r) => {
          const [tagClass, tagText] = conclVerdictTag(r);
          return `<section class="box s-tool s-verdict" style="--tool:${TOOL_COLOR[r.tool]}">
            <header><span class="tool-dot"></span><b>${esc(r.tool)}</b><span class="concl-verdict-tag ${tagClass}">${esc(tagText)}</span></header>
            <div class="s-verdict-grid">
              <div><div class="l">${esc(t("concl_col_accuracy"))}</div><div class="v is-key">${r.precision}%</div></div>
              <div><div class="l">${esc(t("concl_col_volume"))}</div><div class="v">${fmt(r.total)}</div></div>
              <div><div class="l">${esc(t("concl_col_total_time"))}</div><div class="v">${fmt(r.total_wall_seconds)}<small>s</small></div></div>
              <div><div class="l">${esc(t("concl_col_coverage"))}</div><div class="v">${fmt(SUMMARY.coverage[r.tool])}<small>/${fmt(SUMMARY.project_count)}</small></div></div>
            </div></section>`;
        }).join("")}</div>` },

    { stage: 5, page: "conclusion", kicker: t("tab_conclusion"), title: esc(t("concl_scenario_title")),
      body: () => `<div class="concl-scenarios s-scenarios">${$("concl-scenarios").innerHTML}</div>` },
  ];
}

// Verdict bars per tool: absolute counts (overview figure) or shares (dashboard view).
function drawVerdictBars(target, v, share) {
  const tools = [...TOOLS].reverse();
  const total = (tool) => OUTCOMES.reduce((a, o) => a + v[tool][o], 0);
  Plotly.newPlot(target, OUTCOMES.map((o) => ({
    type: "bar", orientation: "h", name: outcomeText(o), y: tools.map(toolShort),
    x: tools.map((tool) => share ? 100 * v[tool][o] / total(tool) : v[tool][o]), customdata: tools.map((tool) => v[tool][o]),
    marker: outcomeMarker(o), texttemplate: share ? "%{x:.1f}%" : "", textposition: "inside", insidetextanchor: "middle", textangle: 0,
    textfont: { family: DS.mono, size: 14, color: o === "supported" ? "#fff" : DS.ink },
    hovertemplate: `%{y} · ${outcomeText(o)}: %{customdata}<extra></extra>`,
  })), deckLayout({
    barmode: "stack", bargap: 0.42, uniformtext: { mode: "hide", minsize: 12 }, margin: { t: 6, r: share ? 16 : 70, b: 34, l: 10 },
    xaxis: share ? { range: [0, 100], ticksuffix: "%" } : {}, yaxis: { ...CATEGORY_AXIS, tickfont: { family: DS.sans, size: 16, color: DS.ink } },
    annotations: share ? [] : tools.map((tool) => ({ x: total(tool), y: toolShort(tool), xanchor: "left", xshift: 8, showarrow: false, text: `<b>${fmt(total(tool))}</b>`, font: { family: DS.mono, size: 16, color: DS.ink } })),
  }), PLOT_CFG);
}

function renderSlide() {
  if (!SUMMARY || !DASH || !RELIABILITY || !SPECIAL_CASES) {
    $("deck-slide").innerHTML = `<div class="empty">${esc(t("running"))}</div>`;
    return;
  }
  const slides = deckSlides();
  SLIDE = Math.min(Math.max(SLIDE, 0), slides.length - 1);
  const slide = slides[SLIDE];
  const pageTab = document.querySelector(`.tab[data-tab="${slide.page}"]`);
  $("deck-slide").innerHTML = `<article class="slide">
    <header class="slide-head"><span class="stage-tag"><span class="stage-tag-no">0${slide.stage}</span>${esc(t(`stage_${slide.stage}`))}</span><span class="slide-kicker">${esc(slide.kicker)}</span></header>
    <h2 class="slide-title">${slide.title}</h2>
    ${slide.sub ? `<p class="slide-sub">${slide.sub}</p>` : ""}
    <div class="slide-body">${slide.body()}</div>
    <button class="slide-explore" type="button" data-tab="${slide.page}">${esc(t("deck_explore"))} · ${esc(t(pageTab.dataset.i18n))} →</button>
  </article>`;
  $("deck-slide").querySelector(".slide-explore").addEventListener("click", (event) => switchTab(event.currentTarget.dataset.tab));
  setNavState(slide.page);
  $("deck-count").textContent = `${String(SLIDE + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")}`;
  $("deck-bar").style.width = `${100 * (SLIDE + 1) / slides.length}%`;
  $("deck-prev").disabled = SLIDE === 0;
  $("deck-next").disabled = SLIDE === slides.length - 1;
  if (slide.draw) requestAnimationFrame(slide.draw);
}

function deckGo(index) {
  SLIDE = index;
  renderSlide();
}

function deckJumpToStage(stage) {
  const index = deckSlides().findIndex((s) => s.stage === stage);
  if (index >= 0) deckGo(index);
}

// Returns false when no slide covers the page, so the caller opens the page itself.
function deckJumpToPage(page) {
  const index = deckSlides().findIndex((s) => s.page === page);
  if (index < 0) return false;
  deckGo(index);
  return true;
}

function deckKey(event) {
  const next = ["ArrowRight", "ArrowDown", "PageDown", " "].includes(event.key);
  const prev = ["ArrowLeft", "ArrowUp", "PageUp"].includes(event.key);
  if (next || prev) {
    event.preventDefault();
    deckGo(SLIDE + (next ? 1 : -1));
  } else if (event.key === "Escape" && !document.fullscreenElement) {
    exitDeck();
  } else if (event.key === "f" || event.key === "F") {
    toggleFullscreen();
  }
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen?.();
}

function setModeLabel() {
  $("mode-label").dataset.i18n = PRESENTING ? "mode_explore" : "mode_present";
  $("mode-label").textContent = t($("mode-label").dataset.i18n);
}

function enterDeck() {
  const page = document.querySelector(".panel.active")?.id;
  PRESENTING = true;
  document.body.classList.add("mode-present");
  $("deck").hidden = false;
  updateRail();
  setModeLabel();
  // Start from the slide for the page being viewed (or the first slide).
  SLIDE = SUMMARY && DASH && RELIABILITY && SPECIAL_CASES ? Math.max(0, deckSlides().findIndex((s) => s.page === page)) : 0;
  renderSlide();
}

function exitDeck() {
  PRESENTING = false;
  document.body.classList.remove("mode-present");
  $("deck").hidden = true;
  if (document.fullscreenElement) document.exitFullscreen();
  updateRail();
  setModeLabel();
  setNavState(document.querySelector(".panel.active")?.id || "overview");
  window.dispatchEvent(new Event("resize"));
}

$("deck-prev").addEventListener("click", () => deckGo(SLIDE - 1));
$("deck-next").addEventListener("click", () => deckGo(SLIDE + 1));
$("deck-exit").addEventListener("click", exitDeck);
$("deck-full").addEventListener("click", toggleFullscreen);

// ---------- page navigation ----------
// Pages in presentation order; the footer of each page links to its neighbours, and the
// arrow keys page through them during a talk.
const PAGE_ORDER = ["overview", "libs", "tools", "run", "dash", "cases", "conclusion", "reliability"];

function renderPageNav() {
  PAGE_ORDER.forEach((id, index) => {
    const panel = $(id);
    let nav = panel.querySelector(":scope > .page-nav");
    if (!nav) {
      nav = document.createElement("nav");
      nav.className = "page-nav";
      panel.appendChild(nav);
    }
    const link = (j, dir) => {
      if (j < 0 || j >= PAGE_ORDER.length) return "<span></span>";
      const tab = document.querySelector(`.tab[data-tab="${PAGE_ORDER[j]}"]`);
      const stage = tab.closest(".stage").dataset.stage;
      return `<button class="page-link page-${dir}" data-tab="${PAGE_ORDER[j]}">
        <span class="page-link-k">${dir === "prev" ? `← ${esc(t("page_prev"))}` : `${esc(t("page_next"))} →`}</span>
        <span class="page-link-t"><span class="stage-tag-no">0${stage}</span>${esc(t(tab.dataset.i18n))}</span>
      </button>`;
    };
    nav.innerHTML = link(index - 1, "prev") + link(index + 1, "next");
    nav.querySelectorAll(".page-link").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));
  });
}

document.addEventListener("keydown", (event) => {
  if (event.altKey || event.ctrlKey || event.metaKey) return;
  if (event.target.closest("input, select, textarea")) return;
  if (PRESENTING) return deckKey(event);
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  const current = PAGE_ORDER.indexOf(document.querySelector(".panel.active")?.id);
  const next = current + (event.key === "ArrowRight" ? 1 : -1);
  if (next >= 0 && next < PAGE_ORDER.length) switchTab(PAGE_ORDER[next]);
});

// ---------- boot ----------
(async function boot() {
  try {
    applyStaticText();
    renderPageNav();
    updateRail();
    await loadLibs();
    setupRun();
    await loadDashboard();
    await loadSpecialCases();
    await loadSummary();
    await loadReliability();
    observeCaseFilterPanel();
    syncCaseStickyOffsets();
    if (location.hash === "#present") enterDeck();
  } catch (err) {
    document.body.insertAdjacentHTML("afterbegin", `<div style="padding:12px;background:#fee;color:#900">${esc(t("load_failed"))}: ${esc(err.message)}</div>`);
  }
})();
