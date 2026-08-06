"""GTFS-style public transport simulator.

Emits two streams:
  * vehicle positions (like GTFS-RT vehicle positions)
  * trip delay updates (like GTFS-RT trip updates)

Delays are driven by a stochastic random walk that reacts to time-of-day
(rush hours), weather state and nearby city events, so the resulting data
contains realistic correlations the analytics/ML layers can rediscover.
"""
from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .base import BaseSimulator, utcnow

EARTH_R = 6371.0


def haversine(a_lat, a_lon, b_lat, b_lon) -> float:
    """Great-circle distance in km between two lat/lon points."""
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


@dataclass
class Stop:
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    zone: str


@dataclass
class Route:
    route_id: str
    mode: str
    stops: list[Stop]
    base_speed: float  # km/h free-flow

    def length_km(self) -> float:
        return sum(haversine(self.stops[i].lat, self.stops[i].lon, self.stops[i + 1].lat, self.stops[i + 1].lon)
                   for i in range(len(self.stops) - 1))


@dataclass
class Vehicle:
    vehicle_id: str
    route: Route
    trip_id: str
    direction: int
    stop_index: int  # current segment [stop_index, stop_index+1)
    progress: float  # 0..1 along segment
    speed: float
    delay_seconds: float
    occupied_stops: int = 0

    def position(self):
        a, b = self.route.stops[self.stop_index], self.route.stops[self.stop_index + 1]
        lat = a.lat + (b.lat - a.lat) * self.progress
        lon = a.lon + (b.lon - a.lon) * self.progress
        heading = math.degrees(math.atan2(b.lon - a.lon, b.lat - a.lat)) % 360
        return lat, lon, heading


