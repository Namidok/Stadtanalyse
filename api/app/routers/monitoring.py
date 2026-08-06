from fastapi import APIRouter, Query

from ..live import live_store
from ..warehouse import provider

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/pipeline")
def pipeline_status():
    """End-to-end pipeline health: ingestion rates, warehouse mode, quality gate."""
    snap = live_store.snapshot()
    counters = snap["counters"]
    total = sum(counters.values())
    return {
        "ingestion": {
            "total_records": total,
            "rates": {k: round(v / max(snap["uptime_seconds"], 1), 2) for k, v in counters.items()},
            "counters": counters,
            "uptime_seconds": snap["uptime_seconds"],
        },
        "warehouse": {"mode": provider.mode},
        "quality": {"last_run": None},
        "streaming": {"vehicles_in_snapshot": len(snap["positions"])},
    }


@router.get("/quality")
def quality_status():
    """Most recent Great Expectations validation outcome (from the quality gate)."""
    try:
        return provider.query(
            """
            SELECT table_name, run_at_utc, success, expectations_passed, expectations_total
            FROM quality.quality_runs
            ORDER BY run_at_utc DESC
            LIMIT 20
            """
        )
    except Exception:  # noqa: BLE001
        return {"note": "quality_runs table not available yet (run the quality job)"}
