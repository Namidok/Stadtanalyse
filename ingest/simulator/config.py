"""Runtime configuration for the ingestion layer.

Every value can be overridden through environment variables so the same code
runs in Docker (Kafka path) and locally (DuckDB/JSON path).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass
class CityProfile:
    name: str
    lat: float
    lon: float
    agency: str

    @classmethod
    def load(cls, path: Path | None = None) -> "CityProfile":
        p = path or ROOT / "data" / "city.json"
        if p.exists():
            data = json.loads(p.read_text())
            return cls(name=data["name"], lat=data["lat"], lon=data["lon"], agency=data.get("agency", "Stadtanalyse Transit"))
        return cls(name="Berlin", lat=52.52, lon=13.405, agency="Stadtanalyse Transit")


@dataclass
class SimConfig:
    city: CityProfile = field(default_factory=CityProfile.load)
    gtfs_dir: Path = ROOT / "data" / "gtfs"

    update_interval_sec: float = field(default_factory=lambda: float(_env("SIM_UPDATE_INTERVAL_SEC", "2")))
    vehicles: int = field(default_factory=lambda: int(_env("SIM_VEHICLES", "40")))
    rush_hour_amplitude: float = field(default_factory=lambda: float(_env("SIM_RUSH_HOUR_AMPLITUDE", "1.6")))
    weather_interval_sec: int = field(default_factory=lambda: int(_env("SIM_WEATHER_INTERVAL_SEC", "30")))
    events_interval_sec: int = field(default_factory=lambda: int(_env("SIM_EVENTS_INTERVAL_SEC", "10")))

    kafka_bootstrap: str = field(default_factory=lambda: _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    topic_transport: str = field(default_factory=lambda: _env("KAFKA_TOPIC_TRANSPORT", "raw.transport.vehicle.positions"))
    topic_trip_updates: str = field(default_factory=lambda: _env("KAFKA_TOPIC_TRIP_UPDATES", "raw.transport.trip.updates"))
    topic_weather: str = field(default_factory=lambda: _env("KAFKA_TOPIC_WEATHER", "raw.weather.observations"))
    topic_events: str = field(default_factory=lambda: _env("KAFKA_TOPIC_EVENTS", "raw.city.events"))

    # Local offline mode
    local: bool = False
    local_db: Path = ROOT / "data" / "local" / "stadtanalyse.duckdb"
    local_limit_seconds: int = 300
    fast_factor: float = field(default_factory=lambda: float(_env("SIM_FAST_FACTOR", "1.0")))


def load_config() -> SimConfig:
    return SimConfig()
