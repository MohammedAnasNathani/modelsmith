
"use strict";

const RADAR_AXES = ["Size −%", "Speed +%", "Accuracy", "Energy", "Deployability"];

const TECH_MARQUEE = [
  "PyTorch", "ONNX Runtime", "FastAPI", "SQLite WAL", "Fernet AES", "JWT + jti",
  "INT8 Quantization", "Structured Pruning", "Knowledge Distillation", "FP16",
  "Graph Export", "Calibration", "Benchmarking", "SHA-256", "Reproducible Runs",
];

let landingObserver = null;

function revealOnScroll() {
  if (landingObserver) landingObserver.disconnect();
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  landingObserver = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      e.target.style.setProperty("--rv-on", "1");
      e.target.classList.add("rv-in");
      if (e.target.classList.contains("n-stats")) animateCounters();
      landingObserver.unobserve(e.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
  $$("[data-rv]").forEach(el => {
    if (reduced) { el.classList.add("rv-in"); return; }
    landingObserver.observe(el);
  });
}

function animateCounters() {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  $$(".n-stats .num").forEach(el => {
    const raw = el.textContent, m = raw.match(/^(\d+)/);
    if (!m) return;
    const target = parseInt(m[1], 10), suffix = raw.replace(m[1], "");
    if (reduced) { el.textContent = target + suffix; return; }
    const t0 = performance.now(), dur = 1400;
    const ease = t => 1 - Math.pow(1 - t, 4);
    (function tick(now) {
      const p = Math.min((now - t0) / dur, 1);
      el.textContent = Math.round(ease(p) * target) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    })(t0);
  });
}

function setupNavScroll() {
  const nav = $("#nNav");
  if (!nav) return;
  const bar = $("#nProgress");
  const onScroll = () => {
    nav.classList.toggle("scrolled", scrollY > 24);
    if (bar) {
      const h = document.documentElement.scrollHeight - innerHeight;
      bar.style.width = (h > 0 ? (scrollY / h) * 100 : 0) + "%";
    }
  };
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

function setupParallax() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const orbs = $$(".n-orb");
  if (!orbs.length) return;
  let raf = null;
  addEventListener("scroll", () => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      const y = scrollY;
      orbs.forEach((o, i) => {
        o.style.transform = `translateY(${y * (0.06 + i * 0.05)}px)`;
      });
      raf = null;
    });
  }, { passive: true });
}

function setupMobileNav() {
  const btn = $("#nMobBtn"), menu = $("#nMobMenu");
  if (!btn || !menu) return;
  btn.onclick = () => {
    const open = menu.classList.toggle("open");
    btn.setAttribute("aria-expanded", open);
    btn.textContent = open ? "✕" : "☰";
  };
  $$("a", menu).forEach(a => a.addEventListener("click", () => {
    menu.classList.remove("open"); btn.textContent = "☰";
  }));
  document.addEventListener("click", e => {
    if (menu.classList.contains("open") && !menu.contains(e.target) && !btn.contains(e.target)) {
      menu.classList.remove("open"); btn.textContent = "☰";
    }
  });
}

