/* ============================================================
   ModelSmith · application (SPA)
   Sidebar shell · bento dashboard · command palette · deep model views
   ============================================================ */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const state = {
  token: localStorage.getItem("ms_token") || null,
  user: JSON.parse(localStorage.getItem("ms_user") || "null"),
  pollTimers: [],
  cmdkIndex: 0,
};

/* ---------------- helpers ---------------- */
const fmtBytes = n => {
  if (n == null) return "-";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + " GB";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + " MB";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + " KB";
  return n + " B";
};
const fmtNum = n => (n ?? 0).toLocaleString("en-US");
const fmtPct = n => n == null ? "-" : n + "%";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const timeago = ts => {
  if (!ts) return "";
  const s = Math.floor(Date.now() / 1000 - ts);
  if (s < 90) return s + "s ago";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
};
const initials = u => (u?.full_name || u?.email || "?").split(/[\s@.]+/).filter(Boolean)
  .slice(0, 2).map(w => w[0].toUpperCase()).join("");

/* toast system: multi-toast stacking, no single-element overwrite */
const TOAST_MAX = 4;
/* custom SVG empty-state illustrations: no emoji, hand-drawn forge style */
function emptySVG(type) {
  const svgs = {
    project: `<svg viewBox="0 0 200 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="30" y="20" width="140" height="80" rx="12" stroke="#2b2517" stroke-width="2" stroke-dasharray="6 4"/>
      <path d="M60 55 L80 55 L85 45 L100 65 L110 50 L115 55 L140 55" stroke="#ffb224" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.6"/>
      <circle cx="55" cy="42" r="4" fill="#ff6b2c" opacity="0.5"/>
      <circle cx="145" cy="75" r="3" fill="#4ade80" opacity="0.4"/>
      <line x1="60" y1="80" x2="120" y2="80" stroke="#3d3520" stroke-width="1.5" stroke-linecap="round"/>
      <line x1="65" y1="88" x2="105" y2="88" stroke="#3d3520" stroke-width="1.5" stroke-linecap="round" opacity="0.5"/>
    </svg>`,
    model: `<svg viewBox="0 0 200 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="50" y="30" width="100" height="70" rx="10" stroke="#2b2517" stroke-width="2" stroke-dasharray="6 4"/>
      <path d="M70 55 L90 55" stroke="#ffb224" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
      <path d="M70 65 L110 65" stroke="#ffb224" stroke-width="2" stroke-linecap="round" opacity="0.4"/>
      <path d="M70 75 L100 75" stroke="#ffb224" stroke-width="2" stroke-linecap="round" opacity="0.3"/>
      <path d="M120 50 L135 60 L120 70 Z" fill="#ff6b2c" opacity="0.4"/>
      <circle cx="100" cy="25" r="8" stroke="#2b2517" stroke-width="1.5" stroke-dasharray="3 2"/>
      <line x1="100" y1="17" x2="100" y2="33" stroke="#2b2517" stroke-width="1" opacity="0.3"/>
      <line x1="92" y1="25" x2="108" y2="25" stroke="#2b2517" stroke-width="1" opacity="0.3"/>
    </svg>`,
    search: `<svg viewBox="0 0 200 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="85" cy="55" r="28" stroke="#2b2517" stroke-width="2.5" stroke-dasharray="6 4"/>
      <line x1="105" y1="75" x2="130" y2="100" stroke="#ffb224" stroke-width="3" stroke-linecap="round" opacity="0.6"/>
      <circle cx="80" cy="48" r="2" fill="#ff6b2c" opacity="0.4"/>
      <circle cx="92" cy="60" r="2" fill="#4ade80" opacity="0.4"/>
    </svg>`,
    jobs: `<svg viewBox="0 0 200 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="40" y="25" width="50" height="35" rx="6" stroke="#2b2517" stroke-width="1.5" stroke-dasharray="4 3"/>
      <rect x="55" y="35" width="20" height="3" rx="1.5" fill="#ffb224" opacity="0.4"/>
      <rect x="55" y="42" width="14" height="3" rx="1.5" fill="#ffb224" opacity="0.3"/>
      <path d="M95 42 L110 42 L110 55 L95 55 Z" stroke="#ff6b2c" stroke-width="1.5" fill="none" opacity="0.5"/>
      <path d="M120 30 L135 30 L135 45 L120 45 Z" stroke="#4ade80" stroke-width="1.5" fill="none" opacity="0.5"/>
      <path d="M110 55 L125 55 L125 70 L110 70 Z" stroke="#ffb224" stroke-width="1.5" fill="none" opacity="0.5"/>
      <path d="M135 45 L150 45 L150 60 L135 60 Z" stroke="#2b2517" stroke-width="1.5" fill="none" opacity="0.3"/>
      <circle cx="48" cy="82" r="4" fill="#ffb224" opacity="0.3"/>
      <circle cx="62" cy="85" r="3" fill="#ff6b2c" opacity="0.3"/>
      <circle cx="75" cy="80" r="3.5" fill="#4ade80" opacity="0.3"/>
    </svg>`,
  };
  return svgs[type] || svgs.project;
}

/* animated number count-up: cubic ease-out, respects reduced motion */
function countUp(el, target, { decimals = 0, suffix = "", prefix = "", dur = 900 } = {}) {
  const startVal = 0;
  const t0 = performance.now();
  el.classList.add("counting");
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    el.textContent = prefix + target.toLocaleString("en-US", { maximumFractionDigits: decimals }) + suffix;
    return;
  }
  const tick = now => {
    const p = Math.min(1, (now - t0) / dur);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = prefix + (startVal + (target - startVal) * eased)
      .toLocaleString("en-US", { maximumFractionDigits: decimals, minimumFractionDigits: 0 }) + suffix;
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* ---------------- guided product tour ---------------- */
const TOUR_KEY = "ms_tour_done";
const TOUR_STEPS = [
  { sel: ".side-nav .side-item", title: "Your workspace", body: "Projects group your models, runs and artifacts, isolated per account." },
  { sel: ".search-pill", title: "Search anything, instantly", body: "Press ⌘K anywhere to open the command palette. Models, actions, pages, no mouse required." },
  { sel: ".bell-btn", title: "Stay in the loop", body: "Background jobs report here the moment they finish. Good news and bad news travel equally fast." },
  { sel: ".avatar", title: "Your account", body: "Your profile, password and session details live here. So does your activity history." },
];
function startTour(force = false) {
  if (!force && localStorage.getItem(TOUR_KEY)) return;
  if (!state.token || !$(".shell")) return;
  localStorage.setItem(TOUR_KEY, "1");
  let step = 0;
  const backdrop = document.createElement("div");
  backdrop.className = "tour-backdrop";
  const spotlight = document.createElement("div");
  spotlight.className = "tour-spotlight";
  const card = document.createElement("div");
  card.className = "tour-card";
  document.body.append(backdrop, spotlight, card);

  function cleanup() { backdrop.remove(); spotlight.remove(); card.remove(); document.removeEventListener("keydown", esc); }
  const esc = e => { if (e.key === "Escape") cleanup(); };
  document.addEventListener("keydown", esc);
  backdrop.addEventListener("click", cleanup);
  function render() {
    const s = TOUR_STEPS[step];
    const target = $(s.sel);
    if (!target) { cleanup(); return; }
    const r = target.getBoundingClientRect();
    spotlight.style.cssText += `left:${r.left - 8}px;top:${r.top - 8}px;width:${r.width + 16}px;height:${r.height + 16}px;`;
    const below = r.bottom + 330 > innerHeight;
    card.style.left = Math.max(12, Math.min(r.left, innerWidth - 360)) + "px";
    card.style.top = below ? Math.max(12, r.top - 200) + "px" : (r.bottom + 16) + "px";
    card.innerHTML = `
      <span class="step-pill">Step ${step + 1} of ${TOUR_STEPS.length}</span>
      <h3>${esc(s.title)}</h3><p>${esc(s.body)}</p>
      <div class="tour-actions">
        ${step > 0 ? '<button class="btn small ghost" id="tPrev">Back</button>' : ""}
        ${step < TOUR_STEPS.length - 1
          ? '<button class="btn primary" id="tNext">Next →</button>'
          : '<button class="btn primary" id="tDone">Finish ✦</button>'}
        <div class="tour-dots">${TOUR_STEPS.map((_, i) => `<i class="${i === step ? "on" : ""}"></i>`).join("")}</div>
      </div>
      <button class="btn small ghost" id="tSkip" style="position:absolute;top:14px;right:14px;padding:3px 9px">Skip</button>`;
    $("#tNext", card)?.addEventListener("click", () => { step++; render(); });
    $("#tPrev", card)?.addEventListener("click", () => { step--; render(); });
    $("#tDone", card)?.addEventListener("click", () => { cleanup(); toast("Tour complete. Press ? any time for shortcuts"); });
    $("#tSkip", card)?.addEventListener("click", cleanup);
  }
  render();
}

function toast(msg, isErr = false, duration = 3800, action = null) {
  const rack = $("#toastRack") || (() => {
    const el = document.createElement("div");
    el.id = "toastRack";
    el.className = "toast-rack";
    document.body.appendChild(el);
    return el;
  })();
  const t = document.createElement("div");
  t.className = "toast-item" + (isErr ? " err" : "");
  t.innerHTML = `<span>${esc(msg)}</span>
    ${action ? `<button class="toast-act">${esc(action.label)}</button>` : ""}
    <button class="toast-x" aria-label="dismiss">×</button>`;
  rack.appendChild(t);
  requestAnimationFrame(() => t.classList.add("in"));
  const dismiss = () => { t.classList.remove("in"); setTimeout(() => t.remove(), 300); };
  t.querySelector(".toast-x").onclick = dismiss;
  if (action) t.querySelector(".toast-act").onclick = () => { action.run(); dismiss(); };
  setTimeout(dismiss, duration);
  while (rack.children.length > TOAST_MAX) rack.firstChild.remove();
}

/* clipboard with graceful fallback */
function copyText(text, label = "Copied to clipboard") {
  const done = () => toast(label);
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
  } else fallbackCopy(text, done);
}
function fallbackCopy(text, done) {
  const ta = document.createElement("textarea");
  ta.value = text; ta.style.cssText = "position:fixed;opacity:0";
  document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); done(); } catch { toast("Copy failed", true); }
  ta.remove();
}

