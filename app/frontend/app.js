/* ReefTriage frontend app.js · Dark Tech UI
 * - Leaflet map (CARTO Dark Matter default / ESRI satellite toggle)
 * - Collapsible left panel (workflow / budget / optimizer / connectivity)
 * - Right detail drawer (replaces popup): 3-score bars, CI, radar, features
 * - Resizable bottom drawer with 5 tabs (segments table / weights / compare / connectivity / ML)
 * - EN/ZH i18n
 */

// ---------- i18n ----------
const I18N = {
  en: {
    app_title: "ReefTriage",
    app_subtitle: "Semporna Reef Restoration",
    stat_segments: "Segments",
    stat_invest: "Invest",
    stat_monitor: "Monitor",
    stat_deprior: "Deprioritize",
    stat_avg: "Avg Score",
    laya_mock: "Laya: MOCK",
    laya_live: "Laya: LIVE",
    recalc: "↻ Recalc",
    legend_title: "Priority",
    legend_invest: "Invest (≥37.6)",
    legend_monitor: "Monitor (30–37.5)",
    legend_deprior: "Deprioritize (<30)",
    loading: "Scoring reef segments…",

    budget_title: "Budget Control",
    budget_label: "Restoration Budget",
    unit_cost_label: "Cost / segment",
    optimizer_title: "Optimizer Result",
    optimizer_selected: "Selected",
    optimizer_cost: "Total Cost",
    optimizer_used: "Budget Used",
    optimizer_gain: "Total Gain",

    basemap_satellite: "Satellite",
    basemap_topo: "Topo",

    detail_close: "Close",
    popup_final: "Fusion Score",
    popup_three: "Score Decomposition",
    popup_ci: "95% CI",
    popup_radar: "6-Dim Reef Profile",
    detail_features: "Features",
    popup_mcdm: "MCDM (obj.)",
    popup_laya: "Laya AI",
    popup_bleach: "Bleach prob.",
    popup_dhw: "Current DHW",
    popup_depth: "Mean depth",
    popup_dist: "To dive site",
    popup_conn: "Connectivity",
    popup_rhi: "CoralCore RHI",
    popup_area: "Reef area",
    popup_model: "Engine",

    tab_segments: "Segment List",
    tab_weights: "Feature Weights",
    tab_compare: "Model Compare",
    tab_connectivity: "Connectivity",
    tab_ml: "ML Model",

    segment_table_rank: "#",
    segment_table_name: "Name",
    segment_table_score: "Score",
    segment_table_choice: "Choice",
    segment_table_dhw: "DHW",
    segment_table_depth: "Depth",

    invest: "INVEST",
    monitor: "MONITOR",
    deprioritize: "DEPRIORITIZE",
    km_unit: "km",
    m_unit: "m",
    cw_unit: "°C·wk",
    km2_unit: "km²",

    recalc_done: "Recalculated",
    error_load: "Failed to load segments",

    // Workflow
    workflow_title: "3-Layer Decision Workflow",
    wf1_t: "12-Dim Features",
    wf2_t: "ML Augment",
    wf3_t: "Fusion",
    wf4_t: "Decision",
    wf5_t: "Priority",
    wf1_title: "Layer 1 · Raw 12-Dim Features",
    wf1_body: "Environmental, ecological & tourism signals feeding the triage model.",
    wf2_title: "Layer 2 · ML Feature Augmentation",
    wf2_body: "Gradient-boosted bleaching predictor + Bayesian resampling (1000 draws) for uncertainty.",
    wf3_title: "Layer 3 · Dual-Engine Fusion",
    wf3_body: "Entropy-weight TOPSIS (objective) fused with Laya AI rubric v2. Final = (1-α)·MCDM + α·Laya.",
    wf4_title: "Decision Layer",
    wf4_body: "Youden-optimised ROC threshold classifies priority; integer programming selects reefs under budget.",
    wf5_title: "Output · Priority Triage",
    wf5_body: "Every reef segment is routed to Invest / Monitor / De-prioritize with a calibrated confidence interval.",
    wf_feat_list: "12 input features",
    wf_ml_auc: "ML bleaching AUC",
    wf_bayes: "Bayesian sampling",
    wf_bayes_n: "1000 draws",
    wf_top_weights: "Top-3 entropy weights",
    wf_alpha: "Fusion weight α",
    wf_rubric: "Laya rubric",
    wf_rubric_v: "v2",
    wf_youden: "Youden threshold",
    wf_obj: "Integer LP objective",
    wf_obj_desc: "max Σ gain·amplifier, s.t. Σ cost ≤ budget",

    conn_btn: "Connectivity Network",
    conn_loading: "Loading connectivity matrix…",
    conn_empty: "Connectivity matrix unavailable",

    chart_weights_title: "Entropy Feature Weights",
    chart_compare_title: "Old vs Fusion Score",
    chart_mlcoef_title: "Top-5 ML Feature Coefficients",
    compare_old: "Old avg",
    compare_new: "Fusion avg",
    weights_empty: "No weights available",
    tooltip_score: "Score",
    tooltip_bleach: "Bleach",
    tooltip_choice: "Choice",
    tooltip_conn: "Conn",
    tooltip_old: "Old",
    tooltip_new: "New",

    ml_not_trained: "Model not trained",
    ml_auc: "AUC",
    ml_acc: "Accuracy",
    ml_precision: "Precision",
    ml_recall: "Recall",
    ml_f1: "F1",
    ml_cm: "Confusion Matrix (rows=actual, cols=pred)",
    cm_actual: "Actual",
    cm_pred: "Predicted",
    cm_neg: "No-bleach",
    cm_pos: "Bleach",

    radar_heat: "Thermal stress",
    radar_conn: "Connectivity",
    radar_tour: "Tourism value",
    radar_rhi: "Coral health",
    radar_bleach: "Bleach risk",
    radar_recov: "Recovery potential",

    budget_method_label: "Method",
    collapse_panel: "Collapse panel",
    expand_panel: "Expand panel",
    drag_to_resize: "Drag to resize",
    reef_lab_btn: "Enter Reef Lab",
    report_export_btn: "Export Report",

    mobile_menu_open: "Open menu",
    mobile_menu_close: "Close menu",
    drawer_open: "Open panels",
    drawer_close: "Hide panels",
    source_label: "Source",
    no_env_data: "No environmental data",
    last_saved: "Last saved",
    ai_analysis_failed: "Analysis failed",
    frac_white: "White",
    frac_pale: "Pale",
    frac_pigmented: "Pigmented",
    frac_water: "Water excluded",
    coral_healthy: "Healthy",
    coral_mild: "Mild",
    coral_moderate: "Moderate",
    coral_severe: "Severe",
    id_label: "ID",
    dhw_short: "DHW",
    usd: "USD",
    unit_cost_refs: "Unit cost references:",
    loading_segment: "Loading…",
    n_a: "N/A",
  },
  zh: {
    app_title: "ReefTriage 礁救三角",
    app_subtitle: "仙本那珊瑚礁恢复优先级系统",
    stat_segments: "礁段总数",
    stat_invest: "优先恢复",
    stat_monitor: "观察",
    stat_deprior: "暂不投入",
    stat_avg: "平均分",
    laya_mock: "Laya: 模拟模式",
    laya_live: "Laya: 实时",
    recalc: "↻ 重新评分",
    legend_title: "优先级",
    legend_invest: "优先恢复 (≥37.6)",
    legend_monitor: "观察 (30–37.5)",
    legend_deprior: "暂不投入 (<30)",
    loading: "正在对礁段评分…",

    budget_title: "预算控制",
    budget_label: "恢复总预算",
    unit_cost_label: "每段恢复成本",
    optimizer_title: "优化结果",
    optimizer_selected: "选中段数",
    optimizer_cost: "总成本",
    optimizer_used: "预算使用率",
    optimizer_gain: "总收益",

    basemap_satellite: "卫星",
    basemap_topo: "地形",

    detail_close: "关闭",
    popup_final: "融合分",
    popup_three: "分数拆解",
    popup_ci: "95% 置信区间",
    popup_radar: "六维礁体画像",
    detail_features: "特征",
    popup_mcdm: "客观分(MCDM)",
    popup_laya: "AI分(Laya)",
    popup_bleach: "白化概率",
    popup_dhw: "当前热压力",
    popup_depth: "平均水深",
    popup_dist: "到潜点距离",
    popup_conn: "连通性",
    popup_rhi: "CoralCore RHI",
    popup_area: "礁体面积",
    popup_model: "评分引擎",

    tab_segments: "礁段列表",
    tab_weights: "特征权重",
    tab_compare: "模型对比",
    tab_connectivity: "连通性网络",
    tab_ml: "ML模型",

    segment_table_rank: "#",
    segment_table_name: "名称",
    segment_table_score: "分数",
    segment_table_choice: "决策",
    segment_table_dhw: "DHW",
    segment_table_depth: "水深",

    invest: "优先恢复",
    monitor: "观察",
    deprioritize: "暂不投入",
    km_unit: "km",
    m_unit: "m",
    cw_unit: "°C·周",
    km2_unit: "km²",

    recalc_done: "已重算",
    error_load: "礁段加载失败",

    workflow_title: "三层决策工作流",
    wf1_t: "12维特征",
    wf2_t: "ML增强",
    wf3_t: "双引擎融合",
    wf4_t: "决策层",
    wf5_t: "优先级输出",
    wf1_title: "第一层 · 12维原始特征",
    wf1_body: "环境、生态与旅游信号输入分诊模型。",
    wf2_title: "第二层 · ML 特征增强",
    wf2_body: "梯度提升白化预测器 + 贝叶斯重采样(1000次)量化不确定性。",
    wf3_title: "第三层 · 双引擎融合",
    wf3_body: "熵权TOPSIS(客观)与Laya AI rubric v2融合。融合分=(1-α)·MCDM+α·Laya。",
    wf4_title: "决策层",
    wf4_body: "Youden最优ROC阈值分类优先级；预算下整数规划选礁。",
    wf5_title: "输出 · 优先级分诊",
    wf5_body: "每个礁段归入 恢复/观察/暂不投入，并附校准置信区间。",
    wf_feat_list: "12个输入特征",
    wf_ml_auc: "ML 白化 AUC",
    wf_bayes: "贝叶斯采样",
    wf_bayes_n: "1000 次抽样",
    wf_top_weights: "熵权 Top-3",
    wf_alpha: "融合权重 α",
    wf_rubric: "Laya 评分准则",
    wf_rubric_v: "v2",
    wf_youden: "Youden 阈值",
    wf_obj: "整数规划目标",
    wf_obj_desc: "max Σ 收益×放大系数, s.t. Σ 成本 ≤ 预算",

    conn_btn: "连通性网络",
    conn_loading: "正在加载连通性矩阵…",
    conn_empty: "连通性矩阵不可用",

    chart_weights_title: "熵权法特征权重",
    chart_compare_title: "旧模型 vs 融合分",
    chart_mlcoef_title: "Top-5 ML 特征系数",
    compare_old: "旧模型均分",
    compare_new: "融合模型均分",
    weights_empty: "暂无权重数据",
    tooltip_score: "分数",
    tooltip_bleach: "白化",
    tooltip_choice: "决策",
    tooltip_conn: "连通",
    tooltip_old: "旧",
    tooltip_new: "新",

    ml_not_trained: "模型未训练",
    ml_auc: "AUC",
    ml_acc: "准确率",
    ml_precision: "精确率",
    ml_recall: "召回率",
    ml_f1: "F1",
    ml_cm: "混淆矩阵 (行=实际, 列=预测)",
    cm_actual: "实际",
    cm_pred: "预测",
    cm_neg: "未白化",
    cm_pos: "白化",

    radar_heat: "热压力",
    radar_conn: "连通性",
    radar_tour: "旅游价值",
    radar_rhi: "珊瑚健康",
    radar_bleach: "白化风险",
    radar_recov: "恢复潜力",

    budget_method_label: "方法",
    collapse_panel: "折叠面板",
    expand_panel: "展开面板",
    drag_to_resize: "拖拽调整高度",
    reef_lab_btn: "进入 Reef Lab",
    report_export_btn: "导出报告",

    mobile_menu_open: "打开菜单",
    mobile_menu_close: "关闭菜单",
    drawer_open: "打开面板",
    drawer_close: "收起面板",
    source_label: "来源",
    no_env_data: "无环境数据",
    last_saved: "上次保存",
    ai_analysis_failed: "分析失败",
    frac_white: "白色",
    frac_pale: "浅色",
    frac_pigmented: "色素",
    frac_water: "水体剔除",
    coral_healthy: "健康",
    coral_mild: "轻度",
    coral_moderate: "中度",
    coral_severe: "重度",
    id_label: "编号",
    dhw_short: "DHW",
    usd: "USD",
    unit_cost_refs: "单位成本参考：",
    loading_segment: "加载中…",
    n_a: "无数据",
  },
};

