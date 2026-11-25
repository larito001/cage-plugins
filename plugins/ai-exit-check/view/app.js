const CLAUDE_MARK_PATH =
  "m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z";

const ANTIGRAVITY_ARCH_PATH =
  "M21.751 22.607c1.34 1.005 3.35.335 1.508-1.508C17.73 15.74 18.904 1 12.037 1 5.17 1 6.342 15.74.815 21.1c-2.01 2.009.167 2.511 1.507 1.506 5.192-3.517 4.857-9.714 9.715-9.714 4.857 0 4.522 6.197 9.714 9.715z";

const CODEX_MARK_PATH =
  "M8.086.457a6.105 6.105 0 013.046-.415c1.333.153 2.521.72 3.564 1.7a.117.117 0 00.107.029c1.408-.346 2.762-.224 4.061.366l.063.03.154.076c1.357.703 2.33 1.77 2.918 3.198.278.679.418 1.388.421 2.126a5.655 5.655 0 01-.18 1.631.167.167 0 00.04.155 5.982 5.982 0 011.578 2.891c.385 1.901-.01 3.615-1.183 5.14l-.182.22a6.063 6.063 0 01-2.934 1.851.162.162 0 00-.108.102c-.255.736-.511 1.364-.987 1.992-1.199 1.582-2.962 2.462-4.948 2.451-1.583-.008-2.986-.587-4.21-1.736a.145.145 0 00-.14-.032c-.518.167-1.04.191-1.604.185a5.924 5.924 0 01-2.595-.622 6.058 6.058 0 01-2.146-1.781c-.203-.269-.404-.522-.551-.821a7.74 7.74 0 01-.495-1.283 6.11 6.11 0 01-.017-3.064.166.166 0 00.008-.074.115.115 0 00-.037-.064 5.958 5.958 0 01-1.38-2.202 5.196 5.196 0 01-.333-1.589 6.915 6.915 0 01.188-2.132c.45-1.484 1.309-2.648 2.577-3.493.282-.188.55-.334.802-.438.286-.12.573-.22.861-.304a.129.129 0 00.087-.087A6.016 6.016 0 015.635 2.31C6.315 1.464 7.132.846 8.086.457zm-.804 7.85a.848.848 0 00-1.473.842l1.694 2.965-1.688 2.848a.849.849 0 001.46.864l1.94-3.272a.849.849 0 00.007-.854l-1.94-3.393zm5.446 6.24a.849.849 0 000 1.695h4.848a.849.849 0 000-1.696h-4.848z";

const SERVICE_LABELS = {
  google_edge: "Google 边缘识别",
  antigravity_web: "Antigravity 官网",
  antigravity_api: "Cloud Code 接口",
  gemini_web: "Gemini 网页端",
  claude_web: "Claude.ai 边缘",
  anthropic_api: "Anthropic API",
  chatgpt_web: "ChatGPT 网页端",
  codex_oauth: "Codex 登录授权",
  openai_api: "OpenAI API",
};

const PROVIDER_META = {
  google: {
    title: "Google",
    subtitle: "Antigravity · Gemini · Cloud Code",
  },
  anthropic: {
    title: "Anthropic",
    subtitle: "Claude Web · Messages API",
  },
  openai: {
    title: "OpenAI",
    subtitle: "Codex CLI · ChatGPT · OAuth",
  },
};

const waiting = new Map();
let nextId = 1;

function request(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    waiting.set(id, { resolve, reject });
    window.parent.postMessage({ jsonrpc: "2.0", id, method, params }, "*");
  });
}

function applyTheme(theme) {
  if (!theme || typeof theme !== "object") return;
  const root = document.documentElement;
  if (theme.scheme === "dark" || theme.scheme === "light") {
    root.dataset.scheme = theme.scheme;
  }
  const tokens = theme.tokens || {};
  for (const [key, value] of Object.entries(tokens)) {
    if (typeof value === "string" && value) {
      root.style.setProperty(`--${key}`, value);
    }
  }
}