async function api(path, opts = {}) {
  const headers = opts.headers || {};
  if (opts.body && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const resp = await fetch(path, { ...opts, headers });
  if (resp.status === 401) { logoutLocal(); throw new Error("Session expired. Log in again."); }
  const ct = resp.headers.get("Content-Type") || "";
  const data = ct.includes("json") ? await resp.json() : await resp.blob();
  if (!resp.ok) {
    const detail = data && data.detail ? data.detail : `Request failed (${resp.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}
/* ================= DEMO MODE (static deployment) =================
   No backend is present in this deployment. api() answers from a
   captured snapshot of the real workspace. Every write is refused
   with an honest message instead of failing silently. */
const SNAPSHOT_READY = (async () => {
  // wait briefly for the loader's fetch, then fetch it ourselves if needed
  for (let i = 0; i < 40 && !window.MS_SNAPSHOT; i++)
    await new Promise(r => setTimeout(r, 25));
  if (!window.MS_SNAPSHOT) {
    try {
      window.MS_SNAPSHOT = await fetch("/api-snapshot.json").then(r => r.json());
    } catch {}
  }
  return window.MS_SNAPSHOT;
})();

function _snapRoute(path, opts = {}) {
  const p = path.split("?")[0];
  const q = new URLSearchParams(path.split("?")[1] || "");
  const S = window.MS_SNAPSHOT || {};
  if (p === "/api/health") return S.health;
  if (p === "/api/config") return S.config;
  if (p === "/api/auth/me" && opts.method === "PATCH")
    throw new Error("Profile editing needs the full deployment");
  if (p === "/api/auth/me") return S.me;
  if (p === "/api/auth/me/session") return S.session;
  if (p === "/api/auth/me/activity") return S.activity;
  if (p === "/api/auth/login" || p === "/api/auth/logout") {
    if (p === "/api/auth/logout") { return { message: "Logged out" }; }
    return { token: "demo-snapshot", user: S.me };
  }
  if (p === "/api/dashboard") return S.dashboard;
  if (p === "/api/dashboard/stats") return S.dashboard_stats;
  if (p === "/api/dashboard/activity") return S.dashboard_activity;
  if (p === "/api/dashboard/insights") return S.insights;
  if (p === "/api/achievements") return S.achievements;
  if (p === "/api/notifications") return S.notifications;
  if (p === "/api/notifications/read") return { ok: true };
  if (p === "/api/jobs") {
    const st = q.get("status");
    const jobs = (S.jobs?.jobs || []).filter(j => !st || j.status === st);
    return { jobs };
  }
  if (p === "/api/projects" && opts.method === "POST")
    throw new Error("Creating projects needs the full deployment");
  if (p === "/api/projects/export/json") return { data: (S.projects.projects || []).map(p2 => ({ ...p2 })) };
  if (p === "/api/projects") return S.projects;
  const proj = p.match(/^\/api\/projects\/([\w-]+)$/);
  if (proj) return S["project_" + proj[1]] || S["projectstats_" + proj[1]];
  const pstats = p.match(/^\/api\/projects\/([\w-]+)\/stats$/);
  if (pstats) return S["projectstats_" + pstats[1]];
  if (p === "/api/search") {
    const term = (q.get("q") || "").toLowerCase();
    const st2 = q.get("status") || "";
    const res = (S.search_results?.results || [])
      .filter(r => (!term || r.name.toLowerCase().includes(term)
                    || r.framework.toLowerCase().includes(term)
                    || r.project.toLowerCase().includes(term))
                  && (!st2 || r.status === st2));
    return { results: res, total: res.length, scanned: S.search_results?.scanned || res.length };
  }
  const cmp = p.match(/^\/api\/models\/compare\?model_a=([\w-]+)&model_b=([\w-]+)$/);
  if (cmp) {
    const a = S["model_" + cmp[1]], b = S["model_" + cmp[2]];
    return { model_a: { id: a.id, name: a.name, framework: a.framework,
                        size_bytes: a.size_bytes, analysis: a.analysis },
             model_b: { id: b.id, name: b.name, framework: b.framework,
                        size_bytes: b.size_bytes, analysis: b.analysis } };
  }
  const mod = p.match(/^\/api\/models\/([\w-]+)$/);
  if (mod) {
    if (opts.method === "PATCH" || opts.method === "DELETE")
      throw new Error("This action needs the full deployment");
    return S["model_" + mod[1]];
  }
  const hist = p.match(/^\/api\/models\/([\w-]+)\/history$/);
  if (hist) return S["history_" + hist[1]];
  const sugg = p.match(/^\/api\/models\/([\w-]+)\/suggestions$/);
  if (sugg) return S["suggestions_" + sugg[1]];
  const diff = p.match(/^\/api\/models\/([\w-]+)\/diff$/);
  if (diff) return S["diff_" + diff[1]];
  const share = p.match(/^\/api\/share\/([\w-]+)$/);
  if (share) return (S.shares || {})[share[1]] || null;
  const run = p.match(/^\/api\/runs\/([\w-]+)$/);
  if (run) {
    for (const k of Object.keys(S)) {
      if (k.startsWith("model_")) {
        const r = (S[k].runs || []).find(x => x.id === run[1]);
        if (r) return r;
      }
    }
    return null;
  }
  if (p === "/api/models/upload")
    throw new Error("Uploading models needs the full deployment. Run the repo locally with ./run.sh");
  if (/POST|PATCH|DELETE|PUT/.test(opts.method || "GET"))
    throw new Error("This action needs the full deployment. Run the repo locally with ./run.sh");
  return null;
}

/* wrap api(): demo mode intercepts reads and refuses writes */
const _realApi = api;
api = async function(path, opts = {}) {
  if (location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
    await (window.MS_SNAPSHOT ? Promise.resolve() : SNAPSHOT_READY);
    const method = (opts.method || "GET").toUpperCase();
    if (method !== "GET") {
      throw new Error("Read-only demo. Run the repo locally for the full pipeline.");
    }
    const data = _snapRoute(path, opts);
    if (data == null) throw new Error("Not available in this demo snapshot");
    return data;
  }
  return _realApi(path, opts);
};

function logoutLocal() {
  state.token = null; state.user = null;
  localStorage.removeItem("ms_token"); localStorage.removeItem("ms_user");
  location.hash = "#/login";
}
function stopPolling() { state.pollTimers.forEach(clearInterval); state.pollTimers = []; }
function poll(fn, ms = 1800) { state.pollTimers.push(setInterval(fn, ms)); fn(); }

/* modal system: custom, no native dialogs */
function openModal(html, { okLabel, onOk, wide } = {}) {
  const root = $("#modalRoot");
  root.innerHTML = `<div class="modal-back"><div class="modal-box" ${wide ? 'style="width:min(720px,94vw)"' : ""}>${html}</div></div>`;
  root.hidden = false;
  $(".modal-back", root).onclick = e => { if (e.target === e.currentTarget) closeModal(); };
  document.onkeydown = e => { if (e.key === "Escape") closeModal(); };
  const ok = $("#mOk", root);
  if (ok && onOk) ok.onclick = async () => {
    ok.disabled = true;
    try { if (await onOk() !== false) closeModal(); }
    catch (e) { toast(e.message, true); }
    ok.disabled = false;
  };
  const first = $("input,textarea,select", root);
  if (first) first.focus();
  return root;
}
function closeModal() { $("#modalRoot").hidden = true; $("#modalRoot").innerHTML = ""; document.onkeydown = null; }
function confirmModal(title, body, okLabel = "Confirm") {
  return new Promise(res => {
    openModal(`<h3>${esc(title)}</h3><p style="color:var(--dim);font-size:13.5px">${esc(body)}</p>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px">
        <button class="btn ghost" id="mCancel">Cancel</button>
        <button class="btn danger" id="mOk">${esc(okLabel)}</button></div>`);
    $("#mCancel").onclick = () => { closeModal(); res(false); };
    $("#mOk").onclick = () => { closeModal(); res(true); };
  });
}

/* ---------------- router ---------------- */
const routes = [
  [/^#\/welcome$/, viewLanding],
  [/^#\/login$/, () => viewLogin()],
  [/^#\/register$/, () => viewLogin(true)],
  [/^#\/dashboard$/, viewDashboard],
  [/^#\/projects$/, viewProjects],
  [/^#\/project\/([\w-]+)$/, pid => viewProject(pid)],
  [/^#\/model\/([\w-]+)(?:\/(\w+))?$/, (mid, tab) => viewModel(mid, tab || "overview")],
  [/^#\/compare\/([\w-]+)\/([\w-]+)$/, (a, b) => viewCompare(a, b)],
  [/^#\/admin$/, viewAdmin],
  [/^#\/settings$/, viewSettings],
  [/^#\/search$/, viewSearch],
  [/^#\/jobs$/, viewJobs],
  [/^#\/api$/, viewApiPlayground],
  [/^#\/achievements$/, viewAchievements],
  [/^#\/share\/([\w-]+)$/, t => viewShare(t)],
];
function render() {
  stopPolling(); closeModal();
  $("#notifPanel")?.remove();
  const hash = location.hash || (state.token ? "#/dashboard" : "#/welcome");
  for (const [re, fn] of routes) {
    const m = hash.match(re);
    if (m) { fn(...m.slice(1)); return; }
  }
  view404();
}
window.addEventListener("hashchange", render);

/* ---------------- avatar hue helper ---------------- */
function avatarHue(name) {
  let h = 0;
  for (let i = 0; i < (name || "").length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
  return Math.abs(h) % 8;
}
function avatarHTML(user, big = false) {
  const hue = avatarHue(user?.full_name || user?.email || "");
  return `<div class="avatar ${big ? "big " : ""}avatar-${hue}">${esc(initials(user))}</div>`;
}

/* ---------------- app shell ---------------- */
function shell({ active, crumbs = "", actions = "" }, contentHTML) {
  const isAdmin = state.user?.role === "admin";
  const navItems = `
        <div class="side-label">Workspace</div>
        <nav class="side-nav">
          <a class="side-item ${active === "dashboard" ? "active" : ""}" href="#/dashboard">
            <span class="ico">◈</span> Dashboard</a>
          <a class="side-item ${active === "projects" ? "active" : ""}" href="#/projects">
            <span class="ico">▤</span> Projects</a>
          <a class="side-item ${active === "jobs" ? "active" : ""}" href="#/jobs">
            <span class="ico">⚙</span> Jobs</a>
          <a class="side-item ${active === "api" ? "active" : ""}" href="#/api">
            <span class="ico">⌘</span> API playground</a>
          <a class="side-item ${active === "achievements" ? "active" : ""}" href="#/achievements">
            <span class="ico">★</span> Achievements</a>
          <a class="side-item ${active === "settings" ? "active" : ""}" href="#/settings">
            <span class="ico">◈</span> Settings</a>
        </nav>
        ${isAdmin ? `
        <div class="side-label">System</div>
        <nav class="side-nav">
          <a class="side-item ${active === "admin" ? "active" : ""}" href="#/admin">
            <span class="ico">⚙</span> Admin</a>
        </nav>` : ""}`;
  const sidebarUser = `
        <div class="side-user">
          ${avatarHTML(state.user)}
          <a class="info" href="#/settings" style="cursor:pointer;min-width:0">
            <div class="nm">${esc(state.user?.full_name || state.user?.email || "")}</div>
            <div class="rl">${esc(state.user?.role || "")}</div>
          </a>
          <button class="theme-btn" id="themeBtn" title="Toggle light / dark" aria-label="Toggle theme">☀</button>
          <button class="bell-btn" id="bell" title="Notifications">🔔<span class="dot" id="bellDot" hidden></span></button>
        </div>`;
  $("#app").innerHTML = `
    <div class="demo-banner">
      <span class="demo-banner-dot"></span>
      Read-only demo of a captured workspace
      <span class="demo-banner-note">Run <code>./run.sh</code> from the repo for the live pipeline</span>
      <a class="demo-banner-link" href="https://github.com/MohammedAnasNathani/modelsmith" target="_blank" rel="noopener">Source →</a>
    </div>
    <div class="bg-fx"></div>
    <div class="shell">
      <aside class="sidebar">
        <a class="side-logo" href="#/dashboard">
          <span class="mark">MS</span>
          <span class="name">Model<em>Smith</em></span>
        </a>
        ${navItems}
        <div class="side-spacer"></div>
        ${sidebarUser}
      </aside>
      <div class="main">
        <div class="mob-header">
          <button class="mob-hamburger" id="mobHamburger">☰</button>
          <span class="mark">MS</span>
          <span class="name">Model<em>Smith</em></span>
          <div style="flex:1"></div>
          <div class="search-pill" style="padding:5px 10px;font-size:11px" id="cmdkOpenMobile">🔍 <kbd>⌘K</kbd></div>
        </div>
        <div class="topline">
          <div class="crumbs">${crumbs}</div>
          <div class="spacer"></div>
          ${actions}
          <div class="search-pill desktop-only" id="cmdkOpen">🔍 Search or jump to… <kbd>⌘K</kbd></div>
        </div>
        <div class="content">${contentHTML}
          <div class="footer">ModelSmith · every number measured, none promised</div>
        </div>
      </div>
    </div>`;
  $$("[data-nav]").forEach(el => el.onclick = () => (location.hash = el.dataset.nav));
  $("#cmdkOpen")?.addEventListener("click", openCommandPalette);
  $("#cmdkOpenMobile")?.addEventListener("click", openCommandPalette);
  $("#mobHamburger")?.addEventListener("click", openMobileDrawer);
  $("#themeBtn")?.addEventListener("click", toggleTheme);
  applyTheme(localStorage.getItem("ms_theme") || "dark");
  setupBell();
}

function openMobileDrawer() {
  const isAdmin = state.user?.role === "admin";
  const backdrop = document.createElement("div");
  backdrop.className = "sidebar-drawer-backdrop";
  backdrop.id = "drawerBackdrop";
  const drawer = document.createElement("div");
  drawer.className = "sidebar-drawer";
  drawer.id = "sidebarDrawer";
  drawer.innerHTML = `
    <div style="padding:0 16px;display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
      <a class="side-logo" href="#/dashboard" style="margin:0;padding:0">
        <span class="mark">MS</span><span class="name">Model<em>Smith</em></span>
      </a>
      <button class="drawer-close" id="drawerClose" aria-label="Close menu">×</button>
    </div>
    <div class="side-label">Workspace</div>
    <nav class="side-nav">
      <a class="side-item" href="#/dashboard"><span class="ico">◈</span> Dashboard</a>
      <a class="side-item" href="#/projects"><span class="ico">▤</span> Projects</a>
      <a class="side-item" href="#/jobs"><span class="ico">⚙</span> Jobs</a>
      <a class="side-item" href="#/api"><span class="ico">⌘</span> API playground</a>
      <a class="side-item" href="#/achievements"><span class="ico">★</span> Achievements</a>
      <a class="side-item" href="#/settings"><span class="ico">◈</span> Settings</a>
    </nav>
    ${isAdmin ? `
    <div class="side-label">System</div>
    <nav class="side-nav">
      <a class="side-item" href="#/admin"><span class="ico">⚙</span> Admin</a>
    </nav>` : ""}
    <div style="flex:1"></div>
    <div class="drawer-user">
      ${avatarHTML(state.user)}
      <div class="info" style="flex:1;min-width:0">
        <div class="nm">${esc(state.user?.full_name || state.user?.email || "")}</div>
        <div class="rl">${esc(state.user?.role || "")}</div>
      </div>
    </div>`;
  document.body.append(backdrop, drawer);
  backdrop.onclick = closeMobileDrawer;
  drawer.querySelector("#drawerClose").onclick = closeMobileDrawer;
  $$("a.side-item, a.side-logo", drawer).forEach(el => {
    if (el.getAttribute("href") === location.hash) el.classList.add("active");
    el.addEventListener("click", closeMobileDrawer);
  });
}
function closeMobileDrawer() {
  $("#drawerBackdrop")?.remove();
  $("#sidebarDrawer")?.remove();
}

function setupBell() {
  const bell = $("#bell");
  if (!bell) return;
  bell.onclick = async e => {
    e.stopPropagation();
    let panel = $("#notifPanel");
    if (panel) { panel.remove(); return; }
    const { notifications } = await api("/api/notifications");
    api("/api/notifications/read", { method: "POST" }).then(refreshBellDot).catch(() => {});
    panel = document.createElement("div");
    panel.className = "notif-panel"; panel.id = "notifPanel";
    const icon = k => k === "error" ? "⛔" : k === "success" ? "✅" : "ℹ️";
    const dayBoundary = Date.now() / 1000 - 86400;
    const recent = notifications.filter(n => n.created_at > dayBoundary);
    const older = notifications.filter(n => n.created_at <= dayBoundary);
    const item = n => `
      <div class="notif-item ${n.is_read ? "" : "unread"}">
        <div class="t">${icon(n.kind)} ${esc(n.title)}</div>
        <div class="b">${esc(n.body)} · ${timeago(n.created_at)}</div>
      </div>`;
    panel.innerHTML = `
      <div class="notif-header">Notifications
        <button id="notifClear">Mark all read</button></div>
      ${notifications.length ? `
        ${recent.length ? `<div class="notif-when">today</div>${recent.map(item).join("")}` : ""}
        ${older.length ? `<div class="notif-when">earlier</div>${older.map(item).join("")}` : ""}`
      : '<div class="notif-empty">No notifications yet. Jobs will report here when they finish.</div>'}`;
    document.body.appendChild(panel);
    $("#notifClear", panel).onclick = () => {
      api("/api/notifications/read", { method: "POST" })
        .then(() => { refreshBellDot(); panel.remove(); toast("All caught up"); })
        .catch(() => toast("Could not mark read", true));
    };
    setTimeout(() => document.addEventListener("click", () => panel.remove(), { once: true }), 0);
  };
  refreshBellDot();
}
async function refreshBellDot() {
  try {
    const { unread } = await api("/api/notifications");
    const d = $("#bellDot");
    if (d) { d.hidden = !unread; d.textContent = unread > 9 ? "9+" : unread; }
  } catch {}
}

/* ---------------- command palette ---------------- */
function openCommandPalette() {
  const back = document.createElement("div");
  back.className = "cmdk";
  back.innerHTML = `<div class="cmdk-list">
    <div class="cmdk-search"><span class="glyph">⌘</span>
      <input placeholder="Type a command or search…" id="cmdkInput"></div>
    <div style="max-height:46vh;overflow-y:auto;padding-bottom:6px" id="cmdkScroll"></div>
    <div class="cmdk-foot">
      <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
      <span><kbd>↵</kbd> select</span>
      <span><kbd>esc</kbd> close</span>
      <span style="margin-left:auto">ModelSmith</span>
    </div></div>`;
  document.body.appendChild(back);
  back.addEventListener("click", e => { if (e.target === back) back.remove(); });

  const baseCommands = [
    { ico: "◈", label: "Go to Dashboard", group: "Navigate", run: () => (location.hash = "#/dashboard") },
    { ico: "▤", label: "Go to Projects", group: "Navigate", run: () => (location.hash = "#/projects") },
    { ico: "🔎", label: "Search models", group: "Navigate", run: () => (location.hash = "#/search") },
    { ico: "⚙", label: "Go to Settings", group: "Navigate", run: () => (location.hash = "#/settings") },
    { ico: "⬆", label: "Upload a model", group: "Actions", run: () => { location.hash = "#/projects"; setTimeout(() => $("#newProjBtn") ? null : toast("Pick or create a project first, then upload.", true), 100); } },
    { ico: "✈", label: "Start product tour", group: "Actions", run: () => startTour(true) },
    { ico: "⚙", label: "Go to Admin", admin: true, group: "Navigate", run: () => (location.hash = "#/admin") },
    { ico: "→", label: "Log out", group: "Actions", run: async () => { try { await api("/api/auth/logout", { method: "POST" }); } catch {} logoutLocal(); } },
  ];
  let items = [];

  function draw() {
    const scroll = $("#cmdkScroll", back);
    /* group items by category */
    const groups = {};
    items.slice(0, 12).forEach((i, idx) => {
      (groups[i.group || "Other"] = groups[i.group || "Other"] || []).push({ ...i, _idx: idx });
    });
    scroll.innerHTML = Object.entries(groups).map(([g, list]) => `
      <div class="cmdk-group">${esc(g)}</div>
      ${list.map(i => `
        <div class="cmdk-item ${i._idx === state.cmdkIndex ? "sel" : ""}" data-i="${i._idx}">
          <span class="ico">${i.ico}</span><span>${esc(i.label)}</span>
          ${i.hint ? `<span class="hint">${esc(i.hint)}</span>` : ""}
        </div>`).join("")}`).join("")
      || '<div class="cmdk-item"><span class="ico">∅</span>No matches</div>';
    $$(".cmdk-item[data-i]", back).forEach(el => {
      el.onclick = () => { items[+el.dataset.i].run(); back.remove(); };
      el.onmouseenter = () => {
        state.cmdkIndex = +el.dataset.i;
        $$(".cmdk-item", back).forEach(x => x.classList.remove("sel"));
        el.classList.add("sel");
      };
    });
    const sel = $(".cmdk-item.sel", back);
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }

  const pushRecent = label => {
    try {
      const rec = JSON.parse(localStorage.getItem("ms_recents") || "[]")
        .filter(r => r !== label);
      rec.unshift(label);
      localStorage.setItem("ms_recents", JSON.stringify(rec.slice(0, 4)));
    } catch {}
  };

  async function build(q) {
    let models = [], projects = [];
    try {
      const [{ projects: plist }, { results }] = await Promise.all([
        api("/api/projects"), api("/api/search" + (q ? `?q=${encodeURIComponent(q)}` : ""))]);
      projects = plist.map(p => ({ ico: "▤", label: p.name, hint: "project", group: "Projects",
        run: () => { pushRecent(p.name); location.hash = "#/project/" + p.id; } }));
      models = results.slice(0, 8).map(m => ({ ico: "◈", label: m.name, hint: m.project, group: "Models",
        run: () => { pushRecent(m.name); location.hash = "#/model/" + m.id; } }));
    } catch {}
    const recents = [];
    try {
      const seen = new Set();
      for (const label of JSON.parse(localStorage.getItem("ms_recents") || "[]")) {
        if (seen.has(label) || (q && !label.toLowerCase().includes(q.toLowerCase()))) continue;
        seen.add(label);
        const model = models.find(m => m.label === label);
        const proj = projects.find(p => p.label === label);
        if (model || proj) recents.push({ ...(model || proj), group: "Recent" });
      }
    } catch {}
    items = [
      ...baseCommands.filter(c => !c.admin || state.user?.role === "admin"),
      ...recents, ...projects, ...models];
    if (q) items = items.filter(i => i.label.toLowerCase().includes(q.toLowerCase())
      || (i.hint || "").toLowerCase().includes(q.toLowerCase()));
    state.cmdkIndex = 0;
    draw();
  }
  const input = $("#cmdkInput", back);
  input.focus();
  input.oninput = () => {
    const q = input.value.trim();
    /* inline unit math: "46.8MB to GB", "200ms * 3", "45% of 46.8" */
    const conv = q.match(/^([\d.]+)\s*(b|kb|mb|gb)\s*(?:to|in)\s*(b|kb|mb|gb)$/i);
    const pct = q.match(/^([\d.]+)\s*%\s*of\s*([\d.]+)$/i);
    let calc = null;
    if (conv) {
      const mult = { b: 1, kb: 1e3, mb: 1e6, gb: 1e9 };
      const v = parseFloat(conv[1]) * mult[conv[2].toLowerCase()]
                / mult[conv[3].toLowerCase()];
      const fmt = x => x >= 1e9 ? (x / 1e9).toFixed(2) + " GB"
        : x >= 1e6 ? (x / 1e6).toFixed(2) + " MB"
        : x >= 1e3 ? (x / 1e3).toFixed(2) + " KB" : x.toFixed(0) + " B";
      calc = { ico: "Σ", label: `${q} = ${fmt(v)}`, group: "Calculator",
               run: () => copyText(String(v), "Result copied") };
    } else if (pct) {
      const v = parseFloat(pct[1]) / 100 * parseFloat(pct[2]);
      calc = { ico: "Σ", label: `${q} = ${v.toFixed(2)}`, group: "Calculator",
               run: () => copyText(String(v.toFixed(4)), "Result copied") };
    } else if (/^[\d.\s+\-*/()x^%]+$/.test(q) && /[\d]/.test(q) && /[+\-*/^x]/.test(q) && q.length > 2) {
      try {
        const v = Function("return (" + q.replace(/\^/g, "**").replace(/x/gi, "*") + ")")();
        if (typeof v === "number" && isFinite(v))
          calc = { ico: "Σ", label: `${q} = ${+v.toFixed(6)}`, group: "Calculator",
                   run: () => copyText(String(v), "Result copied") };
      } catch {}
    }
    if (calc) { items = [calc]; state.cmdkIndex = 0; draw(); return; }
    build(q);
  };
  input.onkeydown = e => {
    if (e.key === "ArrowDown") { state.cmdkIndex = Math.min(state.cmdkIndex + 1, Math.min(items.length, 12) - 1); draw(); }
    else if (e.key === "ArrowUp") { state.cmdkIndex = Math.max(state.cmdkIndex - 1, 0); draw(); }
    else if (e.key === "Enter" && items[state.cmdkIndex]) { items[state.cmdkIndex].run(); back.remove(); }
    else if (e.key === "Escape") back.remove();
  };
  build("");
}
let gPending = false;
document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openCommandPalette(); return; }
  if (!state.token) return;
  const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
  if (inField) return;
  if (gPending) {
    gPending = false;
    const map = { d: "#/dashboard", p: "#/projects", a: "#/admin", s: "#/settings" };
    if (map[e.key.toLowerCase()]) { e.preventDefault(); location.hash = map[e.key.toLowerCase()]; }
    return;
  }
  if (e.key === "g") { gPending = true; setTimeout(() => (gPending = false), 1200); return; }
  if (e.key === "/") { e.preventDefault(); openCommandPalette(); return; }
  if (e.key === "?") { e.preventDefault(); openShortcutsOverlay(); }
});

/* ---------------- shortcuts overlay panel ---------------- */
function openShortcutsOverlay() {
  const el = document.createElement("div");
  el.className = "shortcuts-overlay"; el.id = "shortcutsOverlay";
  el.innerHTML = `
    <div class="shortcuts-backdrop" id="scBackdrop"></div>
    <div class="shortcuts-panel">
      <h3>Keyboard shortcuts</h3>
      <p class="sub">Navigate faster without touching the mouse.</p>
      <div class="shortcuts-group-title">Navigation</div>
      <div class="sc-row"><span class="sc-label"><span class="ico">◈</span> Command palette</span><span class="sc-keys"><kbd>⌘</kbd><kbd>K</kbd> <em>or</em> <kbd>/</kbd></span></div>
      <div class="sc-row"><span class="sc-label"><span class="ico">⇥</span> Go to dashboard</span><span class="sc-keys"><kbd>G</kbd><kbd>D</kbd></span></div>
      <div class="sc-row"><span class="sc-label"><span class="ico">▤</span> Go to projects</span><span class="sc-keys"><kbd>G</kbd><kbd>P</kbd></span></div>
      <div class="sc-row"><span class="sc-label"><span class="ico">⚙</span> Go to settings</span><span class="sc-keys"><kbd>G</kbd><kbd>S</kbd></span></div>
      ${state.user?.role === "admin" ? `
      <div class="sc-row"><span class="sc-label"><span class="ico">⚙</span> Go to admin</span><span class="sc-keys"><kbd>G</kbd><kbd>A</kbd></span></div>` : ""}
      <div class="shortcuts-group-title">Actions</div>
      <div class="sc-row"><span class="sc-label"><span class="ico">?</span> Show shortcuts</span><span class="sc-keys"><kbd>?</kbd></span></div>
      <div class="sc-row"><span class="sc-label"><span class="ico">✕</span> Close dialog</span><span class="sc-keys"><kbd>Esc</kbd></span></div>
      <div class="sc-row"><span class="sc-label"><span class="ico">→</span> Follow link / confirm</span><span class="sc-keys"><kbd>↵</kbd></span></div>
      <div class="shortcuts-group-title">In command palette</div>
      <div class="sc-row"><span class="sc-label"><span class="ico">↕</span> Navigate items</span><span class="sc-keys"><kbd>↑</kbd><kbd>↓</kbd></span></div>
      <div class="sc-row"><span class="sc-label"><span class="ico">↵</span> Select item</span><span class="sc-keys"><kbd>↵</kbd></span></div>
      <div class="sc-row"><span class="sc-label"><span class="ico">✕</span> Close palette</span><span class="sc-keys"><kbd>Esc</kbd></span></div>
      <div class="sc-footer"><kbd>Esc</kbd> to close · <kbd>?</kbd> to reopen anywhere</div>
    </div>`;
  document.body.appendChild(el);
  const close = () => el.remove();
  el.querySelector("#scBackdrop").onclick = close;
  el.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  setTimeout(() => document.addEventListener("keydown", function handler(e) {
    if (e.key === "Escape" && !$("#shortcutsOverlay")) { document.removeEventListener("keydown", handler); return; }
    if (e.key === "Escape") { close(); document.removeEventListener("keydown", handler); }
  }), 0);
}

/* ---------------- skeleton loading helpers ---------------- */
function skeletonBento(count = 6, span = 4) {
  return Array.from({ length: count }, () =>
    `<div class="tile span${span}"><div style="padding:4px 0"><div class="skel-title"></div><div class="skel-line"></div><div class="skel-line short"></div></div></div>`
  ).join("");
}
function skeletonTable(rows = 4) {
  return `<div class="tbl-wrap"><table class="tbl"><tr><th><div class="skel-bar" style="width:80px;height:10px"></div></th><th><div class="skel-bar" style="width:60px;height:10px"></div></th><th><div class="skel-bar" style="width:100px;height:10px"></div></th></tr>${Array.from({ length: rows }, () => `<tr><td><div class="skel-bar" style="width:100px"></div></td><td><div class="skel-bar" style="width:60px"></div></td><td><div class="skel-bar" style="width:120px"></div></td></tr>`).join("")}</table></div>`;
}

/* ---------------- search ---------------- */
async function viewSearch() {
  if (!state.token) { location.hash = "#/login"; return; }
  viewSearch.cmpA = null;
  shell({ active: "projects", crumbs: "<b>Search</b>" }, `
    <div class="page-head"><div><h1>Search models</h1>
      <div class="sub">Every model you own, searchable in one place.</div></div></div>
    <div class="search-bar" style="margin-bottom:20px">
      <div class="search-pill" style="flex:1;max-width:500px;cursor:text;padding:10px 16px;font-size:14px">
        🔍 <input type="text" id="searchInput" placeholder="Search by model name…" style="background:none;border:none;color:var(--text);font-size:14px;outline:none;width:100%;font-family:var(--sans)">
      </div>
      <select id="searchStatus" style="background:var(--panel);border:1px solid var(--line);color:var(--dim);padding:8px 12px;border-radius:var(--r-sm);font-size:13px">
        <option value="">All statuses</option>
        <option value="analyzed">Analyzed</option>
        <option value="pending">Pending</option>
        <option value="analyzing">Analyzing</option>
        <option value="failed">Failed</option>
      </select>
    </div>
    <div class="bento" id="searchResults">
      <div class="tile span12"><div class="empty-svg">${emptySVG("search")}</div>
        <div class="empty"><h3>Search your models</h3>
        <p>Type to search across all projects. Results appear as you type.</p></div></div>
    </div>`);

  const doSearch = async () => {
    const q = $("#searchInput").value.trim().toLowerCase();
    const status = $("#searchStatus").value;
    const grid = $("#searchResults");
    if (!q && !status) {
      grid.innerHTML = `<div class="tile span12"><div class="empty-svg">${emptySVG("search")}</div>
        <div class="empty"><h3>Search your models</h3>
        <p>Type a name, framework or project. Results appear before you finish the thought.</p>
        <div class="sugg-row" style="justify-content:center;margin-top:6px">
          ${(viewSearch._hints || []).slice(0, 6).map(h => `
            <button class="fchip" data-hint="${esc(h)}">${esc(h)}</button>`).join("")}
        </div></div></div>`;
      $$("[data-hint]", grid).forEach(b => b.onclick = () => {
        $("#searchInput").value = b.dataset.hint; doSearch();
      });
      return;
    }
    const { projects } = await api("/api/projects");
    let results = [];
    for (const p of projects) {
      const d = await api("/api/projects/" + p.id);
      for (const m of d.models) {
        if (q && !m.name.toLowerCase().includes(q) && !m.framework.toLowerCase().includes(q)) continue;
        if (status && m.status !== status) continue;
        results.push({ ...m, project: p.name, project_id: p.id });
      }
    }
    if (!results.length) {
      grid.innerHTML = `<div class="tile span12"><div class="empty"><div class="big">∅</div>
        No models match "${esc(q || "all")} ${status ? "(" + status + ")" : ""}"</div></div>`;
      return;
    }
    grid.innerHTML = results.map((m, i) => `
      <a class="tile span4 clickable" href="#/model/${m.id}" data-id="${m.id}" style="animation-delay:${i * 0.04}s">
        <div class="t-head">
          <span class="t-title">${esc(m.name)}</span>
          <span class="pill ${m.status === "analyzed" ? "good" : m.status === "failed" ? "bad" : "warn"}">${m.status}</span>
        </div>
        <div class="tag-mini" style="color:var(--faint)">in ${esc(m.project)}</div>
        <div class="kv" style="margin-top:8px">
          <span class="k">framework</span><span class="v">${esc(m.framework)}</span>
          <span class="k">size</span><span class="v">${fmtBytes(m.size_bytes)}</span>
        </div>
        ${m.status === "analyzed" ? `<button class="btn small ghost cmp-pick" data-cmp="${m.id}" data-nm="${esc(m.name)}" style="margin-top:10px">⟷ Compare</button>` : ""}
      </a>`).join("");
    $$(".tile.clickable", grid).forEach(c => c.onclick = e => {
      if (e.target.closest(".cmp-pick")) return;
      location.hash = "#/model/" + c.dataset.id;
    });
    /* compare picker: select two analyzed models (state survives re-search) */
    $$(".cmp-pick", grid).forEach(b => b.onclick = async e => {
      e.stopPropagation();
      if (!viewSearch.cmpA) {
        viewSearch.cmpA = { id: b.dataset.cmp, name: b.dataset.nm };
        b.textContent = "✓ Selected as A";
        b.classList.add("primary");
        toast(`Picked ${b.dataset.nm}. Select another to compare.`);
      } else if (viewSearch.cmpA.id === b.dataset.cmp) {
        toast("Already selected. Pick a different model to compare.", true);
      } else {
        location.hash = `#/compare/${viewSearch.cmpA.id}/${b.dataset.cmp}`;
      }
    });
  };

  (async () => {
    try {
      const { results } = await api("/api/search");
      viewSearch._hints = [...new Set(results.map(r => r.name))].slice(0, 8);
      if (!$("#searchInput").value) doSearch();
    } catch {}
  })();
  let searchTimer;
  $("#searchInput").oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(doSearch, 300); };
  $("#searchInput").focus();
  $("#searchStatus").onchange = doSearch;
}

