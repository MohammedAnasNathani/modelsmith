/* ModelSmith chart toolkit: hand-rolled SVG, zero dependencies.
   Every chart renders into a container div with viewBox-based responsive SVG. */
"use strict";

const MSCharts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const PALETTE = ["#ffb224", "#ff6b2c", "#4ade80", "#e8c252", "#f87171",
                   "#ffc95e", "#c9a15a", "#8fd3a8", "#ff8f5e", "#a99f8c"];

  function el(tag, attrs = {}, parent = null) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }
  function svg(root, w, h) {
    root.innerHTML = "";
    const s = el("svg", { viewBox: `0 0 ${w} ${h}`, width: "100%",
                          style: `aspect-ratio:${w}/${h};display:block;overflow:visible` });
    root.appendChild(s);
    return s;
  }

  /* ---------------- donut ---------------- */
  function donut(container, data, opts = {}) {
    // data: [{label, value, color?}]
    const size = opts.size || 150, cx = size / 2, cy = size / 2, r = size * 0.38, sw = size * 0.13;
    const total = data.reduce((a, d) => a + d.value, 0) || 1;
    const s = svg(container, size, size);
    const C = 2 * Math.PI * r;
    el("circle", { cx, cy, r, fill: "none", stroke: "rgba(255,255,255,.05)", "stroke-width": sw }, s);
    let acc = 0;
    data.forEach((d, i) => {
      const frac = d.value / total;
      const c = el("circle", {
        cx, cy, r, fill: "none",
        stroke: d.color || PALETTE[i % PALETTE.length],
        "stroke-width": sw, "stroke-linecap": "butt",
        "stroke-dasharray": `${C * frac} ${C}`,
        "stroke-dashoffset": -C * acc,
        transform: `rotate(-90 ${cx} ${cy})`,
        style: `transition:stroke-dasharray .8s cubic-bezier(.2,.7,.3,1),opacity .3s;cursor:pointer`,
      }, s);
      c.addEventListener("mouseenter", () => (c.style.opacity = 0.75));
      c.addEventListener("mouseleave", () => (c.style.opacity = 1));
      acc += frac;
    });
    const t1 = el("text", { x: cx, y: cy - 3, "text-anchor": "middle", fill: "#e6ebf4",
                            "font-size": size * 0.13, "font-weight": 700, "font-family": "JetBrains Mono,monospace" }, s);
    t1.textContent = opts.centerValue ?? "";
    const t2 = el("text", { x: cx, y: cy + size * 0.1, "text-anchor": "middle", fill: "#5b6478",
                            "font-size": size * 0.062, "font-family": "Inter,sans-serif" }, s);
    t2.textContent = opts.centerLabel ?? "";
    if (opts.legend !== false) {
      const lg = document.createElement("div");
      lg.className = "chart-legend";
      lg.innerHTML = data.slice(0, opts.legendMax || 6).map((d, i) => `
        <span class="lg-item"><i style="background:${d.color || PALETTE[i % PALETTE.length]}"></i>
        ${d.label}<b>${opts.fmt ? opts.fmt(d.value) : d.value}</b></span>`).join("");
      container.appendChild(lg);
    }
  }

  /* ---------------- horizontal bars ---------------- */
  function hbars(container, data, opts = {}) {
    // data: [{label, value, color?}]
    const rowH = opts.rowH || 30, labelW = opts.labelW || 150, barMax = 100, top = 6;
    const h = top + data.length * rowH;
    const s = svg(container, 460, h);
    const max = Math.max(...data.map(d => d.value), 1e-9);
    data.forEach((d, i) => {
      const y = top + i * rowH;
      const tl = el("text", { x: labelW - 8, y: y + rowH / 2 + 4, "text-anchor": "end",
                              fill: "#8a94a8", "font-size": 11, "font-family": "JetBrains Mono,monospace" }, s);
      tl.textContent = d.label;
      el("rect", { x: labelW, y: y + 5, width: barMax * 2.6, height: rowH - 10, rx: 4,
                   fill: "rgba(255,255,255,.04)" }, s);
      const w = Math.max(2, (d.value / max) * barMax * 2.6);
      el("rect", { x: labelW, y: y + 5, width: 0, height: rowH - 10, rx: 4,
                   fill: d.color || `url(#grad${i % 2})` || PALETTE[i % PALETTE.length],
                   style: "transition:width .8s cubic-bezier(.2,.7,.3,1)" }, s);
      const bar = s.lastChild;
      requestAnimationFrame(() => requestAnimationFrame(() => bar.setAttribute("width", w)));
      const tv = el("text", { x: labelW + w + 8, y: y + rowH / 2 + 4, fill: "#8a94a8",
                              "font-size": 10.5, "font-family": "JetBrains Mono,monospace" }, s);
      tv.textContent = opts.fmt ? opts.fmt(d.value) : d.value.toLocaleString();
    });
  }

  /* ---------------- radar ---------------- */
  function radar(container, axes, series, opts = {}) {
    // axes: ["Size","Latency",...]; series: [{name, values(0..1), color}]
    const size = opts.size || 210, cx = size / 2, cy = size / 2, R = size * 0.36;
    const n = axes.length;
    const pt = (i, r) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
      return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    };
    const s = svg(container, size, size);
    for (let ring = 1; ring <= 4; ring++) {
      const rr = (R * ring) / 4;
      const pts = axes.map((_, i) => pt(i, rr).join(",")).join(" ");
      el("polygon", { points: pts, fill: ring === 4 ? "rgba(255,255,255,.02)" : "none",
                      stroke: "rgba(255,255,255,.07)", "stroke-width": 1 }, s);
    }
    axes.forEach((a, i) => {
      const [x, y] = pt(i, R);
      el("line", { x1: cx, y1: cy, x2: x, y2: y, stroke: "rgba(255,255,255,.07)" }, s);
      const [lx, ly] = pt(i, R + 16);
      const t = el("text", { x: lx, y: ly + 3, "text-anchor": "middle", fill: "#8a94a8",
                             "font-size": 10, "font-family": "Inter,sans-serif" }, s);
      t.textContent = a;
    });
    series.forEach((ser, si) => {
      const pts = ser.values.map((v, i) => pt(i, R * Math.max(0.04, Math.min(1, v))).join(",")).join(" ");
      el("polygon", { points: pts, fill: ser.color + "22", stroke: ser.color,
                      "stroke-width": 2, "stroke-linejoin": "round",
                      style: "transition:opacity .3s", opacity: si === 0 ? 1 : 0.9 }, s);
      ser.values.forEach((v, i) => {
        const [x, y] = pt(i, R * Math.max(0.04, Math.min(1, v)));
        el("circle", { cx: x, cy: y, r: 2.5, fill: ser.color }, s);
      });
    });
    if (series.length > 1 && opts.legend !== false) {
      const lg = document.createElement("div");
      lg.className = "chart-legend center";
      lg.innerHTML = series.map(x => `<span class="lg-item"><i style="background:${x.color}"></i>${x.name}</span>`).join("");
      container.appendChild(lg);
    }
  }

  /* ---------------- comparison bars (before/after) ---------------- */
  function compareBars(container, rows, opts = {}) {
    // rows: [{label, before, after, unit, betterDown}]
    const rowH = 54, w = 460, h = rows.length * rowH + 8, labelW = 92;
    const s = svg(container, w, h);
    const max = Math.max(...rows.flatMap(r => [r.before ?? 0, r.after ?? 0]), 1e-9);
    const barW = w - labelW - 120;
    rows.forEach((r, i) => {
      const y = 8 + i * rowH;
      const t = el("text", { x: 0, y: y + 15, fill: "#8a94a8", "font-size": 11.5,
                             "font-family": "Inter,sans-serif", "font-weight": 600 }, s);
      t.textContent = r.label;
      const fmtv = v => v == null ? "n/a" : (opts.fmt ? opts.fmt(v) : v);
      // before
      el("rect", { x: labelW, y: y + 2, width: 0, height: 12, rx: 3, fill: "#3a4358" }, s);
      const b1 = s.lastChild;
      el("text", { x: labelW + 6, y: y + 11.5, fill: "#5b6478", "font-size": 9.5,
                   "font-family": "JetBrains Mono,monospace" }, s).textContent = fmtv(r.before);
      // after
      el("rect", { x: labelW, y: y + 22, width: 0, height: 12, rx: 3, fill: "#ffb224" }, s);
      const b2 = s.lastChild;
      const a1 = el("text", { x: labelW + 6, y: y + 31.5, fill: "#ffc95e", "font-size": 9.5,
                              "font-family": "JetBrains Mono,monospace" }, s);
      a1.textContent = fmtv(r.after);
      // animate
      const w1 = ((r.before ?? 0) / max) * barW, w2 = ((r.after ?? 0) / max) * barW;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        b1.setAttribute("width", w1); b2.setAttribute("width", Math.max(3, w2));
      }));
      // delta
      if (r.before != null && r.after != null && r.before > 0) {
        const down = r.after < r.before;
        const good = r.betterDown === false ? !down : down;
        const d = el("text", { x: w - 4, y: y + 20, "text-anchor": "end", "font-size": 12,
                               "font-weight": 700, "font-family": "JetBrains Mono,monospace",
                               fill: good ? "#34d399" : "#fbbf24" }, s);
        d.textContent = `${down ? "−" : "+"}${Math.abs((1 - r.after / r.before) * 100).toFixed(1)}%`;
      }
      // legend chips
      if (i === 0) {
        el("text", { x: labelW, y: y - 4, fill: "#5b6478", "font-size": 9 }, s).textContent = "";
      }
    });
    const lg = document.createElement("div");
    lg.className = "chart-legend";
    lg.innerHTML = `<span class="lg-item"><i style="background:#3a4358"></i>${opts.beforeLabel || "Original"}</span>
                    <span class="lg-item"><i style="background:#ffb224"></i>${opts.afterLabel || "Optimized"}</span>`;
    container.appendChild(lg);
  }

  /* ---------------- gauge ---------------- */
  function gauge(container, pct, opts = {}) {
    const size = opts.size || 120, cx = size / 2, cy = size / 2, r = size * 0.4, sw = size * 0.09;
    const s = svg(container, size, size);
    const C = 2 * Math.PI * r * 0.75;
    el("circle", { cx, cy, r, fill: "none", stroke: "rgba(255,255,255,.06)",
                   "stroke-width": sw, "stroke-dasharray": `${C} ${2 * Math.PI * r}`,
                   transform: `rotate(135 ${cx} ${cy})` }, s);
    const v = el("circle", { cx, cy, r, fill: "none", stroke: opts.color || "#34d399",
                             "stroke-width": sw, "stroke-linecap": "round",
                             "stroke-dasharray": `0 ${2 * Math.PI * r}`,
                             transform: `rotate(135 ${cx} ${cy})`,
                             style: "transition:stroke-dasharray 1s cubic-bezier(.2,.7,.3,1)" }, s);
    requestAnimationFrame(() => requestAnimationFrame(() =>
      v.setAttribute("stroke-dasharray", `${(C * Math.max(0, Math.min(100, pct))) / 100} ${2 * Math.PI * r}`)));
    const t = el("text", { x: cx, y: cy + 6, "text-anchor": "middle", fill: "#e6ebf4",
                           "font-size": size * 0.19, "font-weight": 700,
                           "font-family": "JetBrains Mono,monospace" }, s);
    t.textContent = (opts.signed ? (pct > 0 ? "+" : "") : "") + Math.round(pct) + "%";
    const t2 = el("text", { x: cx, y: cy + size * 0.22, "text-anchor": "middle", fill: "#5b6478",
                            "font-size": size * 0.075, "font-family": "Inter,sans-serif" }, s);
    t2.textContent = opts.label || "";
  }

  /* ---------------- architecture flow graph ---------------- */
  function archGraph(container, layers) {
    // layers: [{name,type,params}] top contributors → horizontal node flow
    const items = layers.slice(0, 8);
    if (!items.length) { container.innerHTML = ""; return; }
    const nodeW = 74, gap = 26, h = 120;
    const w = items.length * (nodeW + gap) + gap;
    const s = svg(container, w, h);
    const maxP = Math.max(...items.map(l => l.params), 1);
    el("circle", { cx: gap - 6, cy: h / 2, r: 5, fill: "#34d399" }, s);
    el("text", { x: gap - 6, y: h / 2 + 18, "text-anchor": "middle", fill: "#5b6478",
                 "font-size": 8.5 }, s).textContent = "in";
    items.forEach((l, i) => {
      const x = gap + i * (nodeW + gap);
      const hh = 28 + 52 * Math.sqrt(l.params / maxP);
      const col = l.type.includes("Conv") ? "#ffb224" : l.type.includes("Linear") ? "#ff6b2c"
                : l.type.includes("Norm") ? "#e8c252" : "#8a9b8e";
      el("line", { x1: x - gap + 6, y1: h / 2, x2: x, y2: h / 2, stroke: "rgba(255,255,255,.15)",
                   "stroke-width": 1.5 }, s);
      el("rect", { x, y: h / 2 - hh / 2, width: nodeW, height: hh, rx: 10, fill: col + "1f",
                   stroke: col + "77", "stroke-width": 1.2 }, s);
      el("circle", { cx: x + nodeW / 2, cy: h / 2, r: Math.min(7, 3 + 4 * (l.params / maxP)),
                     fill: col }, s);
      const t1 = el("text", { x: x + nodeW / 2, y: h / 2 - hh / 2 - 7, "text-anchor": "middle",
                              fill: "#8a94a8", "font-size": 8.5,
                              "font-family": "JetBrains Mono,monospace" }, s);
      t1.textContent = l.type;
      const t2 = el("text", { x: x + nodeW / 2, y: h / 2 + hh / 2 + 13, "text-anchor": "middle",
                              fill: "#5b6478", "font-size": 8.5,
                              "font-family": "JetBrains Mono,monospace" }, s);
      t2.textContent = l.params >= 1e6 ? (l.params / 1e6).toFixed(1) + "M"
                      : l.params >= 1e3 ? (l.params / 1e3).toFixed(1) + "K" : l.params;
    });
    const xOut = gap + items.length * (nodeW + gap);
    el("line", { x1: xOut - gap + 6, y1: h / 2, x2: xOut - 4, y2: h / 2,
                 stroke: "rgba(255,255,255,.15)", "stroke-width": 1.5 }, s);
    el("circle", { cx: xOut, cy: h / 2, r: 5, fill: "#f87171" }, s);
    el("text", { x: xOut, y: h / 2 + 18, "text-anchor": "middle", fill: "#5b6478",
                 "font-size": 8.5 }, s).textContent = "out";
  }

  /* ---------------- sparkline ---------------- */
  function sparkline(container, values, opts = {}) {
    const w = opts.w || 160, h = opts.h || 40;
    const s = svg(container, w, h);
    if (!values.length) return;
    const min = Math.min(...values), max = Math.max(...values);
    const pts = values.map((v, i) => [
      (i / (values.length - 1 || 1)) * (w - 4) + 2,
      h - 4 - ((v - min) / (max - min || 1)) * (h - 10),
    ]);
    el("polyline", { points: pts.map(p => p.join(",")).join(" "), fill: "none",
                     stroke: opts.color || "#ffb224", "stroke-width": 1.8,
                     "stroke-linecap": "round", "stroke-linejoin": "round" }, s);
    const [lx, ly] = pts[pts.length - 1];
    el("circle", { cx: lx, cy: ly, r: 2.6, fill: opts.color || "#ffb224" }, s);
  }


  /* ---------------- pareto frontier ---------------- */
  function pareto(container, plans, opts = {}) {
    // plans: [{plan_id, predicted:{size_mb, latency_ms, size_saved_pct}, auto_executable}]
    const W = opts.width || 520, H = opts.height || 300;
    const P = 44, R = 16;
    const s = svg(container, W, H);
    const pts = plans.map(p => ({
      x: p.predicted.size_mb, y: p.predicted.latency_ms || 0.1,
      id: p.plan_id, auto: p.auto_executable, saved: p.predicted.size_saved_pct,
    }));
    if (!pts.length) return;
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const xMin = 0, xMax = Math.max(...xs) * 1.15, yMin = 0, yMax = Math.max(...ys) * 1.2;
    const px = v => P + (v / xMax) * (W - P - R);
    const py = v => H - R - (v / yMax) * (H - P - R);

    /* grid + axes */
    for (let i = 0; i <= 4; i++) {
      const gy = P + i * (H - P - R) / 4;
      el("line", { x1: P, y1: gy, x2: W - R, y2: gy,
                   stroke: "rgba(255,235,190,.05)", "stroke-width": 1 }, s);
      const t = el("text", { x: P - 6, y: gy + 3, "text-anchor": "end", fill: "#776c58",
                             "font-size": 9, "font-family": "JetBrains Mono,monospace" }, s);
      t.textContent = (yMax * (1 - i / 4)).toFixed(1);
    }
    for (let i = 0; i <= 4; i++) {
      const gx = P + i * (W - P - R) / 4;
      const t = el("text", { x: gx, y: H - 2, "text-anchor": "middle", fill: "#776c58",
                             "font-size": 9, "font-family": "JetBrains Mono,monospace" }, s);
      t.textContent = (xMax * i / 4).toFixed(1);
    }
    const yl = el("text", { x: 12, y: P - 10, fill: "#b0a691", "font-size": 10,
                            "font-family": "Inter,sans-serif", "font-weight": 600 }, s);
    yl.textContent = "latency ms";
    const xl = el("text", { x: W - R, y: P - 10, "text-anchor": "end", fill: "#b0a691",
                            "font-size": 10, "font-family": "Inter,sans-serif", "font-weight": 600 }, s);
    xl.textContent = "size MB";

    /* pareto front: points not dominated by any other (both smaller) */
    const front = pts.filter(a => !pts.some(b =>
      b !== a && b.x <= a.x && b.y <= a.y && (b.x < a.x || b.y < a.y)))
      .sort((a, b) => a.x - b.x);
    if (front.length > 1) {
      const d = "M" + front.map(p => `${px(p.x)},${py(p.y)}`).join(" L");
      el("path", { d, fill: "none", stroke: "rgba(255,178,36,.35)",
                   "stroke-width": 1.5, "stroke-dasharray": "5 4" }, s);
    }

    /* points */
    pts.forEach(p => {
      const on = front.includes(p);
      const g = el("g", { style: "cursor:pointer" }, s);
      if (on) el("circle", { cx: px(p.x), cy: py(p.y), r: 13, fill: "rgba(255,178,36,.12)" }, g);
      el("circle", { cx: px(p.x), cy: py(p.y), r: on ? 6 : 4.5,
                     fill: p.auto ? (on ? "#ffb224" : "#c9a15a") : "#5b5344",
                     stroke: on ? "#ffd979" : "none", "stroke-width": 1.5 }, g);
      const lbl = el("text", { x: px(p.x), y: py(p.y) - 10, "text-anchor": "middle",
                               fill: on ? "#f4efe3" : "#776c58", "font-size": 8.5,
                               "font-family": "JetBrains Mono,monospace" }, g);
      lbl.textContent = p.id.replace("plan_", "p");
      const tip = el("title", {}, g);
      tip.textContent = `${p.id}: ${p.x.toFixed(1)} MB, ${p.y.toFixed(1)} ms, -${p.saved}% size${p.auto ? "" : " (guided)"}`;
    });
  }

  return {
 donut, hbars, radar, compareBars, gauge, archGraph, sparkline, pareto, PALETTE };
})();
window.MSCharts = MSCharts;
