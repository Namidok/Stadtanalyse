"""CityPulse batch pipeline DAG.

Orchestrates the Gold-layer refresh:
  Spark (bronze -> silver, Delta + Postgres) -> Great Expectations quality checks
  -> dbt (Gold marts) -> XGBoost retraining.

Each step runs as its own container through the Docker daemon (the same
compose-built images used by `make jobs`), attached to the citypulse_default
network so they can reach Kafka, MinIO and Postgres by service name.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

NETWORK = os.environ.get("CITYPULSE_NETWORK", "citypulse_default")
ML_VOLUME = os.environ.get("CITYPULSE_ML_VOLUME", "citypulse_ml_artifacts")

SPARK_IMAGE = os.environ.get("CITYPULSE_SPARK_IMAGE", "citypulse/spark:3.5.4")
QUALITY_IMAGE = os.environ.get("CITYPULSE_QUALITY_IMAGE", "citypulse/quality:1.0")
DBT_IMAGE = os.environ.get("CITYPULSE_DBT_IMAGE", "citypulse/dbt:1.0")

SHARED_ENV = {
    "S3_ENDPOINT": os.environ.get("S3_ENDPOINT", "http://minio:9000"),
    "S3_ACCESS_KEY": os.environ.get("S3_ACCESS_KEY", "citypulse"),
    "S3_SECRET_KEY": os.environ.get("S3_SECRET_KEY", "citypulse-secret"),
    "S3_PATH_STYLE_ACCESS": "true",
    "KAFKA_BOOTSTRAP_SERVERS": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
    "DELTA_TABLE_PREFIX": os.environ.get("DELTA_TABLE_PREFIX", "s3a://warehouse"),
    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "postgres"),
    "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER", "citypulse"),
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD", "citypulse-secret"),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB", "citypulse"),
    "SPARK_MASTER_URL": os.environ.get("SPARK_MASTER_URL", "spark://spark-master:7077"),
}

DEFAULTS = {
    "owner": "citypulse",
    "retries": 1,
    "retry_delay": timedelta(seconds=45),
    "start_date": datetime(2026, 1, 1),
    "max_active_runs": 1,
}

with DAG(
    "citypulse_batch_pipeline",
    schedule_interval="*/15 * * * *",
    catchup=False,
    description="Spark silver -> quality -> dbt gold -> ML retrain",
    tags=["citypulse", "batch", "gold-layer"],
    default_args=DEFAULTS,
) as dag:

    silver = DockerOperator(
        task_id="spark_bronze_to_silver",
        image=SPARK_IMAGE,
        command=["/opt/spark/work-dir/scripts/entrypoint.sh", "batch_bronze_to_silver.py"],
        environment=SHARED_ENV,
        network=NETWORK,
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        mount_tmp_dir=False,
    )

    quality = DockerOperator(
        task_id="great_expectations_quality",
        image=QUALITY_IMAGE,
        environment={
            "S3_ENDPOINT": SHARED_ENV["S3_ENDPOINT"],
            "S3_ACCESS_KEY": SHARED_ENV["S3_ACCESS_KEY"],
            "S3_SECRET_KEY": SHARED_ENV["S3_SECRET_KEY"],
        },
        network=NETWORK,
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        mount_tmp_dir=False,
    )

    dbt = DockerOperator(
        task_id="dbt_build_gold",
        image=DBT_IMAGE,
        environment={
            "DBT_PROFILES_DIR": "/usr/app/profiles",
            "DBT_PROJECT_DIR": "/usr/app/project",
            "POSTGRES_HOST": SHARED_ENV["POSTGRES_HOST"],
            "POSTGRES_PORT": SHARED_ENV["POSTGRES_PORT"],
            "POSTGRES_USER": SHARED_ENV["POSTGRES_USER"],
            "POSTGRES_PASSWORD": SHARED_ENV["POSTGRES_PASSWORD"],
            "POSTGRES_DB": SHARED_ENV["POSTGRES_DB"],
        },
        network=NETWORK,
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        mount_tmp_dir=False,
    )

    ml_train = DockerOperator(
        task_id="xgboost_retrain",
        image=SPARK_IMAGE,
        command=["/opt/spark/work-dir/scripts/run_train.sh"],
        environment={**SHARED_ENV,
                     "ML_MODEL_PATH": "/opt/ml/model/model.joblib",
                     "ML_FEATURES_PATH": "/opt/ml/model/features.json",
                     "ML_METRICS_PATH": "/opt/ml/model/metrics.json"},
        mounts=[Mount(source=ML_VOLUME, target="/opt/ml/model", type="volume")],
        network=NETWORK,
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
        mount_tmp_dir=False,
    )

    silver >> quality >> dbt >> ml_train
