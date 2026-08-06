from fastapi import APIRouter, Query

from ..live import live_store
from ..warehouse import provider

router = APIRouter(prefix="/delays", tags=["delays"])


@router.get("/current")
def current_delays():
    """Current per-vehicle delay snapshot from the live stream."""
    positions = sorted(live_store.latest_positions.values(), key=lambda r: float(r.get("delay_seconds", 0) or 0), reverse=True)
    return {
        "count": len(positions),
        "vehicles": positions[:200],
    }


@router.get("/top-routes")
def top_routes(limit: int = Query(10, ge=1, le=50)):
    """Routes with the worst average delay."""
    return provider.rows(
        """
        SELECT route_id, route_mode, avg_delay_seconds, p95_delay_seconds,
               on_time_pct, severe_pct, stops_observed
        FROM gold.mart_route_reliability
        ORDER BY avg_delay_seconds DESC
        LIMIT %s
        """,
        "top_routes",
        (limit,),
    )


@router.get("/trends")
def delay_trends(hours: int = Query(24, ge=1, le=168)):
    """Hourly network delay trend."""
    return provider.rows(
        """
        SELECT service_date, hour_of_day, observations, avg_delay_seconds,
               on_time_pct, severe_pct
        FROM gold.mart_delay_trends
        ORDER BY service_date DESC, hour_of_day DESC
        LIMIT %s
        """,
        "delay_trends",
        (hours,),
    )
