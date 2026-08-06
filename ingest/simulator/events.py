"""City events simulator - concerts, markets, football, protests etc. that put
load on the transport network around their venues.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from .base import BaseSimulator, utcnow

EVENT_TEMPLATES = [
    {"name": "Concerto at the Arena", "category": "concert", "impact": 0.9, "radius": 3.5},
    {"name": "Weekend Market", "category": "market", "impact": 0.55, "radius": 1.5},
    {"name": "Stadium Match", "category": "sports", "impact": 1.0, "radius": 4.0},
    {"name": "City Marathon", "category": "sports", "impact": 0.7, "radius": 6.0},
    {"name": "Tech Conference", "category": "conference", "impact": 0.6, "radius": 2.5},
    {"name": "Street Festival", "category": "festival", "impact": 0.8, "radius": 2.0},
    {"name": "Public Demonstration", "category": "protest", "impact": 0.5, "radius": 3.0},
]


class CityEventsSimulator(BaseSimulator):
    name = "events"

    def __init__(self, city, rng=None):
        super().__init__(rng)
        self.city = city
        self.events: dict[str, dict] = {}
        self._spawn_initial()

    def _spawn_initial(self) -> None:
        n = self.rng.randint(4, 7)
        for _ in range(n):
            self._spawn_event()

    def _spawn_event(self) -> str:
        tpl = self.rng.choice(EVENT_TEMPLATES)
        eid = f"EV-{len(self.events)+1:04d}"
        now = datetime.now(timezone.utc)
        start = now + timedelta(minutes=self.rng.randint(5, 240))
        self.events[eid] = {
            "event_id": eid,
            "name": tpl["name"],
            "category": tpl["category"],
            "lat": round(self.city.lat + self.rng.uniform(-0.055, 0.055), 5),
            "lon": round(self.city.lon + self.rng.uniform(-0.075, 0.075), 5),
            "start_time_utc": start.isoformat(timespec="minutes"),
            "end_time_utc": (start + timedelta(hours=self.rng.randint(2, 5))).isoformat(timespec="minutes"),
            "expected_attendance": self.rng.randint(300, 45000),
            "impact": tpl["impact"],
            "impact_radius_km": tpl["radius"],
            "status": "ACTIVE",
        }
        return eid

    def tick(self, sink, dt: float) -> None:
        now = datetime.now(timezone.utc)
        # prune expired events
        for eid in list(self.events):
            if now > datetime.fromisoformat(self.events[eid]["end_time_utc"]):
                self.events[eid]["status"] = "ENDED"
                sink("events", self.events[eid])
                del self.events[eid]

        if self.rng.random() < 0.05 or not self.events:
            self._spawn_event()

        for eid, ev in self.events.items():
            ev["event_ts"] = utcnow()
            sink("events", dict(ev))
        self.state["events"] = {
            eid: {
                "lat": ev["lat"],
                "lon": ev["lon"],
                "impact": ev["impact"],
                "impact_radius_km": ev["impact_radius_km"],
            }
            for eid, ev in self.events.items()
        }
