# Snowflake migration experiment (unfinished)

These scripts were a one-off attempt to move the warehouse from PostgreSQL to Snowflake. They are **not part of the pipeline**: they skip Kafka, Spark and Great Expectations and write straight into Postgres `silver.*` / `gtfs_raw.*`.

**The data they load is partly synthetic:**

| Script | What it does |
|---|---|
| `load_silver.py` | Loads real GTFS-RT trip delays from a local DuckDB file (`ingest.realtime.run --local`) into `silver.trip_updates` |
| `load_gtfs_raw.py` | Loads the real GTFS static files into `gtfs_raw.*` (caps `stop_times` at 200k rows) |
| `seed_remaining_silver.py` | Fills `silver.weather_observations`, `silver.city_events` and `silver.transport_positions` with **randomly generated** data |
| `migrate_to_snowflake.py` | Copies those Postgres tables into Snowflake |

They connect to Postgres on `localhost:5432` with the default demo credentials from `.env.example`. File paths default to the repo's `data/` folder and can be overridden (`--duckdb`, `--gtfs-dir`).

Snowflake connection settings come from the environment: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE` and `SNOWFLAKE_PAT`. The same variables are used by the `snowflake` target in `dbt/profiles/profiles.yml`. Use a least-privilege role, not `ACCOUNTADMIN`.