let currentLang = "en";
try {
  const saved = localStorage.getItem("reeftriage_lang");
  if (saved === "en" || saved === "zh") currentLang = saved;
} catch (e) { /* ignore */ }
function t(key) {
  return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
}

// ---------- Global state ----------
let map = null;
let topoBasemap = null;
let satBasemap = null;
let usingTopo = false;
let segmentLayers = [];
let currentSegments = [];
let currentSegment = null;   // currently open in detail drawer
let budget = 50000;
let unitCost = 15000;

let optimizeSelected = null;
let optimizeTimer = null;

let lastWeights = null;
let lastCompare = null;
let lastMlInfo = null;
let lastConnectivity = null;
let lastStats = null;

const charts = {};
const initializedTabs = new Set();

// Layui module refs (filled inside layui.use)
let layuiElement = null;
let layuiTable = null;
let layuiSlider = null;
let tableRendered = false;

const CHOICE_COLORS = {
  invest: "#10b981",
  monitor: "#f59e0b",
  deprioritize: "#6b7280",
};
const CHOICE_CSS = {
  invest: "invest",
  monitor: "monitor",
  deprioritize: "deprioritize",
};

// ---------- ECharts dark theme default ----------
const ECHART_BASE = {
  backgroundColor: "transparent",
  textStyle: { color: "#94a3b8" },
  title: { textStyle: { color: "#e2e8f0" } },
  legend: { textStyle: { color: "#94a3b8" } },
  tooltip: {
    backgroundColor: "rgba(13,27,42,0.95)",
    borderColor: "rgba(0,212,255,0.3)",
    textStyle: { color: "#e2e8f0" },
  },
  xAxis: {
    axisLine: { lineStyle: { color: "rgba(148,163,184,0.3)" } },
    axisLabel: { color: "#94a3b8" },
    splitLine: { lineStyle: { color: "rgba(148,163,184,0.1)" } },
  },
  yAxis: {
    axisLine: { lineStyle: { color: "rgba(148,163,184,0.3)" } },
    axisLabel: { color: "#94a3b8" },
    splitLine: { lineStyle: { color: "rgba(148,163,184,0.1)" } },
  },
};

