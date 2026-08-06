"""Shared Spark session bootstrap for Stadtanalyse jobs.

Configures Delta Lake, S3A/MinIO access and PostgreSQL JDBC from environment
variables so jobs run identically on the cluster and in local mode.
"""
from __future__ import annotations

import os

from pyspark.sql import SparkSession


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def build_session(app_name: str, *, streaming: bool = False, local: bool = False) -> SparkSession:
    s3_endpoint = env("S3_ENDPOINT", "http://minio:9000")
    s3_access = env("S3_ACCESS_KEY", "stadtanalyse")
    s3_secret = env("S3_SECRET_KEY", "stadtanalyse-secret")

    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", s3_access)
        .config("spark.hadoop.fs.s3a.secret.key", s3_secret)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.delta.logStore.class", "io.delta.storage.S3SingleDriverLogStore")
    )
    if streaming:
        builder = builder.config("spark.sql.streaming.schemaInference", "false")

    master = os.environ.get("SPARK_MASTER_URL", "")
    if local:
        builder = builder.master("local[4]")
    elif master:
        builder = builder.master(master)

    return builder.getOrCreate()


def postgres_url() -> str:
    host = env("POSTGRES_HOST", "postgres")
    port = env("POSTGRES_PORT", "5432")
    db = env("POSTGRES_DB", "stadtanalyse")
    return f"jdbc:postgresql://{host}:{port}/{db}"


def postgres_properties() -> dict:
    return {
        "user": env("POSTGRES_USER", "stadtanalyse"),
        "password": env("POSTGRES_SECRET", env("POSTGRES_PASSWORD", "stadtanalyse-secret")),
        "driver": "org.postgresql.Driver",
    }


def write_jdbc(df, table: str, mode: str = "overwrite") -> None:
    df.write.mode(mode).jdbc(postgres_url(), table, properties=postgres_properties())


def s3_path(table: str) -> str:
    prefix = env("DELTA_TABLE_PREFIX", "s3a://warehouse")
    return f"{prefix}/{table}"
