from fastapi import APIRouter

from ..live import live_store
from ..warehouse import provider

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "warehouse_mode": provider.mode,
        "kafka_connected": live_store.counters["transport"] > 0,
        "vehicles_tracked": len(live_store.latest_positions),
        "ml_loaded": None,
    }


@router.get("/kpis")
def kpis():
    """Top-line KPIs for the dashboard header."""
    try:
        rows = provider.query(
            """
            SELECT
              (SELECT COUNT(*) FROM gold.fct_trip_delays) AS observations,
              (SELECT ROUND(AVG(delay_seconds)::numeric,2) FROM gold.fct_trip_delays) AS avg_delay_seconds,
              (SELECT ROUND(100.0*COUNT(*) FILTER (WHERE delay_bucket='on_time')/COUNT(*),2) FROM gold.fct_trip_delays) AS on_time_pct,
              (SELECT COUNT(*) FROM gold.fct_trip_delays WHERE delay_bucket='severe') AS severe_delays
            """
        )
        base = rows[0]
        base.update({
            "vehicles_tracked": len(live_store.latest_positions),
            "active_events": len([e for e in live_store.events.values() if e.get("status") == "ACTIVE"]),
            "data_source": "gold-marts",
        })
        return base
    except Exception:  # noqa: BLE001
        mem = provider.memory.kpis()
        mem["data_source"] = "live-stream"
        return mem
