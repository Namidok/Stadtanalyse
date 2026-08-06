"""Configuration for the real-data integration layer.

Downloads the national German GTFS (gtfs.de, de_nv) once, extracts a
normalized per-city network into the same directory contract the transport
simulator expects (data/gtfs), and polls the national GTFS-RT realtime feed
(realtime.gtfs.de) for real per-trip delays.

All values can be overridden through environment variables for Docker.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ..simulator.config import ROOT

GTFS_URL = "https://download.gtfs.de/germany/nv_free/latest.zip"
RT_URL = "https://realtime.gtfs.de/realtime-free.pb"


def slugify(name: str) -> str:
    """Stable ascii slug for a city name ('München' -> 'munchen')."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    chars = "".join(c if c.isalnum() else "-" for c in ascii_name.lower())
    return chars.strip("-")


def _env(key: str, default: str) -> str:
    import os

    return os.environ.get(key, default)


@dataclass
class RealConfig:
    gtfs_url: str
    rt_url: str
    national_dir: Path
    active_dir: Path
    cache_dir: Path
    bbox_radius_km: float
    check_interval_sec: float
    poll_interval_sec: float
    max_records_per_poll: int
    kafka_bootstrap: str
    topic_trip_updates: str
    local: bool
    local_db: Path

    @classmethod
    def from_env(cls, local: bool = False) -> "RealConfig":
        return cls(
            gtfs_url=_env("REALTIME_GTFS_URL", GTFS_URL),
            rt_url=_env("REALTIME_RT_URL", RT_URL),
            national_dir=ROOT / "data" / "gtfs_national",
            active_dir=ROOT / "data" / "gtfs",
            cache_dir=ROOT / "data" / "gtfs_cache",
            bbox_radius_km=float(_env("REALTIME_BBOX_RADIUS_KM", "25")),
            check_interval_sec=float(_env("REALTIME_CHECK_INTERVAL_SEC", "3")),
            poll_interval_sec=float(_env("REALTIME_POLL_INTERVAL_SEC", "20")),
            max_records_per_poll=int(_env("REALTIME_MAX_RECORDS", "600")),
            kafka_bootstrap=_env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic_trip_updates=_env("KAFKA_TOPIC_TRIP_UPDATES", "raw.transport.trip.updates"),
            local=local,
            local_db=ROOT / "data" / "local" / "realtime.duckdb",
        )
