from fastapi import APIRouter

from ..config import settings
from ..live import live_store
from ..ml import model as delay_model
from ..warehouse import provider

router = APIRouter(tags=["meta"])


@router.get("/data-source")
def data_source():
    """Where the demo data comes from: 'real' (national gtfs.de GTFS + live
    GTFS-RT delays, positions simulated on the real network) or 'synthetic'."""
    mode = settings()["data_source"]
    return {
        "mode": mode,
        "label": "REAL GTFS + REALTIME DELAYS" if mode == "real" else "SYNTHETIC DATA",
        "detail": ("National GTFS (gtfs.de) network + live GTFS-RT delays "
                   "(realtime.gtfs.de); vehicle positions simulated on the real network."
                   if mode == "real" else
                   "Fully simulated network, positions and delays (no real feeds)."),
    }


@router.get("/health")
def health():
    delay_model.ensure_loaded()
    return {
        "status": "ok",
        "warehouse_mode": provider.mode,
        "kafka_connected": live_store.counters["transport"] > 0,
        "vehicles_tracked": len(live_store.latest_positions),
        "ml_loaded": delay_model.loaded,
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