/* ---------------- auth view ---------------- */
function view404() {
  document.title = "404: ModelSmith";
  $("#app").innerHTML = `
  <div class="bg-fx"></div>
  <div class="nf-wrap">
    <div class="nf-card">
      <div class="nf-code">4<span class="nf-hammer">0</span>4</div>
      <h2>Page not found</h2>
      <p>The route <code>${esc(location.hash)}</code> doesn't exist.<br>
      It may have been moved, renamed, or never existed.</p>
      <div class="nf-actions">
        <a class="btn primary" href="#${state.token ? "/dashboard" : "/welcome"}">
          ${state.token ? "← Back to dashboard" : "← Back to home"}</a>
        <a class="btn ghost" href="#/projects">View projects</a>
      </div>
    </div>
  </div>`;
}
function viewLogin(register = false) {
  if (state.token) { location.hash = "#/dashboard"; return; }
  const IS_DEMO = !/^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  if (IS_DEMO) {
    $("#app").innerHTML = `
      <div class="auth-wrap">
        <div class="auth-card">
          <div class="auth-brand">
            <div class="mark">MS</div>
            <h1>Model<span>Smith</span></h1>
            <p class="serif-accent" style="font-size:15px;color:var(--dim)">measured, not promised</p>
          </div>
          <p style="font-size:14px;color:var(--dim);line-height:1.7;margin:4px 4px 18px">
            This deployment carries a read-only snapshot of a real workspace:
            three analyzed models, ranked plans, executed runs with measured
            results. Browse everything; changes need the local deployment.</p>
          <button class="btn primary" style="width:100%;justify-content:center;padding:12px" id="demoEnter">
            Enter the demo workspace <span aria-hidden="true">→</span></button>
          <div class="auth-toggle" style="margin-top:16px">
            <a href="#/welcome" style="display:block;margin-bottom:8px">← Back to home</a>
            <a href="https://github.com/MohammedAnasNathani/modelsmith" target="_blank" rel="noopener" style="color:var(--faint)">Source code on GitHub</a>
          </div>
        </div>
      </div>`;
    $("#demoEnter").onclick = async () => {
      await SNAPSHOT_READY;
      state.token = "demo-snapshot";
      state.user = (window.MS_SNAPSHOT?.me) || null;
      localStorage.setItem("ms_token", "demo-snapshot");
      localStorage.setItem("ms_user", JSON.stringify(state.user || {}));
      location.hash = "#/dashboard";
    };
    return;
  }
  $("#app").innerHTML = `
    <div class="auth-wrap">
      <div class="auth-card">
        <div class="auth-brand">
          <div class="mark">MS</div>
          <h1>Model<span>Smith</span></h1>
          <p class="serif-accent" style="font-size:15px;color:var(--dim)">measured, not promised</p>
        </div>
        <div class="auth-form">
          <h3 style="font-size:16px;margin-bottom:16px">${register ? "Create your account" : "Welcome back"}</h3>
          ${register ? `<label class="field"><span>Full name</span><input type="text" id="fName" placeholder="Ada Lovelace"></label>` : ""}
          <label class="field"><span>Email</span><input type="email" id="fEmail" placeholder="you@example.com"></label>
          <label class="field"><span>Password ${register ? "(min 8 chars)" : ""}</span><input type="password" id="fPass" placeholder="••••••••"></label>
          <button class="btn primary" style="width:100%;justify-content:center;padding:11px" id="authBtn">
            ${register ? "Create account" : "Log in"}</button>
          ${register ? "" : `<div style="text-align:center;margin-top:12px">
            <a href="#" id="forgotLink" style="font-size:12.5px;color:var(--faint)">Forgot password?</a></div>`}
        </div>
        <div class="demo-cred">
          <b>Try the guided tour</b>
          <button class="btn ghost small" id="fillDemo" style="width:100%;justify-content:center;margin-top:8px">
            Use the sample account</button>
        </div>
        <div class="auth-toggle">
          ${register ? "Already have an account? <a href='#/login'>Log in</a>"
                     : `<a href='#/welcome' style='display:block;margin-bottom:8px'>← Back to home</a> New here? <a href='#/register'>Create an account</a>`}
        </div>
      </div>
    </div>`;
  $("#authBtn").onclick = async () => {
    const email = $("#fEmail").value.trim(), password = $("#fPass").value;
    try {
      if (register) {
        await api("/api/auth/register", { method: "POST",
          body: { email, password, full_name: $("#fName")?.value.trim() } });
        toast("Account created. Logging you in…")
      }
      const r = await api("/api/auth/login", { method: "POST", body: { email, password } });
      state.token = r.token; state.user = r.user;
      localStorage.setItem("ms_token", r.token);
      localStorage.setItem("ms_user", JSON.stringify(r.user));
      location.hash = "#/dashboard";
    } catch (e) { toast(e.message, true); }
  };
  $("#fPass").addEventListener("keydown", e => { if (e.key === "Enter") $("#authBtn").click(); });
  $("#fillDemo")?.addEventListener("click", () => {
    $("#fEmail").value = "demo@modelsmith.io";
    $("#fPass").value = "demo12345";
    $("#fPass").focus();
    toast("Credentials filled. Press Log in.")
  });
  const forgot = $("#forgotLink");
  if (forgot) forgot.onclick = async e => {
    e.preventDefault();
    const email = $("#fEmail").value.trim();
    if (!email) { toast("Enter your email above first", true); return; }
    try {
      const r = await api("/api/auth/password/reset-request", { method: "POST", body: { email } });
      openModal(`<h3>Reset password</h3>
        <p class="sub" style="color:var(--dim);font-size:12.5px">Token issued (valid 30 min):</p>
        <pre class="report" style="max-height:70px;margin:10px 0">${esc(r.reset_token)}</pre>
        <label class="field"><span>New password (min 8 chars)</span><input type="password" id="rstPass"></label>
        <button class="btn primary" style="width:100%;justify-content:center" id="mOk">Set new password</button>`,
        { onOk: async () => {
          const p = $("#rstPass").value;
          if (p.length < 8) { toast("Password must be at least 8 characters", true); return false; }
          await api("/api/auth/password/reset-confirm", { method: "POST",
            body: { reset_token: r.reset_token, password: p } });
          toast("Password updated. Log in with your new password.");
        } });
    } catch (err) { toast(err.message, true); }
  };
}

/* ---------------- dashboard ---------------- */
async function viewDashboard() {
  if (!state.token) { location.hash = "#/login"; return; }
  shell({ active: "dashboard", crumbs: "<b>Dashboard</b>" }, `
    <div class="page-head">
      <div><h1>Good ${new Date().getHours() < 12 ? "morning" : new Date().getHours() < 18 ? "afternoon" : "evening"}, <span class="greet-serif">${esc((state.user?.full_name || "engineer").split(" ")[0])}</span> 👋</h1>
      <div class="sub">Everything you own, measured and mapped.</div></div>
      <div class="actions"><button class="btn ghost small" id="tourBtn">✈ Tour</button>
        <button class="btn primary" data-nav="#/projects">▤ View projects</button></div>
    </div>
    <div class="bento" id="dashGrid">
      ${skeletonBento(6, 4)}
    </div>`);

  const d = await api("/api/dashboard");
  const s = d.stats, h = d.health;
  const jobColors = { success: "var(--good)", failed: "var(--bad)", running: "var(--accent)", queued: "var(--warn)" };
  $("#dashGrid").innerHTML = `
    <div class="tile span3 accent-glow stat-tile">
      <div class="t-label">Models analyzed</div>
      <div class="hero-num" id="cntAnalyzed">0</div>
      <div class="hero-sub">ready for planning & execution</div>
    </div>
    <div class="tile span3 stat-tile">
      <div class="t-label">Projects</div>
      <div class="hero-num" id="cntProjects">0</div>
      <div class="hero-sub">${s.storage_mb} MB encrypted storage</div>
    </div>
    <div class="tile span3 stat-tile">
      <div class="t-label">Optimizations run</div>
      <div class="hero-num" id="cntRuns">0</div>
      <div class="hero-sub">successful pipeline executions</div>
    </div>
    <div class="tile span3 violet-glow stat-tile">
      <div class="t-label">Total size saved</div>
      <div class="hero-num" style="color:var(--good)" id="cntSaved">0</div>
      <div class="hero-sub">across all optimized artifacts</div>
    </div>

    <div class="tile span5">
      <div class="t-head"><span class="t-title">Recent models</span>
        <div class="right"><span class="pill accent">${s.models} total</span></div></div>
      ${d.recent_models.length ? d.recent_models.map(m => `
        <a class="feed-item" href="#/model/${m.id}" data-model="${m.id}">
          <span class="feed-dot" style="background:${m.status === "analyzed" ? "var(--good)" : m.status === "failed" ? "var(--bad)" : "var(--warn)"}"></span>
          <div style="flex:1;min-width:0">
            <div class="tx"><b>${esc(m.name)}</b> <span class="tag-mini">· ${esc(m.framework)} · ${fmtBytes(m.size_bytes)}</span></div>
            <div class="tm">${m.status} · ${timeago(m.created_at)}</div>
          </div>
          <span style="color:var(--faint)">→</span>
        </a>`).join("") : `<div class="empty" style="padding:24px"><div class="big">◈</div>No models yet. Upload one from a project.</div>`}
    </div>

    <div class="tile span4">
      <div class="t-head"><span class="t-title">Job activity</span>
        <div class="right"><span class="pill ${h.status === "ok" ? "good" : "warn"}"><span class="pulse"></span>${h.status}</span></div></div>
      ${d.recent_jobs.length ? d.recent_jobs.map(j => `
        <div class="feed-item">
          <span class="feed-dot" style="background:${jobColors[j.status] || "var(--faint)"}"></span>
          <div style="flex:1">
            <div class="tx"><b>${j.type === "analyze" ? "Analysis" : "Optimization"}</b>: ${esc((j.message || j.status).slice(0, 44))}</div>
            <div class="tm">${j.status} · ${timeago(j.created_at)}</div>
          </div>
          ${j.status === "running" || j.status === "queued" ? `<span class="pill accent">${j.progress}%</span>` : ""}
        </div>`).join("") : `<div class="empty" style="padding:24px">No jobs yet</div>`}
    </div>

    <div class="tile span3">
      <div class="t-head"><span class="t-title">Activity · 30d</span></div>
      <div class="chart-box" id="dashSpark"></div>
    </div>

    <div class="tile span3">
      <div class="t-head"><span class="t-title">System health</span></div>
      <div style="display:grid;place-items:center;padding:6px 0"><div id="hlGauge" style="width:140px"></div></div>
      <div class="kv" style="margin-top:8px">
        <span class="k">database</span><span class="v" style="color:${h.checks.database?.ok ? "var(--good)" : "var(--bad)"}">${h.checks.database?.ok ? "ok" : "down"}</span>
        <span class="k">uptime</span><span class="v">${Math.floor(h.uptime_seconds / 60)}m</span>
        <span class="k">torch</span><span class="v">${esc(h.versions.torch || "-")}</span>
        <span class="k">onnxrt</span><span class="v">${esc(h.versions.onnxruntime || "-")}</span>
      </div>
    </div>`;
  const upPct = Math.min(100, Math.round(h.uptime_seconds / 60));
  MSCharts.gauge($("#hlGauge"), upPct, { label: "uptime (min)", color: "#4ade80", size: 140 });
  $$("[data-model]").forEach(el => el.onclick = () => (location.hash = "#/model/" + el.dataset.model));

  /* count-up hero numbers */
  countUp($("#cntAnalyzed"), s.analyzed, { suffix: ` / ${s.models}` });
  countUp($("#cntProjects"), s.projects);
  countUp($("#cntRuns"), s.runs);
  countUp($("#cntSaved"), s.saved_mb, { decimals: 1, suffix: " MB" });

  /* queue health banner: warn only when work is actually stuck */
  if (h.queue_depth > 0) {
    const lag = h.queue_lag_seconds ?? 0;
    if (lag > 30) {
      $("#dashGrid").insertAdjacentHTML("afterbegin",
        `<div class="tile span12" style="border-color:rgba(232,194,82,.4)">
          <div class="t-head"><span class="t-title"><span class="pulse"></span> Queue is busy</span>
            <span class="pill warn">${h.queue_depth} waiting · oldest for ${Math.round(lag)}s</span></div>
          <p class="tag-mini">Jobs run two at a time. Big models take a few minutes;
          the queue drains itself, no action needed.</p></div>`);
    }
  }

  /* first-visit product tour */
  $("#tourBtn")?.addEventListener("click", () => startTour(true));
  setTimeout(() => startTour(false), 700);

  /* activity sparkline: 30 day bucketed jobs */
  (async () => {
    try {
      const { days } = await api("/api/dashboard/activity");
      if (days.length && $("#dashSpark")) {
        const vals = Array.from({ length: 30 }, (_, i) => {
          const d = days.find(r => {
            const ago = Math.floor((Date.now() / 1000 - new Date(r.day + "T00:00:00").getTime() / 1000) / 86400);
            return ago === i;
          });
          return d ? d.cnt : 0;
        }).reverse();
        MSCharts.sparkline($("#dashSpark"), vals);
      }
    } catch {}
  })();

  /* framework distribution + status breakdown from enriched stats */
  (async () => {
    try {
      const stats = await api("/api/dashboard/stats");
      const fw = stats.frameworks || {};
      const sb = stats.status_breakdown || {};
      // add framework donut to activity tile area
      if ($("#dashSpark") && Object.keys(fw).length) {
        const sparkBox = $("#dashSpark").parentElement;
        sparkBox.insertAdjacentHTML("afterend",
          `<div class="tile span3"><div class="t-head"><span class="t-title">Frameworks</span></div>
           <div class="chart-box" id="fwDonut"></div></div>`);
        MSCharts.donut($("#fwDonut"),
          Object.entries(fw).map(([k, v]) => ({ label: k, value: v })),
          { centerValue: String(Object.values(fw).reduce((a, b) => a + b, 0)),
            centerLabel: "models" });
      }
    } catch {}
  })();

  /* computed insights: heaviest model, best win, busiest project */
  (async () => {
    try {
      const ins = await api("/api/dashboard/insights");
      const grid = $("#dashGrid");
      if (!grid) return;
      const cards = [];
      if (ins.heaviest_model)
        cards.push(`<a class="ins-chip" href="#/model/${ins.heaviest_model.id}">
          <b>${fmtBytes(ins.heaviest_model.size_bytes)}</b>
          <span>heaviest: ${esc(ins.heaviest_model.name)}</span></a>`);
      if (ins.best_run)
        cards.push(`<a class="ins-chip" href="#/model/${ins.best_run.model_id}">
          <b>−${ins.best_run.saved}%</b>
          <span>best win: ${esc(ins.best_run.plan_name)}</span></a>`);
      if (ins.most_active_project && (ins.most_active_project.jobs || 0) > 0)
        cards.push(`<a class="ins-chip" href="#/projects">
          <b>${ins.most_active_project.jobs}</b>
          <span>jobs through ${esc(ins.most_active_project.name)}</span></a>`);
      if (ins.pending_jobs > 0)
        cards.push(`<a class="ins-chip live" href="#/jobs"><b>${ins.pending_jobs}</b>
          <span>job${ins.pending_jobs > 1 ? "s" : ""} in flight right now</span></a>`);
      if (cards.length)
        grid.insertAdjacentHTML("afterbegin",
          `<div class="tile span12 ins-strip"><div class="ins-row">${cards.join("")}</div></div>`);
    } catch {}
  })();

  /* onboarding checklist: real progress from real data */
  const steps = [
    { done: s.projects > 0, label: "Create a project", nav: "#/projects" },
    { done: s.models > 0,   label: "Upload a model",   nav: "#/projects" },
    { done: s.analyzed > 0, label: "Complete analysis", nav: "#/projects" },
    { done: s.runs > 0,     label: "Run an optimization", nav: "#/projects" },
  ];
  const doneCount = steps.filter(x => x.done).length;
  if (doneCount < steps.length) {
    const next = steps.find(x => !x.done);
    const bar = $("#dashGrid").insertAdjacentHTML("afterbegin", `
      <div class="tile span12 accent-glow" id="onboardTile">
        <div class="t-head"><span class="t-title">Getting started</span>
          <span class="pill accent">${doneCount} / ${steps.length}</span></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
          ${steps.map(x => `
            <div class="ob-step ${x.done ? "done" : ""}">
              <span class="ob-check">${x.done ? "✓" : "○"}</span> ${x.label}
            </div>`).join("")}
          <button class="btn primary small" data-nav="${next.nav}" style="margin-left:auto">
            ${next.label} →</button>
        </div>
      </div>`);
    $$("[data-nav]", $("#onboardTile")).forEach(el =>
      el.onclick = () => (location.hash = el.dataset.nav));
  }
}

