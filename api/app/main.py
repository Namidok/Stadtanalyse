"""Stadtanalyse API - serving layer for the analytics dashboard and ML model."""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from .config import settings
from .live import live_store
from .warehouse import provider
from .routers import analytics, cities, delays, events, health, live, ml, monitoring, weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="Stadtanalyse API", version="1.0.0", description="Smart Urban Mobility Data Lake & Analytics Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings()["cors_origins"]] if settings()["cors_origins"] != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
HTTP_REQUESTS = Counter("stadtanalyse_http_requests_total", "HTTP requests", ["method", "path"])
HTTP_LATENCY = Histogram("stadtanalyse_http_latency_seconds", "HTTP latency", ["path"])
INGEST_RATE = Counter("stadtanalyse_ingest_records_total", "Ingested records", ["stream"])

for router in (health.router, live.router, delays.router, analytics.router, weather.router, events.router, monitoring.router, ml.router, cities.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
def root_health():
    from .warehouse import provider as _p
    return {"status": "ok", "warehouse_mode": _p.mode}


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse({"detail": "internal error"}, status_code=500)
    HTTP_REQUESTS.labels(request.method, request.url.path).inc()
    HTTP_LATENCY.labels(request.url.path).observe(time.monotonic() - start)
    return response


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
def startup():
    live_store.on_ingest = lambda stream: INGEST_RATE.labels(stream).inc()
    live_store.start()
    provider.set_live(live_store)
    logging.getLogger("stadtanalyse.api").info("Stadtanalyse API started")


@app.on_event("shutdown")
def shutdown():
    live_store.stop()
