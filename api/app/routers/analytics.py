from fastapi import APIRouter, Query

from ..warehouse import provider

router = APIRouter(tags=["analytics"])


@router.get("/hotspots")
def hotspots(limit: int = Query(25, ge=1, le=100)):
    """Congestion hotspots ranked by average delay."""
    return provider.rows(
        """
        SELECT grid_cell, cell_lat AS lat, cell_lon AS lon, avg_delay_seconds, avg_speed_kmh,
               avg_congestion, vehicles, severe_pct, congestion_rank
        FROM gold.mart_congestion_hotspots
        ORDER BY congestion_rank
        LIMIT %s
        """,
        "hotspots",
        (limit,),
    )


@router.get("/routes/reliability")
def route_reliability():
    """Daily route reliability scores."""
    return provider.rows(
        """
        SELECT route_id, route_mode, service_date, trips, stops_observed,
               on_time_pct, reliability_score, avg_delay_seconds, p95_delay_seconds
        FROM gold.mart_route_reliability
        ORDER BY service_date DESC, reliability_score ASC
        """,
        "route_reliability",
    )
