"""Streaming ingestion: Kafka -> Bronze Delta tables.

Consumes the four raw topics produced by the simulators and writes
append-only Bronze tables to the Delta Lake (MinIO). No cleaning is applied
at this layer - Bronze is the immutable raw landing zone.

Run:
    spark-submit --master spark://spark-master:7077 jobs/stream_ingest_bronze.py
"""
from __future__ import annotations

import logging

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, LongType, StringType, StructField, StructType, TimestampType,
)

from common import build_session, s3_path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("citypulse.stream")

SCHEMAS: dict[str, StructType] = {
    "transport": StructType([
        StructField("vehicle_id", StringType()),
        StructField("route_id", StringType()),
        StructField("route_mode", StringType()),
        StructField("trip_id", StringType()),
        StructField("direction_id", IntegerType()),
        StructField("stop_id", StringType()),
        StructField("next_stop_id", StringType()),
        StructField("lat", DoubleType()),
        StructField("lon", DoubleType()),
        StructField("speed_kmh", DoubleType()),
        StructField("heading_deg", DoubleType()),
        StructField("delay_seconds", DoubleType()),
        StructField("congestion_level", DoubleType()),
        StructField("event_ts", TimestampType()),
    ]),
    "trip_updates": StructType([
        StructField("trip_id", StringType()),
        StructField("route_id", StringType()),
        StructField("vehicle_id", StringType()),
        StructField("stop_id", StringType()),
        StructField("stop_sequence", IntegerType()),
        StructField("scheduled_arrival_utc", TimestampType()),
        StructField("actual_arrival_utc", TimestampType()),
        StructField("delay_seconds", DoubleType()),
        StructField("status", StringType()),
        StructField("event_ts", TimestampType()),
    ]),
    "weather": StructType([
        StructField("zone_id", StringType()),
        StructField("lat", DoubleType()),
        StructField("lon", DoubleType()),
        StructField("temperature_c", DoubleType()),
        StructField("feels_like_c", DoubleType()),
        StructField("humidity_pct", DoubleType()),
        StructField("wind_speed_kmh", DoubleType()),
        StructField("precipitation_mm", DoubleType()),
        StructField("condition", StringType()),
        StructField("visibility_km", DoubleType()),
        StructField("event_ts", TimestampType()),
    ]),
    "events": StructType([
        StructField("event_id", StringType()),
        StructField("name", StringType()),
        StructField("category", StringType()),
        StructField("lat", DoubleType()),
        StructField("lon", DoubleType()),
        StructField("start_time_utc", TimestampType()),
        StructField("end_time_utc", TimestampType()),
        StructField("expected_attendance", LongType()),
        StructField("impact", DoubleType()),
        StructField("impact_radius_km", DoubleType()),
        StructField("status", StringType()),
        StructField("event_ts", TimestampType()),
    ]),
}

TOPICS = [
    ("raw.transport.vehicle.positions", "transport", "bronze.transport_positions"),
    ("raw.transport.trip.updates", "trip_updates", "bronze.trip_updates"),
    ("raw.weather.observations", "weather", "bronze.weather_observations"),
    ("raw.city.events", "events", "bronze.city_events"),
]


def main():
    spark = build_session("citypulse-stream-bronze", streaming=True)

    for topic, schema_key, table in TOPICS:
        schema = SCHEMAS[schema_key]
        log.info("Starting stream %s -> %s", topic, s3_path(table))
        stream = (
            spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", __import__("os").environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))
            .option("subscribe", topic)
            .option("startingOffsets", "latest")
            .option("failOnDataLoss", "false")
            .load()
            .selectExpr("CAST(value AS STRING) AS json")
            .select(F.from_json("json", schema).alias("data"))
            .select("data.*")
            .withColumn("ingested_ts", F.current_timestamp())
        )

        query = (
            stream.writeStream.format("delta")
            .outputMode("append")
            .option("checkpointLocation", f"/opt/spark/work-dir/checkpoints/{table.replace('.', '_')}")
            .option("mergeSchema", "true")
            .trigger(processingTime="10 seconds")
            .start(s3_path(table))
        )
        query.awaitTermination()


if __name__ == "__main__":
    main()