async function loadLandingData() {
  for (const p of ["assets/landing-data.json", "landing-data.json"]) {
    try { const r = await fetch(p); if (r.ok) return await r.json(); } catch {}
  }
  return null;
}
async function viewLanding() {
  const D = await (loadLandingData()) || {
    captured_at: null, endpoints: null, checks: 153,
    model: { file: "your-model.pt", size_mb: null, layers: null, arch: "model", params: null },
    layers: [], layers_top: [], analysis_summary: {},
    run: { short_id: "—", plan: "your plan", duration_s: null, artifact: "optimized.onnx",
           artifact_mb: null, saved_pct: null, latency_gain_pct: null, agreement_pct: null,
           p95_before: null, p95_after: null, size_before_mb: null, size_after_mb: null, steps: [] },
    plan_radar: [], techniques: 8, max_upload_mb: 500,
  };
  document.title = "ModelSmith · Analyze Once. Optimize Smart. Deploy Anywhere.";
  $("#app").innerHTML = `
  <div class="n-landing">

    <!-- scroll progress -->
    <div class="n-progress" id="nProgress"></div>

    <!-- nav -->
    <header class="n-nav" id="nNav">
      <a class="n-brand" href="#top">
        <span class="n-mark"><svg viewBox="0 0 128 128" width="22" height="22" aria-hidden="true">
  <path d="M30 92 V38 L64 72 L98 38 V92" fill="none" stroke="currentColor"
        stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="98" cy="24" r="6" fill="currentColor"/>
  <circle cx="106" cy="36" r="3.6" fill="currentColor"/>
</svg></span>
        <span class="n-brand-name">Model<em>Smith</em></span>
      </a>
      <nav class="n-links" id="nMobMenu">
        <a href="#capabilities" data-smooth>Capabilities</a>
        <a href="#workflow" data-smooth>Workflow</a>
        <a href="#proof" data-smooth>Proof</a>
        <a href="#pricing" data-smooth>Runs anywhere</a>
        <a href="#faq" data-smooth>FAQ</a>
        <a href="#underhood" data-smooth>Developers</a>
        <a class="n-btn n-btn-primary n-mob-cta" href="#/login">Open the app <span aria-hidden="true">→</span></a>
      </nav>
      <div class="n-nav-cta">
        <a class="n-nav-signin" href="#/login">Open the app</a>
        <a class="n-btn n-btn-primary" href="#/login">Open the app <span aria-hidden="true">→</span></a>
        <button class="n-mob-btn" id="nMobBtn" aria-label="Toggle menu" aria-expanded="false">☰</button>
      </div>
    </header>

    <!-- ============ hero ============ -->
    <section class="n-hero" id="top">
      <div class="n-hero-bg">
        <div class="n-grid-lines"></div>
        <div class="n-orb n-orb-a"></div>
        <div class="n-orb n-orb-b"></div>
        <div class="n-noise"></div>
      </div>

      <div class="n-hero-inner">
        <a class="n-badge" href="#workflow" data-smooth data-rv>
          <span class="n-badge-dot"></span>
          Eight optimization techniques, one honest pipeline
          <span class="n-badge-arrow">→</span>
        </a>

        <h1 data-rv style="--rvd:.08s">
          Ship models
          <span class="n-h1-line"><span class="n-serif">80% smaller.</span></span>
          Keep the accuracy.
        </h1>

        <p class="n-lede" data-rv style="--rvd:.16s">
          Upload a PyTorch or ONNX model. ModelSmith profiles it layer by layer,
          ranks an optimization plan for your exact goals, and runs the whole
          pipeline for you. <span class="n-serif-inline">Every gain is measured, never promised.</span>
        </p>

        <div class="n-hero-cta" data-rv style="--rvd:.24s">
          <a class="n-btn n-btn-primary n-btn-lg" href="#/login">
            Start optimizing <span aria-hidden="true">→</span></a>
          <a class="n-btn n-btn-secondary n-btn-lg" href="#workflow" data-smooth>
            See how it works</a>
        </div>

        <div class="n-hero-hint" data-rv style="--rvd:.32s">
          Analysis, planning and execution all run on your own hardware, against your actual model.
        </div>
      </div>

      <!-- the floating product window -->
      <div class="n-window-wrap" data-rv style="--rvd:.2s">
        <div class="n-window">
          <div class="n-win-head">
            <span class="n-win-dot"></span><span class="n-win-dot"></span><span class="n-win-dot"></span>
            <span class="n-win-title">modelsmith · forge</span>
            <span class="n-win-badge">run ${esc(D.run.short_id)} · captured ${esc(D.captured_at || "from the live workspace")}</span>
          </div>
          <div class="n-win-body">
            <div class="n-win-col">
              <div class="n-win-nav">
                <span class="n-win-nav-item on">◈ Dashboard</span>
                <span class="n-win-nav-item">▤ Projects</span>
                <span class="n-win-nav-item">⚙ Settings</span>
              </div>
            </div>
            <div class="n-win-main">
              <div class="n-win-file">
                <span class="n-win-fname">${esc(D.model.file)}</span>
                <span class="n-win-fmeta">${D.model.size_mb} MB · fp32 · ${D.model.layers} layers</span>
              </div>
              <div class="n-win-flow" aria-hidden="true">
                <svg viewBox="0 0 320 56" class="n-flow-svg">
                  <path d="M4 28 C 80 28, 80 10, 160 10 M 160 10 C 240 10, 240 28, 316 28
                           M4 28 C 80 28, 80 46, 160 46 M 160 46 C 240 46, 240 28, 316 28"
                        fill="none" stroke="#3d3520" stroke-width="1.5"/>
                  <circle r="3.5" fill="#ffb224">
                    <animateMotion dur="2.6s" repeatCount="indefinite"
                      path="M4 28 C 80 28, 80 10, 160 10 C 240 10, 240 28, 316 28"/>
                  </circle>
                  <circle r="3.5" fill="#ff6b2c">
                    <animateMotion dur="2.6s" begin="1.3s" repeatCount="indefinite"
                      path="M4 28 C 80 28, 80 46, 160 46 C 240 46, 240 28, 316 28"/>
                  </circle>
                </svg>
              </div>
              <div class="n-win-stages">
                <div class="n-win-stage">
                  <span class="n-win-stage-ico">◎</span>
                  <b>Analyze</b><i>${D.model.layers} layers profiled</i>
                </div>
                <div class="n-win-stage">
                  <span class="n-win-stage-ico">✎</span>
                  <b>Plan</b><i>${D.techniques} techniques ranked</i>
                </div>
                <div class="n-win-stage">
                  <span class="n-win-stage-ico">⚙</span>
                  <b>Execute</b><i>pipeline · ${D.run.steps.length || 6} steps</i>
                </div>
              </div>
              <div class="n-win-result">
                <div class="n-win-result-glow"></div>
                <div class="n-win-out">
                  <span class="n-win-outname">${esc(D.run.artifact)}</span>
                  <span class="n-win-outmeta">${D.run.artifact_mb} MB · −${D.run.saved_pct}% size · −${D.run.latency_gain_pct}% latency</span>
                </div>
                <span class="n-win-ok">✓ agreement ${D.run.agreement_pct}%</span>
              </div>
            </div>
          </div>
          <a class="n-win-open" href="#/login">Open this workspace in the app →</a>
        </div>

        <!-- floating proof chips -->
        <div class="n-chip n-chip-a"><b>−${D.run.saved_pct}%</b><span>size</span></div>
        <div class="n-chip n-chip-b"><b>${D.run.agreement_pct ? "✓ " + D.run.agreement_pct + "%" : "measured"}</b><span>agreement</span></div>
        <div class="n-chip n-chip-c"><b>${D.run.p95_after ? D.run.p95_after + "ms" : "measured"}</b><span>p95 after</span></div>
      </div>
    </section>

    <!-- ============ marquee stack strip ============ -->
    <section class="n-marquee-sec" aria-label="Technologies and techniques">
      <p class="n-marquee-label" data-rv>The stack behind every run</p>
      <div class="n-marquee" data-rv>
        <div class="n-marquee-track">
          ${TECH_MARQUEE.map(t => `<span class="n-marquee-item">${t}</span>`).join("")}
          ${TECH_MARQUEE.map(t => `<span class="n-marquee-item" aria-hidden="true">${t}</span>`).join("")}
        </div>
        <div class="n-marquee-track n-marquee-rev">
          ${[...TECH_MARQUEE].reverse().map(t => `<span class="n-marquee-item">${t}</span>`).join("")}
          ${[...TECH_MARQUEE].reverse().map(t => `<span class="n-marquee-item" aria-hidden="true">${t}</span>`).join("")}
        </div>
      </div>
    </section>

    <!-- ============ bento capabilities ============ -->
    <section class="n-section n-bento-sec" id="capabilities">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Capabilities</span>
        <h2>A pipeline,<br><span class="n-serif">not a pretty dashboard.</span></h2>
        <p>From upload to downloadable artifact, every step is real: per-layer
        analysis, ranked plans, background execution, encrypted artifacts,
        measured proof.</p>
      </div>

      <div class="n-bento">
        <div class="n-cell n-cell-big" data-rv>
          <div class="n-cell-head">
            <span class="n-cell-ico">◎</span>
            <div><b>Every layer, accounted for.</b><i>Parameters, FLOPs, dtypes and memory, measured per layer with forward hooks. Never guessed from file size.</i></div>
          </div>
          <div class="n-cell-viz">
            ${(D.layers_top || []).map((l, i) => `<div class="n-viz-row"><span class="n-viz-label">${esc(l.name)}</span><div class="n-viz-bar"><i style="width:${Math.min(100, l.share * 4)}%${i > 1 ? ";background:var(--ember)" : ""}"></i></div><span class="n-viz-val">${l.share}%</span></div>`).join("")}
          </div>
          <div class="n-cell-tags"><span>measured per layer</span><span>hooks, not heuristics</span></div>
        </div>

        <div class="n-cell" data-rv style="--rvd:.08s">
          <div class="n-cell-head">
            <span class="n-cell-ico">✎</span>
            <div><b>Plans ranked for your goals.</b><i>Eight techniques, simulated together and scored. Plans that do not make the cut explain exactly why.</i></div>
          </div>
          <div class="n-cell-tags"><span>8 techniques</span><span>5 hardware profiles</span></div>
        </div>

        <div class="n-cell" data-rv style="--rvd:.16s">
          <div class="n-cell-head">
            <span class="n-cell-ico">⚡</span>
            <div><b>Numbers from your machine.</b><i>p50 and p95 latency, plus throughput, measured on your own hardware.</i></div>
          </div>
          <div class="n-cell-metric"><b>${D.run.p95_after ?? "—"}<small>ms</small></b><span>p95 after optimization</span></div>
        </div>

        <div class="n-cell" data-rv>
          <div class="n-cell-head">
            <span class="n-cell-ico">⚙</span>
            <div><b>Close the tab. It keeps going.</b><i>Pipelines run as retryable background jobs with live progress. Walk away any time.</i></div>
          </div>
        </div>

        <div class="n-cell n-cell-wide" data-rv style="--rvd:.16s">
          <div class="n-cell-head">
            <span class="n-cell-ico">☁</span>
            <div><b>Our hardware or yours.</b><i>Execute on this server, or take the one-time runner script to your own AWS account — same techniques, same benchmarks, results land back here.</i></div>
          </div>
          <div class="n-cell-tags"><span>bring your own cloud</span><span>one command on EC2</span></div>
        </div>

        <div class="n-cell n-cell-wide" data-rv style="--rvd:.08s">
          <div class="n-cell-head">
            <span class="n-cell-ico">🔒</span>
            <div><b>Encrypted at rest. Isolated by default.</b><i>Fernet AES storage, SHA-256 fingerprints, revocable sessions, and strict ownership on every file.</i></div>
          </div>
          <div class="n-cell-tags"><span>AES at rest</span><span>strict ownership</span><span>zero plaintext</span></div>
        </div>

        <div class="n-cell" data-rv style="--rvd:.16s">
          <div class="n-cell-head">
            <span class="n-cell-ico">⚖</span>
            <div><b>Proof ships with every run.</b><i>Output agreement checks and before/after benchmarks, attached to each artifact.</i></div>
          </div>
        </div>

        <div class="n-cell" data-rv style="--rvd:.24s">
          <div class="n-cell-head">
            <span class="n-cell-ico">⬇</span>
            <div><b>Reports your team can trust.</b><i>Markdown reports, reproducibility metadata, and downloads, generated per run.</i></div>
          </div>
          <div class="n-cell-tags"><span>per run</span><span>reproducible</span></div>
        </div>
      </div>
    </section>

    <!-- ============ workflow ============ -->
    <section class="n-section n-flow-sec" id="workflow">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Workflow</span>
        <h2>Nine stages.<br><span class="n-serif">One pipeline. Zero glue code.</span></h2>
        <p>Each stage writes its results to SQLite. Any run can be
        reproduced and audited later, with no manual steps in between.</p>
      </div>

      <div class="n-flow">
        <div class="n-flow-card" data-rv>
          <span class="n-flow-num">01</span>
          <span class="n-flow-ico">◎</span>
          <b>Analyze</b>
          <p>Static analysis walks the module tree with forward hooks. Per-layer
          parameters, FLOPs, dtypes, and memory. Then real latency benchmarks
          on your own hardware, not vendor slide decks.</p>
          <div class="n-flow-meta">stages 1 through 4</div>
        </div>
        <div class="n-flow-arrow" aria-hidden="true">→</div>
        <div class="n-flow-card" data-rv style="--rvd:.12s">
          <span class="n-flow-num">02</span>
          <span class="n-flow-ico">✎</span>
          <b>Plan</b>
          <p>Set your goals: target size, latency, accuracy, and hardware.
          Eight techniques are simulated, scored, and ranked. Plans that
          fall short explain exactly why they were filtered out.</p>
          <div class="n-flow-meta">stages 5 through 6</div>
        </div>
        <div class="n-flow-arrow" aria-hidden="true">→</div>
        <div class="n-flow-card" data-rv style="--rvd:.24s">
          <span class="n-flow-num">03</span>
          <span class="n-flow-ico">⚙</span>
          <b>Execute</b>
          <p>The real pipeline runs as a retryable background job. Export, quantize,
          calibrate, benchmark. Artifacts land encrypted, with a reproducible
          report you can hand to your team.</p>
          <div class="n-flow-meta">stages 7 through 9</div>
        </div>
      </div>

      <div class="n-rail" data-rv>
        ${[
          ["⬆", "Upload", "validates and fingerprints"],
          ["◎", "Profile", "params, FLOPs, layers"],
          ["⚡", "Bench", "latency and throughput"],
          ["◆", "Bottleneck", "finds the heavy layers"],
          ["✎", "Goals", "size, speed, accuracy"],
          ["♜", "Plan", "8 techniques, ranked"],
          ["⚙", "Execute", "real pipeline, artifacts"],
          ["⚖", "Verify", "agreement and benchmarks"],
          ["⬇", "Report", "reproducible summary"],
        ].map(([g, b, i]) => `
          <div class="n-rail-stop"><span class="glyph">${g}</span><b>${b}</b><i>${i}</i></div>`).join("")}
      </div>
    </section>

    <!-- ============ manual vs modelsmith ============ -->
    <section class="n-section n-vs-sec" id="compare">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Why bother</span>
        <h2>The manual way,<br><span class="n-serif">versus this.</span></h2>
        <p>Everything here can be done by hand. It usually takes a week and a
        strong opinion about opset versions.</p>
      </div>
      <div class="n-vs" data-rv>
        <div class="n-vs-col">
          <div class="n-vs-head manual">Doing it by hand</div>
          ${[
            "Read the quantization docs, form an opinion, hope it holds",
            "Write the export script, debug every opset mismatch",
            "Benchmark once, under conditions that flatter the result",
            "Results end up scattered across chat threads and notebooks",
          ].map(t => `<div class="n-vs-row"><span class="n-vs-x">✕</span>${t}</div>`).join("")}
        </div>
        <div class="n-vs-col modelsmith">
          <div class="n-vs-head ms">ModelSmith</div>
          ${[
            "Eight techniques simulated against your goals, ranked with reasons",
            "One click runs the real pipeline; failures explain themselves",
            "p50 and p95 measured on your hardware, stored forever",
            "A reproducible report attached to every run",
          ].map(t => `<div class="n-vs-row"><span class="n-vs-check">✓</span>${t}</div>`).join("")}
        </div>
      </div>
    </section>

    <!-- ============ stats band ============ -->
    <section class="n-stats" role="list" data-rv>
      <div role="listitem"><b class="num">8</b><span>optimization techniques</span></div>
      <div role="listitem"><b class="num">5</b><span>hardware profiles</span></div>
      <div role="listitem"><b class="num" id="statEndpoints">…</b><span>REST endpoints</span></div>
      <div role="listitem"><b class="num" id="statUpload">…</b><span>MB max model size</span></div>
      <div role="listitem"><b class="num">0</b><span>external JS dependencies</span></div>
    </section>

    <!-- ============ capability splits with live charts ============ -->
    <section class="n-section" id="proof">
      <div class="n-split" data-rv>
        <div class="n-split-copy">
          <span class="n-eyebrow">Proof · 01</span>
          <h2>Know <span class="n-serif">exactly</span><br>what you are shipping.</h2>
          <p>Static analysis walks the module tree with forward hooks. Per-layer
          parameters, FLOPs, dtypes, and memory, all measured on your own
          hardware. No guessing from file sizes.</p>
          <ul class="n-points">
            <li>Per-layer parameter and FLOPs accounting</li>
            <li>p50 and p95 latency, plus throughput</li>
            <li>Bottleneck detection with actionable notes</li>
          </ul>
        </div>
        <div class="n-panel">
          <div class="n-panel-head"><b>Architecture flow</b><span>${esc(D.model.arch)} · ${D.model.layers} layers</span></div>
          <div id="landingArch" class="n-chart"></div>
        </div>
      </div>

      <div class="n-split n-split-flip" data-rv>
        <div class="n-split-copy">
          <span class="n-eyebrow">Proof · 02</span>
          <h2>Every plan, ranked<br>and <span class="n-serif">comparable.</span></h2>
          <p>The planner simulates combinations of eight techniques against your goals
          and scores each candidate on size, speed, accuracy, and deployability.
          Pick two or three and overlay them. The trade-offs become obvious.</p>
          <ul class="n-points">
            <li>Quantization, pruning, distillation, and export</li>
            <li>Five target hardware profiles</li>
            <li>Side-by-side radar and table comparison</li>
          </ul>
        </div>
        <div class="n-panel">
          <div class="n-panel-head"><b>Plan comparison</b><span>${(D.plan_radar || []).length} of ${D.techniques} candidates</span></div>
          <div id="landingRadar" class="n-chart"></div>
          <div id="landingLegend" class="n-legend"></div>
        </div>
      </div>

      <div class="n-split" data-rv>
        <div class="n-split-copy">
          <span class="n-eyebrow">Proof · 03</span>
          <h2>Real execution,<br><span class="n-serif">real artifacts.</span></h2>
          <p>Executing a plan runs the actual pipeline. Export, quantization,
          and pruning happen as a retryable background job with live progress.
          Every artifact is encrypted at rest, downloadable, and benchmarked
          against the original.</p>
          <ul class="n-points">
            <li>CI-style step view with live progress</li>
            <li>Size, speed, and agreement gauges per run</li>
            <li>Full reproducibility metadata on every run</li>
          </ul>
        </div>
        <div class="n-panel">
          <div class="n-panel-head"><b>Run ${esc(D.run.short_id)}</b><span class="n-ok">● success · ${D.run.duration_s}s</span></div>
          <ol class="n-pipe" role="list">
            ${(D.run.steps || []).slice(0, 4).map(s => `<li class="done"><span>✓</span><div><b>${esc(s.label)}</b><i>${esc(s.detail)}</i></div></li>`).join("")}
            <li class="done"><span>✓</span><div><b>Benchmark</b><i>p95 ${D.run.p95_before ?? "—"} → ${D.run.p95_after ?? "—"} ms · agreement ${D.run.agreement_pct ?? "—"}%</i></div></li>
          </ol>
        </div>
      </div>
    </section>

    <!-- ============ under the hood ============ -->
    <section class="n-section" id="underhood">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Developers</span>
        <h2>Everything is an API.<br><span class="n-serif">Script the whole pipeline.</span></h2>
        <p>Every action in the interface is a REST call with your token. Fire
        analyses from CI, queue optimizations from your training scripts, and
        pull measured results wherever you need them. Interactive reference at
        <a href="/docs" style="color:var(--accent)">/docs</a>.</p>
      </div>
      <div class="n-term" data-rv role="img" aria-label="Terminal session showing the ModelSmith API">
        <div class="n-term-head">
          <span class="n-win-dot"></span><span class="n-win-dot"></span><span class="n-win-dot"></span>
          <span class="n-term-title">zsh: modelsmith</span>
        </div>
<pre><code><span class="t-p">$</span> curl -s localhost:8100/api/models/${esc(D.model.id)}/analysis | jq '.summary'
{
  <span class="t-k">"total_params"</span>: <span class="t-n">${D.model.params ?? 0}</span>,
  <span class="t-k">"total_flops"</span>: <span class="t-n">${D.model.flops ?? 0}</span>,
  <span class="t-k">"layer_count"</span>: <span class="t-n">${D.model.layers ?? 0}</span>,
  <span class="t-k">"bottlenecks"</span>: [<span class="t-s">"${esc((D.layers_top || [{}])[0].name || "layer")}: ${(D.layers_top || [{}])[0].share || ""}% of params"</span>]
}

<span class="t-p">$</span> curl -s -X POST localhost:8100/api/models/${esc(D.model.id)}/execute \
    -H <span class="t-s">"Authorization: Bearer $TOKEN"</span> -d <span class="t-s">'{"plan_id":"plan_1"}'</span>
{<span class="t-k">"job_id"</span>: <span class="t-s">"job_${esc(D.run.short_id)}"</span>, <span class="t-k">"status"</span>: <span class="t-s">"queued"</span>}

<span class="t-p">$</span> curl -s localhost:8100/api/jobs/job_${esc(D.run.short_id)} | jq '.progress'
<span class="t-n">100</span>  <span class="t-c"># artifacts ready → download</span></code></pre>
      </div>
    </section>

    <!-- ============ engineering standards ============ -->
    <section class="n-section" id="standards">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Trust</span>
        <h2>Your models<br><span class="n-serif">stay yours.</span></h2>
        <p>Model weights are sensitive. Every layer of ModelSmith is built so
        your files, your results and your history stay private, encrypted and
        accounted for.</p>
      </div>
      <div class="n-req" data-rv>
        <div class="n-req-row n-req-head">
          <span>What you get</span><span>What it means for you</span>
        </div>
        ${[
          ["Encrypted at rest", "Models and artifacts are AES-encrypted before they touch disk. Deleting a model deletes its bytes."],
          ["Private by default", "Every file and result is scoped to your account. Cross-team access is refused by design."],
          ["Full audit trail", "Uploads, runs, downloads and admin actions are recorded with who, what and when."],
          ["Reproducible results", "Every run pins library versions, platform and seed — rerun the same plan months later and compare."],
          ["Instant session control", "Change your password and every other session dies immediately. API keys revoke in one click."],
          ["Validated uploads", "Type whitelist, size caps and SHA-256 fingerprinting before a file is ever processed."],
        ].map(([cap, how]) => `
        <div class="n-req-row">
          <span>${cap}</span>
          <i>${how}</i>
        </div>`).join("")}
      </div>
      <p class="tag-mini" data-rv style="text-align:center;margin-top:22px">
        <a href="#/login" style="color:var(--accent)">Try it with your own model in minutes →</a></p>
    </section>

    <!-- ============ FAQ ============ -->
    <section class="n-section" id="faq">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Questions</span>
        <h2>Asked <span class="n-serif">frequently.</span><br>Answered honestly.</h2>
      </div>
      <div class="n-faq" data-rv>
        ${[
          ["Will quantization hurt my accuracy?",
           "INT8 dynamic quantization typically keeps output agreement above 95%, but typical is not a guarantee. Every run therefore measures agreement on seeded inputs and reports the exact number."],
          ["Which model formats are supported?",
           "PyTorch full-module checkpoints (.pt and .pth) and ONNX files. TensorFlow and JAX models are welcome the moment you export them to ONNX, which is one command in each framework."],
          ["Where do my models actually live?",
           "On the machine running the server, and nowhere else. Uploads and artifacts are encrypted before they touch disk, never sent to any external service, and deleting a model deletes its bytes. The audit entry outlives the file."],
          ["What does measured, not promised mean?",
           "Before execution you see predictions: size, latency, memory, accuracy retention. After execution you see measurements of the same four things on the real artifact. Both are stored, so you can check the prediction against reality."],
          ["Can I reproduce a run from last month?",
           "Yes. Every run records library versions, platform, seed and benchmark settings. Re-running the same plan reproduces the pipeline; tiny timing differences are expected and honest."],
          ["Is this production infrastructure?",
           "It is built for single-team workloads with production habits: encrypted storage, revocable sessions, rate limiting and a full audit log. When you outgrow one node, bring your own infrastructure — the runner executes on any machine, including your AWS account."],
        ].map(([q, a], i) => `
        <details class="n-faq-item" ${i === 0 ? "open" : ""} data-rv style="--rvd:${i * 0.06}s">
          <summary>${q}<span class="n-faq-plus" aria-hidden="true"></span></summary>
          <p>${a}</p>
        </details>`).join("")}
      </div>
    </section>

    <!-- ============ deployment story ============ -->
    <section class="n-section" id="pricing">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Runs anywhere</span>
        <h2>Your infrastructure.<br><span class="n-serif">Your data.</span></h2>
        <p>ModelSmith ships as a single container. Point it at a volume,
        run it anywhere Docker runs, and your models never leave your
        network. No accounts to create, no telemetry, no phone home.</p>
      </div>
      <div class="n-deploy" data-rv>
        <div class="n-dep-card">
          <span class="n-dep-ico">▣</span><b>One command</b>
          <p>A single <span class="n-mono">docker compose up</span> brings up
          the API, the runner and the frontend together.</p>
        </div>
        <div class="n-dep-card">
          <span class="n-dep-ico">🔒</span><b>Encrypted at rest</b>
          <p>Uploads and artifacts are Fernet-encrypted before they touch
          the disk. Deleting a model deletes its bytes.</p>
        </div>
        <div class="n-dep-card">
          <span class="n-dep-ico">⚙</span><b>Observability included</b>
          <p>Health and Prometheus endpoints, a structured access log, and a
          request id on every response.</p>
        </div>
        <div class="n-dep-card">
          <span class="n-dep-ico">⬇</span><b>Export everything</b>
          <p>Reports, artifacts, reproducible scripts, audit logs and your
          whole workspace as JSON or CSV.</p>
        </div>
      </div>
    </section>

    <!-- ============ final CTA ============ -->
    <section class="n-final" data-rv>
      <div class="n-final-glow"></div>
      <h2>Analyze once. Optimize smart.<br><span class="n-serif">Deploy anywhere.</span></h2>
      <div class="n-final-cta">
        <a class="n-btn n-btn-primary n-btn-xl" href="#/login">Open the app <span aria-hidden="true">→</span></a>
      </div>
      <p class="n-final-hint">Runs locally in one command. Open source, end to end.</p>
    </section>

    <!-- ============ footer ============ -->
    <footer class="n-foot">
      <div class="n-foot-grid">
        <div class="n-foot-brand">
          <span class="n-mark"><svg viewBox="0 0 128 128" width="22" height="22" aria-hidden="true">
  <path d="M30 92 V38 L64 72 L98 38 V92" fill="none" stroke="currentColor"
        stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="98" cy="24" r="6" fill="currentColor"/>
  <circle cx="106" cy="36" r="3.6" fill="currentColor"/>
</svg></span>
          <p>The intelligent AI model optimization and deployment platform.</p>
        </div>
        <div class="n-foot-col">
          <b>Product</b>
          <a href="#capabilities" data-smooth>Capabilities</a>
          <a href="#workflow" data-smooth>Workflow</a>
          <a href="#pricing" data-smooth>Runs anywhere</a>
          <a href="/docs" target="_blank" rel="noopener">API reference</a>
          <a href="#/login">Open the app</a>
        </div>
        <div class="n-foot-col">
          <b>Resources</b>
          <a href="#underhood" data-smooth>Developers</a>
          <a href="#standards" data-smooth>Security</a>
          <a href="#faq" data-smooth>FAQ</a>
        </div>
        <div class="n-foot-col">
          <b>Open source</b>
          <a href="https://github.com/MohammedAnasNathani/modelsmith" target="_blank" rel="noopener">Source code</a>
          <span>MIT licensed</span>
          <span>Zero frontend dependencies</span>
        </div>
      </div>
      <div class="n-foot-base">
        <span>ModelSmith</span>
        <span>Measured, not promised.</span>
      </div>
    </footer>
    <!-- sticky mobile CTA -->
    <div class="n-sticky-cta">
      <div>
        <b>See it on a real model</b>
        <span>Sample workspace loads in seconds</span>
      </div>
      <a class="n-btn n-btn-primary" href="#/login">Open the app</a>
    </div>
  </div>`;

  const arch = $("#landingArch");
  if (arch && window.MSCharts) {
    const LANDING_LAYERS = D.layers || [];
    MSCharts.archGraph(arch, LANDING_LAYERS);
    const LANDING_RADAR = D.plan_radar || [];
    MSCharts.radar($("#landingRadar"), RADAR_AXES, LANDING_RADAR, { size: 260, legend: false });
    $("#landingLegend").innerHTML = LANDING_RADAR.map(s =>
      `<span class="n-lg-item"><i style="background:${s.color}"></i>${s.name}</span>`).join("");
  }

  (async () => {
    try {
      const spec = await fetch("/openapi.json").then(r => r.json());
      const n = Object.keys(spec.paths).length;
      const el = $("#statEndpoints");
      if (el) el.textContent = n;
    } catch { $("#statEndpoints") && ($("#statEndpoints").textContent = "60+"); }
  })();

  (async () => {
    try {
      const el = $("#statTests");
      const up = $("#statUpload");
      if (up) up.textContent = String(D.max_upload_mb || 500);
    } catch {}
  })();

  $$("[data-smooth]").forEach(a => a.onclick = e => {
    e.preventDefault();
    const t = document.querySelector(a.getAttribute("href"));
    if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  revealOnScroll();
  setupNavScroll();
  setupParallax();
  setupMobileNav();
}
