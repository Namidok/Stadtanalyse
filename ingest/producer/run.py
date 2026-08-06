"""Entry point that runs all simulators and publishes to Kafka (or a local
DuckDB store in --local mode).

Usage:
    python -m ingest.producer.run                 # stream to Kafka forever
    python -m ingest.producer.run --local         # write a short demo window to DuckDB
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import threading
import time
from datetime import datetime, timezone

from ..simulator import load_config
from ..simulator.events import CityEventsSimulator
from ..simulator.transport import TransportSimulator
from ..simulator.weather import WeatherSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("citypulse.run")


class DuckDbSink:
    """Offline sink writing raw records into DuckDB tables (one per stream)."""

    def __init__(self, db_path):
        import duckdb

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(db_path))
        for table in ("transport", "trip_updates", "weather", "events"):
            self.con.execute(
                f"CREATE TABLE IF NOT EXISTS {table} (record JSON, event_ts TIMESTAMP, "
                "ingested_ts TIMESTAMP DEFAULT current_timestamp)"
            )
        self.counts = {t: 0 for t in ("transport", "trip_updates", "weather", "events")}
        self._lock = threading.Lock()

    def send(self, stream: str, record: dict) -> None:
        with self._lock:
            self.con.execute(
                "INSERT INTO " + stream + " (record, event_ts) VALUES (?, ?)",
                [json.dumps(record), record.get("event_ts")],
            )
            self.counts[stream] += 1

    def __call__(self, stream: str, record: dict) -> None:
        self.send(stream, record)

    def flush(self):
        pass

    def report(self):
        for k, v in self.counts.items():
            log.info("  %s: %s records", k, v)


def make_sink(config, local: bool):
    if local:
        return DuckDbSink(config.local_db)
    from .kafka_client import KafkaSink

    sink = KafkaSink(config.kafka_bootstrap, {
        "transport": config.topic_transport,
        "trip_updates": config.topic_trip_updates,
        "weather": config.topic_weather,
        "events": config.topic_events,
    })
    sink.connect()
    return sink


def main() -> int:
    ap = argparse.ArgumentParser(description="CityPulse data simulator")
    ap.add_argument("--local", action="store_true", help="write to local DuckDB instead of Kafka")
    ap.add_argument("--seconds", type=int, default=0, help="stop after N seconds (0 = run forever)")
    ap.add_argument("--vehicles", type=int, default=None, help="override number of vehicles")
    args = ap.parse_args()

    cfg = load_config()
    if args.vehicles:
        cfg.vehicles = args.vehicles

    sink = make_sink(cfg, args.local)
    log.info("Starting simulators for %s (%s vehicles) -> %s", cfg.city.name, cfg.vehicles,
             "local DuckDB" if args.local else f"Kafka {cfg.kafka_bootstrap}")

    transport = TransportSimulator(cfg.gtfs_dir, cfg.vehicles, cfg.rush_hour_amplitude, rng=random.Random(11))
    weather = WeatherSimulator(cfg.city, rng=random.Random(22))
    events = CityEventsSimulator(cfg.city, rng=random.Random(33))

    stop = threading.Event()
    threads = [
        threading.Thread(target=weather.run, args=(sink, cfg.weather_interval_sec, stop), daemon=True),
        threading.Thread(target=events.run, args=(sink, cfg.events_interval_sec, stop), daemon=True),
    ]
    for t in threads:
        t.start()

    start = time.monotonic()
    tick_interval = cfg.update_interval_sec
    sim_dt = tick_interval * cfg.fast_factor  # time-compression for local demos
    try:
        while not stop.is_set():
            # weather/events threads update their own `.state`; sync into transport
            transport.state["weather"] = weather.state.get("weather", transport.state.get("weather", {}))
            transport.state["events"] = events.state.get("events", transport.state.get("events", {}))
            transport.tick(sink, sim_dt)
            sink.flush()
            elapsed = time.monotonic() - start
            if args.seconds and elapsed >= args.seconds:
                break
            if args.local and elapsed >= cfg.local_limit_seconds:
                log.info("Local demo window reached (%ss) - stopping", cfg.local_limit_seconds)
                break
            time.sleep(max(0.05, tick_interval))
    except KeyboardInterrupt:
        log.info("Stopping simulators...")
    finally:
        stop.set()
        if isinstance(sink, DuckDbSink):
            sink.report()
        sink.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
