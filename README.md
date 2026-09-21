# ModelSmith · Intelligent AI Model Optimization & Deployment Platform


*Analyze Once. Optimize Smart. Deploy Anywhere.*

ModelSmith is a decision-making and orchestration layer between model
development and deployment. Upload a trained model, and the platform analyzes
its architecture, profiles its real latency, generates **ranked optimization
plans with predicted trade-offs**, executes the chosen plan (INT8
quantization, pruning, FP16, ONNX export), benchmarks original vs optimized,
and packages encrypted, deployment-ready artifacts with a full report.

## The Forge: design system

The product ships a complete visual identity: **molten amber on warm forge-black**, Bricolage
Grotesque + Instrument Serif + Inter + JetBrains Mono typography, purposeful
spring/expo motion with `prefers-reduced-motion` fallbacks, visible focus
rings, and tabular numerals for every metric. Charts are hand-rolled SVG
(zero external JS dependencies).

## Product surface

- **SaaS landing page v3** (`#/welcome`): centered editorial hero with huge
  display type and gradient serif accents, floating 3D-tilt product window
  with animated pipeline and proof chips, scroll-progress bar, parallax glow
  orbs, blueprint-grid backdrop with film-grain texture, dual marquee tech
  strip, bento capability grid with animated bar viz, three numbered workflow
  cards plus a 9-stage rail, animated stat counters, terminal API tour,
  testimonials, pricing, glowing final CTA, full footer with API reference
  link. All reveals are IntersectionObserver-driven with stagger delays.
- **App shell**: sidebar navigation, ⌘K command palette (grouped, fuzzy
  search across projects/models/commands), notification bell with dropdown
  panel, breadcrumbs, **mobile drawer navigation** with hamburger toggle.
- **Bento dashboard**: animated count-up stats, onboarding checklist with
  live progress, recent models, job activity, system health gauge, 30-day
  activity sparkline, framework-distribution donut.
- **Model deep-dive**: 5 tabs: Overview (architecture flow graph, latency
  gauge, compute budget, top plan), Analysis (parameter donut, FLOPs bars,
  layer table, profiler notes), Plans (ranked cards, up-to-3 comparison with
  radar + table), Executions (CI-style pipeline, gauges, artifact downloads),
  Report.
- **Keyboard shortcuts overlay**: press `?` anywhere for a grouped, Linear-
  style shortcut reference (`⌘K` palette, `g`+`d`/`p`/`s`/`a` navigation).
- **Guided product tour**: first-visit spotlight tour (workspace, palette,
  notifications, account), replayable from the dashboard.
- **Settings page** (`#/settings`): profile editing (`PATCH /api/auth/me`),
  in-session password change (`POST /api/auth/password/change`, requires
  current password, rotates the session token), appearance info, session
  details, and a **personal activity feed** (`GET /api/auth/me/activity`)
  rendering your last 50 audited actions with colored category dots.
- **Global search** (`#/search`): debounced live search across all projects
  by name/framework/status, with pick-two **model comparison**.
- **Model comparison** (`#/compare/a/b`): side-by-side analysis of any two
  analyzed models: parameter donuts, grouped FLOPs/param bars, head-to-head
  metric table with deltas (`GET /api/models/compare`).
- **Enhanced project cards**: per-project status-breakdown progress bars
  (analyzed / analyzing / failed / pending), total encrypted storage, latest
  activity timestamp.
- **Workspace export**: all projects & models as JSON or CSV
  (`GET /api/projects/export/{json|csv}`).
- **Upload progress**: real XHR upload progress with file size, percentage,
  and server-processing state.
- **Multi-toast notifications**: stacked, dismissible action feedback.
- **Custom SVG empty states**: hand-drawn forge-style illustrations for
  projects, models, search, and runs.
- **Skeleton loading states**: shimmering title/line/table placeholders while
  dashboards and settings load.
- **Deterministic avatar hues**: each user's initials avatar gets a stable
  color derived from a hash of their name.
- **Run deletion**: `DELETE /api/runs/{id}` removes a run and its encrypted
  artifacts.
- **Custom 404**: forge-themed not-found page with animated hammer "0".

### Platform & API

