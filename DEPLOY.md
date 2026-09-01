# Deploying ModelSmith

ModelSmith is a **stateful long-running service** (PyTorch CPU inference, a
SQLite WAL database, a thread-pool job runner, encrypted files on disk), so
serverless platforms (Vercel functions, Netlify functions) cannot host the
backend: they cap function size (250 MB) and duration, have no persistent
disk, and cannot run worker threads.

The supported deployments are container hosts: **Fly.io, Railway, Render,
Hugging Face Spaces, or any VPS**. The repo already ships everything a
container host needs:

- `Dockerfile` — python:3.11-slim, CPU-only torch, healthcheck at `/api/health`
- `docker-compose.yml` — single service + persistent `ms-data` volume
- `.dockerignore`

## One-command local (reference)

```bash
./run.sh                     # http://127.0.0.1:8100
```

## Docker (any machine)

```bash
docker compose up --build    # http://localhost:8100
```

## Hugging Face Spaces (free, recommended for demos)

1. `pip install -U huggingface_hub && huggingface-cli login`
2. Create a Space, SDK = **Docker**, then push:

```bash
git init && git add -A
git commit -m "ModelSmith"
git remote add space https://huggingface.co/spaces/<you>/modelsmith
git push space main
```

HF builds the Dockerfile automatically. The app runs on port 8100 (already
declared via `EXPOSE`). Data persists in the container across restarts within
the Space's lifetime.

## Railway / Render (one-click from GitHub)

Push the repo to GitHub, then:

- **Render**: New → Web Service → Docker runtime, health check `/api/health`,
  add a persistent disk mounted at `/data`, set `MODELSMITH_DATA=/data`.
- **Railway**: New Project → Deploy from repo (Dockerfile detected
  automatically), add a Volume bound to `/data`.

## Fly.io

```bash
fly launch --no-deploy           # detects the Dockerfile
fly volumes create ms_data --size 3
fly secrets set MODELSMITH_DATA=/data
fly deploy
```

## Environment variables

| Variable                | Default | Purpose                          |
|-------------------------|---------|----------------------------------|
| `MODELSMITH_DATA`       | `backend/data` | DB, uploads, secrets directory |
| `MODELSMITH_PORT`       | 8100    | Listen port                      |
| `MODELSMITH_MAX_UPLOAD_MB` | 500  | Upload size cap                  |
| `MODELSMITH_BENCH_RUNS` | 30      | Benchmark iterations             |
| `MODELSMITH_SEED=0`     | 1       | Disable demo seeding              |

Health endpoint for uptime probes: `GET /api/health`.
Prometheus metrics: `GET /api/metrics`.

## Permanent demo URL (read-only)

**https://modelsmith-alpha.vercel.app**

The marketing site plus a snapshot of a real workspace: three analyzed
models, ranked plans, executed runs, benchmarks. Hosted on Vercel so the
link never expires. The interactive pipeline (upload, execute) requires
the compute-heavy backend, which runs from this repo:

```bash
./run.sh          # full interactive deployment on :8100
./share-url.sh    # temporary public URL for the full deployment
```

The snapshot is regenerated with `deploy-demo` (captured from the live
server, committed as `api-snapshot.json`).