// ---------- Map init ----------
function initMap() {
  map = L.map("map", { zoomControl: true, fadeAnimation: false }).setView([4.5, 118.7], 11);
  satBasemap = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Esri World Imagery", maxZoom: 18, fadeAnimation: false, crossOrigin: true }
  );
  topoBasemap = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Esri World Topo Map", maxZoom: 19, fadeAnimation: false, crossOrigin: true }
  );
  satBasemap.addTo(map);
  // Force tile visibility after load (fixes Leaflet opacity bug on mobile)
  satBasemap.on("load", () => forceTileOpacity());
  satBasemap.on("tileload", () => forceTileOpacity());
}

function forceTileOpacity() {
  document.querySelectorAll("#map img.leaflet-tile").forEach((img) => {
    img.style.opacity = "1";
  });
}

function toggleBasemap() {
  usingTopo = !usingTopo;
  if (usingTopo) {
    if (map.hasLayer(satBasemap)) map.removeLayer(satBasemap);
    topoBasemap.addTo(map);
  } else {
    if (map.hasLayer(topoBasemap)) map.removeLayer(topoBasemap);
    satBasemap.addTo(map);
  }
  setTimeout(forceTileOpacity, 200);
  updateBasemapButton();
}

function updateBasemapButton() {
  const btn = document.getElementById("basemap-toggle");
  if (!btn) return;
  const icon = usingTopo ? "🗺️" : "🛰️";
  const label = t(usingTopo ? "basemap_topo" : "basemap_satellite");
  btn.innerHTML = `${icon} <span>${label}</span>`;
}

// ---------- Data loading ----------
async function loadSegments() {
  showLoading(true);
  try {
    const [segRes, statsRes] = await Promise.all([
      fetch("/api/segments").then((r) => r.json()),
      fetch("/api/stats").then((r) => r.json()),
    ]);
    currentSegments = segRes.segments || [];
    lastStats = statsRes;
    renderStats(statsRes);
    renderLayaBadge(statsRes.laya_mode);
    renderMapMarkers();
    renderSegmentTable();
    renderOptimizeResult(null);
    fetchOptimize();
  } catch (e) {
    console.error(e);
    alert(t("error_load") + ": " + e.message);
  } finally {
    showLoading(false);
  }
}

function renderStats(s) {
  document.getElementById("stat-total").textContent = s.total_segments;
  document.getElementById("stat-invest").textContent = s.invest_count;
  document.getElementById("stat-monitor").textContent = s.monitor_count;
  document.getElementById("stat-deprior").textContent = s.deprioritize_count;
  document.getElementById("stat-avg").textContent = s.avg_score != null ? Number(s.avg_score).toFixed(1) : "–";
}

function renderLayaBadge(mode) {
  const badge = document.getElementById("laya-badge");
  if (mode === "live") {
    badge.className = "badge badge-live";
    badge.textContent = t("laya_live");
  } else {
    badge.className = "badge badge-mock";
    badge.textContent = t("laya_mock");
  }
}

// ---------- Map markers ----------
function renderMapMarkers() {
  segmentLayers.forEach((l) => map.removeLayer(l));
  segmentLayers = [];
  currentSegments.forEach((seg) => {
    const color = CHOICE_COLORS[seg.choice] || "#6b7280";
    const cssClass = CHOICE_CSS[seg.choice] || "deprioritize";
    let layer;
    const score = seg.final_score ?? seg.score ?? 30;
    if (seg.geometry && seg.geometry.coordinates) {
      const rings = seg.geometry.coordinates.map((ring) =>
        ring.map(([lon, lat]) => [lat, lon])
      );
      layer = L.polygon(rings, {
        fillColor: color,
        color: color,
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.6,
        className: "reef-" + cssClass,
      });
    } else {
      layer = L.circleMarker([seg.lat, seg.lon], {
        radius: 6 + (score / 100) * 10,
        fillColor: color,
        color: color,
        weight: 2,
        fillOpacity: 0.9,
        className: "reef-" + cssClass,
      });
    }
    layer.on("click", () => openDetailDrawer(seg));
    layer.addTo(map);
    layer._segId = seg.segment_id;
    layer._seg = seg;
    segmentLayers.push(layer);
  });
  applySelectedHighlight();
}

function applySelectedHighlight() {
  segmentLayers.forEach((layer) => {
    const selected = optimizeSelected && optimizeSelected.has(layer._segId);
    const seg = layer._seg;
    const cssClass = CHOICE_CSS[seg.choice] || "deprioritize";
    if (layer.setStyle) {
      layer.setStyle({
        weight: selected ? 3 : 1.5,
        color: selected ? "#00d4ff" : CHOICE_COLORS[seg.choice] || "#6b7280",
        className: "reef-" + cssClass + (selected ? " reef-selected" : ""),
      });
    }
  });
}

// ---------- Detail drawer ----------
function openDetailDrawer(seg) {
  currentSegment = seg;
  const drawer = document.getElementById("detail-drawer");
  drawer.classList.add("open");
  drawer.style.transition = "none";
  drawer.style.right = "0px";
  requestAnimationFrame(() => requestAnimationFrame(() => { drawer.style.transition = ""; }));

  const name = currentLang === "zh" && seg.name_zh ? seg.name_zh : seg.name;
  document.getElementById("detail-name").textContent = name;
  document.getElementById("detail-id").textContent = "#" + seg.segment_id;

  const score = seg.final_score ?? seg.score;
  document.getElementById("detail-score").textContent = score != null ? score.toFixed(1) : "—";

  const badge = document.getElementById("detail-badge");
  badge.textContent = t(seg.choice || "monitor");
  badge.style.background = CHOICE_COLORS[seg.choice] || "#6b7280";

  // Three-score bars
  const three = document.getElementById("detail-three");
  const rows = [];
  if (seg.mcdm_score != null) rows.push(["#00d4ff", t("popup_mcdm"), seg.mcdm_score]);
  if (seg.laya_score != null) rows.push(["#f59e0b", t("popup_laya"), seg.laya_score]);
  if (seg.final_score != null) rows.push(["#10b981", t("popup_final"), seg.final_score]);
  three.innerHTML = rows.length ? rows.map(([col, k, v]) => `
    <div class="ts-row">
      <span class="ts-k">${k}</span>
      <span class="ts-bar"><span class="ts-fill" style="width:${Math.min(100, v)}%;background:${col};box-shadow:0 0 6px ${col}"></span></span>
      <span class="ts-v">${typeof v === "number" ? v.toFixed(1) : v}</span>
    </div>`).join("") : `<div class="muted">—</div>`;

  // CI
  const ciRange = document.getElementById("detail-ci-range");
  const ciMid = document.getElementById("detail-ci-mid");
  const ciLabel = document.getElementById("detail-ci-label");
  if (seg.confidence_interval && seg.confidence_interval.ci_lower != null) {
    const ci = seg.confidence_interval;
    const lo = Math.max(0, Math.min(100, ci.ci_lower));
    const hi = Math.max(0, Math.min(100, ci.ci_upper));
    const mid = ci.mean != null ? Math.max(0, Math.min(100, ci.mean)) : (lo + hi) / 2;
    ciRange.style.left = lo + "%";
    ciRange.style.width = Math.max(1, hi - lo) + "%";
    ciMid.style.left = mid + "%";
    ciLabel.textContent = `[${Number(ci.ci_lower).toFixed(1)}, ${Number(ci.ci_upper).toFixed(1)}]`;
  } else {
    ciRange.style.left = "0"; ciRange.style.width = "0";
    ciMid.style.left = "0";
    ciLabel.textContent = "—";
  }

  // Feature rows
  const feat = document.getElementById("detail-features");
  const dist = seg.distance_to_nearest_dive_site_km ?? seg.distance_to_dive_site ?? null;
  const conn5 = seg.connectivity_score ?? null;
  const fmtNum = (v, d) => (typeof v === "number" ? v.toFixed(d) : (v ?? "—"));
  const featRows = [
    [t("popup_dhw"), fmtNum(seg.current_dhw, 2) + " " + t("cw_unit")],
    [t("popup_depth"), fmtNum(seg.mean_depth, 1) + " " + t("m_unit")],
    [t("popup_dist"), fmtNum(dist, 2) + " " + t("km_unit")],
    [t("popup_conn"), fmtNum(conn5, 1) + "/5"],
  ];
  if (seg.rhi_score != null) featRows.push([t("popup_rhi"), Number(seg.rhi_score).toFixed(1)]);
  featRows.push([t("popup_area"), fmtNum(seg.reef_area_km2, 2) + " " + t("km2_unit")]);
  if (seg.bleaching_probability != null)
    featRows.push([t("popup_bleach"), (seg.bleaching_probability * 100).toFixed(1) + "%"]);
  if (seg.model) featRows.push([t("popup_model"), seg.model]);
  feat.innerHTML = featRows.map(([k, v]) =>
    `<div class="detail-feature-row"><span class="k">${k}</span><span class="v">${v}</span></div>`
  ).join("");

  // Radar
  setTimeout(() => drawDetailRadar(seg), 120);
}