class TransportSimulator(BaseSimulator):
    name = "transport"

    FREE_FLOW = {"rail": 60.0, "tram": 35.0, "bus": 28.0}

    def __init__(self, gtfs_dir: Path, n_vehicles: int, rush_amplitude: float = 1.6, rng=None):
        super().__init__(rng)
        self.routes, self.trips = self._load_gtfs(gtfs_dir)
        self.rush_amplitude = rush_amplitude
        self.vehicles = self._spawn_vehicles(n_vehicles)
        # shared state hooks set by the run orchestrator
        self.weather_state = {"condition": "clear", "precip": 0.0, "wind": 8.0, "temp": 15.0}
        self.event_state: dict = {}
        self._last_trip_emissions: dict[str, int] = {}

    # ------------------------------------------------------------------ setup
    @staticmethod
    def _load_gtfs(gtfs_dir: Path):
        def read_csv(name):
            with (gtfs_dir / name).open() as f:
                return list(csv.DictReader(f))

        stop_rows = read_csv("stops.txt")
        route_rows = read_csv("routes.txt")
        trips_rows = read_csv("trips.txt")
        stop_times = read_csv("stop_times.txt")

        stops = {
            r["stop_id"]: Stop(r["stop_id"], r["stop_name"], float(r["stop_lat"]), float(r["stop_lon"]), r["stop_zone"])
            for r in stop_rows
        }
        routes: dict[str, Route] = {}
        for r in route_rows:
            ordered = sorted([st for st in stop_times if st["trip_id"] == trips_rows[0]["trip_id"]], key=lambda x: int(x["stop_sequence"]))
            # build stop order from first trip on the route
            rt = next((t for t in trips_rows if t["route_id"] == r["route_id"] and t["direction_id"] == "0"), trips_rows[0])
            seq = sorted([st for st in stop_times if st["trip_id"] == rt["trip_id"]], key=lambda x: int(x["stop_sequence"]))
            stop_list = [stops[st["stop_id"]] for st in seq]
            routes[r["route_id"]] = Route(
                route_id=r["route_id"],
                mode=r["route_mode"],
                stops=stop_list,
                base_speed=TransportSimulator.FREE_FLOW[r["route_mode"]],
            )
        return routes, trips_rows

    def _spawn_vehicles(self, n: int) -> list[Vehicle]:
        vehicles: list[Vehicle] = []
        route_ids = list(self.routes)
        for i in range(n):
            route = self.routes[route_ids[i % len(route_ids)]]
            trip = next((t for t in self.trips if t["route_id"] == route.route_id), None)
            direction = int(trip["direction_id"]) if trip else 0
            vehicles.append(
                Vehicle(
                    vehicle_id=f"CP-{i+1:04d}",
                    route=route,
                    trip_id=f"{route.route_id}-{direction}-{i // len(route_ids) + 1}",
                    direction=direction,
                    stop_index=self.rng.randint(0, len(route.stops) - 2),
                    progress=self.rng.random(),
                    speed=route.base_speed * self.rng.uniform(0.55, 1.05),
                    delay_seconds=self.rng.normalvariate(0, 90),
                )
            )
        return vehicles

    # ------------------------------------------------------------------ model
    def _weather_delay_factor(self) -> float:
        cond = self.state.get("weather", {}).get("condition", "clear")
        table = {"rain": 1.8, "snow": 2.6, "fog": 1.4, "storm": 3.2, "clouds": 1.1, "clear": 1.0, "sleet": 2.2}
        return table.get(cond, 1.0)

    def _event_delay_factor(self, lat: float, lon: float) -> float:
        peak = 0.0
        for ev in self.state.get("events", {}).values():
            d = haversine(lat, lon, ev["lat"], ev["lon"])
            if d < ev.get("impact_radius_km", 3.0):
                proximity = 1.0 - d / max(ev.get("impact_radius_km", 3.0), 0.1)
                peak = max(peak, proximity * ev.get("impact", 0.0))
        return 1.0 + peak

    def _rush_hour_factor(self) -> float:
        hour = datetime.now(timezone.utc).hour + 1  # mock local offset
        morning = math.exp(-((hour - 8) ** 2) / 4.0)
        evening = math.exp(-((hour - 18) ** 2) / 4.0)
        return 1.0 + self.rush_amplitude * 0.35 * (morning + evening)

    def _next_delay(self, v: Vehicle) -> float:
        base = self._weather_delay_factor() * self._event_delay_factor(
            self.route_lat(v), self.route_lon(v)
        )
        target = 40.0 * (base - 1.0) + 25.0 * (self._rush_hour_factor() - 1.0)
        # mean-reverting random walk
        pull = 0.06 * (target - v.delay_seconds)
        noise = self.rng.gauss(0, 22)
        return max(-45.0, min(1500.0, v.delay_seconds + pull + noise))

    def route_lat(self, v: Vehicle) -> float:
        lat, _, _ = v.position()
        return lat

    def route_lon(self, v: Vehicle) -> float:
        _, lon, _ = v.position()
        return lon

    def _speed_from_delay(self, v: Vehicle) -> float:
        congestion = 1.0 / (1.0 + max(0.0, v.delay_seconds) / 180.0)
        weather = {  # fraction of free-flow speed by condition
            "rain": 0.82, "snow": 0.62, "fog": 0.78, "storm": 0.55,
            "clouds": 0.94, "clear": 1.0, "sleet": 0.68,
        }.get(self.state.get("weather", {}).get("condition", "clear"), 0.9)
        base = v.route.base_speed * congestion * weather
        return max(3.0, base * self.rng.uniform(0.9, 1.1))

    # ------------------------------------------------------------------ tick
    def tick(self, sink, dt: float) -> None:
        now = utcnow()
        for v in self.vehicles:
            v.delay_seconds = self._next_delay(v)
            v.speed = self._speed_from_delay(v)

            seg_len = haversine(
                v.route.stops[v.stop_index].lat, v.route.stops[v.stop_index].lon,
                v.route.stops[v.stop_index + 1].lat, v.route.stops[v.stop_index + 1].lon,
            )
            advance = (v.speed / 3600.0) * dt / max(seg_len, 0.05)
            v.progress += advance

            # emit position record
            lat, lon, heading = v.position()
            sink(
                "transport",
                {
                    "vehicle_id": v.vehicle_id,
                    "route_id": v.route.route_id,
                    "route_mode": v.route.mode,
                    "trip_id": v.trip_id,
                    "direction_id": v.direction,
                    "stop_id": v.route.stops[v.stop_index].stop_id,
                    "next_stop_id": v.route.stops[min(v.stop_index + 1, len(v.route.stops) - 1)].stop_id,
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "speed_kmh": round(v.speed, 2),
                    "heading_deg": round(heading, 1),
                    "delay_seconds": round(v.delay_seconds, 1),
                    "congestion_level": round(1.0 / (1.0 + max(0.0, v.delay_seconds) / 180.0), 3),
                    "event_ts": now,
                },
            )

            if v.progress >= 1.0:
                # passed the stop -> emit trip update + advance segment
                passed = v.route.stops[v.stop_index]
                delay = round(v.delay_seconds, 1)
                scheduled = datetime.now(timezone.utc).isoformat(timespec="seconds")
                sink(
                    "trip_updates",
                    {
                        "trip_id": v.trip_id,
                        "route_id": v.route.route_id,
                        "vehicle_id": v.vehicle_id,
                        "stop_id": passed.stop_id,
                        "stop_sequence": v.stop_index,
                        "scheduled_arrival_utc": scheduled,
                        "actual_arrival_utc": (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(timespec="seconds"),
                        "delay_seconds": delay,
                        "status": "EARLY" if delay < -60 else ("ON_TIME" if delay <= 120 else "DELAYED"),
                        "event_ts": now,
                    },
                )
                v.stop_index = (v.stop_index + 1) % (len(v.route.stops) - 1)
                v.progress = 0.0
                # small chance of break-down -> big delay spike for realism
                if self.rng.random() < 0.0015:
                    v.delay_seconds += self.rng.uniform(300, 700)
