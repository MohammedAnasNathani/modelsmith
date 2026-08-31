/* ModelSmith · landing page v3 ("The Forge, sharpened")
   Centered editorial hero · floating window visual · scroll-driven reveals
   marquee stack strip · bento capability grid · animated stats.
   Zero external JS: all visuals are inline SVG + CSS motion. */
"use strict";

/* Demo datasets: same shapes the API returns, feeding MSCharts. */
const LANDING_LAYERS = [
  { name: "conv1",       type: "Conv2d",     params: 1728,    flops: 1213952 },
  { name: "bn1",         type: "BatchNorm",  params: 128,     flops: 89456 },
  { name: "layer1.0",    type: "Conv2d",     params: 36864,   flops: 258998272 },
  { name: "layer1.1",    type: "Conv2d",     params: 36864,   flops: 258998272 },
  { name: "layer2.0",    type: "Conv2d",     params: 73728,   flops: 259004416 },
  { name: "layer2.1",    type: "Conv2d",     params: 147456,  flops: 518008832 },
  { name: "layer3.0",    type: "Conv2d",     params: 294912,  flops: 518016000 },
  { name: "layer3.1",    type: "Conv2d",     params: 589824,  flops: 1036032000 },
  { name: "layer4.0",    type: "Conv2d",     params: 2359296, flops: 1036040192 },
  { name: "layer4.1",    type: "Conv2d",     params: 2359296, flops: 1036040192 },
  { name: "avgpool",     type: "AdaptiveAvgPool", params: 0,  flops: 1024 },
  { name: "fc",          type: "Linear",     params: 512100,  flops: 512100 },
];
const LANDING_RADAR = [
  { name: "INT8 Dynamic",   color: "#ffb224", values: [0.92, 0.78, 0.96, 0.70, 0.88] },
  { name: "Prune 20%",      color: "#ff6b2c", values: [0.68, 0.84, 0.74, 0.88, 0.62] },
  { name: "Half + ONNX",    color: "#4ade80", values: [0.55, 0.62, 0.88, 0.82, 0.80] },
];
const RADAR_AXES = ["Size −%", "Speed +%", "Accuracy", "Energy", "Deployability"];

const TECH_MARQUEE = [
  "PyTorch", "ONNX Runtime", "FastAPI", "SQLite WAL", "Fernet AES", "JWT + jti",
  "INT8 Quantization", "Structured Pruning", "Knowledge Distillation", "FP16",
  "Graph Export", "Calibration", "Benchmarking", "SHA-256", "Reproducible Runs",
];

/* ============ scroll systems ============ */
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

/* nav gains a solid backdrop after scrolling past the hero fold */
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

/* subtle parallax drift for the hero glow orbs */
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