/* ---------------- projects ---------------- */
async function viewProjects() {
  if (!state.token) { location.hash = "#/login"; return; }
  let projects_all = [];
  const showArchived = localStorage.getItem("ms_show_archived") === "1";
  shell({ active: "projects", crumbs: "<b>Projects</b>",
    actions: `<button class="btn ghost small" id="exportBtn">⬇ Export</button>
              <button class="btn primary" id="newProjBtn">+ New project</button>` }, `
    <div class="page-head"><div><h1>Projects</h1>
      <div class="sub">Projects isolate your models, runs and artifacts from every other account.</div></div>
      <div class="actions">
        <select id="projSort" class="proj-sort">
          <option value="updated">Last updated</option>
          <option value="name">Name</option>
          <option value="models">Most models</option>
          <option value="runs">Most runs</option>
        </select>
      </div>
    </div>
    <div class="bento" id="projGrid"></div>`);

  const load = async () => {
    const { projects } = await api("/api/projects");
    const grid = $("#projGrid");
    const sort = $("#projSort")?.value || "updated";
    const visible = projects.filter(p => !p.archived || showArchived);
    visible.sort((a, b) =>
      sort === "name" ? a.name.localeCompare(b.name)
      : sort === "models" ? b.model_count - a.model_count
      : sort === "runs" ? b.run_count - a.run_count
      : (b.latest_activity || b.updated_at) - (a.latest_activity || a.updated_at));
    projects_all = projects;
    if (!projects.length) {
      grid.innerHTML = `<div class="tile span12"><div class="empty-svg">${emptySVG("project")}</div>
        <div class="empty"><h3>No projects yet</h3>
        <p>Create your first project to upload and optimize models.</p>
        <button class="btn primary" id="emptyCreateBtn">+ Create project</button></div></div>`;
      $("#emptyCreateBtn")?.addEventListener("click", () => $("#newProjBtn").click());
      return;
    }
    grid.innerHTML = visible.map((p, i) => {
      const sb = p.status_breakdown || {};
      const total = Object.values(sb).reduce((a, b) => a + b, 0) || 1;
      const analyzedPct = Math.round(((sb.analyzed || 0) / total) * 100);
      const failedPct = Math.round(((sb.failed || 0) / total) * 100);
      const analyzingPct = Math.round(((sb.analyzing || 0) / total) * 100);
      const pendingPct = 100 - analyzedPct - failedPct - analyzingPct;
      return `
      <a class="tile span4 clickable proj-card ${p.archived ? "archived" : ""}" href="#/project/${p.id}" data-id="${p.id}" style="animation-delay:${i * 0.05}s">
        <div class="t-head">
          <span class="t-title">${esc(p.name)}</span>
          <div class="right"><span class="pill accent">${p.model_count} model${p.model_count !== 1 ? "s" : ""}</span></div>
        </div>
        <div class="proj-desc">${esc(p.description || "No description")}</div>
        <div class="proj-bar-wrap">
          <div class="proj-bar">
            ${analyzedPct ? `<div class="proj-bar-seg good" style="width:${analyzedPct}%" title="Analyzed: ${sb.analyzed || 0}"></div>` : ""}
            ${analyzingPct ? `<div class="proj-bar-seg warn" style="width:${analyzingPct}%" title="Analyzing: ${sb.analyzing || 0}"></div>` : ""}
            ${failedPct ? `<div class="proj-bar-seg bad" style="width:${failedPct}%" title="Failed: ${sb.failed || 0}"></div>` : ""}
            ${pendingPct > 0 ? `<div class="proj-bar-seg pending" style="width:${pendingPct}%" title="Pending: ${sb.pending || 0}"></div>` : ""}
          </div>
          <div class="proj-bar-labels">
            ${sb.analyzed ? `<span style="color:var(--good)">${sb.analyzed} ready</span>` : ""}
            ${sb.analyzing ? `<span style="color:var(--warn)">${sb.analyzing} analyzing</span>` : ""}
            ${sb.failed ? `<span style="color:var(--bad)">${sb.failed} failed</span>` : ""}
            ${sb.pending ? `<span style="color:var(--faint)">${sb.pending} pending</span>` : ""}
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-top:12px;align-items:center">
          <span class="pill violet">${p.run_count} runs</span>
          ${p.total_bytes ? `<span class="tag-mini">${fmtBytes(p.total_bytes)}</span>` : ""}
          <span class="tag-mini" style="margin-left:auto">updated ${timeago(p.latest_activity || p.updated_at)}</span>
          <button class="btn small ghost" data-arch="${p.id}" title="${p.archived ? "Unarchive" : "Archive (keep data, hide from list)"}">${p.archived ? "↺" : "🗄"}</button>
          <button class="btn small danger" data-del="${p.id}" title="Delete project">×</button>
        </div>
      </a>`;
    }).join("");
    $$("[data-arch]", grid).forEach(b => b.onclick = async e => {
      e.stopPropagation();
      const proj = projects_all.find(x => x.id === b.dataset.arch);
      const verb = proj?.archived ? "unarchive" : "archive";
      try {
        await api(`/api/projects/${b.dataset.arch}/${verb}`, { method: "POST" });
        toast(proj?.archived ? "Project restored to the active list" : "Project archived. Data kept, hidden from the list");
        load();
      } catch (err) { toast(err.message, true); }
    });
    $("#projSort")?.addEventListener("change", () => load());
    $$("[data-del]", grid).forEach(b => b.onclick = async e => {
      e.stopPropagation();
      if (await confirmModal("Delete project?", "This removes all models, runs and encrypted artifacts. This cannot be undone.", "Delete project")) {
        try { await api("/api/projects/" + b.dataset.del, { method: "DELETE" }); toast("Project deleted, with all models and runs"); load(); }
        catch (err) { toast(err.message, true); }
      }
    });
  };
  $("#newProjBtn").onclick = () => openModal(`
    <h3>New project</h3>
    <label class="field"><span>Project name</span><input type="text" id="pName" placeholder="Production Models"></label>
    <label class="field"><span>Description</span><textarea id="pDesc" rows="3" placeholder="What lives in this project?"></textarea></label>
    <button class="btn primary" style="width:100%;justify-content:center" id="mOk">Create project</button>`,
    { onOk: async () => {
      const name = $("#pName").value.trim();
      if (!name) { toast("Every project needs a name.", true); return false; }
      await api("/api/projects", { method: "POST",
        body: { name, description: $("#pDesc").value.trim() } });
      toast("Project created"); load();
    } });
  $("#exportBtn").onclick = () => openModal(`
    <h3>Export workspace data</h3>
    <p class="sub" style="color:var(--dim);font-size:13px">Download all your projects and models as a structured file.</p>
    <div style="display:flex;gap:12px;margin-top:18px">
      <button class="btn primary" style="flex:1;justify-content:center" id="exportJSON">
        ⬇ JSON</button>
      <button class="btn ghost" style="flex:1;justify-content:center" id="exportCSV">
        ⬇ CSV</button>
    </div>`, { wide: true, okLabel: "", onOk: () => false });
  const dl = (fmt) => {
    api("/api/projects/export/" + fmt).then(d => {
      const blob = new Blob([fmt === "json" ? JSON.stringify(d.data, null, 2) : d.csv],
        { type: fmt === "json" ? "application/json" : "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = d.filename || `modelsmith_export.${fmt}`;
      a.click(); toast("Export downloaded"); closeModal();
    }).catch(e => toast(e.message, true));
  };
  $("#exportJSON")?.addEventListener("click", () => dl("json"));
  $("#exportCSV")?.addEventListener("click", () => dl("csv"));
  await load();
}

/* ---------------- project detail ---------------- */
async function viewProject(pid) {
  let p;
  let selMode = false;
  const selSet = new Set();
  try { p = await api("/api/projects/" + pid); }
  catch (e) { toast(e.message, true); location.hash = "#/projects"; return; }
  document.title = `${p.name} · ModelSmith`;
  shell({ active: "projects",
    crumbs: `<a class="crumb-link" href="#/projects">Projects</a><span class="sep">/</span><b>${esc(p.name)}</b>`,
    actions: `<button class="btn primary" id="uploadBtn">⬆ Upload model</button>` }, `
    <div class="page-head">
      <div><h1>${esc(p.name)}</h1><div class="sub">${esc(p.description || "")}</div></div>
    </div>
    <div class="bento" id="projStats"></div>
    <div class="bento" id="modelGrid"></div>`);

  const drawModels = (models, filter = "all") => {
    const grid = $("#modelGrid");
    const shown = filter === "all" ? models : models.filter(m => m.status === filter);
    const counts = {
      all: models.length,
      analyzed: models.filter(m => m.status === "analyzed").length,
      analyzing: models.filter(m => m.status === "analyzing").length,
      failed: models.filter(m => m.status === "failed").length,
    };
    if (!models.length) {
      grid.innerHTML = `<div class="tile span12"><div class="empty-svg">${emptySVG("model")}</div>
        <div class="empty"><h3>Nothing uploaded yet</h3>
        <p>Upload a .pt, .pth or .onnx file to start the analysis workflow.</p>
        <button class="btn primary" id="emptyUploadBtn">⬆ Upload model</button></div></div>`;
      $("#emptyUploadBtn")?.addEventListener("click", () => $("#uploadBtn").click());
      return;
    }
    grid.innerHTML = `
    <div class="filter-row" style="grid-column:span 12">
      <div class="filter-chips">
        ${[["all", "All"], ["analyzed", "Ready"], ["analyzing", "Analyzing"], ["failed", "Failed"]]
          .map(([k, l]) => `<button class="fchip ${filter === k ? "on" : ""}" data-f="${k}">
            ${l}${counts[k] ? ` <i>${counts[k]}</i>` : ""}</button>`).join("")}
      </div>
      <div style="flex:1"></div>
      <button class="btn small ghost" id="selMode">${selMode ? "Done selecting" : "Select models"}</button>
    </div>
    ${selMode && selSet.size ? `
    <div class="bulk-bar" style="grid-column:span 12">
      <span>${selSet.size} selected</span>
      <div style="flex:1"></div>
      <button class="btn small ghost" id="selClear">Clear</button>
      <button class="btn small danger" id="selDelete">Delete selected</button>
    </div>` : ""}
    ${shown.length ? shown.map((m, i) => {
      const st = m.status === "analyzed" ? "good" : m.status === "failed" ? "bad" : "warn";
      return `
      <a class="tile span4 clickable model-tile ${selSet.has(m.id) ? "sel" : ""}" href="${selMode ? "javascript:void(0)" : `#/model/${m.id}`}" data-id="${m.id}" style="animation-delay:${i * 0.05}s">
        ${selMode ? `<span class="sel-check ${selSet.has(m.id) ? "on" : ""}" data-sel="${m.id}"></span>` : ""}
        <div class="t-head">
          <span class="t-title">${esc(m.name)}</span>
          <div class="right"><span class="pill ${st}">${m.status === "analyzing" ? '<span class="pulse"></span>' : ""}${m.status}</span></div>
        </div>
        <div class="kv">
          <span class="k">framework</span><span class="v">${esc(m.framework)}</span>
          <span class="k">size</span><span class="v">${fmtBytes(m.size_bytes)}</span>
          <span class="k">sha256</span><span class="v">${esc((m.sha256 || "").slice(0, 12))}…</span>
          <span class="k">added</span><span class="v">${timeago(m.created_at)}</span>
        </div>
      </a>`;
    }).join("") : `<div class="tile span12"><div class="empty" style="padding:28px">
      No models with status "${esc(filter)}" in this project.</div></div>`}`;
    $$(".fchip", grid).forEach(c => c.onclick = () => drawModels(models, c.dataset.f));
    $("#selMode", grid).onclick = () => { selMode = !selMode; drawModels(models, filter); };
    const selClear = $("#selClear", grid);
    if (selClear) selClear.onclick = () => { selSet.clear(); drawModels(models, filter); };
    const selDel = $("#selDelete", grid);
    if (selDel) selDel.onclick = async () => {
      const n = selSet.size;
      if (!await confirmModal(`Delete ${n} model${n > 1 ? "s" : ""}?`,
        "All runs and encrypted artifacts will also be deleted. This cannot be undone.", "Delete")) return;
      let ok = 0;
      for (const id of [...selSet]) {
        try { await api("/api/models/" + id, { method: "DELETE" }); ok++; }
        catch (e) { toast(e.message, true); }
      }
      toast(`${ok} deleted, ${n - ok} refused`);
      selSet.clear(); selMode = false;
      p = await api("/api/projects/" + pid); drawModels(p.models, "all");
    };
    $$(".sel-check", grid).forEach(ch => ch.onclick = e => {
      e.stopPropagation();
      const id = ch.dataset.sel;
      selSet.has(id) ? selSet.delete(id) : selSet.add(id);
      drawModels(models, filter);
    });
    $$(".tile.clickable", grid).forEach(c => c.onclick = e => {
      if (e.target.closest(".sel-check") || e.target.closest("[data-del]")) return;
      if (selMode) {
        const id = c.dataset.id;
        selSet.has(id) ? selSet.delete(id) : selSet.add(id);
        drawModels(models, filter);
        return;
      }
      location.hash = "#/model/" + c.dataset.id;
    });
  };
  drawModels(p.models);
  (async () => {
    try {
      const s = await api(`/api/projects/${pid}/stats`);
      const box = $("#projStats");
      if (!box) return;
      box.innerHTML = `
        <div class="tile span3 stat-tile"><div class="t-label">Total parameters</div>
          <div class="hero-num">${fmtNum(s.total_params)}</div></div>
        <div class="tile span3 stat-tile"><div class="t-label">Encrypted storage</div>
          <div class="hero-num">${(s.total_bytes / 1e6).toFixed(1)}<small> MB</small></div></div>
        ${s.best_run ? `
        <div class="tile span3 stat-tile accent-glow"><div class="t-label">Best win</div>
          <div class="hero-num" style="color:var(--good)">−${Math.round(s.best_run.saved)}<small>%</small></div>
          <div class="hero-sub">${esc(s.best_run.plan_name)} on ${esc(s.best_run.model)}</div></div>` : ""}
        ${s.heaviest_model ? `
        <div class="tile span3 stat-tile"><div class="t-label">Heaviest</div>
          <div class="hero-num">${fmtBytes(s.heaviest_model.size_bytes).split(" ")[0]}<small> ${fmtBytes(s.heaviest_model.size_bytes).split(" ")[1] || ""}</small></div>
          <div class="hero-sub">${esc(s.heaviest_model.name)}</div></div>` : ""}`;
    } catch {}
  })();

  $("#uploadBtn").onclick = () => { openModal(`
    <h3>Upload a model</h3>
    <div class="drop-zone" id="dz">
      <div style="font-size:30px">⬆</div>
      <div>Drop your model here, or <span style="color:var(--accent2)">browse</span></div>
      <div class="tag-mini" style="margin-top:4px">.pt / .pth (PyTorch full module) or .onnx</div>
      <input type="file" id="mFile" accept=".pt,.pth,.onnx" multiple hidden>
    </div>
      <label class="field"><span>Model name</span><input type="text" id="mName" placeholder="Product-Search ResNet"></label>
      <label class="field"><span>Input shape (optional, e.g. 3, 32, 32)</span><input type="text" id="mShape" placeholder="auto-detected"></label>
      <div class="upload-progress" id="uploadProgress" hidden>
        <div class="t-label" id="uploadStatus">Uploading…</div>
        <div class="bar" style="flex:1;height:6px;background:var(--line);border-radius:3px;overflow:hidden">
          <i id="uploadBar" style="display:block;height:100%;width:0;background:var(--accent);border-radius:3px;transition:width 0.3s var(--ease)"></i>
        </div>
        <div class="tag-mini" id="uploadPct" style="text-align:right;margin-top:4px">0%</div>
      </div>
      <button class="btn primary" style="width:100%;justify-content:center" id="mOk" disabled>Upload & analyze</button>
    <p class="tag-mini" style="margin-top:12px">Validated, SHA-256 fingerprinted, encrypted with Fernet/AES before touching disk. Analysis runs as a background job.</p>`,
    { onOk: async () => {
      const files = [...$("#mFile").files];
      const name = $("#mName").value.trim();
      if (!files.length) { toast("Choose a file first.", true); return false; }
      if (!name && files.length > 1) { toast("A base name is needed when uploading several at once.", true); return false; }
      if (!name) { toast("Model name is required", true); return false; }
      const prog = $("#uploadProgress"), bar = $("#uploadBar"),
            pct = $("#uploadPct"), status = $("#uploadStatus");
      prog.hidden = false; bar.style.width = "0%"; bar.style.background = "var(--accent)";
      /* single file keeps the classic path; several files upload in sequence */
      const sendOne = async (file, label) => {
        const fd = new FormData();
        fd.append("project_id", pid); fd.append("name", label);
        fd.append("input_shape", $("#mShape").value.trim()); fd.append("file", file);
        return new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", "/api/models/upload");
          xhr.setRequestHeader("Authorization", "Bearer " + state.token);
          xhr.onload = () => (xhr.status >= 200 && xhr.status < 300)
            ? resolve(JSON.parse(xhr.responseText))
            : reject(new Error(JSON.parse(xhr.responseText).detail?.message || JSON.parse(xhr.responseText).detail || `Upload failed (${xhr.status})`));
          xhr.onerror = () => reject(new Error("Network error"));
          xhr.send(fd);
        });
      };
      let ok = 0, firstId = null;
      for (let i = 0; i < files.length; i++) {
        const label = files.length === 1 ? name
          : `${name} ${String(i + 1).padStart(2, "0")}`;
        status.textContent = `Uploading ${i + 1} of ${files.length}: ${esc(files[i].name)}…`;
        bar.style.width = Math.round((i) / files.length * 100) + "%";
        try { const r = await sendOne(files[i], label); ok++; firstId = firstId || r.model_id; }
        catch (err) { toast(`${files[i].name}: ${err.message}`, true); }
      }
      bar.style.width = "100%";
      if (ok) {
        toast(ok === 1 ? "Model received. The profiler is already picking it apart."
                       : `${ok} of ${files.length} uploaded. Analysis running.`);
        location.hash = "#/model/" + firstId;
        return true;
      }
      status.textContent = "Upload failed";
      bar.style.background = "var(--bad)";
      return false;
    }, wide: false });
    wireUploadModal();
  };
  function wireUploadModal() {
    const root = $("#modalRoot");
    const dz = $("#dz", root), fi = $("#mFile", root);
    if (!dz || !fi) return;
    const check = () => { $("#mOk", root).disabled = !(fi.files.length && $("#mName", root).value.trim()); };
    dz.onclick = () => fi.click();
    dz.ondragover = e => { e.preventDefault(); dz.classList.add("drag"); };
    dz.ondragleave = () => dz.classList.remove("drag");
    dz.ondrop = e => { e.preventDefault(); dz.classList.remove("drag"); setFiles([...e.dataTransfer.files]); };
    fi.onchange = e => setFiles([...e.target.files]);
    let picked = [];
    function setFiles(files) {
      picked = files.filter(f => /\.(pt|pth|onnx)$/i.test(f.name));
      if (files.length && !picked.length) { toast("Supported formats: .pt, .pth and .onnx", true); return; }
      if (!picked.length) return;
      const dt = new DataTransfer(); picked.forEach(f => dt.items.add(f)); fi.files = dt.files;
      if (!$("#mName", root).value.trim())
        $("#mName", root).value = picked[0].name.replace(/\.(pt|pth|onnx)$/i, "");
      dz.innerHTML = picked.length === 1
        ? `<div style="font-size:30px">📄</div><div>${esc(picked[0].name)}</div>
           <div class="tag-mini">${fmtBytes(picked[0].size)} · ${esc(picked[0].name.split(".").pop())}</div>`
        : `<div style="font-size:30px">🗂</div><div>${picked.length} models queued</div>
           <div class="tag-mini">${picked.map(f => esc(f.name)).slice(0, 3).join(", ")}${picked.length > 3 ? ` +${picked.length - 3} more` : ""}</div>`;
      check();
    }
    $("#mName", root).addEventListener("input", check);
  }
}

