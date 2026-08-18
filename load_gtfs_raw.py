"""Load real Berlin GTFS static files into Postgres gtfs_raw schema."""
import csv
import psycopg2
from pathlib import Path

GTFS_DIR = Path.home() / "Downloads/GitHub/smart-urban-mobility/data/gtfs"

PG_CONN = dict(
    host="localhost", port=5432, dbname="stadtanalyse",
    user="stadtanalyse", password="stadtanalyse-secret",
)

def load_csv(path, cols):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [tuple(row.get(c, "") for c in cols) for row in reader]

def main():
    pg = psycopg2.connect(**PG_CONN)
    cur = pg.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS gtfs_raw;")
    pg.commit()
    from psycopg2.extras import execute_values

    cur.execute("""
        DROP TABLE IF EXISTS gtfs_raw.gtfs_stops;
        CREATE TABLE gtfs_raw.gtfs_stops (
            stop_id TEXT NOT NULL, stop_name TEXT, stop_lat TEXT, stop_lon TEXT, stop_zone TEXT
        );
    """)
    rows = load_csv(GTFS_DIR / "stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon", "stop_zone"])
    execute_values(cur, "INSERT INTO gtfs_raw.gtfs_stops VALUES %s", rows)
    print(f"gtfs_stops: {len(rows)} rows")

    cur.execute("""
        DROP TABLE IF EXISTS gtfs_raw.gtfs_routes;
        CREATE TABLE gtfs_raw.gtfs_routes (
            route_id TEXT NOT NULL, route_mode TEXT, route_short_name TEXT, route_long_name TEXT
        );
    """)
    rows = load_csv(GTFS_DIR / "routes.txt", ["route_id", "route_mode", "route_short_name", "route_long_name"])
    execute_values(cur, "INSERT INTO gtfs_raw.gtfs_routes VALUES %s", rows)
    print(f"gtfs_routes: {len(rows)} rows")

    cur.execute("""
        DROP TABLE IF EXISTS gtfs_raw.gtfs_trips;
        CREATE TABLE gtfs_raw.gtfs_trips (
            trip_id TEXT NOT NULL, route_id TEXT, service_id TEXT, direction_id TEXT, trip_headsign TEXT
        );
    """)
    rows = load_csv(GTFS_DIR / "trips.txt", ["trip_id", "route_id", "service_id", "direction_id", "trip_headsign"])
    execute_values(cur, "INSERT INTO gtfs_raw.gtfs_trips VALUES %s", rows)
    print(f"gtfs_trips: {len(rows)} rows")

    cur.execute("""
        DROP TABLE IF EXISTS gtfs_raw.gtfs_stop_times;
        CREATE TABLE gtfs_raw.gtfs_stop_times (
            trip_id TEXT NOT NULL, stop_id TEXT, stop_sequence TEXT,
            arrival_time TEXT, departure_time TEXT
        );
    """)
    with open(GTFS_DIR / "stop_times.txt", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader):
            if i >= 200000:
                break
            rows.append((
                row.get("trip_id", ""), row.get("stop_id", ""),
                row.get("stop_sequence", ""), row.get("arrival_time", ""),
                row.get("departure_time", ""),
            ))
    execute_values(cur, "INSERT INTO gtfs_raw.gtfs_stop_times VALUES %s", rows, page_size=5000)
    print(f"gtfs_stop_times: {len(rows)} rows (capped at 200k for load speed)")

    pg.commit()
    cur.close()
    pg.close()

if __name__ == "__main__":
    main()