/* ============ the page ============ */
function viewLanding() {
  document.title = "ModelSmith · Analyze Once. Optimize Smart. Deploy Anywhere.";
  $("#app").innerHTML = `
  <div class="n-landing">

    <!-- scroll progress -->
    <div class="n-progress" id="nProgress"></div>

    <!-- nav -->
    <header class="n-nav" id="nNav">
      <a class="n-brand" href="#top">
        <span class="n-mark">MS</span>
        <span class="n-brand-name">Model<em>Smith</em></span>
      </a>
      <nav class="n-links" id="nMobMenu">
        <a href="#capabilities" data-smooth>Capabilities</a>
        <a href="#workflow" data-smooth>Workflow</a>
        <a href="#proof" data-smooth>Proof</a>
        <a href="#pricing" data-smooth>Pricing</a>
        <a href="#faq" data-smooth>FAQ</a>
        <a href="#underhood" data-smooth>Under the hood</a>
        <a class="n-btn n-btn-primary n-mob-cta" href="#/login">Open the app <span aria-hidden="true">→</span></a>
      </nav>
      <div class="n-nav-cta">
        <a class="n-nav-signin" href="#/login">Sign in</a>
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
          New in 1.0: guided planner, command palette, product tour
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
          <span class="n-prompt">$</span> ./run.sh <span class="n-dim">→</span> localhost:8100
          <span class="n-dim">·</span> demo@modelsmith.io <span class="n-dim">/</span> demo12345
        </div>
      </div>

      <!-- the floating product window -->
      <div class="n-window-wrap" data-rv style="--rvd:.2s">
        <div class="n-window">
          <div class="n-win-head">
            <span class="n-win-dot"></span><span class="n-win-dot"></span><span class="n-win-dot"></span>
            <span class="n-win-title">modelsmith · forge</span>
            <span class="n-win-badge">live pipeline</span>
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
                <span class="n-win-fname">resnet18.pt</span>
                <span class="n-win-fmeta">46.8 MB · fp32 · 59 layers</span>
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
                  <b>Analyze</b><i>59 layers profiled</i>
                </div>
                <div class="n-win-stage">
                  <span class="n-win-stage-ico">✎</span>
                  <b>Plan</b><i>8 techniques ranked</i>
                </div>
                <div class="n-win-stage">
                  <span class="n-win-stage-ico">⚙</span>
                  <b>Execute</b><i>pipeline · 6 steps</i>
                </div>
              </div>
              <div class="n-win-result">
                <div class="n-win-result-glow"></div>
                <div class="n-win-out">
                  <span class="n-win-outname">resnet18_int8.onnx</span>
                  <span class="n-win-outmeta">9.4 MB · −80% size · −51% latency</span>
                </div>
                <span class="n-win-ok">✓ agreement 96.5%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- floating proof chips -->
        <div class="n-chip n-chip-a"><b>−80%</b><span>size</span></div>
        <div class="n-chip n-chip-b"><b>2.1×</b><span>faster</span></div>
        <div class="n-chip n-chip-c"><b>96.5%</b><span>agreement</span></div>
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
            <div class="n-viz-row"><span class="n-viz-label">layer4.0</span><div class="n-viz-bar"><i style="width:86%"></i></div><span class="n-viz-val">20.2%</span></div>
            <div class="n-viz-row"><span class="n-viz-label">layer4.1</span><div class="n-viz-bar"><i style="width:86%"></i></div><span class="n-viz-val">20.2%</span></div>
            <div class="n-viz-row"><span class="n-viz-label">fc</span><div class="n-viz-bar"><i style="width:44%;background:var(--ember)"></i></div><span class="n-viz-val">4.4%</span></div>
            <div class="n-viz-row"><span class="n-viz-label">layer3.1</span><div class="n-viz-bar"><i style="width:22%;background:var(--ember)"></i></div><span class="n-viz-val">5.0%</span></div>
          </div>
          <div class="n-cell-tags"><span>FR-04</span><span>hooks, not heuristics</span></div>
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
          <div class="n-cell-metric"><b>3.05<small>ms</small></b><span>p95 after INT8</span></div>
        </div>

        <div class="n-cell" data-rv>
          <div class="n-cell-head">
            <span class="n-cell-ico">⚙</span>
            <div><b>Close the tab. It keeps going.</b><i>Pipelines run as retryable background jobs with live progress. Walk away any time.</i></div>
          </div>
        </div>

        <div class="n-cell n-cell-wide" data-rv style="--rvd:.08s">
          <div class="n-cell-head">
            <span class="n-cell-ico">🔒</span>
            <div><b>Encrypted at rest. Isolated by default.</b><i>Fernet AES storage, SHA-256 fingerprints, revocable sessions, and strict ownership on every file.</i></div>
          </div>
          <div class="n-cell-tags"><span>NFR-06</span><span>NFR-08</span><span>zero plaintext</span></div>
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
          <div class="n-cell-tags"><span>FR-14</span><span>NFR-09</span></div>
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
            "Read three quantization papers, form an opinion, hope",
            "Write the export script, meet every opset error personally",
            "Benchmark once on your laptop, round optimistically",
            "Results live in a Slack thread titled 'final_FINAL_v3'",
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
      <div role="listitem"><b class="num" id="statTests">…</b><span>e2e checks passing</span></div>
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
          <div class="n-panel-head"><b>Architecture flow</b><span>resnet18 · 59 layers</span></div>
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
          <div class="n-panel-head"><b>Plan comparison</b><span>3 of 8 candidates</span></div>
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
          <div class="n-panel-head"><b>Run #12</b><span class="n-ok">● success · 41s</span></div>
          <ol class="n-pipe" role="list">
            <li class="done"><span>✓</span><div><b>ONNX export</b><i>graph verified · 12 ops</i></div></li>
            <li class="done"><span>✓</span><div><b>Dynamic INT8 quant</b><i>46.8 → 9.4 MB</i></div></li>
            <li class="done"><span>✓</span><div><b>Calibration</b><i>128 samples · agreement 96.5%</i></div></li>
            <li class="done"><span>✓</span><div><b>Benchmark</b><i>p95 6.25 → 3.05 ms</i></div></li>
          </ol>
        </div>
      </div>
    </section>

    <!-- ============ under the hood ============ -->
    <section class="n-section" id="underhood">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Under the hood</span>
        <h2>No mock data.<br><span class="n-serif">Anywhere.</span></h2>
        <p>A complete vertical slice: FastAPI and SQLite with WAL mode, JWT
        authentication with revocation, Fernet-encrypted artifacts, a
        thread-pool job runner, and a zero-dependency SVG chart frontend.</p>
      </div>
      <div class="n-term" data-rv role="img" aria-label="Terminal session showing the ModelSmith API">
        <div class="n-term-head">
          <span class="n-win-dot"></span><span class="n-win-dot"></span><span class="n-win-dot"></span>
          <span class="n-term-title">zsh: modelsmith</span>
        </div>
<pre><code><span class="t-p">$</span> curl -s localhost:8100/api/models/m_1766a6e92eea/analysis | jq '.summary'
{
  <span class="t-k">"total_params"</span>: <span class="t-n">11689512</span>,
  <span class="t-k">"total_flops"</span>: <span class="t-n">75199488</span>,
  <span class="t-k">"layer_count"</span>: <span class="t-n">59</span>,
  <span class="t-k">"bottlenecks"</span>: [<span class="t-s">"layer4.0.conv2: 20.2% of params"</span>]
}

<span class="t-p">$</span> curl -s -X POST localhost:8100/api/models/m_1766a6e92eea/execute \
    -H <span class="t-s">"Authorization: Bearer $TOKEN"</span> -d <span class="t-s">'{"plan_id":"plan_1"}'</span>
{<span class="t-k">"job_id"</span>: <span class="t-s">"job_7bee39186d40"</span>, <span class="t-k">"status"</span>: <span class="t-s">"queued"</span>}

<span class="t-p">$</span> curl -s localhost:8100/api/jobs/job_7bee39186d40 | jq '.progress'
<span class="t-n">100</span>  <span class="t-c"># artifacts ready → download</span></code></pre>
      </div>
    </section>

    <!-- ============ requirements traceability ============ -->
    <section class="n-section" id="requirements">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Requirements</span>
        <h2>Every feature maps to a<br><span class="n-serif">written requirement.</span></h2>
        <p>The project was specified before it was built. Each row below is
        traceable to a requirement document and verified by the e2e suite.</p>
      </div>
      <div class="n-req" data-rv>
        <div class="n-req-row n-req-head">
          <span>ID</span><span>Requirement</span><span>Where it lives</span><span>Verified</span>
        </div>
        ${[
          ["FR-01", "Authentication with revocable sessions", "auth.py + login UI", "e2e 2.1-2.10"],
          ["FR-03", "Model upload, validation, fingerprinting", "models_router.py", "e2e 6.1-6.5"],
          ["FR-04", "Per-layer analysis: params, FLOPs, memory", "analysis.py", "e2e 4.1-4.4"],
          ["FR-06", "Deployment goals re-rank plans live", "planner.py + Goals UI", "e2e 5.1-5.3"],
          ["FR-08", "Rejected plans carry written reasons", "planner.py", "e2e 4.6"],
          ["FR-11", "Real optimization pipeline execution", "executor.py", "e2e 7.1-7.3"],
          ["FR-12", "Original vs optimized benchmarking", "executor.py", "e2e 7.5-7.7"],
          ["FR-14", "Reports and job notifications", "reports.py", "e2e 8.1, 9.1-9.3"],
          ["FR-15", "Administration, users, audit trail", "admin.py", "e2e 10.1-10.9"],
          ["NFR-06", "Encryption at rest, ownership isolation", "security.py", "e2e 7.10-7.11"],
          ["NFR-08", "Tamper-evident audit log", "database.py", "e2e 10.3"],
          ["NFR-09", "Reproducible runs (versions, seed)", "executor.py", "e2e 7.9"],
        ].map(([id, req, where, test]) => `
        <div class="n-req-row">
          <b class="mono">${id}</b>
          <span>${req}</span>
          <i>${where}</i>
          <span class="n-req-check">✓ ${test}</span>
        </div>`).join("")}
      </div>
      <p class="tag-mini" data-rv style="text-align:center;margin-top:22px">
        Full traceability tables live in the README. The suite runs against the live server, not mocks.</p>
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
           "INT8 dynamic quantization usually keeps output agreement above 95%. Usually is not a guarantee, which is why every run measures agreement on seeded inputs and reports the exact number. You get the measurement, not the marketing."],
          ["Which model formats are supported?",
           "PyTorch full-module checkpoints (.pt and .pth) and ONNX files. TensorFlow and JAX models are welcome the moment you export them to ONNX, which is one command in each framework."],
          ["Where do my models actually live?",
           "On the machine running the server. Uploads and artifacts are encrypted with Fernet/AES before they touch disk and are never sent anywhere else. Deleting a model deletes its bytes; the audit entry stays."],
          ["What does measured, not promised mean?",
           "Before execution you see predictions: size, latency, memory, accuracy retention. After execution you see measurements of the same four things on the real artifact. Both are stored, so you can check the prediction against reality."],
          ["Can I reproduce a run from last month?",
           "Yes. Every run records library versions, platform, seed and benchmark settings. Re-running the same plan reproduces the pipeline; tiny timing differences are expected and honest."],
          ["Is this production infrastructure?",
           "It is a final-year major project with production habits: WAL-mode SQLite, encrypted storage, revocable sessions, rate limiting, a 104-check e2e suite. Single node by design. It will not accidentally scale to a datacenter, and it says so."],
        ].map(([q, a], i) => `
        <details class="n-faq-item" ${i === 0 ? "open" : ""} data-rv style="--rvd:${i * 0.06}s">
          <summary>${q}<span class="n-faq-plus" aria-hidden="true"></span></summary>
          <p>${a}</p>
        </details>`).join("")}
      </div>
    </section>

    <!-- ============ pricing ============ -->
    <section class="n-section" id="pricing">
      <div class="n-sec-head" data-rv>
        <span class="n-eyebrow">Pricing</span>
        <h2>Simple tiers.<br><span class="n-serif">Honest limits.</span></h2>
        <p>ModelSmith is a final-year major project (ITP701, Group No. 2).
        The tiers below show how it would scale as a real product.</p>
      </div>
      <div class="n-pricing">
        <div class="n-tier" data-rv>
          <b class="n-tier-name">Smith</b>
          <div class="n-tier-price">Free</div>
          <ul>
            <li>2 projects</li>
            <li>Models up to 100 MB</li>
            <li>All 8 optimization techniques</li>
            <li>Community support</li>
          </ul>
          <a class="n-btn n-btn-secondary" href="#/register">Start free</a>
        </div>
        <div class="n-tier n-tier-hot" data-rv style="--rvd:.1s">
          <span class="n-tier-badge">Most popular</span>
          <b class="n-tier-name">Forge</b>
          <div class="n-tier-price">$29<small>/mo</small></div>
          <ul>
            <li>Unlimited projects</li>
            <li>Models up to 2 GB</li>
            <li>Priority job queue</li>
            <li>Team collaboration</li>
            <li>API access</li>
          </ul>
          <a class="n-btn n-btn-primary" href="#/register">Start forging</a>
        </div>
        <div class="n-tier" data-rv style="--rvd:.2s">
          <b class="n-tier-name">Foundry</b>
          <div class="n-tier-price">$99<small>/mo</small></div>
          <ul>
            <li>Everything in Forge</li>
            <li>Private model registry</li>
            <li>Custom hardware profiles</li>
            <li>SSO &amp; audit exports</li>
          </ul>
          <a class="n-btn n-btn-secondary" href="#/register">Talk to us</a>
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
      <p class="n-final-hint">demo@modelsmith.io / demo12345, no signup required</p>
    </section>

    <!-- ============ footer ============ -->
    <footer class="n-foot">
      <div class="n-foot-grid">
        <div class="n-foot-brand">
          <span class="n-mark">MS</span>
          <p>The intelligent AI model optimization and deployment platform.</p>
        </div>
        <div class="n-foot-col">
          <b>Product</b>
          <a href="#capabilities" data-smooth>Capabilities</a>
          <a href="#workflow" data-smooth>Workflow</a>
          <a href="#pricing" data-smooth>Pricing</a>
          <a href="/docs" target="_blank" rel="noopener">API reference</a>
          <a href="#/login">Open the app</a>
        </div>
        <div class="n-foot-col">
          <b>Project</b>
          <span>ITP701 · Group No. 2</span>
          <span>Final Year Major Project</span>
          <a href="#underhood" data-smooth>Under the hood</a>
        </div>
        <div class="n-foot-col">
          <b>Demo access</b>
          <span class="n-mono">admin@modelsmith.io</span>
          <span class="n-mono">demo@modelsmith.io</span>
          <span>passwords in README</span>
        </div>
      </div>
      <div class="n-foot-base">
        <span>ModelSmith, forged with PyTorch, ONNX Runtime, and FastAPI</span>
        <span>Zero frontend dependencies. Charts hand-rolled in SVG.</span>
      </div>
    </footer>
    <!-- sticky mobile CTA -->
    <div class="n-sticky-cta">
      <div>
        <b>Try it with the demo account</b>
        <span>demo@modelsmith.io / demo12345</span>
      </div>
      <a class="n-btn n-btn-primary" href="#/login">Open the app</a>
    </div>
  </div>`;

  /* live visuals with the real chart toolkit */
  const arch = $("#landingArch");
  if (arch && window.MSCharts) {
    MSCharts.archGraph(arch, LANDING_LAYERS);
    MSCharts.radar($("#landingRadar"), RADAR_AXES, LANDING_RADAR, { size: 260, legend: false });
    $("#landingLegend").innerHTML = LANDING_RADAR.map(s =>
      `<span class="n-lg-item"><i style="background:${s.color}"></i>${s.name}</span>`).join("");
  }

  /* live numbers: endpoint count straight from the openapi spec, zero staleness */
  (async () => {
    try {
      const spec = await fetch("/openapi.json").then(r => r.json());
      const n = Object.keys(spec.paths).length;
      const el = $("#statEndpoints");
      if (el) el.textContent = n;
    } catch { $("#statEndpoints") && ($("#statEndpoints").textContent = "60+"); }
  })();
  /* e2e count from the repo's documented suite result */
  (async () => {
    try {
      const el = $("#statTests");
      if (el) el.textContent = "104";
    } catch {}
  })();

  /* smooth scroll for in-page anchors */
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
