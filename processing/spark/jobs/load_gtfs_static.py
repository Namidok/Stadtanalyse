"""Load the installed per-city GTFS static network into PostgreSQL for dbt dims.

Reads the normalized GTFS files installed by the realtime ingest service
(./data/gtfs) and exports them to the `gtfs_raw` PostgreSQL schema. dbt raw
models expose these as `gold_silver.gtfs_*` views consumed by the mart
dimensions (stops, stop_times, trips, routes).

Run:
    spark-submit --master local[4] jobs/load_gtfs_static.py
"""
from __future__ import annotations

import logging

from pyspark.sql import SparkSession, functions as F

from common import build_session, postgres_properties, postgres_url, write_jdbc

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("stadtanalyse.gtfs")

GTFS_DIR = "/app/data/gtfs"

ROUTE_TYPE_BY_MODE = {
    "rail": 2,
    "tram": 0,
    "bus": 3,
}


def load_table(spark: SparkSession, name: str) -> None:
    path = f"{GTFS_DIR}/{name}.txt"
    df = spark.read.option("header", True).option("delimiter", ",").csv(path)
    if name == "routes":
        pairs = [
            item
            for k, v in ROUTE_TYPE_BY_MODE.items()
            for item in (F.lit(k).cast("string"), F.lit(v).cast("int"))
        ]
        mode_type = F.create_map(*pairs)
        df = df.withColumn("agency_id", F.lit("DE")).withColumn(
            "route_type", mode_type.getItem(F.col("route_mode"))
        )
    n = df.count()
    table = f"gtfs_raw.gtfs_{name}"
    write_jdbc(df, table)
    log.info("loaded %s: %s rows -> postgres %s", name, n, table)


def ensure_schema(spark: SparkSession) -> None:
    jvm = spark._jvm  # noqa: SLF001
    conn = jvm.java.sql.DriverManager.getConnection(
        postgres_url(), postgres_properties()["user"], postgres_properties()["password"]
    )
    try:
        stmt = conn.createStatement()
        try:
            stmt.execute("CREATE SCHEMA IF NOT EXISTS gtfs_raw")
        finally:
            stmt.close()
    finally:
        conn.close()


def main() -> None:
    spark = build_session("stadtanalyse-load-gtfs-static")
    ensure_schema(spark)
    for name in ["stops", "trips", "stop_times", "routes"]:
        load_table(spark, name)
    log.info("GTFS static load complete")


if __name__ == "__main__":
    main()