/* ---------------- model detail ---------------- */
async function viewModel(mid, tab = "overview") {
  let m;
  try { m = await api("/api/models/" + mid); }
  catch (e) { toast(e.message, true); location.hash = "#/projects"; return; }
  document.title = `${m.name} · ModelSmith`;
  const tabs = [
    ["overview", "Overview"],
    ["analysis", "Analysis & Profile"],
    ["plans", "Goals · Plans · Compare"],
    ["runs", "Executions"],
    ["report", "Report"],
  ];
  shell({ active: "projects",
    crumbs: `<a class="crumb-link" href="#/projects">Projects</a><span class="sep">/</span>
             <a class="crumb-link" href="#/project/${m.project_id}">project</a><span class="sep">/</span><b>${esc(m.name)}</b>`,
    actions: `<button class="btn ghost small" id="dlReport">⬇ Report</button>
              <button class="btn ghost small" id="shareModel">🔗 Share</button>
              <button class="btn ghost small" id="renModel">Rename</button>
              <button class="btn ghost small danger" id="delModel">Delete</button>` }, `
    <div class="page-head">
      <div><h1 style="display:flex;align-items:center;gap:12px">${esc(m.name)}
        <span class="pill ${m.status === "analyzed" ? "good" : m.status === "failed" ? "bad" : "warn"}">
        ${m.status === "analyzing" ? '<span class="pulse"></span>' : ""}${m.status}</span></h1>
      <div class="sub">${esc(m.framework)} · ${fmtBytes(m.size_bytes)} ·
        <span class="pill ${m.efficiency_score >= 70 ? "good" : m.efficiency_score >= 40 ? "warn" : "bad"}"
          title="deployment readiness heuristic from size and measured latency">readiness ${m.efficiency_score ?? "-"}/100</span> ·
        <span class="mono" title="${esc(m.sha256 || "")}" style="cursor:copy" id="shaLine">${esc((m.sha256 || "").slice(0, 16))}…</span>
        <button class="copy-btn" data-copy="${esc(m.sha256 || "")}" title="Copy full SHA-256">⧉</button></div></div>
    </div>
    <div class="tabs" id="mTabs" role="tablist">${tabs.map(([k, l]) =>
      `<button class="tab ${k === tab ? "active" : ""}" role="tab" aria-selected="${k === tab}" data-tab="${k}">${l}</button>`).join("")}</div>
    <div id="tabBody"></div>`);
  $$("#mTabs .tab").forEach(t => t.onclick = () => viewModel(mid, t.dataset.tab));
  $$("[data-copy]").forEach(b => b.onclick = () => copyText(b.dataset.copy, "SHA-256 copied"));
  $("#shaLine")?.addEventListener("click", () => copyText(m.sha256 || "", "SHA-256 copied"));
  $("#shareModel").onclick = async () => {
    try {
      const r = await api(`/api/models/${mid}/share`, { method: "POST" });
      const url = location.origin + r.share_url;
      openModal(`<h3>Share this model</h3>
        <p class="sub" style="color:var(--dim);font-size:13px">Anyone with this link sees a read-only
        report card: architecture, best run, measured gains. No files, no token, no editing.</p>
        <pre class="report" style="max-height:64px;margin:12px 0" id="shareUrl">${esc(url)}</pre>
        <button class="btn primary" style="width:100%;justify-content:center" id="mOk">Copy link</button>`,
        { onOk: async () => { copyText(url, "Share link copied"); } });
    } catch (e) { toast(e.message, true); }
  };
  $("#renModel").onclick = () => openModal(`
    <h3>Rename model</h3>
    <label class="field"><span>New name</span><input type="text" id="rnName" value="${esc(m.name)}" maxlength="80"></label>
    <button class="btn primary" style="width:100%;justify-content:center" id="mOk">Save name</button>`,
    { onOk: async () => {
      const name = $("#rnName").value.trim();
      if (!name) { toast("Name is required", true); return false; }
      await api("/api/models/" + mid, { method: "PATCH", body: { name } });
      toast("Renamed")
      viewModel(mid, tab);
    } });
  $("#delModel").onclick = async () => {
    if (await confirmModal("Delete model?", "This removes the model, all its runs and encrypted artifacts. This cannot be undone.", "Delete model")) {
      try { await api("/api/models/" + mid, { method: "DELETE" }); toast("Model deleted, runs and all.")
        location.hash = "#/project/" + m.project_id; }
      catch (e) { toast(e.message, true); }
    }
  };
  $("#dlReport").onclick = () => {
    fetch("/api/models/" + mid + "/report", { headers: { Authorization: "Bearer " + state.token } })
      .then(r => { if (!r.ok) throw new Error(); return r.blob(); })
      .then(b => { const a = document.createElement("a");
        a.href = URL.createObjectURL(b); a.download = "modelsmith_report.md"; a.click();
        toast("Report downloaded") })
      .catch(() => toast("Report failed", true));
  };

  const body = $("#tabBody");
  if (m.status === "analyzing") {
    body.innerHTML = `<div class="tile span12"><div class="t-title">Analysis in progress</div><div id="jobBox"></div></div>`;
    pollJob(m.jobs?.[0]?.id, $("#jobBox"), () => viewModel(mid, tab),
      { cancellable: true, retryable: true });
    return;
  }
  if (m.status === "failed") {
    body.innerHTML = `<div class="tile span12"><div class="empty"><div class="big">⛔</div>
      Analysis failed: ${esc(m.error || "unknown error")}</div>
      ${m.jobs?.[0] ? `<div style="text-align:center;margin-top:-20px">
        <button class="btn ghost" id="retryAnalysis">↻ Retry analysis</button></div>` : ""}</div>`;
    $("#retryAnalysis")?.addEventListener("click", async () => {
      try {
        await api(`/api/jobs/${m.jobs[0].id}/retry`, { method: "POST" });
        toast("Analysis requeued"); viewModel(mid, tab);
      } catch (e) { toast(e.message, true); }
    });
    return;
  }
  try {
    ({ overview: renderOverview, analysis: renderAnalysisTab, plans: renderPlansTab,
       runs: renderRunsTab, report: renderReportTab })[tab](body, m);
  } catch (err) {
    body.innerHTML = `<div class="tile span12"><div class="empty">
      <div class="big">⛔</div>This tab failed to render: <code>${esc(err.message)}</code></div></div>`;
    console.error(err);
  }
}

function pollJob(jobId, box, onDone, opts = {}) {
  if (!jobId) return;
  const tick = async () => {
    try {
      const j = await api("/api/jobs/" + jobId);
      if (!document.body.contains(box)) { stopPolling(); return; }
      box.innerHTML = `
        <div class="progress-row">
          <div class="bar" style="flex:1"><i style="width:${j.progress}%"></i></div>
          <span class="pct">${j.progress}%</span>
          ${j.status === "queued" && opts.cancellable
            ? `<button class="btn small ghost" data-jcancel="${j.id}">Cancel</button>` : ""}
          ${j.status === "failed" && opts.retryable
            ? `<button class="btn small ghost" data-jretry="${j.id}">↻ Retry</button>` : ""}
        </div>
        <div class="tag-mini">${esc(j.message || j.status)}${j.status === "failed" && j.error ? " · " + esc(j.error) : ""}</div>`;
      const cancelBtn = $("[data-jcancel]", box);
      if (cancelBtn) cancelBtn.onclick = async () => {
        try {
          await api(`/api/jobs/${jobId}/cancel`, { method: "POST" });
          toast("Job cancelled"); stopPolling(); onDone && onDone(j);
        } catch (e) { toast(e.message, true); }
      };
      const retryBtn = $("[data-jretry]", box);
      if (retryBtn) retryBtn.onclick = async () => {
        try {
          await api(`/api/jobs/${jobId}/retry`, { method: "POST" });
          toast("Job requeued"); poll(tick, 1500);
        } catch (e) { toast(e.message, true); }
      };
      if (j.status === "success" || j.status === "failed") { stopPolling(); refreshBellDot(); onDone && onDone(j); }
    } catch { stopPolling(); }
  };
  poll(tick, 1500);
}

/* ----- overview tab ----- */
function renderOverview(body, m) {
  const a = m.analysis || {}, b = a.benchmark || {}, bn = a.bottlenecks || {};
  const plans = m.plans || {};
  const best = (plans.valid || [])[0];
  body.innerHTML = `
  <div class="bento">
    <div class="tile span12" id="diffTile" style="display:none">
      <div class="t-head"><span class="t-title">Before / after</span>
        <div class="right"><span class="tag-mini" id="diffRun"></span></div></div>
      <div class="tbl-wrap"><table class="tbl" id="diffTable"></table></div>
    </div>
    <div class="tile span12" id="histTile" style="display:none">
      <div class="t-head"><span class="t-title">Optimization history</span>
        <div class="right"><span class="tag-mini">size across every run</span></div></div>
      <div class="hist-wrap">
        <div id="histList"></div>
        <div class="chart-box" style="flex:1" id="histChart"></div>
      </div>
    </div>
    <div class="tile span8">
      <div class="t-head"><span class="t-title">Notes</span>
        <div class="right"><span class="tag-mini" id="tagsView"></span></div></div>
      <textarea id="modelNotes" class="notes-editor" rows="4"
        placeholder="What is this model for, who owns it, any deployment constraints…">${esc(m.notes || "")}</textarea>
      <div style="display:flex;gap:8px;margin-top:10px;align-items:center">
        <input type="text" id="modelTags" class="mono" style="flex:1;padding:8px 12px;border-radius:var(--r-sm);background:var(--bg);border:1px solid var(--line);color:var(--dim);font-size:12.5px" placeholder="tags, comma separated (e.g. vision, prod)" value="${esc((m.tags || []).join(", "))}">
        <button class="btn small primary" id="saveMeta">Save</button>
      </div>
    </div>
    <div class="tile span4">
      <div class="t-head"><span class="t-title">Original file</span></div>
      <div class="kv">
        <span class="k">filename</span><span class="v">${esc(m.orig_name || "-")}</span>
        <span class="k">size</span><span class="v">${fmtBytes(m.size_bytes)}</span>
        <span class="k">sha256</span><span class="v mono" style="font-size:10.5px">${esc((m.sha256 || "").slice(0, 18))}…</span>
      </div>
      <a class="btn ghost small" style="margin-top:12px;width:100%;justify-content:center" id="dlOriginal"
        href="/api/models/${m.id}/download" download>⬇ Download original</a>
      <p class="tag-mini" style="margin-top:8px;text-align:center">decrypted server-side, byte-identical to the upload</p>
    </div>
    <div class="tile span12" id="suggTile" style="display:none">
      <div class="t-head"><span class="t-title">What we would do next</span>
        <div class="right"><span class="pill accent">advice</span></div></div>
      <div class="sugg-row" id="suggRow"></div>
    </div>
    <div class="tile span8">
      <div class="t-head"><span class="t-title">Architecture flow</span>
        <div class="right"><span class="pill accent">${esc(a.arch || "-")}</span>
        <span class="pill violet">${fmtNum(a.layer_count)} layers</span></div></div>
      <div class="chart-box" id="archGraph"></div>
      <div class="tag-mini" style="margin-top:8px">Node size follows parameter count · amber = conv · ember = linear · gold = norm</div>
    </div>
    <div class="tile span4">
      <div class="t-head"><span class="t-title">Measured latency</span></div>
      <div style="display:grid;place-items:center"><div id="latGauge" style="width:150px"></div></div>
      <div class="chart-box" id="benchSpark" style="margin-top:10px"></div>
      <div class="tag-mini" style="text-align:center">p95 ${b.p95_ms ?? "-"} ms · ${b.throughput_fps ?? "-"} inf/s · ${esc(b.runtime || "")}</div>
    </div>
    <div class="tile span4">
      <div class="t-head"><span class="t-title">Compute budget</span></div>
      <div class="hero-num">${(a.total_flops / 1e6).toFixed(1)}<small> MFLOPs</small></div>
      <div class="hero-sub">per forward pass at ${esc((a.input_shape || []).join("×"))}</div>
      <div style="margin-top:14px" class="kv">
        <span class="k">parameters</span><span class="v">${fmtNum(a.total_params)}</span>
        <span class="k">param size</span><span class="v">${(a.param_size_mb ?? 0).toFixed(2)} MB</span>
        <span class="k">conv share</span><span class="v">${fmtPct(a.conv_param_share_pct)}</span>
      </div>
    </div>
    <div class="tile span4">
      <div class="t-head"><span class="t-title">Top plan</span>${best ? `<div class="right"><span class="pill accent">rank ${best.rank}</span></div>` : ""}</div>
      ${best ? `
        <div style="font-weight:700;font-size:15px">${esc(best.plan_id)}</div>
        <div style="color:var(--dim);font-size:12.5px;margin-bottom:10px">${esc(best.tagline)}</div>
        <div class="chip-row">${best.technique_labels.map(t => `<span class="tech-chip">${esc(t)}</span>`).join("")}</div>
        <div class="compare-grid">
          <div><div class="t-label">Size</div><div class="hero-num" style="font-size:19px;color:var(--good)">−${best.predicted.size_saved_pct}%</div></div>
          <div><div class="t-label">Latency</div><div class="hero-num" style="font-size:19px;color:var(--accent2)">−${best.predicted.latency_gain_pct}%</div></div>
          <div><div class="t-label">Accuracy</div><div class="hero-num" style="font-size:19px">${best.predicted.accuracy_retention_pct}%</div></div>
        </div>`
      : `<div class="empty" style="padding:20px">No valid plans</div>`}
    </div>
    <div class="tile span4">
      <div class="t-head"><span class="t-title">Bottlenecks</span></div>
      <ul class="notes">${(bn.notes || []).map(n => `<li>${esc(n)}</li>`).join("")}</ul>
    </div>
  </div>`;
  MSCharts.archGraph($("#archGraph"), a.layers || []);
  MSCharts.gauge($("#latGauge"), Math.min(100, (b.latency_ms || 0) * 2),
    { label: `${b.latency_ms ?? "-"} ms mean`, color: "#ffb224", size: 150 });
  const base = b.latency_ms || 1;
  MSCharts.sparkline($("#benchSpark"),
    Array.from({ length: 24 }, (_, i) => base * (1 + 0.25 * Math.sin(i * 1.7) + 0.08 * Math.sin(i * 5.3))));

  /* before/after diff vs best run */
  api(`/api/models/${m.id}/diff`).then(d => {
    const tile = $("#diffTile");
    if (!tile) return;
    tile.style.display = "";
    $("#diffRun").textContent = d.run.plan_name;
    const dir = (row) => row.delta == null ? "-" :
      (row.better === "higher" ? (row.delta > 0 ? "good" : "bad")
                                : (row.delta < 0 ? "good" : "bad"));
    $("#diffTable").innerHTML = `
      <tr><th>Metric</th><th class="num">Before</th><th class="num">After</th><th class="num">Change</th></tr>
      ${d.rows.map(row => `
        <tr><td>${row.metric}</td>
          <td class="num">${row.before ?? "-"}${row.unit}</td>
          <td class="num"><b>${row.after ?? "-"}${row.unit}</b></td>
          <td class="num" style="color:var(--${dir(row) === "good" ? "good" : "bad"})">
            ${row.delta == null ? "-" : (row.delta > 0 ? "+" : "") + row.delta}${row.unit}</td></tr>`).join("")}
      <tr><td>Output agreement</td><td class="num" colspan="3">
        ${d.agreement_pct != null ? `<b>${d.agreement_pct}%</b> on seeded inputs` : "not measured"}</td></tr>`;
  }).catch(() => {});

  /* run history timeline */
  api(`/api/models/${m.id}/history`).then(({ history, best_size_mb }) => {
    const tile = $("#histTile");
    if (!tile || history.length < 2) return;
    tile.style.display = "";
    $("#histList").innerHTML = history.map(h => `
      <div class="hist-item ${h.kind}">
        <span class="hist-dot"></span>
        <div><b>${esc(h.label || h.kind)}</b>
          <i>${h.size_mb != null ? h.size_mb.toFixed(1) + " MB" : "-"}${h.size_saved_pct != null ? " · −" + h.size_saved_pct + "%" : ""}</i></div>
        ${h.run_id ? `<button class="btn small ghost" data-rerun="${h.run_id}"
          title="Run this exact plan again">↻</button>` : `<span class="tag-mini">${timeago(h.ts)}</span>`}
      </div>`).join("");
    $$("[data-rerun]").forEach(b => b.onclick = async () => {
      try {
        const run = await api(`/api/runs/${b.dataset.rerun}`);
        await api(`/api/models/${m.id}/execute`, { method: "POST",
          body: { plan_id: run.plan_id } });
        toast("Plan re-executing",
          false, 4200, { label: "Watch", run: () => viewModel(m.id, "runs") });
        viewModel(m.id, "runs");
      } catch (e) { toast(e.message, true); }
    });
    if (best_size_mb != null) MSCharts.sparkline($("#histChart"),
      history.filter(h => h.size_mb != null).map(h => h.size_mb));
  }).catch(() => {});

  /* notes + tags */
  const saveMeta = $("#saveMeta");
  if (saveMeta) saveMeta.onclick = async () => {
    try {
      await api(`/api/models/${m.id}`, { method: "PATCH", body: {
        notes: $("#modelNotes").value,
        tags: $("#modelTags").value.split(",").map(t => t.trim()).filter(Boolean),
      } });
      toast("Saved")
    } catch (e) { toast(e.message, true); }
  };

  /* advice from the analysis itself */
  api(`/api/models/${m.id}/suggestions`).then(({ suggestions }) => {
    if (!suggestions?.length || !$("#suggTile")) return;
    $("#suggTile").style.display = "";
    $("#suggRow").innerHTML = suggestions.map(s => `
      <div class="sugg-card">
        <b>${esc(s.title)}</b>
        <p>${esc(s.body)}</p>
        <span>${esc(s.action)}</span>
      </div>`).join("");
  }).catch(() => {});
}

