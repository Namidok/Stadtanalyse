"""Weather simulator - emits per-zone observations with a realistic seasonal
baseline, diurnal cycle and occasional storm systems.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from .base import BaseSimulator, utcnow

CONDITIONS = {
    "clear": (0.45, "clear"),
    "clouds": (0.30, "clouds"),
    "rain": (0.16, "rain"),
    "fog": (0.05, "fog"),
    "snow": (0.03, "snow"),
    "storm": (0.01, "storm"),
}


class WeatherSimulator(BaseSimulator):
    name = "weather"

    def __init__(self, city, rng=None):
        super().__init__(rng)
        self.city = city
        # grid of observation zones covering the city (+-6km)
        self.zones = []
        for ix in range(-2, 3):
            for iy in range(-2, 3):
                self.zones.append(
                    {
                        "zone_id": f"Z{ix+2}{iy+2}",
                        "lat": city.lat + 0.03 * ix,
                        "lon": city.lon + 0.03 * iy,
                        "temp_offset": self.rng.uniform(-2.0, 2.0),
                    }
                )

    def _seasonal_temp(self) -> float:
        month = datetime.now(timezone.utc).month
        return 15.0 + 13.0 * math.cos((month - 7) / 12 * 2 * math.pi)

    def _diurnal(self) -> float:
        hour = datetime.now(timezone.utc).hour
        return 3.0 * math.sin((hour - 9) / 24 * 2 * math.pi)

    def _pick_condition(self) -> str:
        month = datetime.now(timezone.utc).month
        winter = month in (12, 1, 2)
        weights = {
            "clear": 0.42,
            "clouds": 0.28,
            "rain": 0.22 if not winter else 0.16,
            "fog": 0.05,
            "snow": 0.02 if not winter else 0.12,
            "storm": 0.01,
        }
        r = self.rng.random()
        acc = 0.0
        for cond, p in weights.items():
            acc += p
            if r < acc:
                return cond
        return "clear"

    def tick(self, sink, dt: float) -> None:
        now = utcnow()
        base_temp = self._seasonal_temp() + self._diurnal()
        # a system event drifts the whole city every few minutes
        stormy = self.rng.random() < 0.02
        condition = self._pick_condition()
        if stormy:
            condition = "storm"
        precip = {
            "storm": self.rng.uniform(8, 20),
            "rain": self.rng.uniform(1, 6),
            "snow": self.rng.uniform(0.5, 3),
            "fog": 0.0,
            "clouds": self.rng.uniform(0, 1),
            "clear": 0.0,
        }[condition]
        wind = self.rng.uniform(4, 30) if condition in ("storm", "rain") else self.rng.uniform(2, 14)

        for z in self.zones:
            temp = base_temp + z["temp_offset"] + self.rng.gauss(0, 0.6)
            rec = {
                "zone_id": z["zone_id"],
                "lat": round(z["lat"], 5),
                "lon": round(z["lon"], 5),
                "temperature_c": round(temp, 1),
                "feels_like_c": round(temp - (0.35 if wind > 15 else 0.0), 1),
                "humidity_pct": round(min(100, max(20, 100 - (temp - 5) * 2 + (20 if condition == "rain" else 0)) + self.rng.gauss(0, 5)), 1),
                "wind_speed_kmh": round(wind, 1),
                "precipitation_mm": round(precip, 2),
                "condition": condition,
                "visibility_km": round(self.rng.uniform(0.5, 12) if condition in ("fog", "storm") else self.rng.uniform(8, 25), 1),
                "event_ts": now,
            }
            sink("weather", rec)
        # publish the city-wide headline state for the transport simulator
        self.state["weather"] = {
            "condition": condition,
            "precip": precip,
            "wind": wind,
            "temp": base_temp,
        }
