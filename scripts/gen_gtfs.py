#!/usr/bin/env python3
"""Generate a synthetic GTFS static feed for the CityPulse demo city.

Creates routes.txt, stops.txt, trips.txt and stop_times.txt in data/gtfs.
The network is a realistic grid of radial + ring lines (bus/tram/rail mix).

Usage: python scripts/gen_gtfs.py [--city-json path]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GTFS_DIR = ROOT / "data" / "gtfs"


def _latlon(lat, lon):
    return round(lat, 6), round(lon, 6)


def build_network(center_lat=52.52, center_lon=13.405, seed=42):
    """Return routes (list of stop coordinate tuples) laid out on a grid."""
    rng = random.Random(seed)
    # km-per-degree (approx, mid-latitude Europe)
    KMLAT = 111.0
    KMLON = 71.5
    routes = []

    def line(name, mode, a, b, stops):
        # a, b = (dlat_km, dlon_km) offsets from center
        dist = math.hypot((b[0] - a[0]) / KMLAT, (b[1] - a[1]) / KMLON)
        n = stops
        route_pts = []
        for i in range(n + 1):
            t = i / n
            lat, lon = _latlon(
                center_lat + a[0] / KMLAT + t * (b[0] - a[0]) / KMLAT,
                center_lon + a[1] / KMLON + t * (b[1] - a[1]) / KMLON,
            )
            route_pts.append((lat, lon))
        routes.append({"name": name, "mode": mode, "points": route_pts})

    # Radial lines through the center (like a U-Bahn/S-Bahn network)
    radial = [(0, 12), (0, -12), (10, 0), (-10, 0), (7, 8), (-7, -8), (-7, 8), (7, -8)]
    modes = ["rail", "rail", "tram", "tram", "bus", "bus", "bus", "bus"]
    for i, (dx, dy) in enumerate(radial):
        stops = rng.randint(12, 18)
        line(f"R{i+1}", modes[i], (0, 0), (dx, dy), stops)

    # A ring line
    ring = []
    for k in range(13):
        ang = 2 * math.pi * k / 12
        ring.append((center_lat + 6 * math.sin(ang) / KMLAT, center_lon + 6 * math.cos(ang) / KMLON))
    routes.append({"name": "R9", "mode": "rail", "points": ring})

    # A couple of short feeder bus routes in the outer grid
    for i, (dx, dy) in enumerate([(4, 9), (-6, -10)]):
        line(f"B{i+1}", "bus", (dx, dy), (dx + 3, dy + 3), rng.randint(8, 11))

    return routes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="city.json", help="city profile json (name/lat/lon)")
    args = ap.parse_args()

    city_path = ROOT / "data" / args.city
    if city_path.exists():
        profile = json.loads(city_path.read_text())
    else:
        profile = {"name": "Berlin", "lat": 52.52, "lon": 13.405, "agency": "CityPulse Transit"}

    GTFS_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    network = build_network(center_lat=profile["lat"], center_lon=profile["lon"])

    stops: dict[str, dict] = {}
    routes_rows: list[dict] = []
    trips_rows: list[dict] = []
    stop_times_rows: list[dict] = []

    route_type = {"rail": 1, "tram": 0, "bus": 3}

    for ridx, route in enumerate(network, start=1):
        route_id = route["name"]
        routes_rows.append(
            {
                "route_id": route_id,
                "agency_id": profile["agency"],
                "route_short_name": route_id,
                "route_long_name": f"{route['name']} line",
                "route_type": route_type[route["mode"]],
                "route_mode": route["mode"],
            }
        )
        seq = []
        for pidx, (lat, lon) in enumerate(route["points"]):
            stop_id = f"{route_id}_{pidx}"
            stops[stop_id] = {
                "stop_id": stop_id,
                "stop_name": f"{route['name']} Stop {pidx}",
                "stop_lat": lat,
                "stop_lon": lon,
                "stop_zone": f"Z{1 + (pidx // 4)}",
            }
            seq.append(stop_id)

        # Two trips per direction per route (inbound/outbound service)
        for direction in (0, 1):
            trip_id = f"{route_id}-{direction}-{ridx}"
            trips_rows.append(
                {
                    "trip_id": trip_id,
                    "route_id": route_id,
                    "service_id": "WD",
                    "direction_id": direction,
                    "trip_headsign": f"{route_id} {'Inbound' if direction == 0 else 'Outbound'}",
                }
            )
            ordered = seq if direction == 0 else list(reversed(seq))
            base_min = rng.randint(5, 60) * 6
            for s, sid in enumerate(ordered):
                stop_times_rows.append(
                    {
                        "trip_id": trip_id,
                        "stop_id": sid,
                        "stop_sequence": s,
                        "arrival_time": f"{(base_min + 2 * s) // 60:02d}:{(base_min + 2 * s) % 60:02d}:00",
                        "departure_time": f"{(base_min + 2 * s) // 60:02d}:{(base_min + 2 * s) % 60:02d}:30",
                    }
                )

    def wcsv(name, rows, fieldnames):
        with (GTFS_DIR / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    wcsv("stops.txt", list(stops.values()), ["stop_id", "stop_name", "stop_lat", "stop_lon", "stop_zone"])
    wcsv("routes.txt", routes_rows, ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_mode"])
    wcsv("trips.txt", trips_rows, ["trip_id", "route_id", "service_id", "direction_id", "trip_headsign"])
    wcsv("stop_times.txt", stop_times_rows, ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"])

    print(f"Wrote {len(stops)} stops, {len(routes_rows)} routes, {len(trips_rows)} trips, {len(stop_times_rows)} stop_times to {GTFS_DIR}")


if __name__ == "__main__":
    sys.exit(main())
