"""ModelSmith application assembly.

FastAPI app serving the JSON API and the single-page frontend. Startup
initializes the database, starts the background job runner and seeds demo
data; shutdown drains the runner cleanly.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import admin, auth, config, middleware, models_router, projects
from .database import init_db
from .jobs import JobRunner
from .seed import seed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("modelsmith")

app = FastAPI(title="ModelSmith", version=config.APP_VERSION,
              description="Intelligent AI Model Optimization & Deployment Platform")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
# static assets ship ~336 KB of JS/CSS; gzip cuts app.js alone from 150 KB to 39 KB
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_middleware(middleware.RateLimitMiddleware)
app.add_middleware(middleware.AccessLogMiddleware)
app.add_middleware(middleware.RequestIDMiddleware)

runner = JobRunner()
models_router.RUNNER = runner

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(models_router.router)
app.include_router(admin.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR)), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.on_event("startup")
def startup():
    init_db()
    runner.start()
    if config.SEED_DEMO_DATA:
        seed(runner)
    log.info("ModelSmith %s ready", config.APP_VERSION)


@app.on_event("shutdown")
def shutdown():
    runner.stop()