**Platform / API**
- **Server-side search**: `GET /api/search?q=&status=` across all your models,
  project names included.
- **Optimization suggestions**: `GET /api/models/{id}/suggestions` derives
  next-step advice from the stored analysis (conv share, latency class,
  file-vs-param ratio, top plan), rendered as the "What we would do next"
  panel on the model overview.
- **Model rename**: `PATCH /api/models/{id}` with audit trail.
- **Job cancel / retry**: `POST /api/jobs/{id}/cancel` (queued only, honest
  409 otherwise) and `/retry` (failed only, fresh attempt counter). Runs tied
  to a cancelled job are marked failed; retried runs requeue.
- **Duplicate upload detection**: identical SHA-256 within a project is
  refused with 409 and the existing model's id.
- **Session introspection**: `GET /api/auth/me/session` (issued-at, expiry,
  seconds remaining) powering a live countdown pill in Settings.
- **Admin storage stats**: `GET /api/admin/stats/storage` (encrypted uploads,
  artifacts, database, encrypted share) rendered as an admin tile.
- **Audit CSV export**: `GET /api/admin/audit/export` (admin only).
- **Richer health**: queue depth and data-dir size in `/api/health`.
- **X-Request-ID middleware**: every response carries a correlation id that
  also appears in the access-log line.

**Interface**
- Sortable layer table (click any header; sort state visualized).
- Project model filters (All / Ready / Analyzing / Failed with counts) and
  multi-select bulk delete with a confirmation step.
- Copy-to-clipboard for SHA-256 fingerprints; toasts gained action buttons
  ("Watch" after execution starts).
- Compare view highlights the winning value of every metric with a green ring.
- Notification panel groups by day and offers "mark all read".
- Landing: "The manual way, versus this" comparison strip, an honest FAQ
  accordion, sticky mobile CTA bar.

### Workflow & reliability

**New pages**
- **Job center** (`#/jobs`): every analysis and execution the runner has
  handled for you, filterable by status, with live progress polling, cancel
  (queued) and retry (failed) buttons inline.
- **API playground** (`#/api`): fire real GET requests against the live API
  with your own token, curated endpoint list, pretty-printed responses with
  status, timing and size. Mutations stay in `/docs` where they belong.

**Model intelligence**
- **Optimization history**: `GET /api/models/{id}/history` returns the full
  size/latency progression (baseline plus every run), rendered as a timeline
  with a sparkline on the model overview.
- **Notes and tags**: free-form notes plus up to 8 tags per model
  (`PATCH /api/models/{id}`), editable in the overview with a tag input.
- **Original download**: `GET /api/models/{id}/download` streams the exact
  bytes that were uploaded, decrypted server-side (e2e-verified byte-identical).

**Workspace**
- **Batch upload**: the upload dialog accepts multiple files (select or drag),
  uploads sequentially with per-file progress, names them with numeric
  suffixes.
- **Dashboard insights**: heaviest model, best size win, busiest project and
  live in-flight job count, as clickable chips.
- **Project sorting** (updated / name / models / runs) and **archive /
  unarchive** (soft-hide, data intact, dimmed cards).
- **Command palette v3**: server-side search via `/api/search` (one request
  instead of N), fuzzy matching on hints, and a Recent group learned from
  your navigation history.

**Platform**
- **Light theme** ("The Foundry"): full second palette, toggle in the sidebar
  and persisted per browser.
- **Prometheus metrics** at `GET /api/metrics` (uptime, users, models, runs,
  jobs by status).
- **Public config** at `GET /api/config` (limits, rate rules, versions).
- **Admin broadcast**: notify every active user at once.
- **Admin user detail**: any user's projects, models and job counts.
- **Database backup**: `GET /api/admin/backup` returns a consistent SQLite
  snapshot via `VACUUM INTO`.
- **Print stylesheet**: reports and tables print cleanly.

### Reporting, sharing & admin

**Fun and proof**
- **Achievements** (`#/achievements`): twelve badges earned from real history
  (The 80% Club, Night Shift, Trust but Verify...), plus a live scoreboard.
  `GET /api/achievements`.
