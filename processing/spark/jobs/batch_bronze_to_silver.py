"""Batch ETL: Bronze -> Silver.

Reads the immutable Bronze Delta tables, applies cleaning, validation and
enrichment, writes cleansed Silver Delta tables and exports them to the
PostgreSQL `silver` schema that dbt consumes.

Validation outcomes are recorded so the Great Expectations layer can be
complemented by Spark-side data quality flags (dqr_* columns).

Run:
    spark-submit --master spark://spark-master:7077 jobs/batch_bronze_to_silver.py
"""
from __future__ import annotations

import logging

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import DoubleType

from common import build_session, s3_path, write_jdbc

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("stadtanalyse.silver")

CITY = {"lat": 52.52, "lon": 13.405}
BOUNDS = {"lat_min": 52.35, "lat_max": 52.68, "lon_min": 13.08, "lon_max": 13.75}
MAX_SPEED_KMH = 140.0
MAX_DELAY_SEC = 3600.0


def clean_transport(spark: SparkSession):
    df = spark.read.format("delta").load(s3_path("bronze.transport_positions"))
    n_in = df.count()
    cleaned = (
        df
        .dropDuplicates(["vehicle_id", "event_ts"])
        .filter(F.col("lat").isNotNull() & F.col("lon").isNotNull())
        .filter(F.col("lat").between(BOUNDS["lat_min"], BOUNDS["lat_max"]))
        .filter(F.col("lon").between(BOUNDS["lon_min"], BOUNDS["lon_max"]))
        .withColumn("speed_kmh", F.when(F.col("speed_kmh") < 0, 0.0).otherwise(F.col("speed_kmh")).cast(DoubleType()))
        .withColumn("delay_seconds", F.when(F.col("delay_seconds").isNull(), 0.0).otherwise(F.col("delay_seconds")).cast(DoubleType()))
        .withColumn("dqr_speed_anomaly", F.col("speed_kmh") > MAX_SPEED_KMH)
        .withColumn("dqr_delay_anomaly", F.col("delay_seconds") > MAX_DELAY_SEC)
        .withColumn("dqr_valid", F.col("lat").isNotNull() & F.col("lon").isNotNull() & (~F.col("dqr_speed_anomaly")))
        .withColumn("processed_ts", F.current_timestamp())
    )
    n_out = cleaned.count()
    log.info("transport: bronze=%s silver=%s (rows dropped/flagged: %s)", n_in, n_out, n_in - n_out)
    cleaned.write.mode("overwrite").format("delta").save(s3_path("silver.transport_positions"))
    cleaned.write.mode("overwrite").parquet(s3_path("silver_export/transport_positions"))
    write_jdbc(cleaned.limit(200000), "silver.transport_positions")
    return n_out


def clean_trip_updates(spark: SparkSession):
    df = spark.read.format("delta").load(s3_path("bronze.trip_updates"))
    n_in = df.count()
    cleaned = (
        df
        .dropDuplicates(["trip_id", "stop_id", "event_ts"])
        .filter(F.col("trip_id").isNotNull())
        .withColumn("delay_seconds", F.col("delay_seconds").cast(DoubleType()))
        .withColumn("dqr_delay_anomaly", F.col("delay_seconds") > MAX_DELAY_SEC)
        .withColumn("dqr_valid", ~F.col("dqr_delay_anomaly"))
        .withColumn("processed_ts", F.current_timestamp())
    )
    n_out = cleaned.count()
    log.info("trip_updates: bronze=%s silver=%s", n_in, n_out)
    cleaned.write.mode("overwrite").format("delta").save(s3_path("silver.trip_updates"))
    cleaned.write.mode("overwrite").parquet(s3_path("silver_export/trip_updates"))
    write_jdbc(cleaned.limit(200000), "silver.trip_updates")
    return n_out


def clean_weather(spark: SparkSession):
    df = spark.read.format("delta").load(s3_path("bronze.weather_observations"))
    cleaned = (
        df
        .dropDuplicates(["zone_id", "event_ts"])
        .withColumn(
            "condition",
            F.when(F.col("condition").isin(["clear", "clouds", "rain", "snow", "fog", "storm", "sleet"]), F.col("condition"))
            .otherwise(F.lit("unknown")),
        )
        .withColumn("temperature_c", F.col("temperature_c").cast(DoubleType()))
        .withColumn("dqr_valid", F.col("temperature_c").isNotNull() & F.col("condition") != "unknown")
        .withColumn("processed_ts", F.current_timestamp())
    )
    n = cleaned.count()
    log.info("weather: silver rows=%s", n)
    cleaned.write.mode("overwrite").format("delta").save(s3_path("silver.weather_observations"))
    cleaned.write.mode("overwrite").parquet(s3_path("silver_export/weather_observations"))
    write_jdbc(cleaned.limit(50000), "silver.weather_observations")
    return n


def clean_events(spark: SparkSession):
    df = spark.read.format("delta").load(s3_path("bronze.city_events"))
    cleaned = (
        df
        .dropDuplicates(["event_id", "event_ts"])
        .withColumn("dqr_valid", F.col("lat").isNotNull() & F.col("lon").isNotNull())
        .withColumn("processed_ts", F.current_timestamp())
    )
    n = cleaned.count()
    log.info("events: silver rows=%s", n)
    cleaned.write.mode("overwrite").format("delta").save(s3_path("silver.city_events"))
    cleaned.write.mode("overwrite").parquet(s3_path("silver_export/city_events"))
    write_jdbc(cleaned.limit(50000), "silver.city_events")
    return n


def main():
    spark = build_session("stadtanalyse-bronze-to-silver")
    summary = {
        "transport_positions": clean_transport(spark),
        "trip_updates": clean_trip_updates(spark),
        "weather_observations": clean_weather(spark),
        "city_events": clean_events(spark),
    }
    log.info("Silver ETL complete: %s", summary)
    spark.stop()


if __name__ == "__main__":
    main()
