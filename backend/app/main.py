"""CHAKRA FastAPI application. Run: python -m uvicorn app.main:app --reload"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DATA_DIR, DEMO_CACHE_DIR, MODEL_DIR, UPLOAD_DIR, cors_origins
from app.db import get_conn, get_meta, init_db
from app.routers import (classify, core, dashboard, data, mess, pickups, reports, routes,
                         scale, twin)


def _seed_if_empty() -> None:
    """Hosted instances (CHAKRA_AUTO_SEED=1) start with an empty disk: seed the
    demo database and one forecast run so every page has data."""
    conn = get_conn()
    try:
        seeded = get_meta(conn, "scenario_date") is not None
    finally:
        conn.close()
    if not seeded:
        from app.seed import run_seed, save_initial_forecasts
        run_seed()
        save_initial_forecasts()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for folder in (DATA_DIR, DEMO_CACHE_DIR, UPLOAD_DIR, MODEL_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    init_db(reset=False)
    if os.environ.get("CHAKRA_AUTO_SEED") == "1":
        _seed_if_empty()
    yield


app = FastAPI(title="CHAKRA API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (core, data, twin, classify, routes, reports, scale, pickups, mess, dashboard):
    app.include_router(module.router, prefix="/api")