function drawDetailRadar(seg) {
  const el = document.getElementById("detail-radar");
  if (!el) return;
  if (charts["detail-radar"]) { try { charts["detail-radar"].dispose(); } catch (e) {} }
  const chart = echarts.init(el);
  charts["detail-radar"] = chart;

  const heat = Math.min(1, (seg.current_dhw || 0) / 8);
  const conn = Math.min(1, (seg.connectivity_score || 0) / 5);
  const tour = Math.max(0, Math.min(1,
    0.6 * (1 - (seg.distance_to_nearest_dive_site_km || 0) / 10) +
    0.4 * ((seg.dive_sites_within_5km || 0) / 5)));
  const rhi = Math.min(1, (seg.rhi_score || 0) / 100);
  const bleach = seg.bleaching_probability || 0;
  const recovRaw = (seg.larval_input || 0) + (seg.larval_output || 0);
  const maxRecov = Math.max(1, ...currentSegments.map(s => (s.larval_input || 0) + (s.larval_output || 0)));
  const recov = Math.min(1, recovRaw / maxRecov);

  chart.setOption({
    ...ECHART_BASE,
    radar: {
      indicator: [
        { name: t("radar_heat"), max: 1 },
        { name: t("radar_conn"), max: 1 },
        { name: t("radar_tour"), max: 1 },
        { name: t("radar_rhi"), max: 1 },
        { name: t("radar_bleach"), max: 1 },
        { name: t("radar_recov"), max: 1 },
      ],
      radius: "62%",
      center: ["50%", "55%"],
      axisName: { fontSize: 9, color: "#94a3b8" },
      splitArea: { areaStyle: { color: ["rgba(0,212,255,0.03)", "rgba(0,212,255,0.06)"] } },
      splitLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
      axisLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
    },
    series: [{
      type: "radar",
      data: [{
        value: [heat, conn, tour, rhi, bleach, recov],
        name: seg.segment_id,
        areaStyle: { color: "rgba(0,212,255,0.2)" },
        lineStyle: { color: "#00d4ff", width: 2 },
        itemStyle: { color: "#00d4ff" },
      }],
    }],
  });
}

function closeDetailDrawer() {
  const drawer = document.getElementById("detail-drawer");
  drawer.classList.remove("open");
  drawer.style.transition = "none";
  drawer.style.right = "-400px";
  currentSegment = null;
}

// ---------- Segment table (Layui table, bottom drawer) ----------
let tableSort = { key: "score", dir: -1 };

function getSortedSegments() {
  const key = tableSort.key, dir = tableSort.dir;
  return [...currentSegments].sort((a, b) => {
    let av, bv;
    if (key === "name") {
      av = currentLang === "zh" && a.name_zh ? a.name_zh : a.name;
      bv = currentLang === "zh" && b.name_zh ? b.name_zh : b.name;
      return av.localeCompare(bv) * dir;
    } else if (key === "choice") {
      av = a.choice || ""; bv = b.choice || "";
      return av.localeCompare(bv) * dir;
    } else if (key === "score") {
      av = a.final_score ?? a.score ?? 0;
      bv = b.final_score ?? b.score ?? 0;
    } else if (key === "dhw") {
      av = a.current_dhw ?? 0; bv = b.current_dhw ?? 0;
    } else if (key === "depth") {
      av = a.mean_depth ?? 0; bv = b.mean_depth ?? 0;
    } else {
      return 0;
    }
    return (av - bv) * dir;
  });
}

function buildTableCols() {
  return [[
    { field: "rank", title: t("segment_table_rank"), width: 45, sort: true },
    { field: "name", title: t("segment_table_name"), sort: true },
    { field: "score", title: t("segment_table_score"), width: 80, sort: true, align: "right",
      templet: (d) => `<b>${d.scoreText}</b>` },
    { field: "choice", title: t("segment_table_choice"), width: 110, sort: true,
      templet: (d) => `<span class="seg-pill ${d.choice}">${d.choiceText}</span>` },
    { field: "dhw", title: t("segment_table_dhw"), width: 80, sort: true, align: "right",
      templet: (d) => (typeof d.dhw === "number" ? d.dhw.toFixed(2) : d.dhw) },
    { field: "depth", title: t("segment_table_depth"), width: 80, sort: true, align: "right",
      templet: (d) => (typeof d.depth === "number" ? d.depth.toFixed(1) : d.depth) },
  ]];
}

function renderSegmentTable() {
  if (!layuiTable) return;
  const sorted = getSortedSegments();
  const data = sorted.map((seg, idx) => {
    const showScore = seg.final_score ?? seg.score;
    return {
      seg_id: seg.segment_id,
      rank: idx + 1,
      name: currentLang === "zh" && seg.name_zh ? seg.name_zh : seg.name,
      score: showScore != null ? showScore : 0,
      scoreText: showScore != null ? showScore.toFixed(1) : "—",
      choice: seg.choice || "monitor",
      choiceText: t(seg.choice || "monitor"),
      dhw: seg.current_dhw ?? "—",
      depth: seg.mean_depth ?? "—",
      funded: optimizeSelected ? optimizeSelected.has(seg.segment_id) : false,
    };
  });
  const opts = {
    elem: "#seg-table-layui",
    id: "segTable",
    data: data,
    cols: buildTableCols(),
    page: false,
    even: false,
    skin: "line",
    initSort: { field: tableSort.key, type: tableSort.dir === 1 ? "asc" : "desc" },
    done: function (res) {
      const rows = document.querySelectorAll("#pane-segments .layui-table-body tbody tr");
      res.data.forEach((row, i) => {
        if (row.funded && rows[i]) rows[i].classList.add("funded");
      });
      startSegAutoScroll();
    },
  };
  if (!tableRendered) {
    layuiTable.render(opts);
    tableRendered = true;
  } else {
    layuiTable.reload("segTable", opts);
  }
}

// ---------- Segment table auto-scroll marquee ----------
let segScrollTimer = null;
let segScrollPaused = false;

