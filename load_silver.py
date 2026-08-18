"""Load real Berlin GTFS-RT trip_updates from local DuckDB into Postgres silver schema."""
import json
import duckdb
import psycopg2
from pathlib import Path

DUCKDB_PATH = Path.home() / "Downloads/GitHub/smart-urban-mobility/data/local/realtime.duckdb"

PG_CONN = dict(
    host="localhost",
    port=5432,
    dbname="stadtanalyse",
    user="stadtanalyse",
    password="stadtanalyse-secret",
)

def main():
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    rows = con.execute("SELECT record, event_ts FROM trip_updates").fetchall()
    con.close()
    print(f"Loaded {len(rows)} records from DuckDB")

    parsed = []
    for record_json, event_ts in rows:
        r = json.loads(record_json)
        parsed.append((
            r["trip_id"],
            r["route_id"],
            r["vehicle_id"],
            r["stop_id"],
            r["stop_sequence"],
            r["scheduled_arrival_utc"],
            r["actual_arrival_utc"],
            r["delay_seconds"],
            r["status"],
            r["event_ts"],
        ))

    pg = psycopg2.connect(**PG_CONN)
    cur = pg.cursor()

    cur.execute("""
        DROP TABLE IF EXISTS silver.trip_updates;
        CREATE TABLE silver.trip_updates (
            trip_id TEXT NOT NULL,
            route_id TEXT,
            vehicle_id TEXT,
            stop_id TEXT NOT NULL,
            stop_sequence INT,
            scheduled_arrival_utc TIMESTAMPTZ,
            actual_arrival_utc TIMESTAMPTZ,
            delay_seconds NUMERIC,
            status TEXT,
            event_ts TIMESTAMPTZ
        );
    """)
    pg.commit()

    from psycopg2.extras import execute_values
    execute_values(
        cur,
        """
        INSERT INTO silver.trip_updates
        (trip_id, route_id, vehicle_id, stop_id, stop_sequence,
         scheduled_arrival_utc, actual_arrival_utc, delay_seconds, status, event_ts)
        VALUES %s
        """,
        parsed,
    )
    pg.commit()

    cur.execute("SELECT COUNT(*) FROM silver.trip_updates")
    count = cur.fetchone()[0]
    print(f"Inserted {count} rows into silver.trip_updates")

    cur.close()
    pg.close()

if __name__ == "__main__":
    main()
