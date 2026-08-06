from fastapi import APIRouter

from ..live import live_store
from ..warehouse import provider

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/current")
def weather_current():
    """Latest weather observation per zone."""
    zones = sorted(live_store.weather_latest.values(), key=lambda r: r.get("event_ts", ""), reverse=True)
    # city-wide headline = first zone
    if zones:
        headline = zones[0]
        return {"city": headline, "zones": zones}
    return {"city": None, "zones": []}


@router.get("/impact")
def weather_impact():
    """How weather conditions affect delays."""
    return provider.rows(
        """
        SELECT condition, precip_bucket, temp_bucket, observations,
               avg_delay_seconds, p95_delay_seconds, on_time_pct, severe_pct
        FROM gold.mart_weather_impact
        ORDER BY avg_delay_seconds DESC
        """,
        "weather_impact",
    )
