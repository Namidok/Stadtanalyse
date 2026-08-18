"""Migrate silver.* and gtfs_raw.* tables from Postgres into Snowflake STADTANALYSE db."""
import os
import pandas as pd
from sqlalchemy import create_engine, text

PG_URL = "postgresql+psycopg2://stadtanalyse:stadtanalyse-secret@localhost:5432/stadtanalyse"

SF_ACCOUNT = "FIJWPUK-UL40212"
SF_USER = "SRIKARKODI"
SF_DATABASE = "STADTANALYSE"
SF_WAREHOUSE = "COMPUTE_WH"

TABLES = [
    ("silver", "trip_updates"),
    ("silver", "weather_observations"),
    ("silver", "city_events"),
    ("silver", "transport_positions"),
    ("gtfs_raw", "gtfs_stops"),
    ("gtfs_raw", "gtfs_routes"),
    ("gtfs_raw", "gtfs_trips"),
    ("gtfs_raw", "gtfs_stop_times"),
]

def main():
    pat = os.environ["SNOWFLAKE_PAT"]
    pg_engine = create_engine(PG_URL)

    sf_url = (
        f"snowflake://{SF_USER}:@{SF_ACCOUNT}/{SF_DATABASE}/?"
        f"warehouse={SF_WAREHOUSE}&role=ACCOUNTADMIN&authenticator=programmatic_access_token"
    )
    sf_engine = create_engine(sf_url, connect_args={"token": pat, "authenticator": "programmatic_access_token"})

    for schema, table in TABLES:
        df = pd.read_sql(f"SELECT * FROM {schema}.{table}", pg_engine)
        with sf_engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SF_DATABASE}.{schema.upper()}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {SF_DATABASE}.{schema.upper()}.{table.upper()}"))
            conn.commit()
        df.to_sql(
            table.upper(), sf_engine, schema=schema.upper(),
            if_exists="append", index=False, method="multi", chunksize=5000,
        )
        print(f"{schema}.{table}: migrated {len(df)} rows to Snowflake {schema.upper()}.{table.upper()}")

if __name__ == "__main__":
    main()
