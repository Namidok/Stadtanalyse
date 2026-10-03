"""Seed silver.weather_observations, silver.city_events, silver.transport_positions
with representative sample data matching the dbt staging model schemas.
(This project's own architecture treats these three streams as simulator-sourced;
trip_updates and gtfs_raw already hold real live/static Berlin GTFS data.)
"""
import random
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2.extras import execute_values

PG_CONN = dict(
    host="localhost", port=5432, dbname="stadtanalyse",
    user="stadtanalyse", password="stadtanalyse-secret",
)

BERLIN_LAT, BERLIN_LON = 52.5200, 13.4050
now = datetime.now(timezone.utc)

def main():
    pg = psycopg2.connect(**PG_CONN)
    cur = pg.cursor()

    cur.execute("""
        DROP TABLE IF EXISTS silver.weather_observations;
        CREATE TABLE silver.weather_observations (
            zone_id TEXT NOT NULL, lat NUMERIC, lon NUMERIC,
            temperature_c NUMERIC, feels_like_c NUMERIC, humidity_pct NUMERIC,
            wind_speed_kmh NUMERIC, precipitation_mm NUMERIC, condition TEXT,
            visibility_km NUMERIC, event_ts TIMESTAMPTZ,
            ingested_ts TIMESTAMPTZ DEFAULT now(), dqr_valid BOOLEAN DEFAULT TRUE
        );
    """)
    conditions = ["clear", "clouds", "rain", "fog", "snow", "storm"]
    weather_rows = []
    for ix in range(-2, 3):
        for iy in range(-2, 3):
            zone_id = f"Z{ix+2}{iy+2}"
            for i in range(20):
                ts = now - timedelta(minutes=15 * i)
                weather_rows.append((
                    zone_id, BERLIN_LAT + 0.03 * ix, BERLIN_LON + 0.03 * iy,
                    round(random.uniform(8, 22), 1), round(random.uniform(6, 20), 1),
                    round(random.uniform(40, 90), 1), round(random.uniform(0, 30), 1),
                    round(random.uniform(0, 5), 1), random.choice(conditions),
                    round(random.uniform(3, 15), 1), ts, ts, True,
                ))
    execute_values(cur, """
        INSERT INTO silver.weather_observations
        (zone_id, lat, lon, temperature_c, feels_like_c, humidity_pct,
         wind_speed_kmh, precipitation_mm, condition, visibility_km,
         event_ts, ingested_ts, dqr_valid) VALUES %s
    """, weather_rows)
    print(f"weather_observations: {len(weather_rows)} rows")

    cur.execute("""
        DROP TABLE IF EXISTS silver.city_events;
        CREATE TABLE silver.city_events (
            event_id TEXT NOT NULL, name TEXT, category TEXT, lat NUMERIC, lon NUMERIC,
            start_time_utc TIMESTAMPTZ, end_time_utc TIMESTAMPTZ,
            expected_attendance INT, impact NUMERIC, impact_radius_km NUMERIC,
            status TEXT, event_ts TIMESTAMPTZ,
            ingested_ts TIMESTAMPTZ DEFAULT now(), dqr_valid BOOLEAN DEFAULT TRUE
        );
    """)
    templates = [
        ("Concerto at the Arena", "concert", 0.9, 3.5),
        ("Weekend Market", "market", 0.55, 1.5),
        ("Stadium Match", "sports", 1.0, 4.0),
        ("City Marathon", "sports", 0.7, 6.0),
        ("Tech Conference", "conference", 0.6, 2.5),
        ("Street Festival", "festival", 0.8, 2.0),
        ("Public Demonstration", "protest", 0.5, 3.0),
    ]
    event_rows = []
    for i in range(15):
        name, cat, impact, radius = random.choice(templates)
        start = now + timedelta(minutes=random.randint(-600, 240))
        end = start + timedelta(hours=random.randint(2, 5))
        event_rows.append((
            f"EV-{i+1:04d}", name, cat,
            round(BERLIN_LAT + random.uniform(-0.055, 0.055), 5),
            round(BERLIN_LON + random.uniform(-0.075, 0.075), 5),
            start, end, random.randint(300, 45000), impact, radius,
            "ACTIVE", now, now, True,
        ))
    execute_values(cur, """
        INSERT INTO silver.city_events
        (event_id, name, category, lat, lon, start_time_utc, end_time_utc,
         expected_attendance, impact, impact_radius_km, status, event_ts,
         ingested_ts, dqr_valid) VALUES %s
    """, event_rows)
    print(f"city_events: {len(event_rows)} rows")

    cur.execute("""
        DROP TABLE IF EXISTS silver.transport_positions;
        CREATE TABLE silver.transport_positions (
            vehicle_id TEXT NOT NULL, route_id TEXT NOT NULL, route_mode TEXT,
            trip_id TEXT, direction_id INT, stop_id TEXT, next_stop_id TEXT,
            lat NUMERIC, lon NUMERIC, speed_kmh NUMERIC, heading_deg NUMERIC,
            delay_seconds NUMERIC, congestion_level TEXT, event_ts TIMESTAMPTZ,
            ingested_ts TIMESTAMPTZ DEFAULT now(), dqr_valid BOOLEAN DEFAULT TRUE
        );
    """)
    cur.execute("""
        SELECT vehicle_id, COALESCE(NULLIF(route_id, ''), 'RT-UNKNOWN'), trip_id,
               stop_id, delay_seconds, event_ts
        FROM silver.trip_updates LIMIT 3000
    """)
    tu_rows = cur.fetchall()
    modes = ["bus", "tram", "u-bahn", "s-bahn"]
    congestion = ["low", "medium", "high"]
    pos_rows = []
    for vehicle_id, route_id, trip_id, stop_id, delay_seconds, event_ts in tu_rows:
        pos_rows.append((
            vehicle_id, route_id, random.choice(modes), trip_id,
            random.randint(0, 1), stop_id, stop_id,
            round(BERLIN_LAT + random.uniform(-0.08, 0.08), 5),
            round(BERLIN_LON + random.uniform(-0.1, 0.1), 5),
            round(random.uniform(0, 55), 1), round(random.uniform(0, 359), 1),
            delay_seconds, random.choice(congestion), event_ts, event_ts, True,
        ))
    execute_values(cur, """
        INSERT INTO silver.transport_positions
        (vehicle_id, route_id, route_mode, trip_id, direction_id, stop_id,
         next_stop_id, lat, lon, speed_kmh, heading_deg, delay_seconds,
         congestion_level, event_ts, ingested_ts, dqr_valid) VALUES %s
    """, pos_rows)
    print(f"transport_positions: {len(pos_rows)} rows (derived from real trip_updates)")

    pg.commit()
    cur.close()
    pg.close()

if __name__ == "__main__":
    main()