- **Public share links**: `POST /api/models/{id}/share` mints a token; anyone
  with `#/share/{token}` sees a read-only report card (best run, measured
  gains, view counter). No auth, no files.
- **Reproducible scripts**: `GET /api/runs/{id}/script` returns a standalone
  Python file mirroring what the run did, with the recorded versions.
- **Efficiency score** (0-100) on every model: honest readiness heuristic
  from measured size and latency.
- **Before/after diff**: `GET /api/models/{id}/diff` compares the original
  against the best successful run, metric by metric, rendered as a table.
- **Pareto frontier chart** on the Plans tab: which plans no other plan beats
  on both size and latency, drawn with a dashed front line.
- **What-if slider**: drag your minimum accuracy floor and watch plans
  disappear live, no server round-trip.
- **Re-run from history**: one click re-executes a past run's exact plan.
- **Confetti** when a fresh run cuts size by half or more.
- **Global drag-and-drop**: drop a .pt/.onnx anywhere in the app to upload
  into your most recent project.

**Smarter workspace**
- **Command palette calculator**: type `46.8MB to GB`, `45% of 46.8`, or raw
  arithmetic and get answers inline.
- **Plan keyboard compare**: press 1-9 to toggle plans into comparison;
  copy a one-line plan summary with the ⧉ button.
- **Project stats strip**: total parameters, encrypted storage, best win,
  heaviest model, on every project page.
- **Dashboard queue banner** when jobs wait over 30s, with the oldest wait.
- **Search hint chips**: your real model names offered as starting points.

### Real training, not just compression

Knowledge Distillation is a real training run: the platform builds a
half-width student from your model, then optimizes it with Adam against
the teacher's soft targets (KL, temperature 2) for six epochs. The loss
curve is recorded step by step in the run, the trained student is stored
as an encrypted artifact, and the benchmark measures it exactly like any
other run. Architectures that cannot be auto-shrunk (residual branches)
fall back honestly to self-distillation fine-tuning — either way, real
optimizer steps happen and real weights move.

### Execution venues: the platform or your own cloud

The executor now runs in two venues with identical measured results:

- **Platform execution** (existing): the plan runs on the server's thread
  pool as a background job.
- **Own-infrastructure execution** (new): the platform orchestrates, your
  machine does the work. On execute, choose "Run on my own infrastructure":
  the platform mints a one-time runner token (24h TTL, burned on terminal
  report) and generates a self-contained `ms_runner_<run>.py` that needs
  only torch/onnx/onnxruntime/numpy. The runner downloads the model via a
  token-scoped endpoint, applies the plan's techniques with the same
  pipeline logic as the server executor, benchmarks baseline vs optimized
  on the same seeded inputs, and reports back over
  `POST /api/runner/{token}/result`. The platform then completes the run
  exactly like a platform execution: encrypted artifacts, benchmark
  record, reproducibility metadata tagged `executed_on: user
  infrastructure`, notification, audit entry, token burned.
  - **AWS launch, two ways**: the instructions modal can launch the EC2
    instance directly (`POST /api/runs/{run_id}/aws-launch`, boto3-backed):
    pick a region and instance type, paste credentials, and the platform
    resolves the AMI via SSM, launches, and tracks the runner. Credentials
    are used for that one call and never persisted. Prefer manual? The
    modal also generates a complete `aws ec2 run-instances` command plus
    an `ms_bootstrap.sh` (deps install, runner executes, instance halts).
    Either way the instance runs in **your** AWS account with **your**
    credentials; the platform never stores them.
  - **Runner protocol** (token-scoped, no user JWT):
    `GET /api/runner/{token}/manifest`, `GET /api/runner/{token}/model`,
    `POST /api/runner/{token}/checkin` (live progress in the Jobs view),
    `POST /api/runner/{token}/result` (refuses a run without artifacts),
    `POST /api/runner/{token}/fail`.
  - **Pickle portability**: the generated script installs class shims so
    full-module pickles saved against the platform's own modules (e.g.
    seeded demo architectures) reconstruct on foreign machines; models
    with exotic custom forward logic remain loadable only where their
    defining module exists — a property of `torch.save`, stated honestly.
