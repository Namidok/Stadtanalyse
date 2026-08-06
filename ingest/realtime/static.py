"""National GTFS (gtfs.de, de_nv) download + per-city extraction.

The national feed covers all of Germany (600K+ stops, ~1.5M trips). We keep a
single cached download, then extract a normalized per-city subset with DuckDB
so the transport simulator can run on the *real* public-transit network of the
active city. City subsets are cached under data/gtfs_cache/<city> and installed
into data/gtfs (the directory the simulator already reads) plus a `.city`
sentinel so the producer only restarts once a complete network is in place.
"""
from __future__ import annotations

import logging
import math
import shutil
import zipfile
from pathlib import Path

import requests

from ..simulator.config import CityProfile
from .config import RealConfig, slugify

log = logging.getLogger("stadtanalyse.realtime.static")

# GTFS route_type (standard + extended codes used by the DELFI/gtfs.de feed)
# mapped to the three simulator modes: rail, tram, bus.
ROUTE_MODE: dict[int, str] = {
    0: "tram", 1: "rail", 2: "rail", 3: "bus", 4: "bus", 5: "tram",
    6: "rail", 7: "tram", 11: "bus", 12: "bus",
    100: "rail", 101: "rail", 102: "rail", 103: "rail", 104: "rail",
    105: "rail", 106: "rail", 107: "rail", 108: "rail", 109: "rail",
    110: "rail", 111: "bus", 112: "bus",
    200: "bus", 201: "bus", 202: "bus", 203: "bus", 204: "bus",
    205: "bus", 206: "bus", 207: "bus", 208: "bus",
    400: "rail", 401: "rail", 402: "rail", 403: "rail", 404: "rail",
    700: "bus", 701: "bus", 702: "bus", 703: "bus", 704: "bus",
    705: "bus", 706: "bus", 707: "bus", 708: "bus", 709: "bus",
    710: "bus", 711: "bus", 712: "bus", 713: "bus", 714: "bus",
    715: "bus", 716: "bus", 717: "bus",
    800: "bus",
    900: "tram", 901: "tram", 902: "tram", 903: "tram", 904: "tram", 905: "tram",
    1000: "bus", 1100: "bus", 1200: "bus",
    1300: "rail", 1400: "tram", 1500: "bus", 1700: "bus", 1702: "bus",
}


def normalize_route_mode(route_type: str) -> str:
    try:
        return ROUTE_MODE.get(int(route_type), "bus")
    except (TypeError, ValueError):
        return "bus"