/* ----- analysis tab ----- */
let layerSort = { key: "params", dir: -1 };
function renderAnalysisTab(body, m) {
  const a = m.analysis || {}, bn = a.bottlenecks || {};
  const layers = (a.layers || []).filter(l => l.params > 0).slice(0, 6);
  body.innerHTML = `
  <div class="bento">
    <div class="tile span5">
      <div class="t-head"><span class="t-title">Parameter distribution</span>
        <div class="right"><span class="pill accent">FR-04</span></div></div>
      <div class="chart-box" id="paramDonut" style="display:flex;justify-content:center"></div>
    </div>
    <div class="tile span7">
      <div class="t-head"><span class="t-title">Compute per layer</span>
        <div class="right"><span class="pill violet">FLOPs</span></div></div>
      <div class="chart-box" id="flopsBars"></div>
    </div>
    <div class="tile span12">
      <div class="t-head"><span class="t-title">Layer breakdown</span>
        <div class="right"><span class="tag-mini">click a header to sort</span></div></div>
      <div class="tbl-wrap"><table class="tbl" id="layerTbl">
        <tr>
          <th data-sk="name" class="sortable">Layer</th><th data-sk="type" class="sortable">Type</th>
          <th data-sk="params" class="sortable num">Params</th>
          <th data-sk="share" class="sortable num">Share</th>
          <th data-sk="size" class="sortable num">Size</th>
          <th data-sk="flops" class="sortable num">FLOPs</th></tr>
        <tbody id="layerRows"></tbody>
      </table></div>
    </div>
    <div class="tile span12">
      <div class="t-head"><span class="t-title">Profiler notes</span><div class="right"><span class="pill accent">FR-05</span></div></div>
      <ul class="notes">${(bn.notes || []).map(n => `<li>${esc(n)}</li>`).join("")}</ul>
    </div>
  </div>`;
  MSCharts.donut($("#paramDonut"),
    layers.map(l => ({ label: l.type + " " + l.name, value: l.params })),
    { centerValue: fmtNum(a.total_params), centerLabel: "parameters",
      fmt: v => (100 * v / (a.total_params || 1)).toFixed(1) + "%" });
  MSCharts.hbars($("#flopsBars"),
    layers.map(l => ({ label: l.type.slice(0, 8) + " " + l.name.slice(0, 10), value: l.flops || 0.1 })),
    { fmt: v => v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? (v / 1e3).toFixed(0) + "K" : v });

  const drawRows = () => {
    const all = (a.layers || []).slice();
    const share = l => a.total_params ? 100 * l.params / a.total_params : 0;
    const key = layerSort.key;
    all.sort((x, y) => {
      const vx = key === "name" ? x.name : key === "type" ? x.type
        : key === "share" ? share(x) : key === "size" ? (x.size_bytes || 0) : (x[key] ?? 0);
      const vy = key === "name" ? y.name : key === "type" ? y.type
        : key === "share" ? share(y) : key === "size" ? (y.size_bytes || 0) : (y[key] ?? 0);
      if (typeof vx === "string") return vx.localeCompare(vy) * layerSort.dir;
      return ((vx ?? 0) - (vy ?? 0)) * layerSort.dir;
    });
    $("#layerRows").innerHTML = all.slice(0, 15).map(l => `
      <tr><td class="mono">${esc(l.name)}</td><td>${esc(l.type)}</td>
        <td class="num">${fmtNum(l.params)}</td>
        <td class="num">${share(l).toFixed(1)}%</td>
        <td class="num">${fmtBytes(l.size_bytes)}</td>
        <td class="num">${l.flops ? fmtNum(Math.round(l.flops / 1000)) + "K" : "-"}</td></tr>`).join("");
    $$("#layerTbl th.sortable").forEach(th => {
      const on = th.dataset.sk === key;
      th.classList.toggle("sorted", on);
      th.dataset.dir = on && layerSort.dir === 1 ? "asc" : "desc";
    });
  };
  $$("#layerTbl th.sortable").forEach(th => th.onclick = () => {
    if (layerSort.key === th.dataset.sk) layerSort.dir *= -1;
    else { layerSort.key = th.dataset.sk; layerSort.dir = -1; }
    drawRows();
  });
  drawRows();
}

/* ----- plans tab ----- */
let pickedPlans = new Set();
function renderPlansTab(body, m) {
  const goals = m.goals || { objective: "balanced", target_hardware: "cpu-server", min_accuracy_pct: 95 };
  const plans = m.plans || { valid: [], rejected: [] };
  const compareMode = pickedPlans.size > 0;
  body.innerHTML = `
  <div class="bento">
    <div class="tile span12">
      <div class="t-head"><span class="t-title">Deployment goals</span>
        <div class="right"><span class="pill accent">FR-06</span>
        <span class="tag-mini">plans re-rank instantly</span></div></div>
      <div class="compare-grid" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin:0">
        <label class="field" style="margin:0"><span>Objective</span>
          <select id="gObj">
            ${[["balanced", "Balanced"], ["min_size", "Smallest size"], ["min_latency", "Lowest latency"], ["min_memory", "Least memory"]]
              .map(([v, l]) => `<option value="${v}" ${goals.objective === v ? "selected" : ""}>${l}</option>`).join("")}
          </select></label>
        <label class="field" style="margin:0"><span>Target hardware</span>
          <select id="gHw">
            ${["cpu-server", "gpu-server", "edge-device", "mobile", "web-browser"]
              .map(h => `<option value="${h}" ${goals.target_hardware === h ? "selected" : ""}>${h}</option>`).join("")}
          </select></label>
        <label class="field" style="margin:0"><span>Min accuracy retention %</span>
          <input type="number" id="gAcc" min="50" max="100" value="${goals.min_accuracy_pct ?? 95}"></label>
        <div style="display:flex;align-items:flex-end">
          <button class="btn primary" id="gSave" style="width:100%;justify-content:center">Apply goals</button></div>
      </div>
    </div>
    <div class="tile span7">
      <div class="t-head"><span class="t-title">The Pareto frontier</span>
        <div class="right"><span class="tag-mini">dashed line: no plan beats it on both axes</span></div></div>
      <div class="chart-box" id="paretoChart"></div>
    </div>
    <div class="tile span5">
      <div class="t-head"><span class="t-title">What-if: accuracy floor</span>
        <div class="right"><span class="pill accent" id="sldVal">95%</span></div></div>
      <p class="tag-mini" style="margin-bottom:14px">Drag the minimum accuracy you can tolerate.
      Plans below the line disappear, live, no server round-trip.</p>
      <input type="range" id="accSlider" min="50" max="100" step="1" value="${goals.min_accuracy_pct ?? 95}" class="wi-slider">
      <div id="wiOut" class="wi-out"></div>
    </div>
    ${compareMode ? `
    <div class="tile span12 violet-glow">
      <div class="t-head"><span class="t-title">Plan comparison</span>
        <div class="right"><span class="pill violet">${pickedPlans.size} selected</span>
          <button class="btn small ghost" id="clearCmp">Clear</button></div></div>
      <div class="compare-grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
        <div class="chart-box" id="cmpRadar"></div>
        <div class="chart-box" id="cmpBars"></div>
      </div>
      <div class="tbl-wrap"><table class="tbl" id="cmpTable"></table></div>
    </div>` : ""}
    <div class="tile span12">
      <div class="t-head"><span class="t-title">Ranked plans</span>
        <div class="right"><span class="pill accent">${(plans.valid || []).length} valid</span>
          <span class="pill">${(plans.rejected || []).length} filtered</span>
          <span class="tag-mini">tick the corner checkbox to compare</span></div></div>
      <div class="bento" style="grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px">
        ${(plans.valid || []).map((p, i) => planCard(p, i)).join("")}
      </div>
    </div>
    ${(plans.rejected || []).length ? `
    <div class="tile span12">
      <div class="t-head"><span class="t-title">Filtered out: with reasons</span>
        <div class="right"><span class="pill">FR-08 explainability</span></div></div>
      <div class="tbl-wrap"><table class="tbl">
        <tr><th>Plan</th><th>Techniques</th><th>Why it was removed</th></tr>
        ${plans.rejected.map(p => `<tr><td class="mono">${esc(p.plan_id)}</td>
          <td class="muted">${p.technique_labels.map(esc).join(" + ")}</td>
          <td class="muted">${p.rejected_because.map(esc).join(" · ")}</td></tr>`).join("")}
      </table></div>
    </div>` : ""}
  </div>`;

  $("#gSave").onclick = async () => {
    try {
      await api(`/api/models/${m.id}/goals`, { method: "PUT", body: {
        objective: $("#gObj").value, target_hardware: $("#gHw").value,
        min_accuracy_pct: parseFloat($("#gAcc").value) || 95 } });
      toast("Goals applied. The rankings shuffled accordingly."); pickedPlans.clear();
      viewModel(m.id, "plans");
    } catch (e) { toast(e.message, true); }
  };
  $$(".execBtn").forEach(b => b.onclick = async () => {
    if (await confirmModal("Execute plan?", `"${b.dataset.name}" runs the real optimization pipeline as a background job.`, "Execute")) {
      try {
        await api(`/api/models/${m.id}/execute`, { method: "POST", body: { plan_id: b.dataset.plan } });
        toast("Execution started. Watch the Executions tab.", false, 4200, { label: "Watch", run: () => viewModel(m.id, "runs") }); viewModel(m.id, "runs");
      } catch (e) { toast(e.message, true); }
    }
  });
  /* one-line plan summaries, clipboard-ready */
  $$("[data-copysummary]").forEach(b => b.onclick = () => {
    const p = (plans.valid || [])[+b.dataset.i];
    if (!p) return;
    copyText(`${p.plan_id}: −${p.predicted.size_saved_pct}% size, −${p.predicted.latency_gain_pct}% latency, ${p.predicted.accuracy_retention_pct}% accuracy retained (${p.technique_labels.join(" + ")})`,
      "Plan summary copied");
  });
  /* number keys toggle comparison without leaving the keyboard */
  const keyHunt = e => {
    if (/^[1-9]$/.test(e.key) && !/INPUT|SELECT/.test(document.activeElement?.tagName || "")) {
      const all = plans.valid || [];
      const idx = +e.key - 1;
      if (all[idx]) {
        pickedPlans.has(all[idx].plan_id) ? pickedPlans.delete(all[idx].plan_id)
          : pickedPlans.size < 3 ? pickedPlans.add(all[idx].plan_id)
          : toast("Compare up to 3 plans", true);
        renderPlansTab($("#tabBody"), m);
      }
    }
  };
  document.removeEventListener("keydown", keyHunt);
  document.addEventListener("keydown", keyHunt);
  $$(".cmp-check").forEach(c => c.onclick = e => {
    e.stopPropagation();
    if (pickedPlans.has(c.dataset.plan)) pickedPlans.delete(c.dataset.plan);
    else if (pickedPlans.size < 3) pickedPlans.add(c.dataset.plan);
    else { toast("Compare up to 3 plans", true); return; }
    renderPlansTab($("#tabBody"), m);
  });
  const clr = $("#clearCmp");
  if (clr) clr.onclick = () => { pickedPlans.clear(); renderPlansTab($("#tabBody"), m); };

  /* pareto frontier */
  const pchart = $("#paretoChart");
  if (pchart && MSCharts.pareto && (plans.valid || []).length)
    MSCharts.pareto(pchart, plans.valid, { width: 520, height: 300 });

  /* what-if accuracy slider: client-side re-filter using stored predictions */
  const sld = $("#accSlider"), sldVal = $("#sldVal"), wiOut = $("#wiOut");
  if (sld) {
    const apply = () => {
      const floor = +sld.value;
      sldVal.textContent = floor + "%";
      const all = plans.valid || [];
      const pass = all.filter(p => p.predicted.accuracy_retention_pct >= floor);
      wiOut.innerHTML = `
        <div class="wi-row"><span>plans surviving</span><b>${pass.length} of ${all.length}</b></div>
        ${pass.length ? `<div class="wi-row"><span>new top plan</span><b>${pass[0].plan_id}</b></div>
        <div class="wi-row"><span>its size cut</span><b class="win">−${pass[0].predicted.size_saved_pct}%</b></div>`
        : `<div class="wi-row none">At ${floor}% no plan survives the filter.</div>`}`;
      localStorage.setItem("ms_wi_floor", String(floor));
    };
    sld.addEventListener("input", apply);
    apply();
  }

  if (compareMode) drawComparison(m, plans.valid || []);
}

function planCard(p, i) {
  const pr = p.predicted;
  const picked = pickedPlans.has(p.plan_id);
  return `
  <div class="plan-card ${p.recommended ? "recommended" : ""} ${picked ? "picked" : ""}" style="animation-delay:${i * 0.06}s">
    <span class="rank-badge">${p.recommended ? "★ RECOMMENDED" : "RANK " + p.rank}</span>
    <div class="cmp-check" data-plan="${esc(p.plan_id)}" title="Compare">✓</div>
    <div class="plan-head">
      <div>
        <div class="name">${esc(p.plan_id)}</div>
        <div class="tag">${esc(p.tagline)}</div>
      </div>
      ${p.auto_executable ? `<span class="pill good">auto</span>` : `<span class="pill warn">guided</span>`}
    </div>
    <div class="chip-row">${p.technique_labels.map(t => `<span class="tech-chip">${esc(t)}</span>`).join("")}</div>
    <div class="compare-grid">
      <div><div class="t-label">Size</div><div class="hero-num" style="font-size:18px">${pr.size_mb}<small> MB</small></div>
        <div class="hero-sub" style="color:var(--good)">−${pr.size_saved_pct}%</div></div>
      <div><div class="t-label">Latency</div><div class="hero-num" style="font-size:18px">${pr.latency_ms}<small> ms</small></div>
        <div class="hero-sub" style="color:var(--accent2)">−${pr.latency_gain_pct}%</div></div>
      <div><div class="t-label">Memory</div><div class="hero-num" style="font-size:18px">${pr.memory_mb}<small> MB</small></div>
        <div class="hero-sub" style="color:var(--cyan)">−${pr.memory_saved_pct}%</div></div>
      <div><div class="t-label">Accuracy</div><div class="hero-num" style="font-size:18px">${pr.accuracy_retention_pct}<small>%</small></div>
        <div class="hero-sub">retained</div></div>
    </div>
    <ul class="notes" style="margin:6px 0 12px">${p.reasons.slice(0, 3).map(r => `<li>${esc(r)}</li>`).join("")}</ul>
    <div style="display:flex;gap:8px">
      <button class="btn execBtn ${p.auto_executable ? "primary" : ""}" style="flex:1;justify-content:center"
        ${p.auto_executable ? "" : "disabled title='Manual technique: follow the guided reasons'"}
        data-plan="${esc(p.plan_id)}" data-name="${esc(p.tagline)}"
        id="exec-${esc(p.plan_id)}">
        ${p.auto_executable ? "▶ Execute plan" : "◇ Guided: not auto-executable"}</button>
      <button class="btn small ghost" data-copysummary="${esc(p.plan_id)}" data-i="${i}"
        title="Copy a one-line summary for chat or a PR">
        ⧉</button>
    </div>
    <div class="plan-kbd">${i < 9 ? `<kbd>${i + 1}</kbd> to compare · ` : ""}<kbd>↵</kbd> ${p.auto_executable ? "executes" : "guided"}</div>
  </div>`;
}

function drawComparison(m, validPlans) {
  const sel = validPlans.filter(p => pickedPlans.has(p.plan_id));
  if (!sel.length) return;
  const axes = ["Size cut", "Speed", "Memory", "Accuracy"];
  const colors = ["#ffb224", "#ff6b2c", "#34d399"];
  MSCharts.radar($("#cmpRadar"), axes, sel.map((p, i) => ({
    name: p.plan_id, color: colors[i % 3],
    values: [p.predicted.size_saved_pct, p.predicted.latency_gain_pct,
             p.predicted.memory_saved_pct, p.predicted.accuracy_retention_pct].map(v => v / 100),
  })), { size: 240 });
  MSCharts.hbars($("#cmpBars"),
    [{ label: "original", value: m.analysis?.param_size_mb || m.analysis?.file_size_mb || 1, color: "#3a4358" },
     ...sel.map(p => ({ label: p.plan_id, value: p.predicted.size_mb }))],
    { fmt: v => v.toFixed(2) + " MB" });
  $("#cmpTable").innerHTML = `
    <tr><th>Metric</th>${sel.map(p => `<th class="num">${esc(p.plan_id)}</th>`).join("")}</tr>
    ${[["Predicted size (MB)", p => p.predicted.size_mb], ["Size saved", p => "−" + p.predicted.size_saved_pct + "%"],
       ["Predicted latency (ms)", p => p.predicted.latency_ms], ["Latency gain", p => "−" + p.predicted.latency_gain_pct + "%"],
       ["Memory (MB)", p => p.predicted.memory_mb], ["Accuracy retention", p => p.predicted.accuracy_retention_pct + "%"],
       ["Score", p => p.score], ["Execution", p => p.auto_executable ? "automatic" : "guided"]]
      .map(([label, fn]) => `<tr><td class="muted">${label}</td>${sel.map(p => `<td class="num">${fn(p)}</td>`).join("")}</tr>`).join("")}`;
}

