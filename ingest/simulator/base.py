"""Base simulator helpers shared by transport/weather/events generators."""
from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable

CALLBACK = Callable[[str, dict], None]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BaseSimulator(ABC):
    """A stateful data generator that yields records to a sink callback."""

    name: str = "base"

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self._running = False
        self.state: dict = {}

    @abstractmethod
    def tick(self, sink: CALLBACK, dt: float) -> None:
        """Advance simulation state and emit records through sink(topic, record)."""

    def run(self, sink: CALLBACK, interval_sec: float, stop_event=None) -> None:
        self._running = True
        while self._running:
            t0 = time.monotonic()
            self.tick(sink, interval_sec)
            elapsed = time.monotonic() - t0
            time.sleep(max(0.05, interval_sec - elapsed))
            if stop_event is not None and stop_event.is_set():
                self._running = False

    def stop(self) -> None:
        self._running = False
