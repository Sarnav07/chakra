"""CHAKRA FastAPI application. Run: python -m uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DATA_DIR, DEMO_CACHE_DIR, MODEL_DIR, UPLOAD_DIR, cors_origins
from app.db import init_db
from app.routers import (classify, core, dashboard, data, mess, pickups, reports, routes,
                         scale, twin)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for folder in (DATA_DIR, DEMO_CACHE_DIR, UPLOAD_DIR, MODEL_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    init_db(reset=False)
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
