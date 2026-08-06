"""Realtime data service: real GTFS network sync + GTFS-RT delay ingestion.

Streams real German transit delays (realtime.gtfs.de) into Kafka so the whole
Spark -> dbt -> API/ML pipeline runs on live national data instead of only the
synthetic simulator.

Usage:
    python -m ingest.realtime.run                       # stream to Kafka forever
    python -m ingest.realtime.run --local               # offline DuckDB window
    python -m ingest.realtime.run --static-only         # sync GTFS network only
    python -m ingest.realtime.run --realtime-only       # poll delays only
"""
from __future__ import annotations

import argparse
import json
import logging
import threading
import time

from ..simulator.config import CityProfile
from .config import RealConfig, slugify
from .poller import RealtimePoller
from .static import ensure_national_downloaded, extract_city

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("stadtanalyse.realtime.run")


class DuckDbRealtimeSink:
    """Offline sink for --local testing of the realtime poller."""

    def __init__(self, db_path):
        import duckdb

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(db_path))
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS trip_updates "
            "(record JSON, event_ts TIMESTAMP, ingested_ts TIMESTAMP DEFAULT current_timestamp)"
        )
        self.count = 0
        self._lock = threading.Lock()

    def __call__(self, stream: str, record: dict) -> None:
        with self._lock:
            self.con.execute(
                "INSERT INTO trip_updates (record, event_ts) VALUES (?, ?)",
                [json.dumps(record), record.get("event_ts")],
            )
            self.count += 1

    def flush(self) -> None:
        pass


class StaticWatcher:
    """Keeps the active data/gtfs network in sync with city.json."""

    def __init__(self, cfg: RealConfig):
        self.cfg = cfg
        self._seen = CityProfile.load().name

    def sync(self, city: CityProfile | None = None) -> None:
        city = city or CityProfile.load()
        log.info("Synchronising real GTFS network for %s", city.name)
        extract_city(self.cfg, city)
        self._seen = city.name

    def run(self, stop: threading.Event) -> None:
        self.sync()
        while not stop.wait(self.cfg.check_interval_sec):
            city = CityProfile.load()
            if city.name != self._seen:
                log.info("City profile changed to %s -> extracting real network", city.name)
                self.sync(city)


def make_sink(cfg: RealConfig):
    if cfg.local:
        return DuckDbRealtimeSink(cfg.local_db)
    from ..producer.kafka_client import KafkaSink

    sink = KafkaSink(cfg.kafka_bootstrap, {"trip_updates": cfg.topic_trip_updates})
    sink.connect()
    return sink


def main() -> int:
    ap = argparse.ArgumentParser(description="Stadtanalyse real-data service")
    ap.add_argument("--local", action="store_true", help="write to local DuckDB instead of Kafka")
    ap.add_argument("--static-only", action="store_true", help="only sync the real GTFS network")
    ap.add_argument("--realtime-only", action="store_true", help="only poll realtime delays")
    ap.add_argument("--seconds", type=int, default=0, help="stop after N seconds (0 = run forever)")
    args = ap.parse_args()

    cfg = RealConfig.from_env(local=args.local)
    sink = make_sink(cfg)

    if not args.realtime_only:
        ensure_national_downloaded(cfg)

    stop = threading.Event()
    threads = []

    if not args.realtime_only:
        watcher = StaticWatcher(cfg)
        t = threading.Thread(target=watcher.run, args=(stop,), daemon=True, name="static-watcher")
        t.start()
        threads.append(t)

    if not args.static_only:
        poller = RealtimePoller(cfg, sink)
        t = threading.Thread(target=poller.run, args=(stop,), daemon=True, name="realtime-poller")
        t.start()
        threads.append(t)

    log.info("Realtime service running (local=%s static=%s realtime=%s)",
             args.local, not args.realtime_only, not args.static_only)
    try:
        start = time.monotonic()
        while any(t.is_alive() for t in threads):
            time.sleep(1)
            if args.seconds and time.monotonic() - start >= args.seconds:
                break
    except KeyboardInterrupt:
        log.info("Stopping realtime service...")
    finally:
        stop.set()
        if isinstance(sink, DuckDbRealtimeSink):
            log.info("Local realtime sink: %s trip updates recorded", sink.count)
        sink.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
