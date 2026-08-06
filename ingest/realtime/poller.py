"""GTFS-RT poller for the national German realtime feed (realtime.gtfs.de).

The free feed (realtime-free.pb) carries TripUpdates + ServiceAlerts for the
whole country, updated every ~10s, with no API key. It contains no vehicle
positions, so we only harvest real delays: for each poll we decode the
protobuf, keep trip updates whose stops intersect the active city, map the
trip to its route via the installed real GTFS network, and publish records in
the exact `raw.transport.trip.updates` shape the Spark/dbt pipeline expects.
"""
from __future__ import annotations

import csv
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from google.transit import gtfs_realtime_pb2 as gtfs

from .config import RealConfig

log = logging.getLogger("stadtanalyse.realtime.poller")

SENTINEL = ".city"


class RealtimePoller:
    def __init__(self, cfg: RealConfig, sink):
        self.cfg = cfg
        self.sink = sink
        self._lock = threading.Lock()
        self._stop_ids: set[str] = set()
        self._trip_to_route: dict[str, str] = {}
        self._sentinel: str | None = None
        self._published = 0
        self._matched = 0
        self._load_maps()

    # ------------------------------------------------------------------ maps
    def _sentinel_value(self) -> str | None:
        p = self.cfg.active_dir / SENTINEL
        try:
            return p.read_text().strip()
        except OSError:
            return None

    def _load_maps(self) -> None:
        sentinel = self._sentinel_value()
        stop_ids: set[str] = set()
        trip_to_route: dict[str, str] = {}

        stops_path = self.cfg.active_dir / "stops.txt"
        if stops_path.exists():
            with stops_path.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    stop_ids.add(row["stop_id"])

        trips_path = self.cfg.active_dir / "trips.txt"
        if trips_path.exists():
            with trips_path.open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    trip_to_route[row["trip_id"]] = row["route_id"]

        with self._lock:
            self._stop_ids = stop_ids
            self._trip_to_route = trip_to_route
            self._sentinel = sentinel
        log.info("Loaded real-network maps for city '%s': %s stops, %s trips",
                 sentinel, len(stop_ids), len(trip_to_route))

    def _needs_reload(self) -> bool:
        with self._lock:
            return self._sentinel_value() != self._sentinel

    # ------------------------------------------------------------------ poll
    def run(self, stop: threading.Event) -> None:
        while not stop.wait(self.cfg.poll_interval_sec):
            try:
                if self._needs_reload():
                    time.sleep(2)  # let an in-progress city install finish
                    self._load_maps()
                with self._lock:
                    have_maps = bool(self._stop_ids)
                if not have_maps:
                    log.warning("No real GTFS installed yet - waiting for extraction")
                    continue
                self._poll_once()
            except requests.RequestException as e:
                log.warning("Realtime fetch failed: %s", e)
            except Exception:  # noqa: BLE001
                log.exception("Realtime poll crashed")

    def _poll_once(self) -> None:
        resp = requests.get(self.cfg.rt_url, timeout=90)
        resp.raise_for_status()
        feed = gtfs.FeedMessage()
        feed.ParseFromString(resp.content)

        with self._lock:
            stop_ids = self._stop_ids
            trip_to_route = dict(self._trip_to_route)

        candidates: list[dict] = []
        matched = 0
        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue
            tu = entity.trip_update
            best = self._best_stop_update(tu, stop_ids)
            if best is None:
                continue
            matched += 1
            delay = best["delay"]
            trip_id = tu.trip.trip_id
            record = {
                "trip_id": trip_id,
                "route_id": trip_to_route.get(trip_id, tu.trip.route_id or ""),
                "vehicle_id": tu.vehicle.id if tu.HasField("vehicle") and tu.vehicle.id else f"rt-{entity.id}",
                "stop_id": best["stop_id"],
                "stop_sequence": best["stop_sequence"],
                "scheduled_arrival_utc": best["scheduled"],
                "actual_arrival_utc": best["actual"],
                "delay_seconds": round(float(delay), 1),
                "status": "EARLY" if delay < -60 else ("ON_TIME" if delay <= 120 else "DELAYED"),
                "event_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            candidates.append(record)

        if len(candidates) > self.cfg.max_records_per_poll:
            candidates.sort(key=lambda r: -abs(r["delay_seconds"]))
            candidates = candidates[: self.cfg.max_records_per_poll]

        for record in candidates:
            self.sink("trip_updates", record)
        self._published += len(candidates)
        self._matched += matched
        log.info("poll: %s entities, %s matching trips in city, published %s "
                 "(total published %s, total matched %s)",
                 len(feed.entity), matched, len(candidates), self._published, self._matched)

    # ------------------------------------------------------------------ util
    @staticmethod
    def _stop_delay(su) -> float | None:
        if su.HasField("arrival") and su.arrival.HasField("delay"):
            return su.arrival.delay
        if su.HasField("departure") and su.departure.HasField("delay"):
            return su.departure.delay
        return None

    def _best_stop_update(self, tu, stop_ids: set[str]) -> dict | None:
        """Pick the stop update with the largest |delay| among city stops."""
        best = None
        best_delay = 0.0
        for su in tu.stop_time_update:
            if su.stop_id not in stop_ids:
                continue
            delay = self._stop_delay(su)
            if delay is None:
                continue
            if best is None or abs(delay) > abs(best_delay):
                best, best_delay = su, delay
        if best is not None:
            return self._timing(best, best_delay)
        if tu.HasField("delay") and tu.stop_time_update:
            for su in tu.stop_time_update:
                if su.stop_id in stop_ids:
                    return self._timing(su, tu.delay)
        return None

    def _timing(self, su, delay: float) -> dict:
        ts: int | None = None
        if su.HasField("arrival") and su.arrival.HasField("time"):
            ts = su.arrival.time
        elif su.HasField("departure") and su.departure.HasField("time"):
            ts = su.departure.time
        if ts:
            actual = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")
            scheduled = datetime.fromtimestamp(ts - delay, tz=timezone.utc).isoformat(timespec="seconds")
        else:
            now = datetime.now(timezone.utc)
            scheduled = now.isoformat(timespec="seconds")
            actual = (now + timedelta(seconds=delay)).isoformat(timespec="seconds")
        return {
            "stop_id": su.stop_id,
            "stop_sequence": int(su.stop_sequence),
            "delay": delay,
            "scheduled": scheduled,
            "actual": actual,
        }