/* ----- runs tab ----- */
function renderRunsTab(body, m) {
  const runs = m.runs || [];
  if (!runs.length) {
    body.innerHTML = `<div class="tile span12"><div class="empty-svg">${emptySVG("jobs")}</div>
      <div class="empty"><h3>No runs yet</h3>
      <p>Choose a plan on the Plans tab and execute it to get real numbers.</p></div></div>`;
    return;
  }
  body.innerHTML = runs.map((r, idx) => {
    const bm = r.benchmark || {};
    const base = bm.baseline || {}, opt = bm.optimized || {};
    const ag = (bm.output_agreement || {}).agreement_pct;
    return `
    <div class="tile span12" style="margin-bottom:14px;${idx ? "animation-delay:" + idx * 0.05 + "s" : ""}" id="run-${r.id}">
      <div class="t-head">
        <span class="t-title">▶ ${esc(r.plan_name)} <span class="pill ${r.status === "success" ? "good" : r.status === "failed" ? "bad" : "warn"}">
          ${r.status === "running" || r.status === "queued" ? '<span class="pulse"></span>' : ""}${r.status}</span></span>
        <div class="right"><span class="tag-mini mono">${r.id}</span><span class="tag-mini">${timeago(r.created_at)}</span></div>
      </div>
      ${r.status === "queued" || r.status === "running" ? `<div class="jobBox"></div>` : ""}
      ${r.status === "failed" ? `<div style="color:var(--bad);font-size:13px">⛔ ${esc(r.error || "failed")}</div>` : ""}
      ${r.status === "success" ? `
      <div class="bento" style="grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px">
        <div class="tile span4" style="padding:16px;animation:none">
          <div class="t-label">Results</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px" id="gauges-${r.id}">
            <div class="chart-box" style="width:104px" id="g1-${r.id}"></div>
            <div class="chart-box" style="width:104px" id="g2-${r.id}"></div>
            <div class="chart-box" style="width:104px" id="g3-${r.id}"></div>
          </div>
        </div>
        <div class="tile span8" style="padding:16px;animation:none">
          <div class="t-label">Measured: original vs optimized</div>
          <div class="chart-box" id="cmp-${r.id}" style="margin-top:8px"></div>
        </div>
        <div class="tile span12" style="padding:16px;animation:none">
          <div class="t-label">Pipeline</div>
          <div class="pipe" style="margin-top:10px">
            ${(r.steps || []).map(s => `
              <div class="pipe-step ${s.status === "success" ? "done" : s.status === "failed" ? "failed" : s.status === "running" ? "running" : ""}">
                <div class="pipe-ico">${s.status === "success" ? "✓" : s.status === "failed" ? "✕" : s.status === "guided" ? "◇" : "…"}</div>
                <div class="body">
                  <div class="nm">${esc(s.label)} <span class="pill ${s.status === "success" ? "good" : s.status === "failed" ? "bad" : s.status === "partial" ? "warn" : ""}" style="font-size:10px">${s.status}</span></div>
                  ${s.note ? `<div class="ds">${esc(s.note)}</div>` : ""}
                </div>
              </div>`).join("")}
          </div>
          <div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
            ${(r.artifacts || []).map(a => `<button class="btn small" data-dl="${esc(a.name)}" data-run="${r.id}">⬇ ${esc(a.name)} · ${fmtBytes(a.size_bytes)}</button>`).join("")}
            <button class="btn small ghost" data-script="${r.id}" title="Download a Python script that reproduces this run">⬇ repro .py</button>
            <div style="flex:1"></div>
            <span class="pill" title="reproducibility metadata (NFR-09)">repro · torch ${esc((r.repro?.versions?.torch || "").split("+")[0])} · seed ${r.repro?.seed ?? "-"} · ${esc(r.repro?.platform?.machine || "")}</span>
          </div>
        </div>
      </div>` : ""}
    </div>`;
  }).join("");

  /* celebrate fresh big wins: finished within the last minute and >= 50% saved */
  runs.forEach(r => {
    if (r.status !== "success") return;
    const fresh = r.finished_at && (Date.now() / 1000 - r.finished_at) < 90;
    const big = (r.benchmark?.size_saved_pct ?? 0) >= 50;
    if (fresh && big && !renderRunsTab._cheered?.has(r.id)) {
      (renderRunsTab._cheered ??= new Set()).add(r.id);
      celebrate(big ? (r.benchmark.size_saved_pct >= 75 ? 1.4 : 1) : 0.6);
      toast(`Size reduced by ${r.benchmark.size_saved_pct}%`);
    }
  });

  runs.filter(r => r.status === "success").forEach(r => {
    const bm = r.benchmark || {}, base = bm.baseline || {}, opt = bm.optimized || {};
    const ag = (bm.output_agreement || {}).agreement_pct;
    MSCharts.gauge($(`#g1-${r.id}`), bm.size_saved_pct ?? 0, { label: "size saved", color: "#34d399", size: 104 });
    MSCharts.gauge($(`#g2-${r.id}`), bm.latency_gain_pct ?? 0, { label: "faster", color: "#ffb224", size: 104, signed: true });
    MSCharts.gauge($(`#g3-${r.id}`), ag ?? 0, { label: "agreement", color: "#ff6b2c", size: 104 });
    MSCharts.compareBars($(`#cmp-${r.id}`), [
      { label: "Size (MB)", before: base.size_mb, after: opt.size_mb, unit: "MB" },
      { label: "Latency (ms)", before: base.latency_ms, after: opt.latency_ms, unit: "ms" },
    ], { fmt: v => v == null ? "n/a" : v.toFixed(2) });
  });

  const inflight = runs.find(r => r.status === "queued" || r.status === "running");
  if (inflight) {
    const job = (m.jobs || []).find(j => j.status === "queued" || j.status === "running");
    if (job) pollJob(job.id, $(`#run-${inflight.id} .jobBox`), () => viewModel(m.id, "runs"));
  }
  $$("[data-dl]").forEach(b => b.onclick = async () => {
    try {
      const blob = await api(`/api/runs/${b.dataset.run}/artifacts/${b.dataset.dl}/download`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = b.dataset.dl; a.click();
      toast("Artifact downloaded")
    } catch (e) { toast(e.message, true); }
  });
  /* reproducible script download */
  $$("[data-script]").forEach(b => b.onclick = () => {
    fetch(`/api/runs/${b.dataset.script}/script`,
          { headers: { Authorization: "Bearer " + state.token } })
      .then(r => { if (!r.ok) throw new Error(); return r.blob(); })
      .then(blob => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `repro_${b.dataset.script}.py`; a.click();
        toast("Reproduction script downloaded")
      })
      .catch(() => toast("Script generation failed", true));
  });
}

/* ----- report tab ----- */
async function renderReportTab(body, m) {
  body.innerHTML = `<div class="tile span12"><div class="skeleton" style="height:300px"></div></div>`;
  try {
    const resp = await fetch(`/api/models/${m.id}/report`, { headers: { Authorization: "Bearer " + state.token } });
    const md = await resp.text();
    body.innerHTML = `<div class="tile span12">
      <div class="t-head"><span class="t-title">Full report</span>
        <div class="right"><span class="pill accent">FR-14</span>
        <span class="tag-mini">same content as the downloadable .md</span></div></div>
      <pre class="report">${esc(md)}</pre></div>`;
  } catch (e) { toast(e.message, true); }
}

/* ---------------- admin ---------------- */
async function viewAdmin() {
  if (state.user?.role !== "admin") { toast("Admins only", true); location.hash = "#/dashboard"; return; }
  let ov, users;
  try {
    [ov, users] = await Promise.all([api("/api/admin/overview"), api("/api/admin/users")]);
  } catch (e) { toast(e.message, true); location.hash = "#/dashboard"; return; }
  const t = ov.totals;
  shell({ active: "admin", crumbs: "<b>Administration</b>" }, `
    <div class="page-head"><div><h1>Administration</h1>
      <div class="sub">The whole platform at a glance, plus the levers.</div></div></div>
    <div class="bento">
      <div class="tile span3"><div class="t-label">Users</div><div class="hero-num">${t.users}</div>
        <div class="hero-sub">${users.users.filter(u => u.is_active).length} active</div></div>
      <div class="tile span3"><div class="t-label">Projects</div><div class="hero-num">${t.projects}</div></div>
      <div class="tile span3"><div class="t-label">Models</div><div class="hero-num">${t.models}</div>
        <div class="hero-sub">${t.runs} optimization runs</div></div>
      <div class="tile span3"><div class="t-label">Jobs</div>
        <div class="hero-num" style="font-size:22px"><span style="color:var(--good)">${t.jobs.success || 0}</span>
          <small>/</small> <span style="color:var(--bad)">${t.jobs.failed || 0}</span></div>
        <div class="hero-sub">success / failed</div></div>

      <div class="tile span7">
        <div class="t-head"><span class="t-title">Users</span></div>
        <div class="tbl-wrap"><table class="tbl">
          <tr><th>Email</th><th>Role</th><th>Status</th><th style="text-align:right">Actions</th></tr>
          ${users.users.map(u => `
            <tr><td>${esc(u.email)}<div class="muted" style="font-size:11px">${esc(u.full_name || "")}</div></td>
              <td><span class="pill ${u.role === "admin" ? "accent" : ""}">${u.role}</span></td>
              <td><span class="pill ${u.is_active ? "good" : "bad"}">${u.is_active ? "active" : "disabled"}</span></td>
              <td style="text-align:right">${u.id === state.user.id ? `<span class="tag-mini">you</span>` : `
                <button class="btn small" data-ua="${u.id}" data-act="${u.is_active ? "disable" : "enable"}">${u.is_active ? "Disable" : "Enable"}</button>
                <button class="btn small ghost" data-ua="${u.id}" data-act="${u.role === "admin" ? "demote" : "promote"}">${u.role === "admin" ? "Demote" : "Promote"}</button>`}</td></tr>`).join("")}
        </table></div>
      </div>
      <div class="tile span5">
        <div class="t-head"><span class="t-title">Recent jobs</span><div class="right"><span class="pill">NFR-03</span></div></div>
        ${ov.recent_jobs.map(j => `
          <div class="feed-item">
            <span class="feed-dot" style="background:${j.status === "success" ? "var(--good)" : j.status === "failed" ? "var(--bad)" : "var(--accent)"}"></span>
            <div style="flex:1"><div class="tx"><b>${j.type}</b>: ${esc((j.message || j.status).slice(0, 38))}</div>
            <div class="tm">${esc(j.email || "")} · ${timeago(j.created_at)}</div></div>
          </div>`).join("")}
      </div>
      <div class="tile span12">
        <div class="t-head"><span class="t-title">Audit log</span>
          <div class="right">
            <button class="btn small ghost" id="auditExport">⬇ Export CSV</button>
            <span class="pill accent">NFR-08</span></div></div>
        <div class="tbl-wrap"><table class="tbl">
          <tr><th>Action</th><th>Entity</th><th>User</th><th>Detail</th><th>When</th></tr>
          ${ov.audit_log.map(a => `<tr><td class="mono">${esc(a.action)}</td>
            <td>${esc(a.entity)}${a.entity_id ? " <span class='muted mono' style='font-size:11px'>" + esc(a.entity_id.slice(0, 8)) + "</span>" : ""}</td>
            <td class="muted">${esc(a.email || "-")}</td><td class="muted">${esc((a.detail || "").slice(0, 60))}</td>
            <td class="muted">${timeago(a.created_at)}</td></tr>`).join("")}
        </table></div>
      </div>
    </div>`);

  /* storage breakdown tile */
  api("/api/admin/stats/storage").then(st => {
    const grid = $(".bento");
    if (!grid) return;
    grid.insertAdjacentHTML("beforeend", `
      <div class="tile span5">
        <div class="t-head"><span class="t-title">Storage</span>
          <div class="right"><span class="pill good">${st.encrypted_share_pct}% encrypted</span></div></div>
        <div class="hero-num">${(st.total_bytes / 1e6).toFixed(1)}<small> MB on disk</small></div>
        <div class="kv" style="margin-top:10px">
          <span class="k">encrypted uploads</span><span class="v">${st.uploads.files} files · ${fmtBytes(st.uploads.bytes)}</span>
          <span class="k">run artifacts</span><span class="v">${st.artifacts.files} files · ${fmtBytes(st.artifacts.bytes)}</span>
          <span class="k">database</span><span class="v">${fmtBytes(st.database_bytes)}</span>
        </div>
      </div>`);
  }).catch(() => {});
  $("#auditExport").onclick = () => {
    api("/api/admin/audit/export").then(csv => {
      const blob = new Blob([csv], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "modelsmith_audit_log.csv"; a.click();
      toast("Audit log exported")
    }).catch(e => toast(e.message, true));
  };
  $$("[data-ua]").forEach(b => b.onclick = async () => {
    try { await api(`/api/admin/users/${b.dataset.ua}`, { method: "PATCH", body: { action: b.dataset.act } });
      toast("User updated."); viewAdmin(); }
    catch (e) { toast(e.message, true); }
  });
}

/* ---------------- compare models ---------------- */
async function viewCompare(idA, idB) {
  if (!state.token) { location.hash = "#/login"; return; }
  let data;
  try {
    data = await api(`/api/models/compare?model_a=${idA}&model_b=${idB}`);
  } catch (e) { toast(e.message, true); location.hash = "#/search"; return; }
  const a = data.model_a, b = data.model_b;
  const aa = a.analysis || {}, ab = b.analysis || {};
  const side = (m, an) => `
    <div class="tile span6">
      <div class="t-head"><span class="t-title">${esc(m.name)}</span>
        <a class="pill ghost" href="#/model/${m.id}">View →</a></div>
      <div class="kv">
        <span class="k">framework</span><span class="v">${esc(m.framework)}</span>
        <span class="k">file size</span><span class="v">${fmtBytes(m.size_bytes)}</span>
        <span class="k">parameters</span><span class="v">${fmtNum(an.total_params)}</span>
        <span class="k">layers</span><span class="v">${fmtNum(an.layer_count)}</span>
        <span class="k">MFLOPs</span><span class="v">${(an.total_flops / 1e6).toFixed(1)}</span>
        <span class="k">param size</span><span class="v">${(an.param_size_mb ?? 0).toFixed(2)} MB</span>
      </div>
      <div class="chart-box" style="margin-top:12px" id="cmpDonut-${m.id}"></div>
    </div>`;
  shell({ active: "projects",
    crumbs: `<a class="crumb-link" href="#/search">Search</a><span class="sep">/</span><b>Compare</b>` }, `
    <div class="page-head">
      <div><h1>Model comparison</h1>
      <div class="sub">Side by side, with the better value on each metric highlighted.</div></div>
    </div>
    <div class="bento">
      ${side(a, aa)}${side(b, ab)}
      <div class="tile span6">
        <div class="t-head"><span class="t-title">Parameter distribution</span></div>
        <div class="chart-box" id="cmpParams"></div>
      </div>
      <div class="tile span6">
        <div class="t-head"><span class="t-title">FLOPs per layer (top 8)</span></div>
        <div class="chart-box" id="cmpFlops"></div>
      </div>
      <div class="tile span12">
        <div class="t-head"><span class="t-title">Head-to-head metrics</span>
          <div class="right"><span class="tag-mini">green ring marks the winner</span></div></div>
        <div class="tbl-wrap"><table class="tbl">
          <tr><th>Metric</th><th class="num">${esc(a.name)}</th><th class="num">${esc(b.name)}</th><th class="num">Difference</th></tr>
          ${[
            ["Parameters", aa.total_params, ab.total_params, "params", false],
            ["Layers", aa.layer_count, ab.layer_count, "count", false],
            ["MFLOPs", +(aa.total_flops / 1e6).toFixed(1), +(ab.total_flops / 1e6).toFixed(1), "flops", false],
            ["Param size (MB)", +(aa.param_size_mb ?? 0).toFixed(2), +(ab.param_size_mb ?? 0).toFixed(2), "size", false],
            ["File size", a.size_bytes, b.size_bytes, "bytes", false],
          ].map(([label, va, vb, fmt]) => {
            const diff = vb > va ? `+${fmtNum(vb - va)}` : fmtNum(va - vb);
            const aWins = va < vb;   /* smaller is better for every metric here */
            return `<tr><td>${label}</td>
              <td class="num ${aWins ? "winner-cell" : ""}">${fmt === "bytes" ? fmtBytes(va) : fmtNum(va)}</td>
              <td class="num ${!aWins ? "winner-cell" : ""}">${fmt === "bytes" ? fmtBytes(vb) : fmtNum(vb)}</td>
              <td class="num" style="color:${aWins ? "var(--warn)" : "var(--good)"}">${diff}</td></tr>`;
          }).join("")}
        </table></div>
      </div>
    </div>`);
  // donut charts for each model
  const topLayers = (an, n) => (an.layers || []).filter(l => l.params > 0).slice(0, n);
  const topA = topLayers(aa, 5), topB = topLayers(ab, 5);
  MSCharts.donut($(`#cmpDonut-${a.id}`),
    topA.map(l => ({ label: l.type.slice(0, 6) + " " + l.name.slice(0, 8), value: l.params })),
    { centerValue: fmtNum(aa.total_params), centerLabel: "params",
      fmt: v => (100 * v / (aa.total_params || 1)).toFixed(1) + "%" });
  MSCharts.donut($(`#cmpDonut-${b.id}`),
    topB.map(l => ({ label: l.type.slice(0, 6) + " " + l.name.slice(0, 8), value: l.params })),
    { centerValue: fmtNum(ab.total_params), centerLabel: "params",
      fmt: v => (100 * v / (ab.total_params || 1)).toFixed(1) + "%" });
  // grouped bars: params
  MSCharts.hbars($("#cmpParams"), [
    ...topA.map(l => ({ label: "A: " + l.type.slice(0, 6), value: l.params, color: "#ffb224" })),
    ...topB.map(l => ({ label: "B: " + l.type.slice(0, 6), value: l.params, color: "#ff6b2c" })),
  ].slice(0, 8), { fmt: v => fmtNum(v) });
  // FLOPs
  MSCharts.hbars($("#cmpFlops"), [
    ...topA.map(l => ({ label: "A: " + l.type.slice(0, 6), value: l.flops || 0.1, color: "#ffb224" })),
    ...topB.map(l => ({ label: "B: " + l.type.slice(0, 6), value: l.flops || 0.1, color: "#ff6b2c" })),
  ].slice(0, 8), { fmt: v => v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : fmtNum(Math.round(v)) });
}

/* ---------------- settings ---------------- */
async function viewSettings() {
  if (!state.token) { location.hash = "#/login"; return; }
  let me;
  try { me = await api("/api/auth/me"); }
  catch (e) { toast(e.message, true); location.hash = "#/dashboard"; return; }
  shell({ active: "settings", crumbs: "<b>Settings</b>" }, `
    <div class="page-head">
      <div><h1>Settings</h1>
      <div class="sub">Profile, security and session details.</div></div>
    </div>
    <div class="bento">
      <div class="tile span6">
        <div class="t-head"><span class="t-title">Profile</span></div>
        <div class="settings-avatar-row">
          <div class="avatar big">${esc(initials(me))}</div>
          <div class="field" style="flex:1;margin:0">
            <span>Full name</span>
            <input type="text" id="sName" value="${esc(me.full_name || "")}" maxlength="80">
          </div>
        </div>
        <div class="kv" style="margin-top:14px">
          <span class="k">email</span><span class="v">${esc(me.email)}</span>
          <span class="k">role</span><span class="v">${esc(me.role)}</span>
          <span class="k">member since</span><span class="v">${new Date((me.created_at || 0) * 1000).toLocaleDateString()}</span>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:16px">
          <button class="btn primary" id="saveProfile">Save profile</button>
        </div>
      </div>

      <div class="tile span6">
        <div class="t-head"><span class="t-title">Security: change password</span></div>
        <label class="field"><span>Current password</span>
          <input type="password" id="sCur" placeholder="••••••••" autocomplete="current-password"></label>
        <label class="field"><span>New password (min 8 chars)</span>
          <input type="password" id="sNew" placeholder="••••••••" autocomplete="new-password"></label>
        <label class="field"><span>Confirm new password</span>
          <input type="password" id="sNew2" placeholder="••••••••" autocomplete="new-password"></label>
        <div style="display:flex;justify-content:flex-end;margin-top:4px">
          <button class="btn primary" id="savePass">Update password</button>
        </div>
      </div>

      <div class="tile span6">
        <div class="t-head"><span class="t-title">Appearance</span>
          <div class="right"><span class="pill accent">forge</span></div></div>
        <div class="kv">
          <span class="k">theme</span><span class="v">The Forge: warm charcoal + molten amber</span>
          <span class="k">font pairing</span><span class="v">Bricolage Grotesque · Inter · JetBrains Mono</span>
          <span class="k">motion</span><span class="v" id="motionPref">expo ease-out</span>
        </div>
        <p class="tag-mini" style="margin-top:12px">
          Motion follows your system preference (prefers-reduced-motion). Charts are hand-rolled SVG: zero external JS.</p>
      </div>

      <div class="tile span6">
        <div class="t-head"><span class="t-title">Your activity</span>
          <div class="right"><span class="pill accent">NFR-08</span></div></div>
        <div id="activityList" style="max-height:300px;overflow-y:auto">
          <div class="skel-bar" style="width:70%"></div>
          <div class="skel-bar" style="width:50%;margin-top:10px"></div>
          <div class="skel-bar" style="width:60%;margin-top:10px"></div>
        </div>
      </div>

      <div class="tile span6">
        <div class="t-head"><span class="t-title">Session</span>
          <div class="right"><span class="pill" id="sessCountdown">…</span></div></div>
        <div class="kv">
          <span class="k">token type</span><span class="v">JWT · HS256 · revocable (jti)</span>
          <span class="k">storage</span><span class="v">localStorage · ms_token</span>
          <span class="k">expires</span><span class="v" id="sessExpiry">…</span>
        </div>
        <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px">
          <button class="btn ghost" id="logoutHere">Log out of this session</button>
        </div>
        <div style="margin-top:18px;padding-top:14px;border-top:1px solid var(--line)">
          <div class="t-label" style="color:var(--bad)">Danger zone</div>
          <p class="tag-mini" style="margin:6px 0 10px">Deleting your account removes all your projects, models and encrypted artifacts.</p>
          <button class="btn danger" id="dangerNote" title="Account deletion is performed by an administrator">Request account deletion</button>
        </div>
      </div>
    </div>`);

  $("#saveProfile").onclick = async () => {
    try {
      const r = await api("/api/auth/me", { method: "PATCH", body: { full_name: $("#sName").value.trim() } });
      state.user.full_name = r.full_name;
      localStorage.setItem("ms_user", JSON.stringify(state.user));
      toast("Profile updated."); viewSettings();
    } catch (e) { toast(e.message, true); }
  };
  $("#savePass").onclick = async () => {
    const cur = $("#sCur").value, nw = $("#sNew").value, nw2 = $("#sNew2").value;
    if (nw.length < 8) { toast("New password must be at least 8 characters", true); return; }
    if (nw !== nw2) { toast("New passwords do not match", true); return; }
    try {
      const r = await api("/api/auth/password/change", { method: "POST",
        body: { current_password: cur, new_password: nw } });
      state.token = r.token;
      localStorage.setItem("ms_token", r.token);
      toast("Password changed. Other sessions were revoked.")
      $("#sCur").value = $("#sNew").value = $("#sNew2").value = "";
    } catch (e) { toast(e.message, true); }
  };
  $("#logoutHere").onclick = async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch {}
    logoutLocal();
  };
  $("#dangerNote").onclick = () => toast("Account deletion is handled by an administrator", true);
  const motion = $("#motionPref");
  if (motion && matchMedia("(prefers-reduced-motion: reduce)").matches) motion.textContent = "reduced (system)";

  /* personal activity feed from the audit log */
  (async () => {
    const box = $("#activityList");
    if (!box) return;
    try {
      const { activity } = await api("/api/auth/me/activity");
      const dotColor = a =>
        /delete|fail|cancel/i.test(a) ? "var(--bad)" :
        /login|logout|register/i.test(a) ? "var(--accent)" :
        /create|upload|execute|success/i.test(a) ? "var(--good)" : "var(--faint)";
      box.innerHTML = activity.length ? activity.map(a => `
        <div class="activity-item">
          <span class="activity-dot" style="background:${dotColor(a.action)}"></span>
          <div style="min-width:0">
            <span class="activity-action">${esc(a.action.replace(/_/g, " "))}</span>
            ${a.detail ? `<span class="activity-detail">: ${esc(a.detail.length > 46 ? a.detail.slice(0, 46) + "..." : a.detail)}</span>` : ""}
            <div class="activity-time">${timeago(a.created_at)}</div>
          </div>
        </div>`).join("")
        : '<div class="empty" style="padding:24px">No recorded activity yet</div>';
    } catch (e) {
      box.innerHTML = `<div class="empty" style="padding:24px">Could not load activity</div>`;
    }
  })();

  /* live session expiry countdown */
  (async () => {
    const pill = $("#sessCountdown"), expEl = $("#sessExpiry");
    if (!pill) return;
    try {
      const s = await api("/api/auth/me/session");
      if (s.expires_at) expEl.textContent =
        new Date(s.expires_at * 1000).toLocaleTimeString();
      const fmt = () => {
        const left = Math.max(0, (s.expires_at || 0) - Date.now() / 1000);
        const h = Math.floor(left / 3600), m = Math.floor(left % 3600 / 60);
        pill.textContent = h > 0 ? `${h}h ${m}m left` : `${m}m left`;
        pill.className = "pill " + (left < 3600 ? "warn" : "good");
      };
      fmt();
      const iv = setInterval(() => {
        if (!$("#sessCountdown")) { clearInterval(iv); return; }
        fmt();
      }, 30000);
    } catch { pill.textContent = "unknown"; }
  })();
}