function startSegAutoScroll() {
  if (segScrollTimer) { clearInterval(segScrollTimer); segScrollTimer = null; }
  const container = document.querySelector("#pane-segments .layui-table-body");
  if (!container) return;

  // Pause while the user hovers / interacts with the table; resume on leave.
  segScrollPaused = false;
  container.onmouseenter = () => { segScrollPaused = true; };
  container.onmouseleave = () => { segScrollPaused = false; };

  // Re-check overflow on every tick so scrolling starts/stops automatically
  // when the drawer is resized (CSS var --drawer-h changes the body height).
  segScrollTimer = setInterval(() => {
    if (segScrollPaused) return;
    // Only scroll when content actually overflows the viewport.
    if (container.scrollHeight <= container.clientHeight + 2) return;
    if (container.scrollTop + container.clientHeight >= container.scrollHeight - 2) {
      // Brief pause at the bottom before looping back to top.
      setTimeout(() => { container.scrollTop = 0; }, 600);
    } else {
      container.scrollTop += 1;
    }
  }, 50);
}

function setupTableEvents() {
  if (!layuiTable) return;
  layuiTable.on("sort(segTable)", (obj) => {
    tableSort.key = obj.field;
    tableSort.dir = obj.type === "asc" ? 1 : -1;
    renderSegmentTable();
  });
  layuiTable.on("row(segTable)", (obj) => {
    const segId = obj.data.seg_id;
    const seg = currentSegments.find((s) => s.segment_id === segId);
    if (seg) {
      map.setView([seg.lat, seg.lon], 13);
      openDetailDrawer(seg);
    }
  });
}

// ---------- Budget / Optimizer ----------
function renderBudgetLabels() {
  document.getElementById("budget-value").textContent = "$" + (budget / 1000) + "k";
  document.getElementById("unit-cost").textContent = unitCost / 1000;
}

function renderBudgetResult() {
  renderBudgetLabels();
  clearTimeout(optimizeTimer);
  optimizeTimer = setTimeout(fetchOptimize, 300);
}

async function fetchOptimize() {
  try {
    const url = `/api/optimize?budget=${encodeURIComponent(budget)}&unit_cost=${encodeURIComponent(unitCost)}`;
    const data = await (await fetch(url)).json();
    optimizeSelected = new Set((data.selected || []).map((s) => s.segment_id));
    renderOptimizeResult(data);
  } catch (e) {
    console.warn("Optimizer unavailable:", e);
    optimizeSelected = null;
    renderOptimizeResult(null);
  }
}

function renderOptimizeResult(data) {
  const nEl = document.getElementById("opt-n");
  const cEl = document.getElementById("opt-cost");
  const uEl = document.getElementById("opt-used");
  const gEl = document.getElementById("opt-gain");
  if (!data) {
    nEl.textContent = "–"; cEl.textContent = "–"; uEl.textContent = "–"; gEl.textContent = "–";
    document.getElementById("budget-method").textContent = "";
  } else {
    const n = data.selected_count != null ? data.selected_count : (data.selected || []).length;
    const costK = (data.total_cost / 1000).toFixed(1);
    const pct = (data.budget_used_pct || 0).toFixed(1);
    const gain = (data.total_gain || 0).toFixed(3);
    nEl.textContent = n;
    cEl.textContent = "$" + costK + "k";
    uEl.textContent = pct + "%";
    gEl.textContent = gain;
    document.getElementById("budget-method").textContent =
      `${t("budget_method_label")}: ${data.method || "—"}`;
  }
  applySelectedHighlight();
  renderSegmentTable();
}

// ---------- Model insights ----------
async function loadModelInsights() {
  try {
    const [w, c, m] = await Promise.all([
      fetch("/api/model/weights").then((r) => r.json()).catch(() => null),
      fetch("/api/model/compare").then((r) => r.json()).catch(() => null),
      fetch("/api/model/ml-info").then((r) => r.json()).catch(() => null),
    ]);
    lastWeights = w;
    lastCompare = c;
    lastMlInfo = m;
  } catch (e) {
    console.warn("Model insights load failed:", e);
  }
  renderMlMetrics();
}

function ensureChart(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  if (charts[id]) { try { charts[id].dispose(); } catch (e) {} delete charts[id]; }
  const ch = echarts.init(el);
  charts[id] = ch;
  return ch;
}

function renderWeightsChart() {
  const el = document.getElementById("chart-weights");
  if (!el) return;
  const w = lastWeights && lastWeights.weights;
  if (!w || !Object.keys(w).length) {
    el.innerHTML = `<div class="muted" style="padding:20px;text-align:center">${t("weights_empty")}</div>`;
    return;
  }
  el.innerHTML = "";
  const ch = ensureChart("chart-weights");
  const entries = Object.entries(w).sort((a, b) => b[1] - a[1]);
  ch.setOption({
    ...ECHART_BASE,
    title: { text: t("chart_weights_title"), left: "center", textStyle: { fontSize: 12, color: "#e2e8f0" } },
    grid: { left: 8, right: 50, top: 32, bottom: 8, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "value", axisLabel: { fontSize: 10, formatter: (v) => (v * 100).toFixed(0) + "%" } },
    yAxis: {
      type: "category",
      data: entries.map(e => e[0]).reverse(),
      axisLabel: { fontSize: 10, formatter: (v) => v.length > 22 ? v.substring(0, 20) + "…" : v },
    },
    series: [{
      type: "bar",
      data: entries.map(e => +e[1].toFixed(4)).reverse(),
      itemStyle: { color: '#00d4ff', borderColor: '#2dd4bf', borderWidth: 0 },
      label: { show: true, position: "right", fontSize: 10, color: "#94a3b8", formatter: (p) => (p.value * 100).toFixed(1) + "%" },
    }],
  }, true);
}

function renderCompareChart() {
  const ch = ensureChart("chart-compare");
  if (!ch || !lastCompare || !lastCompare.old_model || !lastCompare.new_model) {
    if (ch) ch.clear();
    return;
  }
  const oldS = lastCompare.old_model.scores || [];
  const newS = lastCompare.new_model.scores || [];
  const pts = oldS.map((o, i) => {
    const n = newS[i] != null ? newS[i] : o;
    let choice = "monitor";
    if (n >= 37.6) choice = "invest";
    else if (n < 30.0) choice = "deprioritize";
    return { value: [o, n], itemStyle: { color: CHOICE_COLORS[choice] } };
  });
  ch.setOption({
    ...ECHART_BASE,
    title: { text: t("chart_compare_title"), left: "center", textStyle: { fontSize: 12, color: "#e2e8f0" } },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: "item", formatter: (p) => `${t("tooltip_old")}: ${p.value[0]}<br/>${t("tooltip_new")}: ${p.value[1]}` },
    xAxis: { name: t("compare_old"), nameLocation: "middle", nameGap: 22, type: "value", min: 30, max: 60 },
    yAxis: { name: t("compare_new"), type: "value", min: 30, max: 60 },
    series: [
      { type: "scatter", data: pts, symbolSize: 9 },
      { type: "line", data: [[30, 30], [60, 60]], lineStyle: { color: "#6b7280", type: "dashed", width: 1 }, symbol: "none", silent: true },
    ],
  }, true);
}