def ensure_national_downloaded(cfg: RealConfig) -> Path:
    """Download + unzip the national feed once; returns the extracted dir."""
    zip_path = cfg.national_dir / "nv_free" / "latest.zip"
    extract_dir = cfg.national_dir / "nv_free" / "unzipped"
    marker = extract_dir / ".done"

    if not zip_path.exists() or zip_path.stat().st_size < 10_000_000:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("Downloading national GTFS (%s) -> %s (~240MB, one time)", cfg.gtfs_url, zip_path)
        tmp = zip_path.with_name("latest.zip.part")
        with requests.get(cfg.gtfs_url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as f:
                for i, chunk in enumerate(resp.iter_content(chunk_size=1 << 20)):
                    if not chunk:
                        continue
                    f.write(chunk)
                    if i % 100 == 0 and i:
                        log.info("  downloaded %d MB", (i * (1 << 20)) // (1 << 20))
        tmp.replace(zip_path)
        log.info("Download complete: %.1f MB", zip_path.stat().st_size / 1e6)

    if not marker.exists():
        log.info("Extracting national GTFS to %s", extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                zf.extract(name, extract_dir)
        marker.write_text("done")
        log.info("Extraction complete: %s", ", ".join(p.name for p in extract_dir.glob("*.txt")))
    return extract_dir


def extract_city(cfg: RealConfig, city: CityProfile, force: bool = False) -> Path:
    """Extract a normalized city network and install it into data/gtfs.

    Cached per city under data/gtfs_cache/<city-slug>; the (usually much
    cheaper) copy into the active dir happens on every switch.
    """
    cache = cfg.cache_dir / slugify(city.name)
    marker = cache / ".done"
    if force or not marker.exists():
        _extract_to_cache(cfg, city, cache)
        marker.write_text(city.name)
    else:
        log.info("Using cached real GTFS for %s (%s)", city.name, cache)
    install_city(cfg, city)
    return cache


def _extract_to_cache(cfg: RealConfig, city: CityProfile, cache: Path) -> None:
    import duckdb

    national = ensure_national_downloaded(cfg)
    log.info("Extracting real GTFS subset for %s (bbox radius %.0f km)",
             city.name, cfg.bbox_radius_km)

    lat_delta = cfg.bbox_radius_km / 111.0
    lon_delta = cfg.bbox_radius_km / (111.0 * max(math.cos(math.radians(city.lat)), 0.2))

    tmp = cache.with_name(cache.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    def p(name: str) -> str:
        return str(national / name)

    try:
        con = duckdb.connect()
        con.execute(f"""
            CREATE OR REPLACE TABLE city_stops AS
            SELECT stop_id, stop_name, stop_lat, stop_lon
            FROM read_csv_auto('{p("stops.txt")}', header=true, sample_size=-1)
            WHERE stop_lat BETWEEN {city.lat - lat_delta} AND {city.lat + lat_delta}
              AND stop_lon BETWEEN {city.lon - lon_delta} AND {city.lon + lon_delta}
        """)
        n_stops = con.execute("SELECT count(*) FROM city_stops").fetchone()[0]
        log.info("  stops in bbox: %s", n_stops)
        if n_stops == 0:
            raise RuntimeError(f"no stops found around {city.name} - feed structure may have changed")

        con.execute(f"""
            CREATE OR REPLACE TABLE city_stop_times AS
            SELECT st.trip_id, st.stop_id, st.stop_sequence, st.arrival_time, st.departure_time
            FROM read_csv_auto('{p("stop_times.txt")}', header=true, sample_size=-1) st
            JOIN city_stops s ON st.stop_id = s.stop_id
        """)
        n_std = con.execute("SELECT count(*) FROM city_stop_times").fetchone()[0]
        log.info("  stop times in city: %s", n_std)

        con.execute(f"""
            CREATE OR REPLACE TABLE city_trips AS
            SELECT t.trip_id, t.route_id, t.service_id
            FROM read_csv_auto('{p("trips.txt")}', header=true, sample_size=-1) t
            WHERE t.trip_id IN (SELECT DISTINCT trip_id FROM city_stop_times)
        """)
        n_trips = con.execute("SELECT count(*) FROM city_trips").fetchone()[0]
        log.info("  trips in city: %s", n_trips)

        con.execute(f"""
            CREATE OR REPLACE TABLE city_routes AS
            SELECT r.route_id, r.route_type, r.route_short_name, r.route_long_name
            FROM read_csv_auto('{p("routes.txt")}', header=true, sample_size=-1) r
            WHERE r.route_id IN (SELECT DISTINCT route_id FROM city_trips)
        """)
        n_routes = con.execute("SELECT count(*) FROM city_routes").fetchone()[0]
        log.info("  routes in city: %s", n_routes)

        # Normalize to the exact contract TransportSimulator._load_gtfs reads.
        _copy_to_csv(con, tmp, "stops.txt",
                     "SELECT stop_id, stop_name, stop_lat, stop_lon, '' AS stop_zone FROM city_stops ORDER BY stop_id")
        _copy_to_csv(con, tmp, "routes.txt",
                     "SELECT route_id, '' AS route_mode, route_short_name, route_long_name FROM city_routes ORDER BY route_id")
        _copy_to_csv(con, tmp, "trips.txt",
                     "SELECT trip_id, route_id, service_id, 0 AS direction_id, '' AS trip_headsign FROM city_trips ORDER BY trip_id")
        _copy_to_csv(con, tmp, "stop_times.txt",
                     "SELECT trip_id, stop_id, stop_sequence, arrival_time, departure_time FROM city_stop_times ORDER BY trip_id, stop_sequence")
    finally:
        con.close()

    # route_mode isn't in the national feed as a column, so derive it after
    # export from route_type via a small in-place rewrite.
    _write_route_modes(tmp, national)

    if cache.exists():
        shutil.rmtree(cache)
    tmp.rename(cache)
    log.info("Cached real GTFS for %s: %s stops, %s routes, %s trips, %s stop-times",
             city.name, n_stops, n_routes, n_trips, n_std)


def _copy_to_csv(con, out_dir: Path, name: str, query: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY ({query}) TO '{out_dir / name}' (HEADER, DELIMITER ',', FORMAT csv)")


def _write_route_modes(cache: Path, national: Path) -> None:
    """Fill route_mode by joining the exported routes back to national route_type."""
    import csv

    types: dict[str, str] = {}
    with (national / "routes.txt").open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            types[row["route_id"]] = row.get("route_type", "")

    routes_path = cache / "routes.txt"
    tmp = cache / "routes.txt.tmp"
    with routes_path.open(newline="", encoding="utf-8") as fin, tmp.open("w", newline="", encoding="utf-8") as fout:
        writer = csv.writer(fout)
        writer.writerow(["route_id", "route_mode", "route_short_name", "route_long_name"])
        for row in csv.DictReader(fin):
            writer.writerow([
                row["route_id"],
                normalize_route_mode(types.get(row["route_id"], "")),
                row.get("route_short_name", ""),
                row.get("route_long_name", ""),
            ])
    tmp.replace(routes_path)


def install_city(cfg: RealConfig, city: CityProfile) -> None:
    """Install a cached city network into the active dir the simulator reads."""
    cache = cfg.cache_dir / slugify(city.name)
    if not cache.exists():
        raise RuntimeError(f"no cached GTFS for {city.name} at {cache}")

    if cfg.active_dir.exists():
        for p in cfg.active_dir.iterdir():
            if p.name == ".city":
                continue
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
    else:
        cfg.active_dir.mkdir(parents=True)

    for p in cache.iterdir():
        if p.name == ".done":
            continue
        shutil.copy2(p, cfg.active_dir / p.name)

    (cfg.active_dir / ".city").write_text(city.name)
    log.info("Installed real GTFS for %s into %s", city.name, cfg.active_dir)
