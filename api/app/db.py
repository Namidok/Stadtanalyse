"""Warehouse access layer.

Two backends:
  * PostgresWarehouse - the Gold-layer serving database (dbt marts).
  * MemoryWarehouse   - in-memory analytics computed from the live Kafka
                        stream, used as a graceful fallback when Postgres
                        (and therefore dbt) is not yet available.

The API uses the Postgres warehouse by default and transparently falls back
to the memory warehouse so the demo never has an empty dashboard.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from .config import pg_url, settings

log = logging.getLogger("citypulse.db")


class DBUnavailable(Exception):
    pass


class PostgresWarehouse:
    """Read-only access to the dbt Gold-layer marts."""

    def __init__(self):
        self._available: Optional[bool] = None

    def ping(self) -> bool:
        try:
            with psycopg2.connect(pg_url(), connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Postgres unavailable (%s)", e)
            return False

    def query(self, sql: str, params: Optional[tuple] = None) -> list[dict]:
        try:
            with psycopg2.connect(pg_url(), connect_timeout=3) as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql, params)
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:  # noqa: BLE001
            raise DBUnavailable(str(e)) from e


class MemoryWarehouse:
    """Fallback analytics computed from the live in-memory stream window."""

    def __init__(self, live):
        self.live = live

    @staticmethod
    def _f(row: Any, default: float = 0.0) -> float:
        try:
            return float(row)
        except (TypeError, ValueError):
            return default

    def _recent(self, n: int = 1500):
        return list(self.live.trip_window)[-n:]

    def current_delays(self) -> list[dict]:
        out = []
        for r in self.live.latest_positions.values():
            out.append({
                "vehicle_id": r.get("vehicle_id"),
                "route_id": r.get("route_id"),
                "route_mode": r.get("route_mode"),
                "lat": r.get("lat"),
                "lon": r.get("lon"),
                "speed_kmh": r.get("speed_kmh"),
                "delay_seconds": r.get("delay_seconds"),
                "congestion_level": r.get("congestion_level"),
                "event_ts": r.get("event_ts"),
            })
        return out

    def top_routes(self, limit: int = 10) -> list[dict]:
        agg: dict[str, list[float]] = defaultdict(list)
        for r in self._recent():
            agg[r.get("route_id")].append(self._f(r.get("delay_seconds")))
        rows = []
        for route, delays in agg.items():
            delays.sort()
            rows.append({
                "route_id": route,
                "avg_delay_seconds": round(sum(delays) / len(delays), 2),
                "p95_delay_seconds": round(delays[int(0.95 * (len(delays) - 1))], 2),
                "observations": len(delays),
                "on_time_pct": round(100 * sum(1 for d in delays if d <= 120) / len(delays), 2),
            })
        return sorted(rows, key=lambda r: r["avg_delay_seconds"], reverse=True)[:limit]

    def delay_trends(self, hours: int = 24) -> list[dict]:
        buckets: dict[str, list[float]] = defaultdict(list)
        for r in self._recent():
            ts = r.get("event_ts")
            if not ts:
                continue
            try:
                hour = datetime.fromisoformat(str(ts)).replace(tzinfo=None).strftime("%Y-%m-%dT%H:00:00")
            except ValueError:
                continue
            buckets[hour].append(self._f(r.get("delay_seconds")))
        rows = []
        for hour, delays in sorted(buckets.items()):
            rows.append({
                "bucket": hour,
                "avg_delay_seconds": round(sum(delays) / len(delays), 2),
                "observations": len(delays),
                "on_time_pct": round(100 * sum(1 for d in delays if d <= 120) / len(delays), 2),
            })
        return rows[-hours:]

    def hotspots(self, limit: int = 20) -> list[dict]:
        agg: dict[str, dict] = defaultdict(lambda: {"lat": 0.0, "lon": 0.0, "delays": [], "speeds": [], "congestion": []})
        for r in self.live.latest_positions.values():
            try:
                lat = round(float(r.get("lat")), 2)
                lon = round(float(r.get("lon")), 2)
            except (TypeError, ValueError):
                continue
            key = f"{lat}|{lon}"
            cell = agg[key]
            cell["lat"], cell["lon"] = lat, lon
            cell["delays"].append(self._f(r.get("delay_seconds")))
            cell["speeds"].append(self._f(r.get("speed_kmh")))
            cell["congestion"].append(self._f(r.get("congestion_level")))
        rows = []
        for key, cell in agg.items():
            delays = cell["delays"]
            rows.append({
                "grid_cell": key,
                "lat": cell["lat"],
                "lon": cell["lon"],
                "avg_delay_seconds": round(sum(delays) / len(delays), 2),
                "avg_speed_kmh": round(sum(cell["speeds"]) / len(cell["speeds"]), 2),
                "avg_congestion": round(sum(cell["congestion"]) / len(cell["congestion"]), 3),
                "vehicles": len(delays),
            })
        return sorted(rows, key=lambda r: r["avg_delay_seconds"], reverse=True)[:limit]

    def weather_impact(self) -> list[dict]:
        def condition_for(lat: float, lon: float) -> str:
            best, best_d = "unknown", math.inf
            for z in self.live.weather_latest.values():
                try:
                    dlat = lat - float(z.get("lat"))
                    dlon = lon - float(z.get("lon"))
                    d = dlat * dlat + dlon * dlon
                except (TypeError, ValueError):
                    continue
                if d < best_d:
                    best_d, best = d, z.get("condition") or "unknown"
            return best

        agg: dict[str, list[float]] = defaultdict(list)
        for r in self._recent():
            cond = r.get("condition")
            if not cond:
                lat, lon = r.get("lat"), r.get("lon")
                if lat is None:
                    pos = self.live.latest_positions.get(r.get("vehicle_id"))
                    if pos:
                        lat, lon = pos.get("lat"), pos.get("lon")
                if lat is not None:
                    cond = condition_for(float(lat), float(lon))
                else:
                    cond = "unknown"
            agg[cond].append(self._f(r.get("delay_seconds")))
        rows = []
        for cond, delays in agg.items():
            delays.sort()
            rows.append({
                "condition": cond,
                "observations": len(delays),
                "avg_delay_seconds": round(sum(delays) / len(delays), 2),
                "on_time_pct": round(100 * sum(1 for d in delays if d <= 120) / len(delays), 2),
            })
        return rows

    def route_reliability(self, limit: int = 25) -> list[dict]:
        agg: dict[str, dict] = defaultdict(lambda: {"delays": [], "mode": "unknown"})
        for r in self._recent():
            agg[r.get("route_id")]["delays"].append(self._f(r.get("delay_seconds")))
        for vid, p in self.live.latest_positions.items():
            if p.get("route_id") in agg:
                agg[p.get("route_id")]["mode"] = p.get("route_mode")
        rows = []
        for route, cell in agg.items():
            delays = sorted(cell["delays"])
            rows.append({
                "route_id": route,
                "route_mode": cell["mode"],
                "avg_delay_seconds": round(sum(delays) / len(delays), 2),
                "p95_delay_seconds": round(delays[int(0.95 * (len(delays) - 1))], 2),
                "on_time_pct": round(100 * sum(1 for d in delays if d <= 120) / len(delays), 2),
                "severe_pct": round(100 * sum(1 for d in delays if d > 600) / len(delays), 2),
                "stops_observed": len(delays),
            })
        return sorted(rows, key=lambda r: r["avg_delay_seconds"], reverse=True)[:limit]

    def events_impact(self) -> list[dict]:
        events = [e for e in self.live.events.values() if e.get("status") == "ACTIVE"]
        if not events:
            return []
        trips = self._recent()
        buckets: dict[str, list[float]] = defaultdict(list)
        for ev in events:
            try:
                ev_lat, ev_lon = float(ev.get("lat")), float(ev.get("lon"))
            except (TypeError, ValueError):
                continue
            for r in trips:
                pos = self.live.latest_positions.get(r.get("vehicle_id")) or r
                try:
                    dlat = (float(pos.get("lat")) - ev_lat) * 111.0
                    dlon = (float(pos.get("lon")) - ev_lon) * 111.0 * 0.7
                    dist_km = (dlat * dlat + dlon * dlon) ** 0.5
                except (TypeError, ValueError):
                    continue
                bucket = "within_2km" if dist_km <= 2.0 else ("within_5km" if dist_km <= 5.0 else "far")
                buckets[bucket].append(self._f(r.get("delay_seconds")))
        rows = []
        for bucket, delays in sorted(buckets.items()):
            delays.sort()
            rows.append({
                "proximity_bucket": bucket,
                "observations": len(delays),
                "avg_delay_seconds": round(sum(delays) / len(delays), 2),
                "p95_delay_seconds": round(delays[int(0.95 * (len(delays) - 1))], 2),
                "on_time_pct": round(100 * sum(1 for d in delays if d <= 120) / len(delays), 2),
                "avg_event_impact": 0.0,
            })
        return rows

    def kpis(self) -> dict:
        positions = list(self.live.latest_positions.values())
        delays = [self._f(r.get("delay_seconds")) for r in positions]
        speeds = [self._f(r.get("speed_kmh")) for r in positions]
        active = [e for e in self.live.events.values() if e.get("status") == "ACTIVE"]
        return {
            "vehicles_tracked": len(positions),
            "avg_delay_seconds": round(sum(delays) / len(delays), 2) if delays else 0,
            "on_time_pct": round(100 * sum(1 for d in delays if d <= 120) / len(delays), 2) if delays else 100,
            "severe_delays": sum(1 for d in delays if d > 600),
            "avg_speed_kmh": round(sum(speeds) / len(speeds), 2) if speeds else 0,
            "active_events": len(active),
            "data_source": "live-stream",
        }