function renderMlMetrics() {
  const box = document.getElementById("ml-metrics");
  if (!box) return;
  if (!lastMlInfo || lastMlInfo.status !== "trained" || !lastMlInfo.metrics) {
    box.innerHTML = `<div class="muted">${t("ml_not_trained")}</div>`;
    return;
  }
  const m = lastMlInfo.metrics;
  const auc = m.auc != null ? Number(m.auc).toFixed(3) : "—";
  const acc = m.accuracy != null ? (Number(m.accuracy) * 100).toFixed(1) + "%" : "—";
  const prec = m.precision != null ? (Number(m.precision) * 100).toFixed(1) + "%" : "—";
  const rec = m.recall != null ? (Number(m.recall) * 100).toFixed(1) + "%" : "—";
  const f1 = m.f1 != null ? Number(m.f1).toFixed(3) : "—";
  box.innerHTML = `
    <div class="ml-metric"><span class="v">${auc}</span><span class="k">${t("ml_auc")}</span></div>
    <div class="ml-metric"><span class="v">${acc}</span><span class="k">${t("ml_acc")}</span></div>
    <div class="ml-metric"><span class="v">${prec}</span><span class="k">${t("ml_precision")}</span></div>
    <div class="ml-metric"><span class="v">${rec}</span><span class="k">${t("ml_recall")}</span></div>
    <div class="ml-metric"><span class="v">${f1}</span><span class="k">${t("ml_f1")}</span></div>
  `;
  const cmBox = document.getElementById("ml-cm");
  const cm = m.confusion_matrix;
  if (cm && cm.length === 2) {
    cmBox.innerHTML = `
      <div class="cm-cell cm-head"></div>
      <div class="cm-cell cm-head">${t("cm_pred")} · ${t("cm_neg")}</div>
      <div class="cm-cell cm-head">${t("cm_pred")} · ${t("cm_pos")}</div>
      <div class="cm-cell cm-head">${t("cm_actual")} · ${t("cm_neg")}</div>
      <div class="cm-cell cm-tn">${cm[0][0]}</div>
      <div class="cm-cell cm-fp">${cm[0][1]}</div>
      <div class="cm-cell cm-head">${t("cm_actual")} · ${t("cm_pos")}</div>
      <div class="cm-cell cm-fn">${cm[1][0]}</div>
      <div class="cm-cell cm-tp">${cm[1][1]}</div>
    `;
  }
  renderMlCoefChart();
}

function renderMlCoefChart() {
  const ch = ensureChart("chart-mlcoef");
  if (!ch || !lastMlInfo || !lastMlInfo.coef) { if (ch) ch.clear(); return; }
  const entries = Object.entries(lastMlInfo.coef)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 5);
  ch.setOption({
    ...ECHART_BASE,
    title: { text: t("chart_mlcoef_title"), left: "center", textStyle: { fontSize: 11, color: "#e2e8f0" } },
    grid: { left: 8, right: 40, top: 28, bottom: 8, containLabel: true },
    xAxis: { type: "value" },
    yAxis: { type: "category", data: entries.map(e => e[0]).reverse(), axisLabel: { fontSize: 10, formatter: (v) => v.length > 22 ? v.substring(0, 20) + "…" : v } },
    series: [{
      type: "bar",
      data: entries.map(e => +e[1].toFixed(3)).reverse(),
      itemStyle: { color: (p) => p.value >= 0 ? "#10b981" : "#f87171" },
      label: { show: true, position: "right", fontSize: 10, color: "#94a3b8" },
    }],
  }, true);
}

// ---------- Connectivity (bottom drawer tab) ----------
async function renderConnectivityGraph() {
  const box = document.getElementById("chart-connectivity");
  if (!lastConnectivity) {
    box.innerHTML = `<div style="padding:20px;text-align:center;color:#94a3b8">${t("conn_loading")}</div>`;
    try {
      lastConnectivity = await (await fetch("/api/model/connectivity")).json();
    } catch (e) {
      box.innerHTML = `<div style="padding:20px;text-align:center;color:#f87171">${t("conn_empty")}</div>`;
      return;
    }
  }
  if (!lastConnectivity || !lastConnectivity.nodes) {
    box.innerHTML = `<div style="padding:20px;text-align:center;color:#f87171">${t("conn_empty")}</div>`;
    return;
  }
  box.innerHTML = "";
  if (charts["chart-connectivity"]) { try { charts["chart-connectivity"].dispose(); } catch(e){} }
  const ch = echarts.init(box);
  charts["chart-connectivity"] = ch;

  const names = lastConnectivity.nodes;
  const matrix = lastConnectivity.matrix;
  const segByName = {};
  currentSegments.forEach(s => { segByName[s.name] = s; });

  const maxScore = Math.max(1, ...currentSegments.map(s => s.final_score ?? s.score ?? 30));
  const nodes = names.map((name, i) => {
    const seg = segByName[name] || {};
    const score = seg.final_score ?? seg.score ?? 30;
    const choice = seg.choice || "monitor";
    return {
      id: String(i), name,
      symbolSize: 8 + (score / maxScore) * 22,
      itemStyle: { color: CHOICE_COLORS[choice] || "#6b7280" },
      _score: score, _choice: choice, _bleach: seg.bleaching_probability,
    };
  });

  const links = [];
  for (let i = 0; i < matrix.length; i++) {
    for (let j = 0; j < matrix[i].length; j++) {
      const v = matrix[i][j];
      if (v > 0.01 && i !== j) {
        links.push({
          source: String(i), target: String(j), value: v,
          lineStyle: { width: Math.max(0.5, v * 6), opacity: Math.min(0.8, v * 1.5), color: "#00d4ff" },
        });
      }
    }
  }

  ch.setOption({
    ...ECHART_BASE,
    tooltip: {
      backgroundColor: "rgba(13,27,42,0.95)", borderColor: "rgba(0,212,255,0.3)", textStyle: { color: "#e2e8f0" },
      formatter: (p) => {
        if (p.dataType === "node") {
          const d = p.data;
          return `<b>${d.name}</b><br/>${t("tooltip_score")}: ${d._score ?? "—"}<br/>` +
                 `${t("tooltip_bleach")}: ${d._bleach != null ? (d._bleach * 100).toFixed(1) + "%" : "—"}<br/>` +
                 `${t("tooltip_choice")}: ${t(d._choice)}`;
        }
        return `${p.data.source} → ${p.data.target}<br/>${t("tooltip_conn")}: ${p.data.value.toFixed(3)}`;
      },
    },
    series: [{
      type: "graph", layout: "force", roam: true, draggable: true,
      force: { repulsion: 180, edgeLength: [40, 120] },
      label: { show: true, fontSize: 8, color: "#94a3b8" },
      edgeSymbol: ["none", "arrow"], edgeSymbolSize: 4,
      data: nodes, links,
      lineStyle: { curveness: 0.1, color: "#00d4ff" },
    }],
  });
}

// ---------- Bottom drawer tabs (Layui element) ----------
const TAB_NAMES = ["segments", "weights", "compare", "connectivity", "ml"];

function setupDrawerTabs() {
  if (!layuiElement) return;
  layuiElement.on("tab(drawerTab)", function (data) {
    const tab = TAB_NAMES[data.index] || "segments";
    onTabActivated(tab);
  });
}

function onTabActivated(tab) {
  setTimeout(() => {
    if (tab === "weights") { renderWeightsChart(); }
    else if (tab === "compare") { renderCompareChart(); }
    else if (tab === "connectivity") { renderConnectivityGraph(); }
    else if (tab === "ml") { renderMlMetrics(); }
    Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
    setTimeout(() => {
      Object.values(charts).forEach(ch => { try { ch.resize(); ch.setOption({}); } catch (e) {} });
    }, 120);
  }, 60);
}

// Switch the bottom drawer to the tab at the given index. Uses layui's
// tabChange when available, otherwise toggles the active classes directly so
// the click works even before (or without) the layui element module.
function switchDrawerTab(index) {
  if (layuiElement) {
    try {
      layuiElement.tabChange("drawerTab", index);
      onTabActivated(TAB_NAMES[index] || "segments");
      return;
    } catch (e) { /* fall through to DOM */ }
  }
  const tabs = document.querySelectorAll(".reef-tab > .layui-tab-title li");
  const panes = document.querySelectorAll(".reef-tab > .layui-tab-content > .layui-tab-item");
  tabs.forEach((li, i) => li.classList.toggle("layui-this", i === index));
  panes.forEach((p, i) => p.classList.toggle("layui-show", i === index));
  onTabActivated(TAB_NAMES[index] || "segments");
}