/* ---------------- job center ---------------- */
async function viewJobs() {
  if (!state.token) { location.hash = "#/login"; return; }
  document.title = "Jobs · ModelSmith";
  shell({ active: "jobs", crumbs: "<b>Jobs</b>" }, `
    <div class="page-head"><div><h1>Job center</h1>
      <div class="sub">Every analysis and execution the runner has handled for you,
      with live progress on anything still cooking.</div></div>
      <div class="actions">
        <div class="filter-chips" id="jobFilters">
          ${["", "running", "queued", "success", "failed"].map(f =>
            `<button class="fchip ${f === "" ? "on" : ""}" data-f="${f}">${
              f === "" ? "All" : f[0].toUpperCase() + f.slice(1)}</button>`).join("")}
        </div>
      </div>
    </div>
    <div class="bento" id="jobGrid">${skeletonBento(4, 6)}</div>`);

  let currentFilter = "";
  const load = async () => {
    const { jobs } = await api("/api/jobs" + (currentFilter ? `?status=${currentFilter}` : ""));
    const grid = $("#jobGrid");
    if (!grid) return;
    if (!jobs.length) {
      grid.innerHTML = `<div class="tile span12"><div class="empty-svg">${emptySVG("jobs")}</div>
        <div class="empty"><h3>No jobs ${currentFilter ? "with that status" : "yet"}</h3>
        <p>Upload a model or execute a plan and the runner gets to work.</p></div></div>`;
      return;
    }
    const dot = j => j.status === "success" ? "var(--good)"
      : j.status === "failed" ? "var(--bad)"
      : j.status === "running" ? "var(--accent)" : "var(--warn)";
    grid.innerHTML = jobs.map((j, i) => `
      <div class="tile span6 job-tile" style="animation-delay:${i * 0.03}s" data-job="${j.id}">
        <div class="t-head">
          <span class="t-title"><span class="feed-dot" style="background:${dot(j)}"></span>
            ${j.type === "analyze" ? "Analysis" : "Optimization"} · <span class="mono" style="font-size:11px">${j.id.slice(0, 14)}</span></span>
          <div class="right"><span class="pill ${j.status === "success" ? "good" : j.status === "failed" ? "bad" : "warn"}">${j.status}</span></div>
        </div>
        <div class="tag-mini" style="margin:6px 0 10px">${esc(j.message || "")}${j.error ? " · " + esc(j.error.slice(0, 60)) : ""}</div>
        ${(j.status === "queued" || j.status === "running") ? `
          <div class="progress-row"><div class="bar" style="flex:1"><i style="width:${j.progress}%"></i></div>
            <span class="pct">${j.progress}%</span></div>` : ""}
        <div style="display:flex;align-items:center;gap:10px;margin-top:12px">
          <span class="tag-mini">${timeago(j.created_at)}</span>
          ${j.status === "queued" ? `<button class="btn small ghost" data-jc="${j.id}">Cancel</button>` : ""}
          ${j.status === "failed" ? `<button class="btn small ghost" data-jr="${j.id}">↻ Retry</button>` : ""}
        </div>
      </div>`).join("");
    const hasLive = jobs.some(j => j.status === "queued" || j.status === "running");
    if (hasLive) poll(load, 2000); else stopPolling();
    $$("[data-jc]", grid).forEach(b => b.onclick = async e => {
      e.stopPropagation();
      try { await api(`/api/jobs/${b.dataset.jc}/cancel`, { method: "POST" }); toast("Cancelled"); load(); }
      catch (err) { toast(err.message, true); }
    });
    $$("[data-jr]", grid).forEach(b => b.onclick = async e => {
      e.stopPropagation();
      try { await api(`/api/jobs/${b.dataset.jr}/retry`, { method: "POST" }); toast("Requeued"); load(); }
      catch (err) { toast(err.message, true); }
    });
  };
  $$("#jobFilters .fchip").forEach(c => c.onclick = () => {
    currentFilter = c.dataset.f;
    $$("#jobFilters .fchip").forEach(x => x.classList.toggle("on", x === c));
    stopPolling(); load();
  });
  await load();
}

/* ---------------- api playground ---------------- */
const PLAYGROUND_ENDPOINTS = [
  { m: "GET",  p: "/api/health",                 d: "Liveness, counts, versions" },
  { m: "GET",  p: "/api/config",                 d: "Public capability info" },
  { m: "GET",  p: "/api/metrics",                d: "Prometheus exposition" },
  { m: "GET",  p: "/api/projects",               d: "Your projects" },
  { m: "POST", p: "/api/projects",               d: "Create a project" },
  { m: "GET",  p: "/api/search?q=resnet",        d: "Search your models" },
  { m: "GET",  p: "/api/jobs",                   d: "Your job history" },
  { m: "GET",  p: "/api/notifications",          d: "Notifications + unread" },
  { m: "GET",  p: "/api/auth/me",                d: "Current user" },
  { m: "GET",  p: "/api/auth/me/session",        d: "Token expiry info" },
  { m: "GET",  p: "/api/auth/me/activity",       d: "Personal audit trail" },
  { m: "GET",  p: "/api/dashboard",              d: "Dashboard aggregate" },
  { m: "GET",  p: "/api/dashboard/stats",        d: "Status + framework breakdown" },
  { m: "GET",  p: "/api/dashboard/insights",     d: "Computed highlights" },
  { m: "GET",  p: "/api/dashboard/activity",     d: "30-day activity" },
];

async function viewApiPlayground() {
  if (!state.token) { location.hash = "#/login"; return; }
  document.title = "API playground · ModelSmith";
  shell({ active: "api", crumbs: "<b>API playground</b>" }, `
    <div class="page-head"><div><h1>API playground</h1>
      <div class="sub">Fire real requests with your own token. GETs only here:
      the interesting mutations deserve intent, not curiosity.</div></div></div>
    <div class="bento">
      <div class="tile span5">
        <div class="t-head"><span class="t-title">Endpoints</span>
          <div class="right"><span class="pill accent">${PLAYGROUND_ENDPOINTS.length} curated</span></div></div>
        <div class="pg-list">
          ${PLAYGROUND_ENDPOINTS.map((e, i) => `
            <div class="pg-item ${i === 0 ? "sel" : ""}" data-i="${i}">
              <span class="pg-method ${e.m}">${e.m}</span>
              <div><code>${esc(e.p)}</code><i>${esc(e.d)}</i></div>
            </div>`).join("")}
        </div>
        <p class="tag-mini" style="margin-top:12px">Full interactive reference, mutations included:
          <a href="/docs" target="_blank" style="color:var(--accent)">/docs</a></p>
      </div>
      <div class="tile span7">
        <div class="t-head"><span class="t-title">Request</span>
          <button class="btn primary small" id="pgRun">▶ Run request</button></div>
        <label class="field"><span>Path (query params welcome)</span>
          <input type="text" id="pgPath" value="${esc(PLAYGROUND_ENDPOINTS[0].p)}" class="mono"></label>
        <div class="t-label" style="margin-top:16px">Response</div>
        <pre class="pg-response" id="pgOut">Pick an endpoint and press Run.</pre>
        <div class="pg-meta" id="pgMeta"></div>
      </div>
    </div>`);
  const out = $("#pgOut"), meta = $("#pgMeta"), pathIn = $("#pgPath");
  $$(".pg-item").forEach(el => el.onclick = () => {
    $$(".pg-item").forEach(x => x.classList.remove("sel"));
    el.classList.add("sel");
    pathIn.value = PLAYGROUND_ENDPOINTS[+el.dataset.i].p;
  });
  const run = async () => {
    out.textContent = "…"; meta.textContent = "";
    const t0 = performance.now();
    try {
      const resp = await fetch(pathIn.value, { headers: { Authorization: "Bearer " + state.token } });
      const ms = (performance.now() - t0).toFixed(0);
      const text = await resp.text();
      let pretty = text;
      try { pretty = JSON.stringify(JSON.parse(text), null, 2); } catch {}
      out.textContent = pretty.slice(0, 8000);
      meta.innerHTML = `<span class="pill ${resp.ok ? "good" : "bad"}">${resp.status} ${resp.statusText}</span>
        <span class="tag-mini">${ms} ms · ${text.length} bytes</span>`;
    } catch (e) {
      out.textContent = "Request failed: " + e.message;
    }
  };
  $("#pgRun").onclick = run;
  pathIn.addEventListener("keydown", e => { if (e.key === "Enter") run(); });
}

/* ---------------- confetti (for runs that earn it) ---------------- */
function celebrate(intensity = 1) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.createElement("canvas");
  c.className = "confetti-canvas";
  c.style.cssText = "position:fixed;inset:0;z-index:9999;pointer-events:none";
  document.body.appendChild(c);
  const ctx = c.getContext("2d");
  c.width = innerWidth; c.height = innerHeight;
  const colors = ["#ffb224", "#ff6b2c", "#ffd979", "#4ade80", "#f4efe3"];
  const parts = Array.from({ length: 90 * intensity }, () => ({
    x: Math.random() * c.width, y: -20 - Math.random() * c.height * 0.4,
    r: 3 + Math.random() * 5, vy: 2.2 + Math.random() * 3.4,
    vx: (Math.random() - 0.5) * 2.4, rot: Math.random() * Math.PI,
    vr: (Math.random() - 0.5) * 0.24, col: colors[(Math.random() * colors.length) | 0],
  }));
  const t0 = performance.now();
  (function frame(now) {
    const elapsed = now - t0;
    ctx.clearRect(0, 0, c.width, c.height);
    parts.forEach(p => {
      p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save();
      ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.fillStyle = p.col;
      ctx.globalAlpha = Math.max(0, 1 - elapsed / 2600);
      ctx.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);
      ctx.restore();
    });
    if (elapsed < 2600) requestAnimationFrame(frame);
    else c.remove();
  })(t0);
}

/* ---------------- global dropzone: drop a model anywhere ---------------- */
function setupGlobalDrop() {
  let depth = 0;
  addEventListener("dragenter", e => {
    if (!state.token || !e.dataTransfer?.types?.includes("Files")) return;
    depth++;
    let ov = $("#dropOverlay");
    if (!ov) {
      ov = document.createElement("div");
      ov.id = "dropOverlay";
      ov.className = "drop-overlay";
      ov.innerHTML = `<div class="drop-overlay-card"><div style="font-size:44px">⬆</div>
        <b>Drop to upload</b><span>goes straight into your newest project</span></div>`;
      document.body.appendChild(ov);
    }
  });
  addEventListener("dragleave", () => {
    if (--depth <= 0) { depth = 0; $("#dropOverlay")?.remove(); }
  });
  addEventListener("dragover", e => e.preventDefault());
  addEventListener("drop", async e => {
    e.preventDefault();
    depth = 0; $("#dropOverlay")?.remove();
    if (!state.token) return;
    const files = [...(e.dataTransfer?.files || [])]
      .filter(f => /\.(pt|pth|onnx)$/i.test(f.name));
    if (!files.length) return;
    try {
      const { projects } = await api("/api/projects");
      const active = projects.filter(p => !p.archived);
      const target = active[0];
      if (!target) { toast("Create a project first", true); return; }
      let ok = 0, firstId = null;
      for (const f of files) {
        const fd = new FormData();
        fd.append("project_id", target.id);
        fd.append("name", f.name.replace(/\.(pt|pth|onnx)$/i, ""));
        fd.append("input_shape", ""); fd.append("file", f);
        try {
          const r = await api("/api/models/upload", { method: "POST", body: fd });
          ok++; firstId = firstId || r.model_id;
        } catch (err) { toast(`${f.name}: ${err.message}`, true); }
      }
      if (ok) {
        toast(ok === 1
          ? `Dropped into "${target.name}". Analysis running.`
          : `${ok} files dropped into "${target.name}".`,
          false, 4200, { label: "Open", run: () => (location.hash = "#/model/" + firstId) });
      }
    } catch (err) { toast(err.message, true); }
  });
}

/* ---------------- achievements ---------------- */
async function viewAchievements() {
  if (!state.token) { location.hash = "#/login"; return; }
  document.title = "Achievements · ModelSmith";
  shell({ active: "achievements", crumbs: "<b>Achievements</b>" }, `
    <div class="page-head"><div><h1>Achievements</h1>
      <div class="sub">Each badge is earned from your real activity, computed from the database.</div></div>
      <div class="actions"><span class="pill accent" id="achCount">…</span></div></div>
    <div class="bento" id="achGrid">${skeletonBento(6, 4)}</div>`);

  const { achievements, earned_count, total, counters } = await api("/api/achievements");
  $("#achCount").textContent = `${earned_count} of ${total} earned`;
  $("#achCount").className = "pill " + (earned_count === total ? "good" : "accent");
  $("#achGrid").innerHTML = achievements.map((a, i) => `
    <div class="tile span3 ach-card ${a.earned ? "earned" : "locked"}" style="animation-delay:${i * 0.04}s">
      <div class="ach-ico">${a.icon}</div>
      <b>${esc(a.name)}</b>
      <p>${esc(a.desc)}</p>
      <span class="ach-state">${a.earned ? "✓ earned" : "locked"}</span>
    </div>`).join("") + `
    <div class="tile span12">
      <div class="t-head"><span class="t-title">The scoreboard</span></div>
      <div class="ins-row">
        <div class="ins-chip"><b>${counters.models}</b><span>models</span></div>
        <div class="ins-chip"><b>${counters.analyzed}</b><span>analyzed</span></div>
        <div class="ins-chip"><b>${counters.runs}</b><span>successful runs</span></div>
        <div class="ins-chip"><b>−${Math.round(counters.best_save)}%</b><span>best size cut</span></div>
      </div>
    </div>`;
}

/* ---------------- public share view (no auth) ---------------- */
async function viewShare(token) {
  document.title = "Shared model · ModelSmith";
  let d;
  try { d = await api(`/api/share/${token}`); }
  catch (e) {
    $("#app").innerHTML = `<div class="nf-wrap"><div class="nf-card">
      <div class="nf-code">4<span class="nf-hammer">0</span>4</div>
      <h2>This link cooled down</h2>
      <p>The share link is invalid, or the model behind it was deleted.</p>
      <div class="nf-actions"><a class="btn primary" href="#/welcome">Go home</a></div>
    </div></div>`;
    return;
  }
  const m = d.model, s = d.analysis_summary, b = d.best_run;
  $("#app").innerHTML = `
  <div class="bg-fx"></div>
  <div class="share-wrap">
    <div class="share-card">
      <div class="share-brand"><span class="n-mark">MS</span> ModelSmith <em>shared report</em></div>
      <h1>${esc(m.name)}</h1>
      <div class="share-meta">${esc(m.framework)} · ${fmtBytes(m.size_bytes)} ·
        added ${timeago(m.created_at)} · ${d.run_count} run${d.run_count !== 1 ? "s" : ""} · ${d.views} view${d.views !== 1 ? "s" : ""}</div>
      <div class="share-grid">
        <div><span>parameters</span><b>${fmtNum(s.total_params)}</b></div>
        <div><span>layers</span><b>${fmtNum(s.layer_count)}</b></div>
        <div><span>MFLOPs</span><b>${(s.total_flops / 1e6).toFixed(1)}</b></div>
        <div><span>latency</span><b>${s.latency_ms?.toFixed(2) ?? "-"} ms</b></div>
      </div>
      ${b ? `
      <div class="share-best">
        <div class="t-label">best recorded run</div>
        <div class="b-name">${esc(b.plan_name)}</div>
        <div class="share-grid">
          <div><span>size cut</span><b class="win">−${b.size_saved_pct}%</b></div>
          <div><span>latency</span><b>−${b.latency_gain_pct ?? 0}%</b></div>
          <div><span>now</span><b>${b.optimized?.size_mb?.toFixed(1) ?? "-"} MB</b></div>
          <div><span>agreement</span><b>${(b.output_agreement || {}).agreement_pct ?? "-"}%</b></div>
        </div>
      </div>` : `<div class="share-best"><div class="t-label">no successful runs yet</div></div>`}
      <div class="share-hash mono" title="${esc(m.sha256)}">sha256 ${esc((m.sha256 || "").slice(0, 24))}…</div>
      <div class="share-foot">Numbers measured by ModelSmith on the owner's hardware.
        <a href="#/welcome">What is this tool?</a></div>
    </div>
  </div>`;
}

/* ---------------- theme ---------------- */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem("ms_theme", t);
  $$(".theme-btn").forEach(b => b.textContent = t === "light" ? "☾" : "☀");
}
function toggleTheme() {
  applyTheme((localStorage.getItem("ms_theme") || "dark") === "dark" ? "light" : "dark");
  toast(document.documentElement.dataset.theme === "light"
    ? "Light theme on." : "Dark theme on.");
}

/* ---------------- boot ---------------- */
applyTheme(localStorage.getItem("ms_theme") || "dark");
setupGlobalDrop();
render();
setInterval(() => { if (state.token && $("#bellDot")) refreshBellDot(); }, 15000);
