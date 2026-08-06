from fastapi import APIRouter

from ..live import live_store
from ..warehouse import provider

router = APIRouter(tags=["events"])


@router.get("/events/active")
def active_events():
    """Currently active city events."""
    return [e for e in live_store.events.values() if e.get("status") == "ACTIVE"]


@router.get("/events/impact")
def events_impact():
    """Delay uplift by proximity to an event."""
    return provider.rows(
        """
        SELECT proximity_bucket, observations, avg_delay_seconds,
               p95_delay_seconds, on_time_pct, avg_event_impact
        FROM gold.mart_events_impact
        ORDER BY avg_delay_seconds DESC
        """,
        "events_impact",
    )