// ---------- Bottom drawer resize handle (updates --drawer-h CSS var) ----------
function setupDrawerResize() {
  const handle = document.getElementById("drawer-handle");
  const layout = document.getElementById("reef-layout");
  let startY = 0, startH = 0;
  function onMove(e) {
    const y = e.touches ? e.touches[0].clientY : e.clientY;
    const dh = startY - y;
    let h = startH + dh;
    h = Math.max(120, Math.min(window.innerHeight * 0.6, h));
    layout.style.setProperty("--drawer-h", h + "px");
    setTimeout(() => Object.values(charts).forEach(ch => { try { ch.resize(); } catch(e){} }), 30);
    if (map) map.invalidateSize();
  }
  function onUp() {
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    handle.classList.remove("dragging");
    document.body.style.userSelect = "";
  }
  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    startY = e.clientY;
    const drawer = document.getElementById("bottom-drawer");
    startH = drawer.getBoundingClientRect().height;
    handle.classList.add("dragging");
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// ---------- Left panel collapse ----------
let customSideW = null;
try {
  const _savedW = parseInt(localStorage.getItem("reeftriage_leftpanel_width"), 10);
  if (_savedW >= 200 && _savedW <= 500) customSideW = _savedW;
} catch (e) { /* ignore */ }

// Re-apply the custom expanded width only when the panel is NOT collapsed.
// When collapsed we must drop the inline --side-w so the .side-collapsed
// rule (48px) takes effect.
function applySideW() {
  const layout = document.getElementById("reef-layout");
  if (!layout) return;
  if (layout.classList.contains("side-collapsed") || window.innerWidth < 1200) {
    layout.style.removeProperty("--side-w");
  } else if (customSideW) {
    layout.style.setProperty("--side-w", customSideW + "px");
  } else {
    layout.style.removeProperty("--side-w");
  }
}

function setupPanelToggle() {
  const layout = document.getElementById("reef-layout");
  const btn = document.getElementById("panel-toggle-btn");
  function toggle() {
    layout.classList.toggle("side-collapsed");
    applySideW();
    setTimeout(() => {
      if (map) map.invalidateSize();
      Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
    }, 280);
  }
  btn.addEventListener("click", toggle);

  // collapsed icon buttons: expand and scroll to section
  document.querySelectorAll(".panel-icon-btn").forEach((b) => {
    b.addEventListener("click", () => {
      layout.classList.remove("side-collapsed");
      applySideW();
      const zone = b.getAttribute("data-goto");
      setTimeout(() => {
        const el = document.querySelector(`.panel-section[data-zone="${zone}"]`);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
        if (map) map.invalidateSize();
        Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
      }, 280);
    });
  });

  // auto-collapse on narrow screens (tablet & below)
  if (window.innerWidth < 1200) layout.classList.add("side-collapsed");
  applySideW();

  // mobile menu button (hamburger in header)
  const menuBtn = document.getElementById("mobile-menu-btn");
  if (menuBtn) {
    menuBtn.addEventListener("click", () => {
      layout.classList.toggle("mobile-panel-open");
      setTimeout(() => {
        if (map) map.invalidateSize();
        Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
      }, 280);
    });
  }

  // mobile bottom-drawer FAB
  const drawerFab = document.getElementById("drawer-fab");
  if (drawerFab) {
    let drawerOpen = false;
    drawerFab.addEventListener("click", () => {
      drawerOpen = !drawerOpen;
      const drawer = document.getElementById("bottom-drawer");
      layout.classList.toggle("drawer-open", drawerOpen);
      if (window.innerWidth < 768) {
        drawer.style.display = drawerOpen ? "flex" : "none";
      }
      setTimeout(() => {
        Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
        if (map) map.invalidateSize();
      }, 280);
    });
  }
}

// ---------- Left panel width resizer (drag the right edge) ----------
function setupPanelResize() {
  const resizer = document.getElementById("panel-resizer");
  const layout = document.getElementById("reef-layout");
  if (!resizer || !layout) return;

  applySideW();

  let startX = 0, startW = 0, dragging = false;

  function onMove(e) {
    if (!dragging) return;
    let w = startW + (e.clientX - startX);
    w = Math.max(200, Math.min(500, w));
    customSideW = w;
    layout.style.setProperty("--side-w", w + "px");
    if (map) map.invalidateSize();
  }
  function onUp() {
    if (!dragging) return;
    dragging = false;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    resizer.classList.remove("dragging");
    layout.classList.remove("panel-resizing");
    document.body.style.userSelect = "";
    try { localStorage.setItem("reeftriage_leftpanel_width", String(customSideW)); } catch (e) {}
    Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
    if (map) map.invalidateSize();
  }
  resizer.addEventListener("mousedown", (e) => {
    e.preventDefault();
    if (window.innerWidth < 1200) return;
    if (layout.classList.contains("side-collapsed")) return;
    dragging = true;
    startX = e.clientX;
    const panel = document.getElementById("left-panel");
    startW = panel.getBoundingClientRect().width;
    resizer.classList.add("dragging");
    layout.classList.add("panel-resizing");
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// ---------- Workflow ----------
function setupWorkflow() {
  const nodes = document.querySelectorAll(".wf-node");
  let step = 0;
  setInterval(() => {
    nodes.forEach(n => n.classList.remove("pulse-live"));
    if (nodes[step % nodes.length]) nodes[step % nodes.length].classList.add("pulse-live");
    step++;
  }, 900);
  nodes.forEach((node) => {
    node.addEventListener("click", () => openWorkflowDetail(node.getAttribute("data-wf")));
  });
}

function openWorkflowDetail(n) {
  const titleEl = document.getElementById("wf-modal-title");
  const bodyEl = document.getElementById("wf-modal-body");
  let title = "", rows = [];
  if (n === "1") {
    title = t("wf1_title");
    const feats = lastWeights && lastWeights.weights ? Object.keys(lastWeights.weights) :
      ["current_dhw", "max_dhw_5yr", "mean_depth", "reef_area_km2",
       "distance_to_nearest_dive_site_km", "dive_sites_within_5km",
       "connectivity_score", "larval_input", "larval_output",
       "rhi_score", "total_settlements", "bleaching_probability"];
    rows = [`<div class="detail-section-title">${t("wf_feat_list")} (${feats.length})</div>`,
      `<ul>${feats.map(f => `<li>${f}</li>`).join("")}</ul>`];
  } else if (n === "2") {
    title = t("wf2_title");
    const auc = lastMlInfo && lastMlInfo.metrics ? Number(lastMlInfo.metrics.auc).toFixed(3) : "—";
    rows = [
      `<div class="wf-detail-row"><span>${t("wf_ml_auc")}</span><b>${auc}</b></div>`,
      `<div class="wf-detail-row"><span>${t("wf_bayes")}</span><b>${t("wf_bayes_n")}</b></div>`,
      `<p>${t("wf2_body")}</p>`,
    ];
  } else if (n === "3") {
    title = t("wf3_title");
    let wTop = "—";
    if (lastWeights && lastWeights.weights) {
      wTop = Object.entries(lastWeights.weights).sort((a, b) => b[1] - a[1])
        .slice(0, 3).map(([f, w]) => `${f} ${(w * 100).toFixed(1)}%`).join(" · ");
    }
    const alpha = lastCompare ? lastCompare.alpha : 0.30;
    rows = [
      `<div class="wf-detail-row"><span>${t("wf_top_weights")}</span><b>${wTop}</b></div>`,
      `<div class="wf-detail-row"><span>${t("wf_alpha")}</span><b>α = ${Number(alpha).toFixed(2)}</b></div>`,
      `<div class="wf-detail-row"><span>${t("wf_rubric")}</span><b>${t("wf_rubric_v")}</b></div>`,
      `<p>${t("wf3_body")}</p>`,
    ];
  } else if (n === "4") {
    title = t("wf4_title");
    rows = [
      `<div class="wf-detail-row"><span>${t("wf_youden")}</span><b>≈ 37.6</b></div>`,
      `<div class="wf-detail-row"><span>${t("wf_obj")}</span><b style="max-width:220px;text-align:right">${t("wf_obj_desc")}</b></div>`,
      `<p>${t("wf4_body")}</p>`,
    ];
  } else if (n === "5") {
    title = t("wf5_title");
    const s = lastStats || { invest_count: 0, monitor_count: 0, deprioritize_count: 0 };
    rows = [
      `<div class="wf-detail-row"><span style="color:${CHOICE_COLORS.invest}">● ${t("invest")}</span><b>${s.invest_count}</b></div>`,
      `<div class="wf-detail-row"><span style="color:${CHOICE_COLORS.monitor}">● ${t("monitor")}</span><b>${s.monitor_count}</b></div>`,
      `<div class="wf-detail-row"><span style="color:${CHOICE_COLORS.deprioritize}">● ${t("deprioritize")}</span><b>${s.deprioritize_count}</b></div>`,
      `<p>${t("wf5_body")}</p>`,
    ];
  }
  titleEl.textContent = title;
  bodyEl.innerHTML = rows.join("");
  document.getElementById("wf-modal").classList.remove("hidden");
}

// ---------- Recalc ----------
async function recalc() {
  const btn = document.getElementById("recalc-btn");
  btn.disabled = true;
  showLoading(true);
  try {
    await fetch("/api/recalc", { method: "POST" });
    await loadSegments();
    await loadModelInsights();
  } catch (e) {
    console.error(e);
  } finally {
    btn.disabled = false;
    showLoading(false);
  }
}

function showLoading(on) {
  document.getElementById("loading").classList.toggle("hidden", !on);
}

// ---------- i18n apply ----------
function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const k = el.getAttribute("data-i18n");
    if (I18N[currentLang][k]) el.innerHTML = I18N[currentLang][k];
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    const k = el.getAttribute("data-i18n-title");
    if (I18N[currentLang][k]) el.setAttribute("title", I18N[currentLang][k]);
  });
  document.title = currentLang === "zh"
    ? "ReefTriage · 仙本那珊瑚礁恢复优先级"
    : "ReefTriage · Semporna Reef Prioritization";
  updateBasemapButton();
  const langBtn = document.getElementById("lang-btn");
  if (langBtn) langBtn.textContent = currentLang === "en" ? "中文" : "EN";
  renderBudgetLabels();
  renderSegmentTable();
  if (currentSegment) openDetailDrawer(currentSegment);
  // re-render charts that use t() in labels
  if (lastWeights) renderWeightsChart();
  if (lastCompare) renderCompareChart();
  if (lastMlInfo) renderMlMetrics();
  Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
}

// ---------- Resize ----------
let resizeTimer = null;
window.addEventListener("resize", () => {
  if (map) map.invalidateSize();
  Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
  // breakpoint-aware: auto-collapse panel on tablet, auto-expand on desktop
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    const layout = document.getElementById("reef-layout");
    if (!layout) return;
    if (window.innerWidth >= 1200) {
      layout.classList.remove("side-collapsed");
    } else if (window.innerWidth < 1200 && window.innerWidth >= 768) {
      layout.classList.add("side-collapsed");
    }
    applySideW();
    if (map) map.invalidateSize();
    Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
  }, 200);
});