window.addEventListener("message", (event) => {
  const message = event.data;
  if (event.source !== window.parent || !message || message.jsonrpc !== "2.0") {
    return;
  }
  if (message.id !== undefined && waiting.has(message.id)) {
    const pending = waiting.get(message.id);
    waiting.delete(message.id);
    if (message.error) {
      pending.reject(new Error(message.error.message || "RPC error"));
    } else {
      pending.resolve(message.result);
    }
    return;
  }
  if (message.method === "ui/themeChanged") {
    applyTheme(message.params);
  }
});

const els = {
  routeSelect: document.getElementById("routeSelect"),
  expectedSelect: document.getElementById("expectedSelect"),
  maskIpToggle: document.getElementById("maskIpToggle"),
  copyBtn: document.getElementById("copyBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  refreshSpinner: document.getElementById("refreshSpinner"),
  refreshLabel: document.getElementById("refreshLabel"),
  summaryBanner: document.getElementById("summaryBanner"),
  summaryPill: document.getElementById("summaryPill"),
  summaryTitle: document.getElementById("summaryTitle"),
  summaryMeta: document.getElementById("summaryMeta"),
  summaryBadges: document.getElementById("summaryBadges"),
  baselineSource: document.getElementById("baselineSource"),
  baselineGrid: document.getElementById("baselineGrid"),
  providersGrid: document.getElementById("providersGrid"),
};

const appState = {
  routeId: "default",
  expectedCountry: "",
  hideIp: false,
  lastReport: null,
  loading: false,
};

function maskIpText(ip) {
  const raw = String(ip || "").trim();
  if (!raw) return "—";
  if (!appState.hideIp) return raw;
  if (raw.includes(".")) {
    const parts = raw.split(".");
    if (parts.length === 4) {
      return `${parts[0]}.${parts[1]}.***.${parts[3]}`;
    }
  }
  if (raw.includes(":")) {
    const parts = raw.split(":").filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0]}:****:****:${parts[parts.length - 1]}`;
    }
  }
  return raw;
}

function maskTextIps(text) {
  const s = String(text || "");
  if (!appState.hideIp) return s;
  return s.replace(/\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b/g, "$1.$2.***.$4");
}

function parseToolJson(res) {
  const chunks = Array.isArray(res?.content) ? res.content : [];
  const text = chunks
    .filter((item) => item && item.type === "text" && typeof item.text === "string")
    .map((item) => item.text)
    .join("\n")
    .trim();
  if (res?.isError) {
    throw new Error(text || "检测调用失败");
  }
  return JSON.parse(text || "{}");
}

async function persistState() {
  try {
    await request("ui/setState", {
      state: {
        routeId: appState.routeId,
        expectedCountry: appState.expectedCountry,
        hideIp: appState.hideIp,
        lastReport: appState.lastReport,
      },
    });
  } catch {
    // Ignore persistence quota or transient bridge errors.
  }
}

function createBrandSvg(provider) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("width", "20");
  svg.setAttribute("height", "20");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");

  if (provider === "google") {
    const defs = document.createElementNS(ns, "defs");
    const clip = document.createElementNS(ns, "clipPath");
    clip.setAttribute("id", "agy-clip");
    const clipPath = document.createElementNS(ns, "path");
    clipPath.setAttribute("d", ANTIGRAVITY_ARCH_PATH);
    clip.appendChild(clipPath);

    const g1 = document.createElementNS(ns, "linearGradient");
    g1.setAttribute("id", "agy-crown");
    g1.setAttribute("x1", "3");
    g1.setAttribute("y1", "2");
    g1.setAttribute("x2", "21");
    g1.setAttribute("y2", "2");
    g1.setAttribute("gradientUnits", "userSpaceOnUse");
    for (const [offset, color] of [["0%", "#00B95C"], ["50%", "#FBBC04"], ["100%", "#EA4335"]]) {
      const stop = document.createElementNS(ns, "stop");
      stop.setAttribute("offset", offset);
      stop.setAttribute("stop-color", color);
      g1.appendChild(stop);
    }

    const g2 = document.createElementNS(ns, "linearGradient");
    g2.setAttribute("id", "agy-body");
    g2.setAttribute("x1", "12");
    g2.setAttribute("y1", "5");
    g2.setAttribute("x2", "12");
    g2.setAttribute("y2", "22");
    g2.setAttribute("gradientUnits", "userSpaceOnUse");
    for (const [offset, color, op] of [["0%", "#3186FF", "0"], ["48%", "#3186FF", "0.92"], ["100%", "#2563EB", "1"]]) {
      const stop = document.createElementNS(ns, "stop");
      stop.setAttribute("offset", offset);
      stop.setAttribute("stop-color", color);
      stop.setAttribute("stop-opacity", op);
      g2.appendChild(stop);
    }

    defs.append(clip, g1, g2);
    const group = document.createElementNS(ns, "g");
    group.setAttribute("clip-path", "url(#agy-clip)");
    for (const fill of ["url(#agy-crown)", "url(#agy-body)"]) {
      const rect = document.createElementNS(ns, "rect");
      rect.setAttribute("width", "24");
      rect.setAttribute("height", "24");
      rect.setAttribute("fill", fill);
      group.appendChild(rect);
    }
    svg.append(defs, group);
    return svg;
  }

  if (provider === "anthropic") {
    const path = document.createElementNS(ns, "path");
    path.setAttribute("fill", "#D97757");
    path.setAttribute("d", CLAUDE_MARK_PATH);
    svg.appendChild(path);
    return svg;
  }

  const defs = document.createElementNS(ns, "defs");
  const grad = document.createElementNS(ns, "linearGradient");
  grad.setAttribute("id", "codex-grad");
  grad.setAttribute("x1", "0");
  grad.setAttribute("y1", "0");
  grad.setAttribute("x2", "24");
  grad.setAttribute("y2", "24");
  grad.setAttribute("gradientUnits", "userSpaceOnUse");
  for (const [offset, color] of [["0%", "#7E46FF"], ["100%", "#2762EE"]]) {
    const stop = document.createElementNS(ns, "stop");
    stop.setAttribute("offset", offset);
    stop.setAttribute("stop-color", color);
    grad.appendChild(stop);
  }
  defs.appendChild(grad);
  const path = document.createElementNS(ns, "path");
  path.setAttribute("fill", "url(#codex-grad)");
  path.setAttribute("fill-rule", "evenodd");
  path.setAttribute("clip-rule", "evenodd");
  path.setAttribute("d", CODEX_MARK_PATH);
  svg.append(defs, path);
  return svg;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function verdictInfo(verdict) {
  if (verdict === "ok") return { tone: "ok", label: "地区对应 · 可用" };
  if (verdict === "warn") return { tone: "warn", label: "存在偏差" };
  if (verdict === "blocked") return { tone: "blocked", label: "地区受限" };
  return { tone: "blocked", label: "连接失败" };
}

function renderLoadingSkeleton() {
  els.providersGrid.replaceChildren();
  for (const key of ["google", "anthropic", "openai"]) {
    const meta = PROVIDER_META[key];
    const card = el("div", "provider-card skeleton-card");
    card.textContent = `正在探测 ${meta.title} (${meta.subtitle})…`;
    els.providersGrid.appendChild(card);
  }
}

function formatCheckedTime(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "";
  return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function renderReport(report) {
  if (!report) return;
  els.copyBtn.disabled = false;

  const tone =
    report.overall_status === "ok"
      ? "ok"
      : report.overall_status === "warn"
        ? "warn"
        : "blocked";

  els.summaryBanner.dataset.tone = tone;
  els.summaryPill.dataset.tone = tone;
  els.summaryPill.textContent =
    tone === "ok"
      ? "三端一致 · 可用"
      : tone === "warn"
        ? "存在分流或地区偏差"
        : "受限或连接异常";
  els.summaryTitle.textContent = maskTextIps(report.summary || "");

  const timeText = formatCheckedTime(report.checked_at);
  const routeLabel =
    report.route && report.route !== "default"
      ? `独立账号出口 (${report.route.slice(0, 8)}…)`
      : "默认网络出口";
  els.summaryMeta.textContent = `检测出口：${routeLabel}${timeText ? ` · 更新于 ${timeText}` : ""}`;

  els.summaryBadges.replaceChildren();
  const ipBadge = el(
    "span",
    "mini-badge",
    report.all_ips_consistent ? "出口 IP：三端一致" : "出口 IP：存在分流差异"
  );
  ipBadge.dataset.tone = report.all_ips_consistent ? "ok" : "warn";

  const regionBadge = el(
    "span",
    "mini-badge",
    report.all_regions_consistent ? "识别地区：三端一致" : "识别地区：存在不一致"
  );
  regionBadge.dataset.tone = report.all_regions_consistent ? "ok" : "warn";
  els.summaryBadges.append(ipBadge, regionBadge);

  if (report.expected_country) {
    const expOk = (report.providers || []).every(
      (p) => p.country && p.country === report.expected_country
    );
    const expBadge = el(
      "span",
      "mini-badge",
      expOk ? `符合期望 (${report.expected_country})` : `偏离期望 (${report.expected_country})`
    );
    expBadge.dataset.tone = expOk ? "ok" : "warn";
    els.summaryBadges.appendChild(expBadge);
  }

  // Baseline card
  const base = report.baseline || {};
  els.baselineSource.textContent = base.ok
    ? `数据源：${base.source}${base.latency_ms ? ` · ${base.latency_ms} ms` : ""}`
    : `基准查询异常：${base.error || "不可用"}`;

  const locParts = [base.city, base.region].filter(Boolean).join(", ") || "—";
  const baseItems = [
    ["出口 IP", maskIpText(base.ip), true],
    ["GeoIP 标称地区", base.country_label || "—", false],
    ["城市 / 区域", locParts, false],
    ["运营商 / ASN", base.org || "—", false],
  ];
  els.baselineGrid.replaceChildren();
  for (const [label, value, isMono] of baseItems) {
    const item = el("div", "metric-item");
    item.appendChild(el("span", "metric-label", label));
    const valNode = el("span", isMono ? "metric-value mono" : "metric-value", value);
    valNode.title = value;
    item.appendChild(valNode);
    els.baselineGrid.appendChild(item);
  }

  // Provider cards
  els.providersGrid.replaceChildren();
  for (const prov of report.providers || []) {
    const meta = PROVIDER_META[prov.provider] || { title: prov.name, subtitle: "" };
    const vInfo = verdictInfo(prov.verdict);
    const card = el("article", "provider-card");
    card.dataset.tone = vInfo.tone;

    const header = el("div", "provider-header");
    const brand = el("div", "provider-brand");
    const iconWrap = el("div", "brand-icon-wrap");
    iconWrap.appendChild(createBrandSvg(prov.provider));
    const titleWrap = el("div");
    titleWrap.appendChild(el("div", "provider-title", meta.title));
    titleWrap.appendChild(el("div", "provider-sub", meta.subtitle));
    brand.append(iconWrap, titleWrap);

    const pill = el("span", "status-pill", vInfo.label);
    pill.dataset.tone = vInfo.tone;
    header.append(brand, pill);
    card.appendChild(header);

    // Region & IP box
    const regionBox = el("div", "region-highlight");
    const regionRow = el("div", "region-row");
    regionRow.appendChild(el("span", "kv-key", "官方识别地区"));
    regionRow.appendChild(
      el("span", "region-big", prov.country_label || (prov.reachable ? "未知" : "未获取"))
    );
    regionBox.appendChild(regionRow);

    // Match relation row
    const matchRow = el("div", "kv-row");
    matchRow.appendChild(el("span", "kv-key", "与基准地区对应"));
    let relationText = "—";
    if (prov.country && base.country) {
      if (prov.matches_baseline_region) {
        relationText = "一致";
      } else if (prov.same_ip_as_baseline) {
        relationText = `不一致 · 同 IP 库偏差（基准 ${base.country}）`;
      } else {
        relationText = `不一致 · 分流至 ${prov.country}（基准 ${base.country}）`;
      }
    } else if (prov.country) {
      relationText = `已识别 (${prov.country})`;
    }
    matchRow.appendChild(el("span", "kv-val", relationText));
    regionBox.appendChild(matchRow);

    // Seen IP row
    const ipRow = el("div", "kv-row");
    ipRow.appendChild(el("span", "kv-key", "平台看到的 IP"));
    const ipSuffix = prov.same_ip_as_baseline
      ? " (同主出口)"
      : prov.split_routed
        ? " (独立分流)"
        : "";
    ipRow.appendChild(el("span", "kv-val mono", `${maskIpText(prov.ip)}${prov.ip ? ipSuffix : ""}`));
    regionBox.appendChild(ipRow);

    // OpenAI OAuth comparison row when available
    if (prov.provider === "openai" && (prov.auth_ip || prov.auth_country)) {
      const authRow = el("div", "kv-row");
      authRow.appendChild(el("span", "kv-key", "Codex 授权页识别"));
      const authDesc = `${prov.auth_country || "?"} · ${maskIpText(prov.auth_ip)}`;
      authRow.appendChild(el("span", "kv-val mono", authDesc));
      regionBox.appendChild(authRow);
    }

    // Edge / latency row
    const edgeRow = el("div", "kv-row");
    edgeRow.appendChild(el("span", "kv-key", "边缘节点 / 延迟"));
    const edgeParts = [];
    if (prov.colo) edgeParts.push(prov.colo);
    if (typeof prov.latency_ms === "number") edgeParts.push(`${prov.latency_ms} ms`);
    edgeRow.appendChild(el("span", "kv-val mono", edgeParts.join(" · ") || "—"));
    regionBox.appendChild(edgeRow);

    card.appendChild(regionBox);

    // Sub-services chips
    const svcEntries = Object.entries(prov.services || {});
    if (svcEntries.length > 0) {
      const svcBlock = el("div", "services-block");
      svcBlock.appendChild(el("span", "metric-label", "子端点连通与风控检查"));
      const svcList = el("div", "services-list");
      for (const [svcKey, svcVal] of svcEntries) {
        const ok = Boolean(svcVal && svcVal.ok);
        const chip = el("span", "svc-chip");
        chip.dataset.ok = String(ok);
        chip.appendChild(el("span", "svc-dot"));
        let label = SERVICE_LABELS[svcKey] || svcKey;
        if (svcVal?.region_blocked || svcVal?.region_blocked_redirect) {
          label += " (地区拦截)";
        } else if (!ok && svcVal?.status) {
          label += ` (${svcVal.status})`;
        }
        chip.appendChild(document.createTextNode(label));
        svcList.appendChild(chip);
      }
      svcBlock.appendChild(svcList);
      card.appendChild(svcBlock);
    }

    // Diagnostic notes
    const notes = Array.isArray(prov.notes) ? prov.notes : [];
    if (notes.length > 0) {
      const ul = el("ul", "notes-list");
      for (const note of notes) {
        ul.appendChild(el("li", "", maskTextIps(note)));
      }
      card.appendChild(ul);
    }

    els.providersGrid.appendChild(card);
  }
}

function populateRoutes(routes) {
  els.routeSelect.replaceChildren();
  const items = Array.isArray(routes) && routes.length > 0
    ? routes
    : [{ id: "default", label: "默认网络出口" }];
  let foundCurrent = false;
  for (const r of items) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = r.label;
    if (r.id === appState.routeId) foundCurrent = true;
    els.routeSelect.appendChild(opt);
  }
  if (!foundCurrent) {
    appState.routeId = "default";
  }
  els.routeSelect.value = appState.routeId;
}

async function loadRoutes() {
  try {
    const res = await request("tools/call", { name: "list_exit_routes", arguments: {} });
    const data = parseToolJson(res);
    populateRoutes(data.routes);
  } catch {
    populateRoutes([{ id: "default", label: "默认网络出口" }]);
  }
}

async function runCheck() {
  if (appState.loading) return;
  appState.loading = true;
  els.refreshBtn.disabled = true;
  els.refreshSpinner.hidden = false;
  els.refreshLabel.textContent = "检测中…";

  if (!appState.lastReport) {
    renderLoadingSkeleton();
  }
  els.summaryPill.dataset.tone = "neutral";
  els.summaryPill.textContent = "正在探测";
  els.summaryTitle.textContent = "正在并发请求 Google、Anthropic、OpenAI 官方边缘节点…";

  try {
    await loadRoutes();
    const res = await request("tools/call", {
      name: "check_ai_exit_regions",
      arguments: {
        route_id: appState.routeId,
        expected_country: appState.expectedCountry,
      },
    });
    const report = parseToolJson(res);
    appState.lastReport = report;
    renderReport(report);
    await persistState();
  } catch (err) {
    els.summaryBanner.dataset.tone = "blocked";
    els.summaryPill.dataset.tone = "blocked";
    els.summaryPill.textContent = "检测失败";
    els.summaryTitle.textContent = err?.message || "无法完成出口与地区检测";
    els.summaryMeta.textContent = "请确认运行环境已启动且代理连接可用后重试";
  } finally {
    appState.loading = false;
    els.refreshBtn.disabled = false;
    els.refreshSpinner.hidden = true;
    els.refreshLabel.textContent = "重新检测";
  }
}

function buildPlainReport(report) {
  if (!report) return "";
  const base = report.baseline || {};
  const lines = [
    "=== AI 出口与地区对应检测报告 ===",
    `时间: ${report.checked_at || ""}`,
    `结论: ${maskTextIps(report.summary || "")}`,
    `基准出口: ${maskIpText(base.ip)} | GeoIP: ${base.country_label || "未知"} | ${base.org || ""}`,
    "",
  ];
  for (const p of report.providers || []) {
    lines.push(
      `- ${p.name}: 识别地区=${p.country_label || "未知"} | 出口IP=${maskIpText(p.ip)}${
        p.colo ? ` | 节点=${p.colo}` : ""
      } | 状态=${p.verdict}`
    );
    for (const n of p.notes || []) {
      lines.push(`  · ${maskTextIps(n)}`);
    }
  }
  return lines.join("\n");
}

els.refreshBtn.addEventListener("click", () => {
  runCheck();
});

els.routeSelect.addEventListener("change", () => {
  appState.routeId = els.routeSelect.value || "default";
  runCheck();
});

els.expectedSelect.addEventListener("change", () => {
  appState.expectedCountry = els.expectedSelect.value || "";
  runCheck();
});

els.maskIpToggle.addEventListener("change", () => {
  appState.hideIp = Boolean(els.maskIpToggle.checked);
  if (appState.lastReport) {
    renderReport(appState.lastReport);
  }
  persistState();
});

els.copyBtn.addEventListener("click", async () => {
  if (!appState.lastReport) return;
  try {
    await request("ui/copy", { text: buildPlainReport(appState.lastReport) });
    await request("ui/notify", { message: "已复制 AI 出口与地区检测报告", tone: "info" });
  } catch (err) {
    await request("ui/notify", { message: err?.message || "复制失败", tone: "error" });
  }
});

const init = await request("ui/initialize", { protocolVersion: 1 });
applyTheme(init?.theme);

if (init?.state && typeof init.state === "object") {
  if (typeof init.state.routeId === "string") appState.routeId = init.state.routeId;
  if (typeof init.state.expectedCountry === "string") {
    appState.expectedCountry = init.state.expectedCountry;
    els.expectedSelect.value = appState.expectedCountry;
  }
  if (typeof init.state.hideIp === "boolean") {
    appState.hideIp = init.state.hideIp;
    els.maskIpToggle.checked = appState.hideIp;
  }
  if (init.state.lastReport && typeof init.state.lastReport === "object") {
    appState.lastReport = init.state.lastReport;
    renderReport(appState.lastReport);
  }
}

await loadRoutes();
await runCheck();
