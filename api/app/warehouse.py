"""Warehouse provider with availability caching + memory fallback."""
from __future__ import annotations

import logging
import threading
import time

from .config import settings
from .db import DBUnavailable, MemoryWarehouse, PostgresWarehouse

log = logging.getLogger("citypulse.warehouse")

_TTL = 30  # seconds between Postgres availability checks


class WarehouseProvider:
    def __init__(self):
        self._pg = PostgresWarehouse()
        self._mem: MemoryWarehouse | None = None
        self._mode = "memory" if settings()["force_memory_mode"] else None
        self._last_check = 0.0
        self._lock = threading.Lock()

    def set_live(self, live) -> None:
        self._mem = MemoryWarehouse(live)

    def _probe(self) -> None:
        now = time.monotonic()
        with self._lock:
            if now - self._last_check < _TTL:
                return
            self._last_check = now
            if self._mode != "memory" and self._pg.ping():
                self._mode = "postgres"
                log.info("Warehouse mode: postgres (gold marts)")
            else:
                self._mode = "memory"

    @property
    def mode(self) -> str:
        self._probe()
        return self._mode

    def query(self, sql: str, params: tuple | None = None) -> list[dict]:
        self._probe()
        if self._mode == "postgres":
            try:
                return self._pg.query(sql, params)
            except DBUnavailable:
                self._mode = "memory"
        raise DBUnavailable("postgres unavailable")

    @property
    def memory(self) -> MemoryWarehouse:
        return self._mem  # type: ignore[return-value]

    def rows(self, sql: str, memory_method: str, params: tuple | None = None) -> list[dict]:
        """Try the Gold-layer SQL; fall back to an in-memory aggregation."""
        try:
            return self.query(sql, params)
        except DBUnavailable:
            return getattr(self.memory, memory_method)()


provider = WarehouseProvider()
