"""Kafka producer wrapper with automatic topic mapping and retries."""
from __future__ import annotations

import json
import logging
import time

from kafka import KafkaProducer

log = logging.getLogger("stadtanalyse.ingest")

TOPIC_MAP = {
    "transport": "raw.transport.vehicle.positions",
    "trip_updates": "raw.transport.trip.updates",
    "weather": "raw.weather.observations",
    "events": "raw.city.events",
}


class KafkaSink:
    def __init__(self, bootstrap: str, topics: dict[str, str] | None = None):
        self.topics = topics or TOPIC_MAP
        self._producer = None
        self._bootstrap = bootstrap

    def connect(self, retries: int = 30, wait_sec: float = 2.0) -> None:
        last_err = None
        for i in range(retries):
            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self._bootstrap,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    acks="all",
                    retries=5,
                    linger_ms=50,
                    compression_type="gzip",
                )
                # force metadata fetch so we know the broker is reachable
                self._producer.metrics()
                log.info("Connected to Kafka at %s", self._bootstrap)
                return
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.warning("Kafka not ready (%s) - retry %s/%s", e, i + 1, retries)
                time.sleep(wait_sec)
        raise RuntimeError(f"Could not connect to Kafka at {self._bootstrap}: {last_err}")

    def __call__(self, stream: str, record: dict) -> None:
        self.send(stream, record)

    def send(self, stream: str, record: dict) -> None:
        topic = self.topics.get(stream)
        if not topic:
            raise ValueError(f"No topic mapped for stream '{stream}'")
        future = self._producer.send(topic, value=record)
        future.add_callback(lambda md: None).add_errback(self._on_error, topic, record)

    @staticmethod
    def _on_error(exc, topic, record) -> None:
        log.error("Kafka produce error on %s: %s (record keys=%s)", topic, exc, list(record.keys()))

    def flush(self) -> None:
        if self._producer:
            self._producer.flush()