// ---------- Wire up ----------
document.addEventListener("DOMContentLoaded", () => {
  initMap();
  // Force map recalculation after layout/CSS settles (fixes tile fade on mobile)
  setTimeout(() => { if (map) { map.invalidateSize(); forceTileOpacity(); } }, 300);
  setTimeout(() => { if (map) { map.invalidateSize(); forceTileOpacity(); } }, 800);

  // Non-Layui wiring (works regardless of module load order)
  setupDrawerResize();
  setupPanelToggle();
  setupPanelResize();
  setupWorkflow();

  document.getElementById("recalc-btn").addEventListener("click", recalc);

  document.getElementById("lang-btn").addEventListener("click", () => {
    currentLang = currentLang === "en" ? "zh" : "en";
    try { localStorage.setItem("reeftriage_lang", currentLang); } catch (e) {}
    document.getElementById("lang-btn").textContent = currentLang === "en" ? "中文" : "EN";
    applyI18n();
  });

  document.getElementById("basemap-toggle").addEventListener("click", toggleBasemap);
  document.getElementById("detail-close").addEventListener("click", closeDetailDrawer);
  document.getElementById("conn-btn").addEventListener("click", () => {
    // Visual feedback: briefly highlight the button
    const btn = document.getElementById("conn-btn");
    btn.classList.remove("conn-btn-flash");
    void btn.offsetWidth; // restart CSS animation
    btn.classList.add("conn-btn-flash");

    const layout = document.getElementById("reef-layout");
    const drawer = document.getElementById("bottom-drawer");

    // 1. Make sure the bottom drawer is expanded to a usable height
    const curH = drawer.getBoundingClientRect().height;
    const targetH = Math.max(curH, 300, Math.min(320, window.innerHeight * 0.5));
    layout.style.setProperty("--drawer-h", targetH + "px");

    // On mobile, ensure the drawer sheet is open
    if (window.innerWidth < 768) {
      layout.classList.add("drawer-open");
      drawer.style.display = "flex";
    }

    // 2. Switch to the Connectivity tab (index 3 in drawerTab)
    switchDrawerTab(3);

    // 3. Force-render the connectivity graph (tabChange event also triggers
    //    onTabActivated, but call explicitly for robustness)
    setTimeout(() => {
      renderConnectivityGraph();
      setTimeout(() => {
        Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
      }, 150);
    }, 90);
  });
  document.getElementById("reef-lab-btn").addEventListener("click", () => {
    if (currentSegment) {
      window.open("/static/micro.html?segment=" + encodeURIComponent(currentSegment.segment_id), "_blank");
    }
  });
  document.getElementById("report-export-btn").addEventListener("click", () => {
    if (currentSegment) {
      window.open("/static/report.html?segment=" + encodeURIComponent(currentSegment.segment_id), "_blank");
    }
  });
  document.getElementById("wf-close").addEventListener("click", () =>
    document.getElementById("wf-modal").classList.add("hidden"));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDetailDrawer();
      document.getElementById("wf-modal").classList.add("hidden");
    }
  });

  // initial basemap button label
  updateBasemapButton();
  // set lang button initial text
  document.getElementById("lang-btn").textContent = currentLang === "en" ? "中文" : "EN";
  // apply saved language on initial load
  applyI18n();

  // ---- Layui modules: slider / table / element ----
  layui.use(["element", "slider", "table"], function () {
    layuiElement = layui.element;
    layuiSlider = layui.slider;
    layuiTable = layui.table;

    // Budget sliders (Layui slider replaces native range)
    layuiSlider.render({
      elem: "#budget-slider",
      min: 10000, max: 200000, step: 5000, value: 50000,
      tips: true,
      change: function (value) {
        budget = value;
        renderBudgetResult();
      },
    });
    layuiSlider.render({
      elem: "#unit-slider",
      min: 5, max: 40, step: 1, value: 15,
      tips: true,
      change: function (value) {
        unitCost = value * 1000;
        renderBudgetResult();
      },
    });

    // Bottom drawer tabs
    setupDrawerTabs();
    // Segment table + its row/sort events
    renderSegmentTable();
    setupTableEvents();

    // Now load all data (table is ready)
    loadSegments().then(() => loadModelInsights());
  });
});