- Runs and jobs carry `execution_mode` ("platform" / "own_infra"); the
  Jobs view shows "waiting for your runner" with a live progress bar fed
  by runner check-ins, a runner-instructions button, and cancellation of
  not-yet-started remote runs; the Runs tab badges runs executed off-server.
- e2e: 18 new checks simulate the runner lifecycle and AWS-launch
  validation against the live server (129 total).

### Integrations

- **Personal API keys**: create, list and revoke keys (`msk_…`) in Settings
  for scripts, CI and the API playground — no browser session needed. Only
  the SHA-256 is stored, the secret is shown once, revocation is instant,
  and last-used timestamps are tracked. Ten active keys per account.
- **Webhooks**: set a per-account URL and receive a POST on every run
  completion (platform or own-infrastructure) with the model, plan,
  size saved, latency gain and output agreement. A "Send test ping"
  button reports delivery honestly. Delivery is best-effort and never
  blocks the request path.
- **Project report export**: `GET /api/projects/{id}/report` renders one
  markdown file covering every model in the project: per-model best
  measured result, cumulative savings, and the full run log.
- **Progress chart**: the Runs tab plots size-saved-per-run across the
  model's history once two or more runs exist — improvement becomes a
  line, not a memory exercise.
- **Print / PDF**: the full report tab renders with print styles
  (sidebar, chrome and backgrounds stripped) behind a dedicated button.
- **Hardening**: every response now carries X-Content-Type-Options,
  X-Frame-Options: DENY and Referrer-Policy; versioned /assets files are
  served `Cache-Control: immutable` (one week).

### Account control & visibility

- **Full account export**: `GET /api/auth/me/export` — one JSON file with
  profile, projects, models, every run (benchmarks, steps, repro metadata),
  API-key metadata and the recent audit trail. Your data, portable on
  demand, from the Settings page.
- **Log out everywhere**: `POST /api/auth/logout-all` moves the account's
  token watermark forward; every previously issued session dies instantly
  (tokens mint sub-second `iat`, so revocation is exact and logins made
  after the watermark stay valid).
- **Rate-limit visibility**: every response carries `X-RateLimit-Remaining`.
- **Search filters**: status + framework facets on the search page, fed by
  a one-time model cache (keystrokes filter locally instead of refetching).
- **Cumulative impact chart**: the dashboard plots total % of model size
  removed, run by run, from a dedicated `/api/dashboard/impact` endpoint.
- **More keyboard**: `g j` jobs, `g f` search, `g h` achievements join the
  existing `g d/p/a/s` navigation (press `?` for the full map).

### Security hardening

- **Password reset/change revokes all outstanding sessions** via a
  `tokens_valid_after` watermark on the user row (`security.py`
  `decode_token`): a stolen token dies the moment the password changes.
  Password change returns a fresh token so the current session survives.
- **Rate limiting** (`middleware.py`): sliding-window per client. General
  API: 300 req/min. Auth endpoints: 20 **failed** attempts/min (successes
  are never throttled) with `429 + Retry-After`. General API: 600 req/min.
- **Access logging** (`middleware.py`): one structured line per request
  (method, path, status, duration, client) at INFO level.
- **Cascading deletes**: deleting a project removes its models, encrypted
  uploads, runs, artifacts, and jobs; deleting a model or run likewise
  cleans up everything it owns.
- **Input validation**: server-side length limits on project names (120),
  descriptions (500), model names (120 on both create and update paths);
  upload extensions restricted to `.pt/.pth/.onnx` with a hard size cap.
  Verified against hostile inputs: markup payloads in names render escaped
  on every surface, cross-user project reads/writes 403, disguised
  executables fail analysis honestly instead of being marked successful.
- **Frontend escape discipline**: every user-supplied string passes
  through an `esc()` helper before reaching `innerHTML`; toasts and
  confirm dialogs escape their bodies; a rejected view load surfaces a
  toast instead of a blank page.

## Quick start

```bash
cd modelsmith
./run.sh                 # creates .venv (python3.11) + installs deps on first run
# open http://127.0.0.1:8100
```

Or with Docker:

```bash
docker compose up --build
# open http://127.0.0.1:8100  (data persisted in the ms-data volume)
```

