import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..live import live_store

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/snapshot")
def snapshot():
    """Current snapshot of the live stream state (positions, weather, events)."""
    return live_store.snapshot()


@router.get("/positions/stream")
async def positions_stream():
    """Server-Sent-Events stream of vehicle positions (~1Hz)."""

    async def generator():
        while True:
            snap = live_store.snapshot()
            payload = json.dumps({
                "positions": snap["positions"],
                "counters": snap["counters"],
                "uptime_seconds": snap["uptime_seconds"],
            })
            yield f"data: {payload}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
