"""Application configuration for the CityPulse API."""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache
def settings() -> dict:
    return {
        "postgres_host": os.environ.get("POSTGRES_HOST", "postgres"),
        "postgres_port": os.environ.get("POSTGRES_PORT", "5432"),
        "postgres_user": os.environ.get("POSTGRES_USER", "citypulse"),
        "postgres_password": os.environ.get("POSTGRES_PASSWORD", "citypulse-secret"),
        "postgres_db": os.environ.get("POSTGRES_DB", "citypulse"),
        "kafka_bootstrap": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        "topic_transport": os.environ.get("KAFKA_TOPIC_TRANSPORT", "raw.transport.vehicle.positions"),
        "topic_trip_updates": os.environ.get("KAFKA_TOPIC_TRIP_UPDATES", "raw.transport.trip.updates"),
        "topic_weather": os.environ.get("KAFKA_TOPIC_WEATHER", "raw.weather.observations"),
        "topic_events": os.environ.get("KAFKA_TOPIC_EVENTS", "raw.city.events"),
        "ml_model_path": os.environ.get("ML_MODEL_PATH", "/opt/ml/model/model.joblib"),
        "ml_features_path": os.environ.get("ML_FEATURES_PATH", "/opt/ml/model/features.json"),
        "cors_origins": os.environ.get("API_CORS_ORIGINS", "*"),
        "force_memory_mode": os.environ.get("API_MEMORY_MODE", "0") == "1",
    }


def pg_url() -> str:
    s = settings()
    return (f"postgresql://{s['postgres_user']}:{s['postgres_password']}"
            f"@{s['postgres_host']}:{s['postgres_port']}/{s['postgres_db']}")