Demo accounts (seeded automatically on first run):

| Role   | Email                  | Password    |
|--------|------------------------|-------------|
| admin  | admin@modelsmith.io    | admin12345  |
| member | demo@modelsmith.io     | demo12345   |

A demo project with three models (MNIST CNN, CIFAR-10 CNN, ResNet-18) is
seeded and analyzed automatically so every feature is explorable immediately.

## The workflow

1. **Upload**: validated (extension whitelist, size cap), SHA-256
   fingerprinted, stored **encrypted at rest** (Fernet/AES).
2. **Analyze** *(async job)*: layers, parameter counts, FLOPs estimate,
   tensor shapes, memory estimates; PyTorch and ONNX adapters.
3. **Profile** *(async job)*: measured CPU latency (mean + p95),
   throughput, bottleneck/hotspot detection with plain-language notes.
4. **Plan**: knowledge-base driven candidate strategies, filtered by
   compatibility rules (framework × target hardware × precision), ranked
   against your objective.
5. **Predict**: size / latency / memory / accuracy-retention trade-offs
   per plan, before anything expensive runs.
6. **Compare**: plans side-by-side in the UI with reasons for every
   recommendation (and reasons for every rejection).
7. **Execute** *(async job)*: real pipeline: magnitude pruning → ONNX
   export (opset 13, checker-validated) → INT8 dynamic quantization / FP16.
8. **Benchmark**: measured original-vs-optimized size and latency, plus an
   output-agreement behavioral check on seeded inputs (dataset-free
   accuracy proxy: labeled as such, never presented as true accuracy).
9. **Export**: encrypted artifacts (`optimized.pt` / `optimized.onnx`),
   SHA-256 manifests, reproducibility metadata, markdown report download.

## Architecture

```
frontend (vanilla JS SPA)
    │  fetch + JWT
    ▼
FastAPI (backend/app/main.py)
    ├─ middleware.py      rate limiting + structured access logging
    ├─ auth.py / projects.py / models_router.py / admin.py   API routers
    ├─ jobs.py            persistent thread-pool job runner (analyze / execute)
    ├─ analysis.py        PyTorch + ONNX adapters, FLOPs, benchmarks, bottlenecks
    ├─ planner.py         technique knowledge base, compatibility filter, ranking, prediction
    ├─ executor.py        prune → ONNX export → INT8/FP16 pipelines + benchmarking
    ├─ reports.py         markdown report builder
    └─ security.py        PBKDF2 · HS256 JWT · Fernet at-rest encryption
SQLite (WAL)  backend/data/modelsmith.db
Files         backend/data/uploads · artifacts (encrypted) · tmp (auto-cleaned)
```

## Verification

`tests/e2e_test.py` drives the **live server** through every flow.
auth (incl. reset + revocation), project CRUD + access control, upload,
async analysis, goals re-ranking, plan execution, benchmark assertions,
artifact authorization, report content, notifications, admin actions,
run/project deletion with cascade verification, plus a dedicated
validation and abuse-limits section (oversized names rejected, forged
tokens 401, injection-shaped queries safe).

```bash
./run.sh &            # server on :8100
.venv/bin/python tests/e2e_test.py
# → RESULT: 153 passed, 0 failed
```

## Honest limitations

- **Latency numbers are CPU-local.** FP16 latency on CPU is honestly reported
  as unavailable rather than faked; TensorRT/distillation are guided (manual)
  plans, marked as such.
- **Output agreement ≠ accuracy.** True accuracy needs labeled data uploads;
  the platform measures behavioral agreement on seeded inputs instead and
  labels it clearly.
- **Pruning** zeroes structured filters/weights and reports achieved sparsity;
  deploy-time channel removal converts that to physical gains.
- **Reset tokens** are returned in-response (no email server in this
  deployment) and expire in 30 minutes, single-use.

## Configuration

Environment variables: `MODELSMITH_DATA` (data dir), `MODELSMITH_PORT`,
`MODELSMITH_MAX_UPLOAD_MB`, `MODELSMITH_BENCH_RUNS`, `MODELSMITH_SEED=0` to
skip demo seeding. Interactive API docs at `/docs`.
