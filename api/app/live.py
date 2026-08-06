"""Live stream store: a background Kafka consumer that keeps a rolling window
of the latest transport / weather / event state in memory, powers the SSE
endpoint and feeds the memory warehouse fallback."""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from pathlib import Path

from kafka import KafkaConsumer

from .config import settings

log = logging.getLogger("citypulse.live")

WINDOW_SIZE = 5000


class LiveStore:
    def __init__(self):
        self.latest_positions: dict[str, dict] = {}
        self.trip_window: deque = deque(maxlen=WINDOW_SIZE)
        self.weather_latest: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self.counters = {"transport": 0, "trip_updates": 0, "weather": 0, "events": 0}
        self.started_at = time.time()
        self._seeded = False
        self.on_ingest = None  # optional callback(stream_label) for metrics
        self._lock = threading.Lock()
        self._stop = threading.Event()

    # ------------------------------------------------------------------ kafka
    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True, name="kafka-live")
        t.start()

    def _run(self) -> None:
        s = settings()
        retries = 0
        while not self._stop.is_set():
            try:
                consumer = KafkaConsumer(
                    s["topic_transport"], s["topic_trip_updates"], s["topic_weather"], s["topic_events"],
                    bootstrap_servers=s["kafka_bootstrap"],
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    consumer_timeout_ms=500,
                )
                log.info("LiveStore connected to Kafka")
                for msg in consumer:
                    if self._stop.is_set():
                        break
                    self._ingest(msg.topic, msg.value)
            except Exception as e:  # noqa: BLE001
                retries += 1
                if retries == 3:
                    self._seed_local_demo()
                log.warning("Kafka consumer retry %s: %s", retries, e)
                time.sleep(min(30, 2 * retries))

    def _seed_local_demo(self) -> None:
        """When no Kafka broker is reachable, load the offline demo snapshot
        (data/local/citypulse.duckdb) so the dashboard works end-to-end."""
        if self._seeded:
            return
        try:
            import duckdb

            db = Path(__file__).resolve().parents[2] / "data/local/citypulse.duckdb"
            if not db.exists():
                log.info("No local demo snapshot found at %s", db)
                return
            con = duckdb.connect(str(db), read_only=True)
            self._seeded = True
            for stream, topic in (("transport", settings()["topic_transport"]),
                                  ("trip_updates", settings()["topic_trip_updates"]),
                                  ("weather", settings()["topic_weather"]),
                                  ("events", settings()["topic_events"])):
                rows = con.execute(f"SELECT record FROM {stream}").fetchall()
                for (record,) in rows:
                    self._ingest(topic, json.loads(record))
            con.close()
            log.info("Seeded %s records from local demo snapshot", self.counters)
        except Exception as e:  # noqa: BLE001
            log.warning("Could not seed local demo snapshot: %s", e)

    def _ingest(self, topic: str, record: dict) -> None:
        with self._lock:
            if topic == settings()["topic_transport"]:
                vid = record.get("vehicle_id")
                if vid:
                    self.latest_positions[vid] = record
                self.counters["transport"] += 1
                self._notify("transport")
            elif topic == settings()["topic_trip_updates"]:
                self.trip_window.append(record)
                self.counters["trip_updates"] += 1
                self._notify("trip_updates")
            elif topic == settings()["topic_weather"]:
                zid = record.get("zone_id")
                if zid:
                    self.weather_latest[zid] = record
                self.counters["weather"] += 1
                self._notify("weather")
            elif topic == settings()["topic_events"]:
                eid = record.get("event_id")
                if eid:
                    self.events[eid] = record
                self.counters["events"] += 1
                self._notify("events")

    def _notify(self, stream: str) -> None:
        if self.on_ingest:
            try:
                self.on_ingest(stream)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ reads
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "positions": list(self.latest_positions.values()),
                "weather": list(self.weather_latest.values()),
                "events": [e for e in self.events.values() if e.get("status") == "ACTIVE"],
                "counters": dict(self.counters),
                "uptime_seconds": round(time.time() - self.started_at, 1),
            }

    def stop(self) -> None:
        self._stop.set()


live_store = LiveStore()
